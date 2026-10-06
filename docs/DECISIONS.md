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

## Pending

- GCP project identifier and bucket location.
- Vertex AI model identifiers available to the project.
- Web-search provider.
- Weekly review day, time, and delivery surface.
- GitHub repository allowlist and private-repository policy.
