# Scan uploader

A phone-friendly local app that accepts notebook photos and PDFs, validates
them, and writes them to the private paper-notes GCS bucket. Tailscale Serve
provides private HTTPS access from approved devices. The browser never receives
Cloud credentials and the bucket remains private.

Each request accepts up to 10 files, with a 20 MB per-file limit and a 100 MB
total batch limit. The complete batch is validated before storage begins.

## Required environment

```text
GCP_PROJECT_ID=your-project-id
PAPER_NOTES_BUCKET=your-private-bucket
UPLOADER_AUTH_MODE=local
UPLOAD_ACCESS_KEY=a-long-random-value
UPLOADER_TIMEZONE=Asia/Kolkata
```

The access key is a second layer after Tailscale device authentication. It is
stored only in the ignored local `.env` file and the trusted phone's browser.

## Run privately over Tailscale

Authenticate local Google Cloud client libraries once:

```bash
gcloud auth application-default login
```

Start the uploader. It binds only to localhost, not the Wi-Fi interface:

```bash
uv run python scripts/start_uploader.py
```

On macOS, install it as a user service after verifying the manual command:

```bash
uv run python scripts/install_uploader_service.py
```

The service starts at login and restarts after a crash. It does not run while
the user is logged out, and the Mac must remain awake. To remove it:

```bash
uv run python scripts/install_uploader_service.py --uninstall
```

In another terminal, publish that local port only inside the tailnet:

```bash
tailscale serve --bg 8000
```

`tailscale serve status` prints the private HTTPS URL. Do not use `tailscale
funnel`; Funnel would publish the service to the internet.

The previous Google Sign-In mode remains available for a future hosted
deployment by setting `UPLOADER_AUTH_MODE=google`, `GOOGLE_OAUTH_CLIENT_ID`, and
`UPLOAD_ALLOWED_EMAIL`.
