from fastapi.testclient import TestClient

from apps.uploader.application import (
    UploaderSettings,
    VerifiedIdentity,
    create_app,
)
from personal_os.ports.object_store import StoredObject


class FakeStore:
    def __init__(self) -> None:
        self.saved = None

    def put_file(self, uri, file, *, size, content_type, metadata=None):
        self.saved = (uri, file.read(), metadata)
        return StoredObject(uri=uri, size=size, content_type=content_type)


class FakeVerifier:
    def verify(self, token: str) -> VerifiedIdentity:
        if token != "valid-token":
            raise PermissionError("Invalid sign-in")
        return VerifiedIdentity(subject="user-1", email="person@example.com")


def _client(store: FakeStore | None = None) -> tuple[TestClient, FakeStore]:
    store = store or FakeStore()
    app = create_app(
        UploaderSettings(
            project_id="project",
            bucket="notes",
            google_oauth_client_id="client-id",
            allowed_email="person@example.com",
        ),
        object_store=store,
        token_verifier=FakeVerifier(),
    )
    return TestClient(app), store


def test_public_shell_and_config_are_available() -> None:
    client, _ = _client()

    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/api/config").json() == {"googleOAuthClientId": "client-id"}
    assert "Send a page" in client.get("/").text


def test_upload_requires_google_identity() -> None:
    client, store = _client()

    response = client.post(
        "/api/notes",
        files={"file": ("page.png", b"\x89PNG\r\n\x1a\nscan", "image/png")},
    )

    assert response.status_code == 401
    assert store.saved is None


def test_authenticated_scan_is_uploaded() -> None:
    client, store = _client()

    response = client.post(
        "/api/notes",
        headers={"Authorization": "Bearer valid-token"},
        files={"file": ("page.png", b"\x89PNG\r\n\x1a\nscan", "image/png")},
    )

    assert response.status_code == 201
    assert response.json()["count"] == 1
    assert response.json()["uploads"][0]["uri"].startswith("gs://notes/inbox/")
    assert store.saved[1] == b"\x89PNG\r\n\x1a\nscan"
    assert store.saved[2]["uploaded_by"] == "person@example.com"


def test_multiple_scans_are_uploaded_in_one_request() -> None:
    client, store = _client()

    response = client.post(
        "/api/notes",
        headers={"Authorization": "Bearer valid-token"},
        files=[
            ("file", ("page-1.png", b"\x89PNG\r\n\x1a\none", "image/png")),
            ("file", ("page-2.jpg", b"\xff\xd8\xfftwo", "image/jpeg")),
        ],
    )

    assert response.status_code == 201
    assert response.json()["count"] == 2
    assert len(response.json()["uploads"]) == 2


def test_disguised_file_is_rejected() -> None:
    client, store = _client()

    response = client.post(
        "/api/notes",
        headers={"Authorization": "Bearer valid-token"},
        files={"file": ("page.png", b"not really a png", "image/png")},
    )

    assert response.status_code == 400
    assert "do not match" in response.json()["detail"]
    assert store.saved is None


def test_oversized_request_is_rejected_before_parsing() -> None:
    client, store = _client()

    response = client.post(
        "/api/notes",
        headers={
            "Authorization": "Bearer valid-token",
            "Content-Length": str(102 * 1024 * 1024),
            "Content-Type": "multipart/form-data; boundary=test",
        },
        content=b"not parsed",
    )

    assert response.status_code == 413
    assert store.saved is None
