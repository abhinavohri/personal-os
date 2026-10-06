"""Durable memory contracts used by Personal OS workflows."""

from dataclasses import dataclass
from typing import Protocol

from personal_os.domain.notes import ExtractedNote


@dataclass(frozen=True)
class MemoryRecordRef:
    id: str
    url: str | None = None


class DurableMemory(Protocol):
    """Use-case-sized interface for durable context and note drafts."""

    async def read_page_text(self, page_id: str) -> str: ...

    async def create_note_draft(self, note: ExtractedNote) -> MemoryRecordRef: ...
