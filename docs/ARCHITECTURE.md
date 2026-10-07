# Architecture

## Product boundary

Personal OS is an orchestration layer, not a replacement for every tool. Each
system has one clear responsibility and one authoritative data type.

| System | Responsibility | Authoritative data |
| --- | --- | --- |
| Hermes | Conversation, orchestration, review loops | No unique durable data |
| Vertex AI | Reasoning and multimodal extraction | No durable user state |
| Cloud Storage | Original paper notes and extraction artifacts | Raw scans |
| Notion | Roadmap and durable agent memory | Goals, decisions, reviews |
| Todoist | Daily execution | Task status and completion |
| GitHub | Work evidence and repository context | Source history, PRs, issues |
| This repository | Implementation and configuration | Code and schemas |

## User experience

The user should normally interact with only three surfaces:

1. Hermes for planning, questions, approvals, and reviews.
2. Todoist for today's executable tasks.
3. A physical notebook for thinking and learning.

Notion is a backstage control center. It is available for inspection and manual
editing but should not require daily attention.

## Note ingestion

```text
Phone scan
  -> Tailscale private HTTPS
  -> local authenticated uploader
  -> gs://<bucket>/inbox/<date>/<object>
  -> local note processor
  -> Vertex AI structured extraction
  -> extracted JSON in Cloud Storage
  -> draft item in Notion Notes Inbox
  -> user approval in Hermes
  -> durable memory, roadmap update, or Todoist task
```

Unclear handwriting must be flagged. The system must retain the original scan
and must not silently convert low-confidence text into tasks or durable memory.

The local processor uses deterministic `extracted/` and `processed/` artifact
paths. It also checks Notion by source object before creating a draft so retries
do not duplicate model calls or inbox entries.

## Notion structure

```text
Personal OS
├── Agent Brief
├── Profile and Constraints
├── Spine
├── Interests and Lanes
├── Roadmap
├── Current Week
├── Notes Inbox
├── Resources
├── Repository Catalog
├── Decision Log
├── Weekly Reviews
└── Archive
```

The Agent Brief is the small session-start document. It points to deeper data
without forcing Hermes to load the entire workspace on every interaction.

## Planning model

- **Spine:** the central outcome connecting multiple interests.
- **Build:** the primary active interest receiving most effort.
- **Reading:** one slow-moving study track.
- **Open:** one bounded exploratory side quest.
- **Parking Lot:** preserved interests that are not active.

The Notion roadmap contains outcomes and milestones. Todoist contains only the
small actions required now.

### Adaptive planning loop

The system does not ask the user to predict a fixed number of available weekly
hours. The first execution plan is deliberately conservative. Each review uses
completed, overdue, and long-running Todoist tasks; allowlisted GitHub activity;
processed notes; the Current Week context; and explicit blocker or priority
check-ins. Task completion is a load signal, not a claim that all tasks have
equal effort.

Hermes first adjusts action size, order, scope, and work in progress. It proposes
a strategic change only when repeated evidence shows that the outcome or lane
itself is wrong. Every proposed change includes its evidence and remains a draft
until the applicable approval boundary is satisfied.

Each saved review uses a deterministic key for its date and observation window.
Repeated runs refresh the same Notion draft rather than creating duplicates.
Comparable task and GitHub metrics remain available to later reviews so the
planner can distinguish a one-off bad period from a repeated pattern.

## GitHub as work evidence

GitHub supplements the resume and self-reported progress with concrete work.
Hermes maintains a Notion Repository Catalog containing only explicitly
allowlisted repositories and their relevance to the roadmap.

Read-only collection can include repository metadata, README files, languages,
commits, pull requests, issues, releases, and contribution activity. The weekly
review uses those signals to describe progress, identify neglected projects,
and propose maintenance work.

