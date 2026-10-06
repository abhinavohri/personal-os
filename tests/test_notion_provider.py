import asyncio
import json

import httpx
import pytest

from personal_os.domain.notes import ExtractedNote, ExtractedTask
from personal_os.providers.notion import NOTION_API_VERSION, NotionMemory, NotionMemoryError


def _note() -> ExtractedNote:
    return ExtractedNote(
        source_object="gs://notes/inbox/page.jpg",
        title="Project sketch",
        transcription="Build the first version.",
        summary="A project idea.",
        confidence=0.9,
        tasks=(ExtractedTask(text="Create prototype"),),
        insights=("Keep it small",),
        questions=(),
        resources=(),
        uncertainties=(),
    )


def test_create_note_draft_uses_data_source_and_current_api_version() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "page-1", "url": "https://notion.so/page-1"})

    async def run():
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.notion.com/v1"
        )
        memory = NotionMemory("secret", "notes-source", client=client)
        result = await memory.create_note_draft(_note())
        await client.aclose()
        return result

    result = asyncio.run(run())
    payload = json.loads(requests[0].content)

    assert result.id == "page-1"
    assert requests[0].headers["Notion-Version"] == NOTION_API_VERSION
    assert payload["parent"]["data_source_id"] == "notes-source"
    assert payload["properties"]["Name"]["title"][0]["text"]["content"] == "Project sketch"
    assert "Create prototype" in payload["children"][0]["paragraph"]["rich_text"][0]["text"]["content"]


def test_read_page_text_follows_pagination() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "start_cursor=next" in str(request.url):
            return httpx.Response(200, json={"results": [_block("Second")], "has_more": False})
        return httpx.Response(
            200,
            json={"results": [_block("First")], "has_more": True, "next_cursor": "next"},
        )

    async def run():
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), base_url="https://api.notion.com/v1"
        )
        memory = NotionMemory("secret", "notes-source", client=client)
        text = await memory.read_page_text("brief")
        await client.aclose()
        return text

    assert asyncio.run(run()) == "First\nSecond"


def test_notion_errors_are_translated() -> None:
    async def run():
        client = httpx.AsyncClient(
            transport=httpx.MockTransport(lambda _: httpx.Response(403)),
            base_url="https://api.notion.com/v1",
        )
        memory = NotionMemory("secret", "notes-source", client=client)
        with pytest.raises(NotionMemoryError):
            await memory.create_note_draft(_note())
        await client.aclose()

    asyncio.run(run())


def _block(text: str) -> dict:
    return {
        "type": "paragraph",
        "paragraph": {"rich_text": [{"plain_text": text}]},
    }
