# Note processor

A local, idempotent worker that processes new objects from the paper-notes
bucket, calls Vertex AI with the versioned extraction prompt and schema, stores
artifacts, and creates a draft entry in the Notion Notes Inbox.

Run up to ten pending scans:

```bash
uv run python scripts/process_notes.py --limit 10
```

For each `inbox/...` scan, the worker writes:

- `extracted/...json`: validated structured model output.
- `processed/...json`: completion receipt containing the Notion page ID.

The deterministic paths make retries inexpensive. Before creating a Notion
page, the worker also queries the `Source Object` property, preventing a crash
between page creation and receipt storage from creating a duplicate draft.

The worker never publishes extracted tasks. They remain proposals inside the
Notion draft until explicitly approved.
