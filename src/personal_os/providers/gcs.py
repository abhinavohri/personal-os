"""Google Cloud Storage adapter."""

from dataclasses import dataclass
from typing import Any, BinaryIO, Mapping
from urllib.parse import urlparse

from google.cloud import storage

from personal_os.ports.object_store import StoredObject


class ObjectStoreError(RuntimeError):
    """Raised when an object storage operation fails."""


@dataclass(frozen=True)
class GCSLocation:
    bucket: str
    object_name: str


def parse_gcs_uri(uri: str) -> GCSLocation:
    parsed = urlparse(uri)
    if parsed.scheme != "gs" or not parsed.netloc or not parsed.path.lstrip("/"):
        raise ValueError(f"Expected a GCS object URI, got {uri!r}")
    return GCSLocation(parsed.netloc, parsed.path.lstrip("/"))


class GCSObjectStore:
    """Store scanned notes and generated artifacts in GCS."""

    def __init__(self, project_id: str, *, client: Any | None = None) -> None:
        self._client = client or storage.Client(project=project_id)

    def stat(self, uri: str) -> StoredObject:
        location = parse_gcs_uri(uri)
        try:
            blob = self._client.bucket(location.bucket).get_blob(location.object_name)
            if blob is None:
                raise ObjectStoreError(f"Object does not exist: {uri}")
            return self._metadata(uri, blob)
        except ObjectStoreError:
            raise
        except Exception as exc:
            raise ObjectStoreError(f"Could not read object metadata: {uri}") from exc

    def exists(self, uri: str) -> bool:
        location = parse_gcs_uri(uri)
        try:
            return self._client.bucket(location.bucket).get_blob(location.object_name) is not None
        except Exception as exc:
            raise ObjectStoreError(f"Could not check object existence: {uri}") from exc

    def list(self, prefix_uri: str) -> tuple[StoredObject, ...]:
        location = parse_gcs_uri(prefix_uri)
        try:
            blobs = self._client.list_blobs(
                location.bucket,
                prefix=location.object_name,
            )
            return tuple(
                self._metadata(f"gs://{location.bucket}/{blob.name}", blob)
                for blob in blobs
                if not blob.name.endswith("/")
            )
        except Exception as exc:
            raise ObjectStoreError(f"Could not list objects: {prefix_uri}") from exc

    def get_bytes(self, uri: str) -> bytes:
        location = parse_gcs_uri(uri)
        try:
            blob = self._client.bucket(location.bucket).get_blob(location.object_name)
            if blob is None:
                raise ObjectStoreError(f"Object does not exist: {uri}")
            return blob.download_as_bytes()
        except ObjectStoreError:
            raise
        except Exception as exc:
            raise ObjectStoreError(f"Could not read object: {uri}") from exc

    def put_bytes(self, uri: str, data: bytes, content_type: str) -> StoredObject:
        location = parse_gcs_uri(uri)
        try:
            blob = self._client.bucket(location.bucket).blob(location.object_name)
            blob.upload_from_string(data, content_type=content_type)
            blob.reload()
            return self._metadata(uri, blob)
        except Exception as exc:
            raise ObjectStoreError(f"Could not write object: {uri}") from exc

    def put_file(
        self,
        uri: str,
        file: BinaryIO,
        *,
        size: int,
        content_type: str,
        metadata: Mapping[str, str] | None = None,
    ) -> StoredObject:
        location = parse_gcs_uri(uri)
        try:
            blob = self._client.bucket(location.bucket).blob(location.object_name)
            blob.metadata = dict(metadata or {})
            blob.upload_from_file(
                file,
                rewind=True,
                size=size,
                content_type=content_type,
                if_generation_match=0,
            )
            blob.reload()
            return self._metadata(uri, blob)
        except Exception as exc:
            raise ObjectStoreError(f"Could not write object: {uri}") from exc

    def copy(self, source_uri: str, destination_uri: str) -> StoredObject:
        source = parse_gcs_uri(source_uri)
        destination = parse_gcs_uri(destination_uri)
        try:
            source_bucket = self._client.bucket(source.bucket)
            source_blob = source_bucket.blob(source.object_name)
            destination_bucket = self._client.bucket(destination.bucket)
            copied = source_bucket.copy_blob(
                source_blob,
                destination_bucket,
                new_name=destination.object_name,
            )
            return self._metadata(destination_uri, copied)
        except Exception as exc:
            raise ObjectStoreError(
                f"Could not copy {source_uri} to {destination_uri}"
            ) from exc

    @staticmethod
    def _metadata(uri: str, blob: Any) -> StoredObject:
        return StoredObject(
            uri=uri,
            size=getattr(blob, "size", None),
            content_type=getattr(blob, "content_type", None),
            updated_at=getattr(blob, "updated", None),
        )
