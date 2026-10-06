# Engineering guide

## Design principle

Use the least abstraction that preserves an important boundary. Personal OS is
a personal tool first, not a general-purpose agent framework.

Simple transformations should remain simple functions. External providers get
interfaces because credentials, APIs, cost, and availability can change.

## Intended module shape

```text
src/personal_os/
├── domain/       Data models and planning rules; no vendor SDK imports
├── ports/        Small protocols for replaceable external capabilities
├── providers/    Vertex, GCS, Notion, Todoist, GitHub, and search adapters
├── services/     Use-case orchestration across ports
└── config/       Validated settings and secret references

apps/             Human-facing entry points
services/         Deployable Cloud Run or event-handler entry points
```

This structure should be introduced incrementally. Empty packages should not be
created merely to match the diagram.

## Replaceable boundaries

### LLM provider

The core needs operations such as text generation and structured multimodal
generation. It should not know whether the implementation is Vertex AI, a local
model, or another cloud provider.

Normalize provider responses into domain objects at the adapter boundary. Do
not expose Vertex request or response objects to planning services.

### Search provider

Return a small shared result type containing title, URL, snippet, and optional
published date. Provider-specific ranking metadata stays in the adapter.

### Object store

The note processor needs object identity, content metadata, and controlled read
or write operations. GCS event payloads should be converted at the entry point.

### Roadmap and memory store

Notion is the first implementation. Services work with roadmap, decision,
resource, and review records rather than generic Notion blocks.

### Task store

Todoist is the first implementation. Draft tasks remain domain objects until an
approval step publishes them.

### Work-evidence provider

GitHub is the first implementation. It returns normalized repository, commit,
pull-request, issue, and release evidence from an explicit allowlist.

## What not to abstract prematurely

- One-off prompt text and small deterministic mappings.
- A workflow that has only one call site and no meaningful policy boundary.
- Configuration keys that are specific to one deployed service.
- Provider capabilities that the product does not yet use.

## Error handling

- Translate SDK exceptions into a small set of service-level failures.
- Retry only transient operations and cap retries.
- Use idempotency keys for storage events and external writes.
- Send ambiguous or low-confidence results to review instead of guessing.
- Preserve enough source metadata to diagnose failures without logging private
  note contents.

## Testing

- Unit-test domain rules and normalization without network access.
- Use contract tests for each provider adapter.
- Keep live-provider tests optional and separately marked.
- Rehearse the entire weekly loop with synthetic data before real scheduling.
