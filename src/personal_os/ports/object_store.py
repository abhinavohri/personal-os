"""Provider-neutral object storage contracts."""

from dataclasses import dataclass
from datetime import datetime
from typing import BinaryIO, Mapping, Protocol


@dataclass(frozen=True)
class StoredObject:
    """Metadata for an object without loading its contents."""

    uri: str
    size: int | None = None
    content_type: str | None = None
    updated_at: datetime | None = None


class ObjectStore(Protocol):
    """Small storage surface needed by the note ingestion workflow."""

    def stat(self, uri: str) -> StoredObject: ...

    def exists(self, uri: str) -> bool: ...

    def list(self, prefix_uri: str) -> tuple[StoredObject, ...]: ...

    def get_bytes(self, uri: str) -> bytes: ...

    def put_bytes(self, uri: str, data: bytes, content_type: str) -> StoredObject: ...

    def put_file(
        self,
        uri: str,
        file: BinaryIO,
        *,
        size: int,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject: ...

    def copy(self, source_uri: str, destination_uri: str) -> StoredObject: ...
