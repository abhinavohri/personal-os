"""FastAPI entry point for authenticated paper-note uploads."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Mapping, Protocol

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from personal_os.providers.gcs import GCSObjectStore, ObjectStoreError
from personal_os.services.note_upload import (
    MAX_BATCH_UPLOAD_BYTES,
    MAX_FILES_PER_UPLOAD,
    MAX_UPLOAD_BYTES,
    InvalidNoteUpload,
    NoteUpload,
    NoteUploadService,
)


STATIC_DIR = Path(__file__).with_name("static")


@dataclass(frozen=True)
class UploaderSettings:
    project_id: str
    bucket: str
    google_oauth_client_id: str
    allowed_email: str
    timezone: str = "Asia/Kolkata"

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "UploaderSettings":
        values = {
            "project_id": environment.get("GCP_PROJECT_ID", ""),
            "bucket": environment.get("PAPER_NOTES_BUCKET", ""),
            "google_oauth_client_id": environment.get("GOOGLE_OAUTH_CLIENT_ID", ""),
            "allowed_email": environment.get("UPLOAD_ALLOWED_EMAIL", ""),
            "timezone": environment.get("UPLOADER_TIMEZONE", "Asia/Kolkata"),
        }
        missing = [name for name, value in values.items() if not value]
        if missing:
            raise RuntimeError(f"Missing uploader settings: {', '.join(missing)}")
        return cls(**values)


@dataclass(frozen=True)
class VerifiedIdentity:
    subject: str
    email: str


class TokenVerifier(Protocol):
    def verify(self, token: str) -> VerifiedIdentity: ...


class GoogleTokenVerifier:
    def __init__(self, client_id: str, allowed_email: str) -> None:
        self._client_id = client_id
        self._allowed_email = allowed_email.casefold()

    def verify(self, token: str) -> VerifiedIdentity:
        try:
            claims: dict[str, Any] = id_token.verify_oauth2_token(
                token,
                google_requests.Request(),
                self._client_id,
            )
        except ValueError as exc:
            raise PermissionError("Invalid or expired Google sign-in") from exc

        email = str(claims.get("email", ""))
        if not claims.get("email_verified") or email.casefold() != self._allowed_email:
            raise PermissionError("This Google account is not allowed to upload")
        return VerifiedIdentity(subject=str(claims["sub"]), email=email)


def create_app(
    settings: UploaderSettings,
    *,
    object_store: GCSObjectStore | None = None,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    store = object_store or GCSObjectStore(settings.project_id)
    verifier = token_verifier or GoogleTokenVerifier(
        settings.google_oauth_client_id, settings.allowed_email
    )
    uploads = NoteUploadService(store, settings.bucket, settings.timezone)

    app = FastAPI(title="Personal OS Scan Uploader", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.middleware("http")
    async def reject_oversized_requests(request: Request, call_next):
        if request.url.path == "/api/notes":
            content_length = request.headers.get("content-length")
            request_limit = MAX_BATCH_UPLOAD_BYTES + 1024 * 1024
            if content_length and int(content_length) > request_limit:
                return JSONResponse(
                    status_code=413,
                    content={"detail": "The upload request is larger than 101 MB"},
                )
        return await call_next(request)

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/healthz")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/config")
    def public_config() -> dict[str, str]:
        return {"googleOAuthClientId": settings.google_oauth_client_id}

    @app.post("/api/notes", status_code=201)
    def upload_notes(
        files: Annotated[list[UploadFile], File(alias="file")],
        authorization: Annotated[str | None, Header()] = None,
    ) -> dict[str, int | list[dict[str, str | int | None]]]:
        identity = _identity(authorization, verifier)
        try:
            stored_objects = uploads.upload_many(
                NoteUpload(
                    filename=file.filename or "",
                    content_type=file.content_type or "",
                    size=_file_size(file),
                    file=file.file,
                    uploaded_by=identity.email,
                )
                for file in files
            )
        except InvalidNoteUpload as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except ObjectStoreError as exc:
            raise HTTPException(status_code=502, detail="Cloud Storage upload failed") from exc
        return {
            "count": len(stored_objects),
            "uploads": [
                {
                    "uri": stored.uri,
                    "size": stored.size,
                    "contentType": stored.content_type,
                }
                for stored in stored_objects
            ],
        }

    return app


def _identity(authorization: str | None, verifier: TokenVerifier) -> VerifiedIdentity:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.casefold() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="Sign in with Google first")
    try:
        return verifier.verify(token)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc


def _file_size(file: UploadFile) -> int:
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(0)
    return size
