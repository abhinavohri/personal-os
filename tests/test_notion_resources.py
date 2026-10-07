import asyncio
import json
from datetime import UTC, datetime

import httpx

from personal_os.domain.resources import ResourceCapture
from personal_os.providers.notion_resources import NotionResourceInbox


NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)
ITEM = ResourceCapture(
    title="Distributed systems playlist",
    resource_type="youtube_playlist",
    url="https://youtube.com/playlist?list=abc&utm_source=x",
    notes="Watch later",
    tags=("systems",),
    source="twitter_bookmark",
)


def test_resource_batch_creates_schema_and_deduplicated_page() -> None:
    requests: list[httpx.Request] = []
    created: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if request.method == "GET":
            return httpx.Response(
                200,
                json={
                    "properties": {
                        "Name": {"title": {}},
                        "URL": {"url": {}},
                        "Type": {"select": {}},
                        "Status": {"select": {}},
                    }
                },
            )
        if request.method == "PATCH" and path == "/v1/data_sources/resources":
            return httpx.Response(200, json={})
        if request.method == "POST" and path.endswith("/query"):
            return httpx.Response(200, json={"results": []})
        if request.method == "POST" and path == "/v1/pages":
            created.update(json.loads(request.content)["properties"])
            return httpx.Response(200, json=_page())
        raise AssertionError((request.method, path))

    async def run():
        client = _client(handler)
        store = NotionResourceInbox("token", "resources", client=client, clock=lambda: NOW)
        records = await store.upsert_many((ITEM, ITEM))
        await client.aclose()
        return records

    records = asyncio.run(run())
    assert len(records) == 1
    assert created["Status"]["select"]["name"] == "Inbox"
    assert created["Resource Key"]["rich_text"][0]["text"]["content"] == (
        "url:https://youtube.com/playlist?list=abc"
    )
    assert any(
        request.method == "PATCH"
        and request.url.path == "/v1/data_sources/resources"
        for request in requests
    )


def test_existing_resource_preserves_status_and_merges_tags() -> None:
    patched: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if request.method == "GET":
            return httpx.Response(200, json={"properties": _schema()})
        if request.method == "POST" and path.endswith("/query"):
            return httpx.Response(200, json={"results": [_page(status="Active") ]})
        if request.method == "PATCH" and path == "/v1/pages/resource-page":
            patched.update(json.loads(request.content)["properties"])
            return httpx.Response(200, json=_page(status="Active", tags=("systems", "course")))
        raise AssertionError((request.method, path))

    async def run():
        client = _client(handler)
        store = NotionResourceInbox("token", "resources", client=client, clock=lambda: NOW)
        updated = ITEM.model_copy(update={"notes": "", "tags": ("course",)})
        records = await store.upsert_many((updated,))
        await client.aclose()
        return records

    records = asyncio.run(run())
    assert records[0].status == "Active"
    assert patched["Status"]["select"]["name"] == "Active"
    assert patched["Notes"]["rich_text"][0]["text"]["content"] == "Watch later"
    assert [item["name"] for item in patched["Tags"]["multi_select"]] == [
        "systems",
        "course",
    ]


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.notion.com/v1",
    )


def _schema() -> dict:
    return {
        "Name": {"title": {}},
        "URL": {"url": {}},
        "Type": {"select": {}},
        "Status": {"select": {}},
        "Resource Key": {"rich_text": {}},
        "Notes": {"rich_text": {}},
        "Tags": {"multi_select": {}},
        "Source": {"select": {}},
        "Added At": {"date": {}},
    }


def _page(*, status: str = "Inbox", tags: tuple[str, ...] = ("systems",)) -> dict:
    def rich_text(value: str):
        return {"rich_text": [{"plain_text": value}]}

    return {
        "id": "resource-page",
        "url": "https://notion.so/resource-page",
        "properties": {
            "Name": {"title": [{"plain_text": ITEM.title}]},
            "URL": {"url": ITEM.url},
            "Type": {"select": {"name": ITEM.resource_type}},
            "Status": {"select": {"name": status}},
            "Resource Key": rich_text("url:https://youtube.com/playlist?list=abc"),
            "Notes": rich_text(ITEM.notes),
            "Tags": {"multi_select": [{"name": tag} for tag in tags]},
            "Source": {"select": {"name": ITEM.source}},
            "Added At": {"date": {"start": NOW.isoformat()}},
        },
    }
