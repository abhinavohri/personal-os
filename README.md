# Personal OS

Personal OS is an AI-assisted planning system for people with several interests,
projects, and learning goals. Hermes is the conversational front door; Notion
stores the roadmap and memory; Todoist holds daily tasks; GitHub provides work
evidence; and handwritten notes are scanned into private Cloud Storage.

## How it works

```text
Paper notes -> Cloud Storage -> Vertex AI extraction -> Notion Notes Inbox

GitHub activity -----+
Todoist progress ----+-> Hermes weekly review -> Notion roadmap -> next tasks
Web research --------+
```

On a normal day, you talk to Hermes and work from Todoist. You keep writing on
paper. Notion stays backstage as the inspectable roadmap and durable memory.

## Components

| Component | Purpose |
| --- | --- |
| Hermes Agent | Conversation, orchestration, scheduled reviews, and approvals |
| Vertex AI | Handwriting extraction, routine planning, and deep reasoning |
| Notion | Goals, lanes, roadmap, decisions, resources, and weekly reviews |
| Todoist | Today's tasks, deadlines, recurring work, and completion status |
| GitHub | Resume context, repository catalog, commits, PRs, issues, and work evidence |
| Cloud Storage | Private archive of original notebook scans and extracted artifacts |
| Web search | Current papers, courses, jobs, tools, and other research |

## Planning model

The system finds a central **spine** connecting your interests, then assigns
them to four lanes:

- **Build:** the primary project receiving most effort.
- **Reading:** one slow, continuous learning track.
- **Open:** one bounded exploratory side quest.
- **Parking Lot:** preserved interests that are not active now.

Notion contains outcomes and milestones. Todoist contains only the next small
actions. Hermes reviews both and proposes changes; it does not silently change
strategic priorities.

## GitHub support

GitHub is treated as evidence, not as the planning database. With an explicit
repository allowlist, Hermes can:

- Build a profile of existing skills from repositories and README files.
- Include selected repositories alongside a resume during the initial interview.
- Summarize commits, pull requests, issues, releases, and repository activity.
- Use real development progress during daily and weekly reviews.
- Suggest maintenance work such as documentation, issue triage, tests, or stale
  dependency updates.

GitHub starts read-only. Creating issues, opening pull requests, pushing code,
merging, closing issues, or changing repository settings always requires
explicit approval.

## Handwritten notes

Scans are uploaded from a phone into a private GCS bucket. Vertex AI produces a
transcription, summary, proposed tasks, insights, resources, questions, diagram
descriptions, and confidence flags. Unclear content goes to review. Original
scans remain in Cloud Storage and are never committed to Git.

## Setup overview

### Accounts and tools

You need:

- A Google Cloud project with Vertex AI and Cloud Storage billing or credits.
- A Notion workspace and internal integration.
- A Todoist account and API token.
- A GitHub account authenticated through the `gh` CLI or a narrowly scoped app.
- Hermes Agent, Git, Google Cloud CLI, and the GitHub CLI on the host machine.
- Tailscale on the host machine and phone for private uploader access.

### Local configuration

```bash
git clone git@github.com:abhinavohri/personal-os.git
cd personal-os
cp .env.example .env
cp config/system.example.yaml config/system.yaml
uv sync
gcloud auth application-default login
gh auth login
```

After filling `config/system.yaml`, verify Vertex inference and grounded search:

```bash
uv run python scripts/verify_vertex.py
uv run python scripts/verify_gcs.py
uv run python scripts/bootstrap_notion.py
uv run python scripts/verify_notion.py
uv run python scripts/bootstrap_todoist.py
# Put the printed project_id in config/system.yaml, then:
uv run python scripts/verify_todoist.py
# Add your GitHub username and exact owner/repository allowlist, then:
uv run python scripts/verify_github.py
uv run python scripts/sync_github_catalog.py
```

Then:

1. Put only secrets in `.env`; never commit it.
2. Add project IDs, Notion data source IDs, model choices, and the GitHub repository
   allowlist to `config/system.yaml`.
3. Export `GITHUB_TOKEN="$(gh auth token)"` and load the other values from
   `.env` into your shell or deployment secret manager.
4. Configure Hermes to use Vertex AI; web research uses Vertex AI Google Search
   grounding and does not need a second search API key.
5. Create the Notion structure described in `docs/ARCHITECTURE.md` and share
   only that root page with the Notion integration.
6. Create the dedicated Todoist project with `bootstrap_todoist.py`, save the
   printed ID in `config/system.yaml`, and verify it with `verify_todoist.py`.
7. Add only the repositories you want the agent to read to the GitHub allowlist.
   Private repositories remain blocked unless you explicitly enable them.
8. Configure the local uploader variables described in `apps/uploader/README.md`,
   start it on localhost, and publish it privately with Tailscale Serve.
9. Run the personal interview and approve the first spine, lanes, and roadmap.
10. Rehearse the weekly loop with test data before scheduling it.

The provider adapters, configuration boundary, and authenticated mobile scan
uploader are implemented and covered by isolated tests. Deployment, Hermes tool
registration, the note-processing event handler, and end-to-end workflows
remain to be built.

Application code loads non-secret provider settings with
`PersonalOSConfig.from_yaml("config/system.yaml")`, loads tokens with
`RuntimeSecrets.from_environment(os.environ)`, and passes both to
`build_adapters(...)`. This produces the GCS, Notion, Todoist, GitHub, Vertex
inference, and grounded-search clients without coupling workflows to vendors.

## Security and cost defaults

- Keep credentials, scans, personal exports, and Terraform state out of Git.
- Prefer Google Application Default Credentials over service-account key files.
- Enforce public-access prevention and uniform bucket access on Cloud Storage.
- Allowlist GitHub repositories; exclude private repositories by default.
- Use a cost-efficient Vertex model for routine work and a stronger model only
  for difficult planning.
- Require approval for extracted tasks, low-confidence handwriting, material
  roadmap changes, and all GitHub write actions.
- Configure Google Cloud budgets and alerts before scheduled processing.

Notion, Todoist, and Hermes can be used without separate subscription charges.
Vertex AI—including grounded web searches—and Cloud Storage beyond the free
allowance may incur usage-based costs.

## Repository layout

```text
apps/uploader/              Authenticated phone-friendly scan uploader
services/note-processor/    Event-driven handwriting extraction
config/                     Safe configuration templates
infra/                      GCP infrastructure definitions
prompts/                    Versioned agent prompts
schemas/                    Structured output contracts
docs/                       Architecture, decisions, and implementation plan
```

Read [the architecture](docs/ARCHITECTURE.md),
[implementation roadmap](docs/IMPLEMENTATION_ROADMAP.md), and
[architecture decisions](docs/DECISIONS.md) before deploying. Contributors
should also read the [engineering guide](docs/ENGINEERING.md).

## Project status

The design, safety boundaries, provider-neutral ports, adapters, and local scan
uploader are implemented. The bucket and external workspaces are configured;
Hermes tools, note processing, and scheduled jobs have not yet been deployed.
