import asyncio
import json
from datetime import UTC, datetime

import httpx

from personal_os.ports.work_evidence import RepositorySnapshot
from personal_os.providers.notion import NOTION_API_VERSION
from personal_os.providers.notion_repository_catalog import NotionRepositoryCatalog


REPOSITORY = RepositorySnapshot(
    full_name="octocat/personal-os",
    url="https://github.com/octocat/personal-os",
    description="A useful planning system",
    primary_language="Python",
    topics=("planning", "ai"),
    is_private=False,
    default_branch="main",
)


def test_catalog_adds_schema_and_creates_missing_repository() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"properties": {"Name": {}}})
        if request.url.path.endswith("/query"):
            return httpx.Response(200, json={"results": []})
        if request.method == "PATCH" and "/data_sources/" in request.url.path:
            return httpx.Response(200, json={"id": "catalog", "properties": {}})
        if request.method == "POST" and request.url.path == "/v1/pages":
            return httpx.Response(
                200, json={"id": "page-1", "url": "https://notion.so/page-1"}
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    result = asyncio.run(_upsert(handler))

    assert result.id == "page-1"
    schema_request = next(
        request
        for request in requests
        if request.method == "PATCH" and "/data_sources/" in request.url.path
    )
    assert set(json.loads(schema_request.content)["properties"]) == {
        "Description",
        "Topics",
        "README Excerpt",
    }
    create_request = next(
        request
        for request in requests
        if request.method == "POST" and request.url.path == "/v1/pages"
    )
    properties = json.loads(create_request.content)["properties"]
    assert properties["Full Name"]["rich_text"][0]["text"]["content"] == REPOSITORY.full_name
    assert properties["README Excerpt"]["rich_text"][0]["text"]["content"] == "# Read me"
    assert create_request.headers["Notion-Version"] == NOTION_API_VERSION


def test_catalog_updates_existing_repository_without_duplicate() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "properties": {
                        "Description": {},
                        "Topics": {},
                        "README Excerpt": {},
                    }
                },
            )
        if request.url.path.endswith("/query"):
            return httpx.Response(200, json={"results": [{"id": "page-1"}]})
        if request.method == "PATCH" and request.url.path.endswith("/pages/page-1"):
            return httpx.Response(
                200, json={"id": "page-1", "url": "https://notion.so/page-1"}
            )
        raise AssertionError(f"Unexpected request: {request.method} {request.url}")

    result = asyncio.run(_upsert(handler))

    assert result.id == "page-1"
    assert not any(
        request.method == "POST" and request.url.path == "/v1/pages"
        for request in requests
    )


async def _upsert(handler):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.notion.com/v1",
    )
    catalog = NotionRepositoryCatalog("token", "catalog", client=client)
    result = await catalog.upsert_repository(
        REPOSITORY,
        "# Read me",
        reviewed_at=datetime(2026, 10, 7, tzinfo=UTC),
    )
    await client.aclose()
    return result
