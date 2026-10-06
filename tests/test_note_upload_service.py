from datetime import datetime
from io import BytesIO
from uuid import UUID
from zoneinfo import ZoneInfo

import pytest

from personal_os.ports.object_store import StoredObject
from personal_os.services.note_upload import InvalidNoteUpload, NoteUpload, NoteUploadService


class FakeStore:
    def __init__(self) -> None:
        self.saved = None

    def put_file(self, uri, file, *, size, content_type, metadata=None):
        self.saved = {
            "uri": uri,
            "data": file.read(),
            "size": size,
            "content_type": content_type,
            "metadata": metadata,
        }
        return StoredObject(uri=uri, size=size, content_type=content_type)


def _service(store: FakeStore) -> NoteUploadService:
    return NoteUploadService(
        store,
        "notes",
        "Asia/Kolkata",
        clock=lambda: datetime(2026, 10, 7, 9, 30, tzinfo=ZoneInfo("Asia/Kolkata")),
        uuid_factory=lambda: UUID("00000000-0000-0000-0000-000000000123"),
    )


def test_valid_scan_is_stored_under_dated_collision_safe_key() -> None:
    store = FakeStore()

    result = _service(store).upload(
        NoteUpload(
            filename="../My notes (1).png",
            content_type="image/png",
            size=12,
            file=BytesIO(b"\x89PNG\r\n\x1a\nscan"),
            uploaded_by="person@example.com",
        )
    )

    assert result.uri == (
        "gs://notes/inbox/2026/10/07/"
        "00000000000000000000000000000123-My-notes-1-.png"
    )
    assert store.saved["metadata"]["original_filename"] == "My notes (1).png"
    assert store.saved["metadata"]["uploaded_by"] == "person@example.com"


@pytest.mark.parametrize(
    ("content_type", "data"),
    [
        ("text/plain", b"hello"),
        ("image/png", b"not a png"),
        ("application/pdf", b""),
    ],
)
def test_invalid_scan_is_rejected(content_type: str, data: bytes) -> None:
    with pytest.raises(InvalidNoteUpload):
        _service(FakeStore()).upload(
            NoteUpload(
                filename="page",
                content_type=content_type,
                size=len(data),
                file=BytesIO(data),
                uploaded_by="person@example.com",
            )
        )


def test_oversized_scan_is_rejected_before_storage() -> None:
    store = FakeStore()
    with pytest.raises(InvalidNoteUpload, match="larger than 20 MB"):
        _service(store).upload(
            NoteUpload(
                filename="page.jpg",
                content_type="image/jpeg",
                size=20 * 1024 * 1024 + 1,
                file=BytesIO(b"\xff\xd8\xff"),
                uploaded_by="person@example.com",
            )
        )
    assert store.saved is None


def test_batch_with_more_than_ten_files_is_rejected_before_storage() -> None:
    store = FakeStore()
    notes = [
        NoteUpload(
            filename=f"page-{index}.png",
            content_type="image/png",
            size=8,
            file=BytesIO(b"\x89PNG\r\n\x1a\n"),
            uploaded_by="person@example.com",
        )
        for index in range(11)
    ]

    with pytest.raises(InvalidNoteUpload, match="no more than 10"):
        _service(store).upload_many(notes)

    assert store.saved is None


def test_batch_larger_than_100_mb_is_rejected_before_storage() -> None:
    store = FakeStore()
    notes = [
        NoteUpload(
            filename=f"page-{index}.png",
            content_type="image/png",
            size=20 * 1024 * 1024,
            file=BytesIO(b"\x89PNG\r\n\x1a\n"),
            uploaded_by="person@example.com",
        )
        for index in range(6)
    ]

    with pytest.raises(InvalidNoteUpload, match="larger than 100 MB"):
        _service(store).upload_many(notes)

    assert store.saved is None
