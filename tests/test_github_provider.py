import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from personal_os.providers.github import (
    GITHUB_API_VERSION,
    GitHubEvidenceError,
    GitHubWorkEvidence,
)


REPO = "octocat/personal-os"
SINCE = datetime(2026, 10, 1, tzinfo=UTC)


def test_repository_metadata_is_normalized_and_versioned() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "full_name": REPO,
                "html_url": f"https://github.com/{REPO}",
                "description": "My system",
                "language": "Python",
                "topics": ["personal-os"],
                "private": True,
                "default_branch": "main",
            },
        )

    async def run():
        client = _client(handler)
        provider = GitHubWorkEvidence(
            "token", "octocat", (REPO,), allow_private=True, client=client
        )
        result = await provider.get_repository(REPO)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert result.primary_language == "Python"
    assert result.is_private is True
    assert requests[0].headers["X-GitHub-Api-Version"] == GITHUB_API_VERSION


def test_recent_activity_combines_read_only_evidence() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == f"/repos/{REPO}":
            return httpx.Response(
                200,
                json={
                    "full_name": REPO,
                    "html_url": f"https://github.com/{REPO}",
                    "description": "My system",
                    "language": "Python",
                    "topics": ["personal-os"],
                    "private": False,
                    "default_branch": "main",
                },
            )
        if path.endswith("/commits"):
            return httpx.Response(200, json=[_commit()])
        if path.endswith("/issues"):
            return httpx.Response(200, json=[_issue(), {**_issue(), "pull_request": {}}])
        if path.endswith("/pulls"):
            return httpx.Response(200, json=[_pull()])
        if path.endswith("/releases"):
            return httpx.Response(200, json=[_release()])
        raise AssertionError(path)

    async def run():
        client = _client(handler)
        provider = GitHubWorkEvidence("token", "octocat", (REPO,), client=client)
        result = await provider.recent_activity(REPO, SINCE)
        await client.aclose()
        return result

    result = asyncio.run(run())
    assert {event.kind for event in result} == {"commit", "issue", "pull_request", "release"}
    assert result[0].occurred_at >= result[-1].occurred_at


def test_non_allowlisted_repository_is_rejected_without_http() -> None:
    calls = []

    async def run():
        client = _client(lambda request: calls.append(request))
        provider = GitHubWorkEvidence("token", "octocat", (REPO,), client=client)
        with pytest.raises(GitHubEvidenceError, match="not allowlisted"):
            await provider.get_repository("octocat/secret")
        await client.aclose()

    asyncio.run(run())
    assert calls == []


def test_private_repository_is_rejected_unless_enabled() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "full_name": REPO,
                "html_url": f"https://github.com/{REPO}",
                "description": None,
                "language": None,
                "topics": [],
                "private": True,
                "default_branch": "main",
            },
        )

    async def run():
        client = _client(handler)
        provider = GitHubWorkEvidence("token", "octocat", (REPO,), client=client)
        with pytest.raises(GitHubEvidenceError, match="Private repository access"):
            await provider.get_repository(REPO)
        await client.aclose()

    asyncio.run(run())


def test_readme_is_returned_as_raw_text() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/readme"):
            return httpx.Response(200, text="# Personal OS\nUseful context")
        return httpx.Response(
            200,
            json={
                "full_name": REPO,
                "html_url": f"https://github.com/{REPO}",
                "description": "My system",
                "language": "Python",
                "topics": ["personal-os"],
                "private": False,
                "default_branch": "main",
            },
        )

    async def run():
        client = _client(handler)
        provider = GitHubWorkEvidence("token", "octocat", (REPO,), client=client)
        result = await provider.get_readme_text(REPO)
        await client.aclose()
        return result

    assert asyncio.run(run()) == "# Personal OS\nUseful context"
    assert requests[-1].headers["Accept"] == "application/vnd.github.raw+json"


def test_missing_readme_returns_none() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/readme"):
            return httpx.Response(404)
        return httpx.Response(
            200,
            json={
                "full_name": REPO,
                "html_url": f"https://github.com/{REPO}",
                "description": None,
                "language": None,
                "topics": [],
                "private": False,
                "default_branch": "main",
            },
        )

    async def run():
        client = _client(handler)
        provider = GitHubWorkEvidence("token", "octocat", (REPO,), client=client)
        result = await provider.get_readme_text(REPO)
        await client.aclose()
        return result

    assert asyncio.run(run()) is None


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://api.github.com"
    )


def _commit() -> dict:
    return {
        "html_url": f"https://github.com/{REPO}/commit/abc",
        "commit": {
            "message": "Add adapter\n\nDetails",
            "author": {"date": "2026-10-02T10:00:00Z"},
        },
    }


def _issue() -> dict:
    return {
        "title": "Track weekly work",
        "html_url": f"https://github.com/{REPO}/issues/1",
        "updated_at": "2026-10-03T10:00:00Z",
    }


def _pull() -> dict:
    return {
        "title": "Add work tracking",
        "html_url": f"https://github.com/{REPO}/pull/2",
        "updated_at": "2026-10-04T10:00:00Z",
        "user": {"login": "octocat"},
    }


def _release() -> dict:
    return {
        "name": "First release",
        "tag_name": "v0.1",
        "html_url": f"https://github.com/{REPO}/releases/v0.1",
        "created_at": "2026-10-05T10:00:00Z",
        "published_at": "2026-10-05T10:00:00Z",
    }
