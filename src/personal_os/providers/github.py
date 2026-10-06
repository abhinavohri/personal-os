"""Read-only GitHub work-evidence adapter."""

from datetime import datetime
from typing import Any

import httpx

from personal_os.ports.work_evidence import RepositorySnapshot, WorkEvent


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


def _timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
