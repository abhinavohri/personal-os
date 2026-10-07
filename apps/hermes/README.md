# Hermes integration

Hermes connects to Personal OS through a local stdio MCP server. The server
loads this repository's ignored `.env` and `config/system.yaml`, then exposes a
small set of bounded tools:

- read one named Notion context page;
- run grounded web research with citations;
- read the public GitHub profile, profile README, repositories, and pins;
- inspect metadata, README text, and activity for an allowlisted GitHub repo;
- read active and recently completed Todoist tasks; and
- process pending notebook scans into review drafts.

It does not expose email sending, job applications, course enrollment, Todoist
task creation, GitHub writes, or arbitrary Notion writes. Hermes can recommend
those actions, but the user must approve them before a separate write path is
used.

## Run locally

From the repository root:

```bash
uv sync
uv run python -m apps.hermes.server
```

The process speaks MCP over stdin/stdout, so a terminal started this way will
appear idle. Normally Hermes starts and manages it using this configuration:

```yaml
mcp_servers:
  personal_os:
    command: "/absolute/path/to/personal-os/.venv/bin/python"
    args: ["-m", "apps.hermes.server"]
    cwd: "/absolute/path/to/personal-os"
    timeout: 120
    supports_parallel_tool_calls: false
```

Do not copy integration secrets into Hermes configuration. The server reads
them directly from the repository's ignored `.env` file.
