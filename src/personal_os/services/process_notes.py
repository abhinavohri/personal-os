"""Reliable processing workflow for scans waiting in object storage."""

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import PurePosixPath
from typing import Callable, Literal

from personal_os.domain.notes import ExtractedNote
from personal_os.ports.memory import DurableMemory, MemoryRecordRef
from personal_os.ports.object_store import ObjectStore, StoredObject
from personal_os.services.extract_note import PaperNoteExtractor
from personal_os.services.note_upload import SUPPORTED_CONTENT_TYPES


ProcessingStatus = Literal["processed", "skipped", "failed"]


@dataclass(frozen=True)
class NoteProcessingResult:
    source_uri: str
    status: ProcessingStatus
    extraction_uri: str | None = None
    notion_page_id: str | None = None
    error: str | None = None


class PaperNoteProcessor:
    """Turn each inbox scan into one cached extraction and one Notion draft."""

    def __init__(
        self,
        object_store: ObjectStore,
        extractor: PaperNoteExtractor,
        memory: DurableMemory,
        bucket: str,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store = object_store
        self._extractor = extractor
        self._memory = memory
        self._bucket = bucket
        self._clock = clock or (lambda: datetime.now(UTC))

    async def process_pending(self, limit: int = 10) -> tuple[NoteProcessingResult, ...]:
        if limit < 1:
            raise ValueError("limit must be at least one")

        results: list[NoteProcessingResult] = []
        processed = {
            item.uri
            for item in self._store.list(f"gs://{self._bucket}/processed/")
        }
        sources = sorted(
            self._store.list(f"gs://{self._bucket}/inbox/"),
            key=lambda item: item.uri,
        )
        for source in sources:
            if source.content_type not in SUPPORTED_CONTENT_TYPES:
                continue
            _, receipt_uri = _artifact_uris(source.uri, self._bucket)
            if receipt_uri in processed:
                continue
            if len(results) >= limit:
                break
            try:
                results.append(await self.process_one(source))
            except Exception as exc:
                results.append(
                    NoteProcessingResult(
                        source_uri=source.uri,
                        status="failed",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                )
        return tuple(results)

    async def process_one(self, source: StoredObject) -> NoteProcessingResult:
        extraction_uri, receipt_uri = _artifact_uris(source.uri, self._bucket)
        if self._store.exists(receipt_uri):
            return NoteProcessingResult(source_uri=source.uri, status="skipped")

        note = await self._load_or_extract(source, extraction_uri)
        record = await self._memory.find_note_by_source(source.uri)
        if record is None:
            record = await self._memory.create_note_draft(note)
        self._write_receipt(source.uri, extraction_uri, receipt_uri, record)
        return NoteProcessingResult(
            source_uri=source.uri,
            status="processed",
            extraction_uri=extraction_uri,
            notion_page_id=record.id,
        )

    async def _load_or_extract(
        self,
        source: StoredObject,
        extraction_uri: str,
    ) -> ExtractedNote:
        if self._store.exists(extraction_uri):
            return ExtractedNote.model_validate_json(self._store.get_bytes(extraction_uri))
        note = await self._extractor.extract(
            source.uri,
            source.content_type or "application/octet-stream",
        )
        self._store.put_bytes(
            extraction_uri,
            note.model_dump_json(indent=2).encode(),
            "application/json",
        )
        return note

    def _write_receipt(
        self,
        source_uri: str,
        extraction_uri: str,
        receipt_uri: str,
        record: MemoryRecordRef,
    ) -> None:
        receipt = {
            "source_object": source_uri,
            "extraction_object": extraction_uri,
            "notion_page_id": record.id,
            "notion_url": record.url,
            "processed_at": self._clock().astimezone(UTC).isoformat(),
        }
        self._store.put_bytes(
            receipt_uri,
            json.dumps(receipt, indent=2, sort_keys=True).encode(),
            "application/json",
        )


def _artifact_uris(source_uri: str, bucket: str) -> tuple[str, str]:
    prefix = f"gs://{bucket}/inbox/"
    if not source_uri.startswith(prefix):
        raise ValueError(f"Source is outside the configured inbox: {source_uri}")
    relative = PurePosixPath(source_uri.removeprefix(prefix)).with_suffix(".json")
    return (
        f"gs://{bucket}/extracted/{relative}",
        f"gs://{bucket}/processed/{relative}",
    )
