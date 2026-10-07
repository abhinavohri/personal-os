# Architecture decisions

## Accepted

### Hermes is the primary interface

The user talks to Hermes for daily focus, approvals, and reviews. Notion remains
inspectable but should not require daily use.

### Vertex AI provides inference

Cloud inference avoids running a large local model. Routine work and deep
reasoning use separately configurable model roles to control cost.

### Notion stores roadmap and durable memory

Notion is simpler and more human-readable than operating a separate application
database for the first version.

### Todoist stores executable tasks

Strategic context stays in Notion. Todoist contains only small actions, due
dates, recurring work, and completion state.

### Cloud Storage stores paper-note originals

Google Drive is near its quota. A private GCS bucket provides a separate,
automation-friendly archive for scans and extraction artifacts.

### The scan uploader runs locally over Tailscale

The laptop hosts the uploader on localhost. Tailscale Serve provides private
HTTPS access to approved tailnet devices, and an application access key adds a
second authorization layer. This avoids an always-on hosted server and keeps
Google Cloud credentials on the laptop. Tailscale Funnel is not used.

### GitHub is an evidence source

Selected repositories supplement the resume and provide objective progress
signals. Access is allowlisted and read-only by default; Notion remains the
authoritative roadmap, and GitHub write actions require explicit approval.

### Obsidian is not required

The physical notebook remains the primary note-taking surface. Notion holds the
searchable extracted record and agent memory.

### Human approval protects strategic state

Low-confidence handwriting, material roadmap changes, and generated tasks are
drafts until the user approves them.

### Adaptive reviews run before the day begins

Hermes prepares a draft at 03:00 Asia/Kolkata from Monday through Saturday. A
deeper weekly review replaces the daily run at 03:00 on Sunday. Both jobs use
observed execution rather than a user estimate of available hours, and both
remain draft-only until the user approves consequential changes.

### Plan publication uses exact interactive approval

Scheduled runs may create or revise a bounded Notion Plan Proposal, but they
cannot publish it. Hermes presents the proposal and its exact approval phrase in
an interactive conversation. Todoist publication uses deterministic command
IDs and records task receipts so retries do not duplicate work.

## Pending

- The approval experience for material roadmap changes.
