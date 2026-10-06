"""Validation and storage orchestration for handwritten-note scans."""

import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO, Callable, Iterable
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from personal_os.ports.object_store import ObjectStore, StoredObject


MAX_UPLOAD_BYTES = 20 * 1024 * 1024
MAX_BATCH_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_FILES_PER_UPLOAD = 10
SUPPORTED_CONTENT_TYPES = frozenset(
    {
        "application/pdf",
        "image/heic",
        "image/heif",
        "image/jpeg",
        "image/png",
        "image/webp",
    }
)


class InvalidNoteUpload(ValueError):
    """Raised when an uploaded file is not a supported note scan."""


@dataclass(frozen=True)
class NoteUpload:
    filename: str
    content_type: str
    size: int
    file: BinaryIO
    uploaded_by: str


class NoteUploadService:
    """Validate a scan and persist it under a collision-safe inbox key."""

    def __init__(
        self,
        object_store: ObjectStore,
        bucket: str,
        timezone: str,
        *,
        clock: Callable[[], datetime] | None = None,
        uuid_factory: Callable[[], UUID] = uuid4,
    ) -> None:
        self._object_store = object_store
        self._bucket = bucket
        self._timezone = ZoneInfo(timezone)
        self._clock = clock or (lambda: datetime.now(self._timezone))
        self._uuid_factory = uuid_factory

    def upload(self, note: NoteUpload) -> StoredObject:
        _validate(note)
        return self._store(note)

    def upload_many(self, notes: Iterable[NoteUpload]) -> tuple[StoredObject, ...]:
        """Validate an entire batch before storing its files sequentially."""
        batch = tuple(notes)
        if not batch:
            raise InvalidNoteUpload("Choose at least one image or PDF to upload")
        if len(batch) > MAX_FILES_PER_UPLOAD:
            raise InvalidNoteUpload("Choose no more than 10 files at once")
        if sum(note.size for note in batch) > MAX_BATCH_UPLOAD_BYTES:
            raise InvalidNoteUpload("The selected files are larger than 100 MB in total")
        for note in batch:
            _validate(note)
        return tuple(self._store(note) for note in batch)

    def _store(self, note: NoteUpload) -> StoredObject:
        now = self._clock().astimezone(self._timezone)
        safe_name = _safe_filename(note.filename)
        object_name = (
            f"inbox/{now:%Y/%m/%d}/"
            f"{self._uuid_factory().hex}-{safe_name}"
        )
        uri = f"gs://{self._bucket}/{object_name}"
        note.file.seek(0)
        return self._object_store.put_file(
            uri,
            note.file,
            size=note.size,
            content_type=note.content_type,
            metadata={
                "original_filename": Path(note.filename).name[:200],
                "uploaded_by": note.uploaded_by[:200],
                "uploaded_at": now.isoformat(),
            },
        )


def _validate(note: NoteUpload) -> None:
    if not note.filename:
        raise InvalidNoteUpload("Choose an image or PDF to upload")
    if note.content_type not in SUPPORTED_CONTENT_TYPES:
        raise InvalidNoteUpload("Use a JPEG, PNG, WebP, HEIC, HEIF, or PDF file")
    if note.size <= 0:
        raise InvalidNoteUpload("The selected file is empty")
    if note.size > MAX_UPLOAD_BYTES:
        raise InvalidNoteUpload("The selected file is larger than 20 MB")

    note.file.seek(0)
    header = note.file.read(16)
    note.file.seek(0)
    if not _matches_signature(note.content_type, header):
        raise InvalidNoteUpload("The file contents do not match its reported type")


def _matches_signature(content_type: str, header: bytes) -> bool:
    if content_type == "application/pdf":
        return header.startswith(b"%PDF-")
    if content_type == "image/jpeg":
        return header.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return header.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return header.startswith(b"RIFF") and header[8:12] == b"WEBP"
    if content_type in {"image/heic", "image/heif"}:
        return len(header) >= 12 and header[4:8] == b"ftyp"
    return False


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip()
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    return (stem or "scan")[-120:]
