# Implementation roadmap

## Phase 1: foundation

- Confirm the GCP project and billing guardrails.
- Authenticate locally with Application Default Credentials.
- Install and configure Hermes with Vertex AI.
- Verify one model turn and one Hermes tool call.
- Select the web-search backend and verify citations.

Exit condition: Hermes can reason through Vertex AI and perform a web search.

## Phase 2: roadmap and memory

- Create the Notion Personal OS root page.
- Create the Agent Brief, profile, lanes, roadmap, resources, decisions, notes
  inbox, and weekly review databases.
- Connect a least-privilege Notion integration.
- Define memory admission, correction, and archival rules.

Exit condition: Hermes can read the Agent Brief and draft a safe Notion update.

## Phase 3: GitHub evidence

- Reauthenticate the GitHub CLI or install a narrowly scoped GitHub App.
- Define the repository allowlist and private-repository policy.
- Import selected repository summaries alongside the resume.
- Create the Notion Repository Catalog.
- Collect commits, pull requests, issues, and releases for weekly reviews.
- Verify every GitHub write action is blocked pending explicit approval.

Exit condition: Hermes can summarize work from an allowlisted repository without
changing GitHub state.

## Phase 4: daily execution

- Create a dedicated Todoist project.
- Connect Todoist to Hermes.
- Implement draft-before-publish approval for generated tasks.
- Verify completion status is available to the review workflow.

Exit condition: an approved roadmap action appears in Todoist and its completion
is visible to Hermes.

## Phase 5: paper-note capture

- Create the private Cloud Storage bucket.
- Enable public-access prevention, uniform access, and soft delete.
- Build the authenticated mobile uploader.
- Build the local idempotent note processor.
- Validate extraction against representative handwriting and diagrams.
- Route low-confidence content to manual review.

Exit condition: a phone scan becomes a reviewed Notion inbox item while the
original remains private in Cloud Storage.

## Phase 6: Hermes orchestration

- Register provider-neutral tools for roadmap context, note processing,
  Todoist drafts, GitHub evidence, and grounded web research.
- Load the concise Agent Brief at session start.
- Require explicit approval for durable memory changes, generated tasks, and
  all consequential browser or GitHub actions.
- Record corrections to extracted notes as feedback and propose prompt changes
  rather than silently rewriting extraction behavior.

Exit condition: Hermes can process a note, explain the resulting draft, and
propose an approved next action without directly coupling to provider APIs.

## Phase 7: career and learning

- Add Learning Tracks, Topics, and Applications to the durable Notion model.
- Import books, public course pages, syllabi, and user-provided course material.
- Build prerequisite-aware learning plans with evidence and confidence per
  topic.
- Add retrieval practice, spaced review, mock interviews, and small practical
  assessments.
- Search periodically for relevant jobs and courses with citations; shortlist
  by explicit criteria and never apply automatically.
- Use direct URL extraction for public pages and browser control only for
  authenticated or JavaScript-heavy portals.

Exit condition: one learning track has an approved topic plan and revision
queue, and one job search produces a cited, deduplicated shortlist.

## Phase 8: personal planning

- Collect the initial brain dump and personal resources.
- Run the Hermes interview.
- Draft and approve the spine.
- Assign Build, Reading, Open, and Parking Lot lanes.
- Generate the first roadmap and daily actions.

Exit condition: the system contains an approved roadmap and a realistic first
week of tasks.

## Phase 9: closed loop

- Implement the weekly review workflow.
- Schedule it at a user-approved time.
- Add failure reporting and idempotency.
- Run one complete rehearsal with test data.
- Run the first real weekly review with explicit approval.

Exit condition: task progress, GitHub activity, and notes update the roadmap and
generate the next week without duplicating tasks or silently changing strategic
priorities.

## Phase 10: optional focus coach

- Start with explicit focus blocks, check-ins, work-in-progress limits, and a
  one-click Parking Lot action for distractions.
- Measure whether prompts are helpful before collecting activity telemetry.
- If still useful, design opt-in local browser/app signals with pause and
  retention controls.

Exit condition: focus interventions are user-controlled, demonstrably useful,
and do not require continuous invasive monitoring.
