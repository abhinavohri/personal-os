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
- Build the event-driven note processor.
- Validate extraction against representative handwriting and diagrams.
- Route low-confidence content to manual review.

Exit condition: a phone scan becomes a reviewed Notion inbox item while the
original remains private in Cloud Storage.

## Phase 6: personal planning

- Collect the initial brain dump and personal resources.
- Run the Hermes interview.
- Draft and approve the spine.
- Assign Build, Reading, Open, and Parking Lot lanes.
- Generate the first roadmap and daily actions.

Exit condition: the system contains an approved roadmap and a realistic first
week of tasks.

## Phase 7: closed loop

- Implement the weekly review workflow.
- Schedule it at a user-approved time.
- Add failure reporting and idempotency.
- Run one complete rehearsal with test data.
- Run the first real weekly review with explicit approval.

Exit condition: task progress, GitHub activity, and notes update the roadmap and
generate the next week without duplicating tasks or silently changing strategic
priorities.
