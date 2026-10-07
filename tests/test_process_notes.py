import asyncio
import json
from datetime import UTC, datetime

from personal_os.domain.notes import ExtractedNote
from personal_os.ports.memory import MemoryRecordRef
from personal_os.ports.object_store import StoredObject
from personal_os.services.process_notes import PaperNoteProcessor


SOURCE = "gs://notes/inbox/2026/10/07/page.jpg"
EXTRACTION = "gs://notes/extracted/2026/10/07/page.json"
RECEIPT = "gs://notes/processed/2026/10/07/page.json"


class FakeStore:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {
            SOURCE: (b"scan", "image/jpeg"),
        }

    def list(self, prefix_uri: str):
        return tuple(
            StoredObject(uri=uri, size=len(data), content_type=content_type)
            for uri, (data, content_type) in self.objects.items()
            if uri.startswith(prefix_uri)
        )

    def exists(self, uri: str) -> bool:
        return uri in self.objects

    def get_bytes(self, uri: str) -> bytes:
        return self.objects[uri][0]

    def put_bytes(self, uri: str, data: bytes, content_type: str):
        self.objects[uri] = (data, content_type)
        return StoredObject(uri=uri, size=len(data), content_type=content_type)


class FakeExtractor:
    def __init__(self) -> None:
        self.calls = 0

    async def extract(self, source_object: str, media_type: str) -> ExtractedNote:
        self.calls += 1
        return ExtractedNote(
            source_object=source_object,
            title="Test note",
            transcription="Remember this.",
            summary="A reminder.",
            confidence=0.95,
            tasks=(),
            insights=(),
            questions=(),
            resources=(),
            uncertainties=(),
        )


class FakeMemory:
    def __init__(self) -> None:
        self.record: MemoryRecordRef | None = None
        self.created = 0

    async def find_note_by_source(self, source_object: str):
        return self.record

    async def create_note_draft(self, note: ExtractedNote):
        self.created += 1
        self.record = MemoryRecordRef("notion-page", "https://notion.so/notion-page")
        return self.record


def _processor(store: FakeStore, extractor: FakeExtractor, memory: FakeMemory):
    return PaperNoteProcessor(
        store,
        extractor,
        memory,
        "notes",
        clock=lambda: datetime(2026, 10, 7, 6, 0, tzinfo=UTC),
    )


def test_pending_scan_creates_extraction_notion_draft_and_receipt() -> None:
    store = FakeStore()
    extractor = FakeExtractor()
    memory = FakeMemory()

    results = asyncio.run(_processor(store, extractor, memory).process_pending())

    assert results[0].status == "processed"
    assert results[0].notion_page_id == "notion-page"
    assert extractor.calls == 1
    assert memory.created == 1
    assert ExtractedNote.model_validate_json(store.get_bytes(EXTRACTION)).title == "Test note"
    receipt = json.loads(store.get_bytes(RECEIPT))
    assert receipt["source_object"] == SOURCE
    assert receipt["notion_page_id"] == "notion-page"


def test_processing_receipt_makes_retry_a_noop() -> None:
    store = FakeStore()
    store.put_bytes(RECEIPT, b"{}", "application/json")
    extractor = FakeExtractor()
    memory = FakeMemory()

    results = asyncio.run(_processor(store, extractor, memory).process_pending())

    assert results == ()
    assert extractor.calls == 0
    assert memory.created == 0


def test_retry_reuses_extraction_and_existing_notion_page() -> None:
    store = FakeStore()
    note = asyncio.run(FakeExtractor().extract(SOURCE, "image/jpeg"))
    store.put_bytes(EXTRACTION, note.model_dump_json().encode(), "application/json")
    extractor = FakeExtractor()
    memory = FakeMemory()
    memory.record = MemoryRecordRef("existing-page")

    results = asyncio.run(_processor(store, extractor, memory).process_pending())

    assert results[0].status == "processed"
    assert results[0].notion_page_id == "existing-page"
    assert extractor.calls == 0
    assert memory.created == 0
    assert store.exists(RECEIPT)


def test_processed_history_does_not_consume_pending_limit() -> None:
    store = FakeStore()
    store.put_bytes(RECEIPT, b"{}", "application/json")
    second_source = "gs://notes/inbox/2026/10/07/page-2.jpg"
    store.put_bytes(second_source, b"scan", "image/jpeg")
    extractor = FakeExtractor()
    memory = FakeMemory()

    results = asyncio.run(
        _processor(store, extractor, memory).process_pending(limit=1)
    )

    assert len(results) == 1
    assert results[0].source_uri == second_source
    assert results[0].status == "processed"
