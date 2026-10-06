# Scan uploader

A phone-friendly Cloud Run app that accepts notebook photos and PDFs after
Google Sign-In, validates them, and writes them to the private paper-notes GCS
bucket. The browser never receives Cloud credentials and the bucket remains
private.

## Required environment

```text
GCP_PROJECT_ID=your-project-id
PAPER_NOTES_BUCKET=your-private-bucket
GOOGLE_OAUTH_CLIENT_ID=your-web-client-id.apps.googleusercontent.com
UPLOAD_ALLOWED_EMAIL=you@example.com
UPLOADER_TIMEZONE=Asia/Kolkata
```

Create a Google OAuth **Web application** client and add the deployed HTTPS URL
to its authorized JavaScript origins. The backend verifies the token audience,
expiry, signature, verified email, and exact email allowlist.

## Run locally

```bash
uv run uvicorn apps.uploader.main:app --reload
```

For a container build from the repository root:

```bash
docker build -f apps/uploader/Dockerfile -t personal-os-uploader .
```

The Cloud Run service account needs `roles/storage.objectUser` on only the
paper-notes bucket. No service-account key file is required.