Portfolio coaching adds the user's public GitHub profile, profile README, owned
public repositories, and current pinned repositories. Hermes compares that
evidence with target roles and recommends a sequence: fix an existing project's
architecture or documentation when it already demonstrates the needed skill,
extend a relevant existing project with a focused feature when that naturally
demonstrates a missing skill, then propose a new project only when a meaningful
evidence gap cannot credibly fit existing work. Every feature recommendation
should name the target skill, the smallest credible milestone, and the evidence
to add to the README. Profile README edits, pin changes, and repository changes
remain approval-gated.

GitHub is not the source of strategic truth; Notion remains authoritative for
goals and roadmap state. GitHub write actions—including pushes, issues, pull
requests, merges, and repository settings—require explicit user approval.

## Model roles

- A cost-efficient Vertex AI model handles extraction, classification,
  summaries, and routine planning.
- A stronger reasoning model handles the initial interview, spine creation,
  difficult tradeoffs, and weekly roadmap restructuring.
- Exact model identifiers remain configuration, because Vertex availability
  changes over time.

## Scheduled review

The weekly job gathers completed, overdue, and long-running Todoist tasks,
allowlisted GitHub activity, processed notes, roadmap state, and recent
decisions. Hermes drafts a review and a revised next plan using observed
execution as its capacity signal. Material roadmap changes and newly extracted
tasks require user approval.

## Career and learning

The same planning loop supports employment, courses, books, and formal study:

- **Learning tracks** define outcomes such as completing an IIT course,
  preparing for an interview area, or working through a book.
- **Topics** capture prerequisites, confidence, evidence, and the next review
  date instead of treating course completion as proof of understanding.
- **Resources** hold books, course pages, syllabi, papers, and videos.
- **Applications** track job fit, evidence gaps, deadlines, status, and the next
  action without permitting automatic applications.
- Todoist receives current study, revision, interview, and application actions;
  Notion retains the durable plan and progress evidence.
- GitHub activity and approved paper notes provide evidence of practiced skills,
  not just self-reported progress.

Revision should be retrieval-based: Hermes proposes questions, mock interviews,
small implementation exercises, and spaced review dates from approved material.
It must distinguish completed content from demonstrated understanding.

## Web and browser acquisition

Use the least fragile acquisition method that can access the source:

1. Vertex AI Google Search grounding discovers current jobs, courses, books,
   papers, and official pages with source attribution.
2. Direct URL retrieval extracts a known public job description, syllabus, or
   course outline.
3. Browser control is reserved for JavaScript-heavy or authenticated portals
   that do not expose a suitable API or stable public page.
4. The user can upload a syllabus, permitted PDF, screenshot, or table of
   contents when automated retrieval is unavailable.

Browser control starts read-only. Logging in requires the user to handle
credentials and MFA, and consequential actions such as applying for a job,
submitting coursework, enrolling, purchasing, or sending a message require
explicit approval.

Recruiter discovery follows an additional privacy boundary: the system may
surface professional contact information explicitly published on an official
company, recruiter, or individual's public professional page. It must not guess
email patterns, infer private addresses, or collect personal contact details.
Cold outreach remains a draft until the user explicitly approves sending it.

## Focus guardrails

The first focus feature is a deliberate check-in loop, not passive surveillance:
Hermes asks for the current focus block, compares new work with the approved
weekly plan, and offers to continue, deliberately switch, or park the diversion.
It should enforce work-in-progress limits and preserve interesting distractions
in the Parking Lot.

Automatic app or browser activity monitoring is a later, opt-in feature. Any
such telemetry must stay local by default, collect only the minimum needed, and
have a visible pause control and retention limit.

## Security boundaries

- Enforce public-access prevention and uniform bucket-level access on GCS.
- Bind the local uploader only to localhost and expose it with Tailscale Serve,
  never Tailscale Funnel.
- Require an uploader access key in addition to tailnet device access.
- Prefer Application Default Credentials over long-lived service-account keys.
- Give each service account the minimum bucket and Vertex permissions required.
- Keep secrets, personal exports, and scans outside Git.
- Start GitHub access read-only, exclude private repositories by default, and
  use an explicit repository allowlist.
- Never place an expiring signed URL into durable Notion memory; store the GCS
  object identifier and mint access only when requested.
