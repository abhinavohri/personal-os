from datetime import UTC, datetime

import pytest

from personal_os.providers.gcs import GCSObjectStore, ObjectStoreError, parse_gcs_uri


class FakeBlob:
    def __init__(self, name: str, *, exists: bool = True) -> None:
        self.name = name
        self.exists = exists
        self.size = 42
        self.content_type = "image/jpeg"
        self.updated = datetime(2026, 10, 6, tzinfo=UTC)
        self.upload = None

    def upload_from_string(self, data: bytes, *, content_type: str) -> None:
        self.upload = (data, content_type)
        self.size = len(data)
        self.content_type = content_type

    def reload(self) -> None:
        pass


class FakeBucket:
    def __init__(self, name: str) -> None:
        self.name = name
        self.blobs: dict[str, FakeBlob] = {}

    def blob(self, name: str) -> FakeBlob:
        return self.blobs.setdefault(name, FakeBlob(name))

    def get_blob(self, name: str) -> FakeBlob | None:
        return self.blobs.get(name)

    def copy_blob(self, source: FakeBlob, destination: "FakeBucket", *, new_name: str):
        copied = FakeBlob(new_name)
        copied.size = source.size
        copied.content_type = source.content_type
        destination.blobs[new_name] = copied
        return copied


class FakeClient:
    def __init__(self) -> None:
        self.buckets: dict[str, FakeBucket] = {}

    def bucket(self, name: str) -> FakeBucket:
        return self.buckets.setdefault(name, FakeBucket(name))


def test_parse_gcs_uri_requires_an_object() -> None:
    assert parse_gcs_uri("gs://notes/inbox/page.jpg").object_name == "inbox/page.jpg"
    with pytest.raises(ValueError):
        parse_gcs_uri("gs://notes")


def test_put_stat_and_copy() -> None:
    client = FakeClient()
    store = GCSObjectStore("project", client=client)

    written = store.put_bytes("gs://notes/inbox/page.jpg", b"scan", "image/jpeg")
    found = store.stat(written.uri)
    copied = store.copy(written.uri, "gs://notes/processed/page.jpg")

    assert found.size == 4
    assert copied.uri == "gs://notes/processed/page.jpg"
    assert copied.content_type == "image/jpeg"


def test_stat_translates_missing_object() -> None:
    store = GCSObjectStore("project", client=FakeClient())
    with pytest.raises(ObjectStoreError, match="does not exist"):
        store.stat("gs://notes/missing.jpg")
