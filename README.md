# Personal OS

Personal OS is an AI-assisted planning system for people with several interests,
projects, and learning goals. Hermes is the conversational front door; Notion
stores the roadmap and memory; Todoist holds daily tasks; GitHub provides work
evidence; and handwritten notes are scanned into private Cloud Storage.

## How it works

```text
Paper notes -> Cloud Storage -> local worker -> Vertex AI -> Notion Notes Inbox

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

The plan is a hypothesis, not a fixed calendar based on a guessed weekly-hours
number. Hermes observes Todoist completions and rollovers, allowlisted GitHub
activity, processed notes, and deliberate check-ins. It estimates a sustainable
task load from actual execution, diagnoses blockers or oversized actions, and
improves task size, order, scope, and work in progress. Only repeated evidence
should trigger a proposed strategic change.

## Career and learning support

Personal OS is intended to manage more than software projects. Learning tracks
can come from books, courses, an IIT syllabus, interview requirements, or a
user-defined goal. The system breaks them into prerequisite-aware topics,
tracks confidence and evidence, schedules retrieval-based revision, and uses
approved notes and GitHub work to generate practice questions and interview
preparation.

Grounded web research can discover current jobs, courses, books, and papers.
Known public pages are read directly; browser automation is reserved for
authenticated or dynamic portals. Job applications, enrollment, purchases,
messages, and submissions always require explicit approval.

Career research may find recruiter contact routes, but only when professional
contact information is explicitly published on an official company, recruiter,
or public professional page. The system never guesses email patterns or seeks
private contact details, and cold emails remain drafts until approved.

Focus support begins with declared focus blocks, plan-aware check-ins, and a
Parking Lot for distracting ideas. Passive browser or app monitoring is an
optional later feature with local-first telemetry and an obvious pause control.

## GitHub support

GitHub is treated as evidence, not as the planning database. With an explicit
repository allowlist, Hermes can:

- Build a profile of existing skills from repositories and README files.
- Include selected repositories alongside a resume during the initial interview.
- Summarize commits, pull requests, issues, releases, and repository activity.
- Use real development progress during daily and weekly reviews.
- Suggest maintenance work such as documentation, issue triage, tests, or stale
  dependency updates.
- Compare the public profile, profile README, owned repositories, and current
  pins with target roles to propose an ordered portfolio improvement plan.
- Recommend focused features for relevant existing projects when they can
  demonstrate a missing target-role skill more credibly than another new repo.

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
4. Configure Hermes to use Vertex AI, then register the local MCP server using
   the commands below; web research uses Vertex AI Google Search grounding and
   does not need a second search API key.
5. Create the Notion structure described in `docs/ARCHITECTURE.md` and share
   only that root page with the Notion integration.
6. Create the dedicated Todoist project with `bootstrap_todoist.py`, save the
   printed ID in `config/system.yaml`, and verify it with `verify_todoist.py`.
7. Add only the repositories you want the agent to read to the GitHub allowlist.
   Private repositories remain blocked unless you explicitly enable them.
8. Configure the local uploader variables described in `apps/uploader/README.md`,
   install its macOS user service, and publish it privately with Tailscale
   Serve.
9. Run `uv run python scripts/process_notes.py` to convert pending scans into
   structured GCS artifacts and idempotent Notion drafts.
10. Provide target outcomes and hard constraints, then approve the first spine,
    lanes, and deliberately conservative plan; Hermes will refine the load from
    observed execution.
11. Rehearse the weekly loop with test data before scheduling it.

### Hermes

Install the lean Hermes core from the official installer. Browser control can
be added later when a specific authenticated or dynamic site requires it.

```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh -o /tmp/hermes-install.sh
bash /tmp/hermes-install.sh --non-interactive --skip-browser --skip-computer-use

hermes config set model.default google/gemini-3.8-flash
hermes config set model.provider vertex
hermes config set vertex.project_id YOUR_GCP_PROJECT_ID
hermes config set vertex.region global

hermes mcp add personal_os \
  --command "$PWD/.venv/bin/python" \
  --connect-timeout 30 \
  --args "$PWD/apps/hermes/server.py"
hermes mcp test personal_os
```

Choose **yes** when Hermes asks whether to enable all reviewed Personal OS
tools. Hermes uses Google Application Default Credentials, so no Vertex API key
is placed in its configuration. Start it from this repository with
`hermes --in "$PWD"` so its terminal and code-review tools are scoped to the
project you intend to work on.

The provider adapters, configuration boundary, authenticated mobile scan
uploader, local note processor, and bounded Hermes MCP tool server are
implemented and covered by isolated tests. Hermes host installation, recurring
jobs, approval-gated write workflows, and full end-to-end reviews remain to be
built.

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
apps/hermes/                Bounded local MCP tools for Hermes
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

The design, safety boundaries, provider-neutral ports, adapters, local scan
uploader, idempotent local note processor, and Hermes MCP tools are implemented.
The primary local Hermes host is registered with Vertex AI, and its execution
review can diagnose recent planning pressure. Approval-gated plan publication,
durable review drafts, and scheduled reviews have not yet been completed.
