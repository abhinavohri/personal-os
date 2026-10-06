# Personal OS contributor instructions

## Priorities

1. Keep the daily user experience simple.
2. Protect personal data and require approval for consequential writes.
3. Prefer clear, testable code over framework-heavy abstractions.
4. Make provider boundaries replaceable without turning the project into a
   generic plugin platform.

## Architecture rules

- Keep domain models and planning rules independent of vendor SDKs.
- Put each external system behind a small interface when substitution is a real
  requirement: LLM, search, object storage, roadmap/memory, tasks, and work
  evidence.
- Keep provider-specific authentication, request formats, retries, and response
  normalization inside that provider's adapter.
- Services orchestrate interfaces; they must not import provider SDKs directly.
- Apps and event handlers are thin entry points. Business rules belong in the
  domain or service layer.
- Use direct functions for simple parsing, mapping, and formatting. Do not add a
  class, registry, factory, or dependency-injection container without a concrete
  need.
- Add a second implementation by extending an existing interface, not by adding
  provider conditionals throughout the codebase.

## Safety rules

- Never commit `.env`, credentials, raw scans, personal notes, or exports.
- Default integrations to read-only and least privilege.
- Require explicit approval for GitHub writes, Todoist task publication,
  material roadmap changes, and low-confidence handwriting extraction.
- Preserve source identifiers and idempotency keys for all event-driven work.
- Log operational metadata, not personal note contents or secrets.

## Development workflow

- Implement one coherent vertical slice at a time.
- Add or update tests in the same commit as behavior changes.
- Keep commits small, descriptive, and independently understandable.
- Run formatting, tests, schema validation, and `git diff --check` before each
  commit.
- Do not mix unrelated cleanup with a feature commit.

See `docs/ENGINEERING.md` for the intended module boundaries.
