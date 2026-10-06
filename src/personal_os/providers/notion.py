"""Notion implementation of durable Personal OS memory."""

from typing import Any

import httpx

from personal_os.domain.notes import ExtractedNote
from personal_os.ports.memory import MemoryRecordRef


NOTION_API_VERSION = "2026-03-11"


class NotionMemoryError(RuntimeError):
    """Raised when Notion cannot complete a memory operation."""


class NotionMemory:
    """Read context pages and create reviewable handwritten-note drafts."""

    def __init__(
        self,
        token: str,
        notes_data_source_id: str,
        *,
        title_property: str = "Name",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._notes_data_source_id = notes_data_source_id
        self._title_property = title_property
        self._owner = client is None
        self._client = client or httpx.AsyncClient(
            base_url="https://api.notion.com/v1", timeout=30
        )
        self._client.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json",
            }
        )

    async def read_page_text(self, page_id: str) -> str:
        blocks: list[dict[str, Any]] = []
        cursor: str | None = None
        try:
            while True:
                params: dict[str, Any] = {"page_size": 100}
                if cursor:
                    params["start_cursor"] = cursor
                response = await self._client.get(
                    f"/blocks/{page_id}/children", params=params
                )
                response.raise_for_status()
                body = response.json()
                blocks.extend(body.get("results", []))
                if not body.get("has_more"):
                    break
                cursor = body.get("next_cursor")
                if not cursor:
                    break
        except Exception as exc:
            raise NotionMemoryError(f"Could not read Notion page {page_id}") from exc

        return "\n".join(filter(None, (_block_text(block) for block in blocks)))

    async def create_note_draft(self, note: ExtractedNote) -> MemoryRecordRef:
        title = note.title or f"Paper note — {note.page_date or 'undated'}"
        content = _render_note(note)
        payload = {
            "parent": {
                "type": "data_source_id",
                "data_source_id": self._notes_data_source_id,
            },
            "properties": {
                self._title_property: {
                    "type": "title",
                    "title": [{"type": "text", "text": {"content": title[:2000]}}],
                }
            },
            "children": [_paragraph(chunk) for chunk in _chunks(content, 2000)],
        }
        try:
            response = await self._client.post("/pages", json=payload)
            response.raise_for_status()
            body = response.json()
            return MemoryRecordRef(id=body["id"], url=body.get("url"))
        except Exception as exc:
            raise NotionMemoryError("Could not create Notion note draft") from exc

    async def close(self) -> None:
        if self._owner:
            await self._client.aclose()


def _block_text(block: dict[str, Any]) -> str:
    block_type = block.get("type")
    value = block.get(block_type, {}) if block_type else {}
    rich_text = value.get("rich_text", []) if isinstance(value, dict) else []
    return "".join(item.get("plain_text", "") for item in rich_text)


def _render_note(note: ExtractedNote) -> str:
    sections = [
        f"Source: {note.source_object}",
        f"Confidence: {note.confidence:.0%}",
        f"Needs review: {'yes' if note.needs_review else 'no'}",
        f"Summary\n{note.summary}",
        f"Transcription\n{note.transcription}",
    ]
    for heading, values in (
        ("Tasks", tuple(task.text for task in note.tasks)),
        ("Insights", note.insights),
        ("Questions", note.questions),
        ("Resources", note.resources),
        ("Diagrams", note.diagrams),
        ("Uncertainties", note.uncertainties),
    ):
        if values:
            sections.append(f"{heading}\n" + "\n".join(f"- {value}" for value in values))
    return "\n\n".join(sections)


def _chunks(value: str, size: int) -> list[str]:
    return [value[index : index + size] for index in range(0, len(value), size)] or [""]


def _paragraph(value: str) -> dict[str, Any]:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {
            "rich_text": [{"type": "text", "text": {"content": value}}]
        },
    }
