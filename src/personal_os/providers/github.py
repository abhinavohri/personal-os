"""Read-only GitHub work-evidence adapter."""

from datetime import datetime
from typing import Any

import httpx

from personal_os.ports.work_evidence import (
    DeveloperProfile,
    PortfolioRepository,
    PortfolioSnapshot,
    RepositorySnapshot,
    WorkEvent,
)


GITHUB_API_VERSION = "2026-03-10"


class GitHubEvidenceError(RuntimeError):
    """Raised when GitHub evidence cannot be read safely."""


class GitHubWorkEvidence:
    """Read allowlisted repositories without exposing any write operation."""

    def __init__(
        self,
        token: str,
        username: str,
        allowed_repositories: tuple[str, ...],
        *,
        allow_private: bool = False,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._username = username
        self._allowed = frozenset(allowed_repositories)
        self._allow_private = allow_private
        self._owner = client is None
        self._client = client or httpx.AsyncClient(
            base_url="https://api.github.com", timeout=30
        )
        self._client.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": GITHUB_API_VERSION,
            }
        )

    async def get_repository(self, full_name: str) -> RepositorySnapshot:
        self._check_allowed(full_name)
        body = await self._get(f"/repos/{full_name}")
        if body.get("private", False) and not self._allow_private:
            raise GitHubEvidenceError(
                f"Private repository access is disabled: {full_name}"
            )
        return RepositorySnapshot(
            full_name=body["full_name"],
            url=body["html_url"],
            description=body.get("description"),
            primary_language=body.get("language"),
            topics=tuple(body.get("topics", [])),
            is_private=body.get("private", False),
            default_branch=body["default_branch"],
        )

    async def get_readme_text(self, full_name: str) -> str | None:
        """Return the default README as text after applying repository policy."""
        await self.get_repository(full_name)
        try:
            response = await self._client.get(
                f"/repos/{full_name}/readme",
                headers={"Accept": "application/vnd.github.raw+json"},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.text
        except Exception as exc:
            raise GitHubEvidenceError(
                f"Could not read GitHub README for {full_name}"
            ) from exc

    async def recent_activity(
        self, full_name: str, since: datetime
    ) -> tuple[WorkEvent, ...]:
        await self.get_repository(full_name)
        since_text = _iso_z(since)
        commits = await self._get(
            f"/repos/{full_name}/commits",
            params={"author": self._username, "since": since_text, "per_page": 100},
        )
        issues = await self._get(
            f"/repos/{full_name}/issues",
            params={
                "creator": self._username,
                "state": "all",
                "since": since_text,
                "per_page": 100,
            },
        )
        pulls = await self._get(
            f"/repos/{full_name}/pulls",
            params={"state": "all", "sort": "updated", "direction": "desc", "per_page": 100},
        )
        releases = await self._get(
            f"/repos/{full_name}/releases", params={"per_page": 100}
        )

        events = [_commit_event(full_name, item) for item in commits]
        events.extend(
            _issue_event(full_name, item)
            for item in issues
            if "pull_request" not in item
        )
        events.extend(
            _pull_event(full_name, item)
            for item in pulls
            if item.get("user", {}).get("login") == self._username
            and _timestamp(item["updated_at"]) >= since
        )
        events.extend(
            _release_event(full_name, item)
            for item in releases
            if _timestamp(item.get("published_at") or item["created_at"]) >= since
        )
        return tuple(sorted(events, key=lambda event: event.occurred_at, reverse=True))

    async def get_portfolio(self, limit: int = 30) -> PortfolioSnapshot:
        """Return public profile evidence for portfolio coaching."""
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        profile, repositories, pinned = await self._portfolio_data(limit)
        profile_repository = f"{self._username}/{self._username}".lower()
        profile_readme = None
        if any(
            item.get("full_name", "").lower() == profile_repository
            for item in repositories
        ):
            profile_readme = await self._get_public_readme(
                f"{self._username}/{self._username}"
            )
        return PortfolioSnapshot(
            profile=DeveloperProfile(
                username=profile["login"],
                url=profile["html_url"],
                name=profile.get("name"),
                bio=profile.get("bio"),
                company=profile.get("company"),
                blog=profile.get("blog") or None,
                location=profile.get("location"),
                followers=profile.get("followers", 0),
                following=profile.get("following", 0),
                public_repositories=profile.get("public_repos", 0),
            ),
            profile_readme=profile_readme,
            repositories=tuple(
                _portfolio_repository(item, pinned) for item in repositories
            ),
        )

    async def _portfolio_data(
        self, limit: int
    ) -> tuple[dict[str, Any], list[dict[str, Any]], frozenset[str]]:
        profile = await self._get(f"/users/{self._username}")
        repositories = await self._get(
            f"/users/{self._username}/repos",
            params={
                "type": "owner",
                "sort": "updated",
                "direction": "desc",
                "per_page": limit,
            },
        )
        pinned = await self._pinned_repositories()
        return profile, repositories, pinned

    async def _pinned_repositories(self) -> frozenset[str]:
        query = """
        query PortfolioPins($login: String!) {
          user(login: $login) {
            pinnedItems(first: 6, types: REPOSITORY) {
              nodes { ... on Repository { nameWithOwner } }
            }
          }
        }
        """
        try:
            response = await self._client.post(
                "/graphql",
                json={"query": query, "variables": {"login": self._username}},
            )
            response.raise_for_status()
            body = response.json()
            if body.get("errors"):
                raise GitHubEvidenceError("GitHub GraphQL rejected the pinned-repo query")
            nodes = (
                body.get("data", {})
                .get("user", {})
                .get("pinnedItems", {})
                .get("nodes", [])
            )
            return frozenset(
                item["nameWithOwner"]
                for item in nodes
                if item and item.get("nameWithOwner")
            )
        except GitHubEvidenceError:
            raise
        except Exception as exc:
            raise GitHubEvidenceError("Could not read pinned GitHub repositories") from exc

    async def _get_public_readme(self, full_name: str) -> str | None:
        try:
            response = await self._client.get(
                f"/repos/{full_name}/readme",
                headers={"Accept": "application/vnd.github.raw+json"},
            )
            if response.status_code == 404:
                return None
            response.raise_for_status()
            return response.text
        except Exception as exc:
            raise GitHubEvidenceError(
                f"Could not read public GitHub README for {full_name}"
            ) from exc

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        try:
            response = await self._client.get(path, params=params)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            raise GitHubEvidenceError(f"Could not read GitHub endpoint {path}") from exc

    def _check_allowed(self, full_name: str) -> None:
        if full_name not in self._allowed:
            raise GitHubEvidenceError(f"Repository is not allowlisted: {full_name}")

    async def close(self) -> None:
        if self._owner:
            await self._client.aclose()


def _commit_event(repository: str, item: dict[str, Any]) -> WorkEvent:
    details = item["commit"]
    return WorkEvent(
        kind="commit",
        repository=repository,
        title=details["message"].splitlines()[0],
        url=item["html_url"],
        occurred_at=_timestamp(details["author"]["date"]),
    )


def _issue_event(repository: str, item: dict[str, Any]) -> WorkEvent:
    return WorkEvent(
        kind="issue",
        repository=repository,
        title=item["title"],
        url=item["html_url"],
        occurred_at=_timestamp(item["updated_at"]),
    )


def _pull_event(repository: str, item: dict[str, Any]) -> WorkEvent:
    return WorkEvent(
        kind="pull_request",
        repository=repository,
        title=item["title"],
        url=item["html_url"],
        occurred_at=_timestamp(item["updated_at"]),
    )


def _release_event(repository: str, item: dict[str, Any]) -> WorkEvent:
    return WorkEvent(
        kind="release",
        repository=repository,
        title=item.get("name") or item["tag_name"],
        url=item["html_url"],
        occurred_at=_timestamp(item.get("published_at") or item["created_at"]),
    )


def _portfolio_repository(
    item: dict[str, Any], pinned: frozenset[str]
) -> PortfolioRepository:
    pushed_at = item.get("pushed_at")
    return PortfolioRepository(
        full_name=item["full_name"],
        url=item["html_url"],
        description=item.get("description"),
        primary_language=item.get("language"),
        topics=tuple(item.get("topics", [])),
        stars=item.get("stargazers_count", 0),
        forks=item.get("forks_count", 0),
        is_archived=item.get("archived", False),
        is_fork=item.get("fork", False),
        updated_at=_timestamp(item["updated_at"]),
        pushed_at=_timestamp(pushed_at) if pushed_at else None,
        is_pinned=item["full_name"] in pinned,
    )


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
