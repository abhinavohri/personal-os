"""Safe, provider-neutral capabilities exposed to Hermes."""

import asyncio
from collections import Counter
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from typing import Literal, Protocol
from zoneinfo import ZoneInfo

from personal_os.config import PersonalOSConfig
from personal_os.domain.planning import ExecutionObservation, assess_execution
from personal_os.domain.plans import (
    PlanActionInput,
    PlanCadence,
    PlanProposal,
    validate_daily_shape,
)
from personal_os.ports.memory import DurableMemory
from personal_os.ports.plans import PlanProposalStore
from personal_os.ports.reviews import ExecutionReviewSnapshot, ReviewStore
from personal_os.ports.search import WebSearch
from personal_os.ports.tasks import TaskRecord, TaskStore
from personal_os.ports.work_evidence import WorkEvidence
from personal_os.services.process_notes import NoteProcessingResult


ContextSection = Literal[
    "agent_brief",
    "profile",
    "spine",
    "interests_and_lanes",
    "current_week",
]
ResearchPurpose = Literal["career", "learning", "general"]


class PendingNoteProcessor(Protocol):
    async def process_pending(
        self, limit: int = 10
    ) -> tuple[NoteProcessingResult, ...]: ...


class HermesOrchestrator:
    """Translate Hermes tool calls into bounded Personal OS operations."""

    def __init__(
        self,
        config: PersonalOSConfig,
        memory: DurableMemory,
        web_search: WebSearch,
        work_evidence: WorkEvidence,
        tasks: TaskStore,
        note_processor: PendingNoteProcessor,
        reviews: ReviewStore,
        plans: PlanProposalStore,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._memory = memory
        self._web_search = web_search
        self._work_evidence = work_evidence
        self._tasks = tasks
        self._note_processor = note_processor
        self._reviews = reviews
        self._plans = plans
        self._clock = clock or (lambda: datetime.now(UTC))
        self._context_pages = {
            "agent_brief": config.notion.agent_brief_page_id,
            "profile": config.notion.profile_page_id,
            "spine": config.notion.spine_page_id,
            "interests_and_lanes": config.notion.interests_and_lanes_page_id,
            "current_week": config.notion.current_week_page_id,
        }

    async def read_context(self, section: ContextSection) -> dict[str, object]:
        """Read one approved Notion context page, never an arbitrary page ID."""
        page_id = self._context_pages.get(section)
        if page_id is None:
            raise ValueError(f"Unsupported context section: {section}")
        return {
            "section": section,
            "text": await self._memory.read_page_text(page_id),
        }

    async def research_web(
        self,
        query: str,
        purpose: ResearchPurpose = "general",
        max_sources: int = 8,
    ) -> dict[str, object]:
        """Run cited web research with an explicit professional-contact policy."""
        normalized = query.strip()
        if not normalized:
            raise ValueError("query must not be empty")
        if len(normalized) > 2000:
            raise ValueError("query must be at most 2000 characters")
        if not 1 <= max_sources <= 12:
            raise ValueError("max_sources must be between 1 and 12")

        policy = {
            "career": (
                "\n\nSafety and sourcing requirements: Use current public sources. If the "
                "request involves recruiters or contact details, return only professional "
                "contact information explicitly published on an official company, recruiter, "
                "or individual's public professional page. Never guess an email pattern, infer "
                "a private address, or include personal phone/address data. Distinguish verified "
                "contact details from a suggested company contact route. Do not apply, message, "
                "or send anything."
            ),
            "learning": (
                "\n\nSourcing requirements: Prefer official course, syllabus, publisher, "
                "institution, and primary technical sources. Separate prerequisites from the "
                "advertised curriculum."
            ),
            "general": "\n\nSourcing requirements: Prefer current primary sources.",
        }[purpose]
        response = await self._web_search.search(
            normalized + policy,
            max_sources=max_sources,
        )
        return {
            "purpose": purpose,
            "answer": response.answer,
            "queries": list(response.queries),
            "sources": [
                {
                    "title": source.title,
                    "url": source.url,
                    "domain": source.domain,
                }
                for source in response.sources
            ],
            "action_boundary": (
                "Research and drafting only. Sending outreach, applying, enrolling, or "
                "purchasing requires explicit user approval."
            ),
        }

    async def inspect_repository(
        self,
        full_name: str,
        activity_days: int = 30,
        readme_limit: int = 12000,
    ) -> dict[str, object]:
        """Read evidence from one repository allowed by configuration."""
        if not 1 <= activity_days <= 365:
            raise ValueError("activity_days must be between 1 and 365")
        if not 1000 <= readme_limit <= 30000:
            raise ValueError("readme_limit must be between 1000 and 30000")

        repository = await self._work_evidence.get_repository(full_name)
        readme = await self._work_evidence.get_readme_text(full_name)
        since = self._clock().astimezone(UTC) - timedelta(days=activity_days)
        activity = await self._work_evidence.recent_activity(full_name, since)
        return {
            "repository": {
                "full_name": repository.full_name,
                "url": repository.url,
                "description": repository.description,
                "primary_language": repository.primary_language,
                "topics": list(repository.topics),
                "is_private": repository.is_private,
                "default_branch": repository.default_branch,
            },
            "readme": (readme or "")[:readme_limit],
            "readme_truncated": bool(readme and len(readme) > readme_limit),
            "activity_since": since.isoformat(),
            "activity": [
                {
                    "kind": event.kind,
                    "title": event.title,
                    "url": event.url,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in activity
            ],
            "action_boundary": (
                "Read-only evidence. Repository edits, pushes, issues, pull requests, "
                "pins, and settings changes require explicit user approval."
            ),
            "coaching_scope": (
                "Assess whether this project should be maintained, extended, or left alone. "
                "When a target-role skill gap fits the project, suggest a concrete feature "
                "that demonstrates that skill, explain why it belongs here, and define the "
                "smallest credible milestone plus README evidence. Prefer this over proposing "
                "a disconnected new project."
            ),
        }

    async def portfolio_evidence(self, repository_limit: int = 30) -> dict[str, object]:
        """Read public profile evidence used for portfolio coaching."""
        if not 1 <= repository_limit <= 100:
            raise ValueError("repository_limit must be between 1 and 100")
        snapshot = await self._work_evidence.get_portfolio(repository_limit)
        profile = snapshot.profile
        return {
            "profile": {
                "username": profile.username,
                "url": profile.url,
                "name": profile.name,
                "bio": profile.bio,
                "company": profile.company,
                "blog": profile.blog,
                "location": profile.location,
                "followers": profile.followers,
                "following": profile.following,
                "public_repositories": profile.public_repositories,
            },
            "profile_readme": snapshot.profile_readme or "",
            "repositories": [
                {
                    "full_name": repository.full_name,
                    "url": repository.url,
                    "description": repository.description,
                    "primary_language": repository.primary_language,
                    "topics": list(repository.topics),
                    "stars": repository.stars,
                    "forks": repository.forks,
                    "is_archived": repository.is_archived,
                    "is_fork": repository.is_fork,
                    "updated_at": repository.updated_at.isoformat(),
                    "pushed_at": (
                        repository.pushed_at.isoformat()
                        if repository.pushed_at
                        else None
                    ),
                    "is_pinned": repository.is_pinned,
                }
                for repository in snapshot.repositories
            ],
            "coaching_scope": (
                "Use this evidence with target roles and the Personal OS profile to rank "
                "portfolio gaps, feature additions to relevant existing projects, profile "
                "README improvements, candidate pins, repositories needing deeper review, "
                "and only then new project ideas for gaps that cannot credibly fit existing "
                "work. Tie each recommendation to a target-role skill and observable evidence. "
                "Do not change GitHub without explicit user approval."
            ),
        }

    async def task_progress(self, completed_days: int = 14) -> dict[str, object]:
        """Read active and recently completed tasks from the Personal OS project."""
        if not 1 <= completed_days <= 90:
            raise ValueError("completed_days must be between 1 and 90")
        until = self._clock().astimezone(UTC)
        since = until - timedelta(days=completed_days)
        project_id = self._config.todoist.project_id
        active = await self._tasks.list_active(project_id)
        completed = await self._tasks.list_completed(project_id, since, until)
        return {
            "active": [_task_payload(task) for task in active],
            "completed": [_task_payload(task) for task in completed],
            "completed_since": since.isoformat(),
            "action_boundary": (
                "Read-only progress. New or changed Todoist tasks must be proposed and "
                "explicitly approved before publication."
            ),
        }

    async def execution_review(
        self, window_days: int | None = None
    ) -> dict[str, object]:
        """Gather execution evidence and diagnose how the plan should adapt."""
        days = window_days or self._config.planning.review_window_days
        if not 7 <= days <= 90:
            raise ValueError("window_days must be between 7 and 90")

        now = self._clock().astimezone(UTC)
        since = now - timedelta(days=days)
        project_id = self._config.todoist.project_id
        active, completed, current_week = await asyncio.gather(
            self._tasks.list_active(project_id),
            self._tasks.list_completed(project_id, since, now),
            self._memory.read_page_text(self._config.notion.current_week_page_id),
        )
        repository_activity = await asyncio.gather(
            *(
                self._work_evidence.recent_activity(repository, since)
                for repository in self._config.github.allowed_repositories
            )
        )
        events = tuple(event for group in repository_activity for event in group)

        local_today = now.astimezone(ZoneInfo(self._config.system.timezone)).date()
        rollover_before = now - timedelta(
            days=self._config.planning.rollover_after_days
        )
        overdue = tuple(
            task for task in active if task.due_date and task.due_date < local_today
        )
        focus_due = tuple(
            task for task in active if task.due_date and task.due_date <= local_today
        )
        rollovers = tuple(
            task
            for task in active
            if task.created_at and task.created_at.astimezone(UTC) <= rollover_before
        )
        observation = ExecutionObservation(
            active_tasks=len(active),
            completed_tasks=len(completed),
            overdue_tasks=len(overdue),
            rollover_tasks=len(rollovers),
            focus_due_tasks=len(focus_due),
            github_events=len(events),
            window_days=days,
        )
        assessment = assess_execution(
            observation,
            max_daily_tasks=self._config.planning.max_daily_tasks,
        )
        event_counts = Counter(event.kind for event in events)
        return {
            "window": {
                "start": since.isoformat(),
                "end": now.isoformat(),
                "days": days,
            },
            "current_week_context": current_week,
            "metrics": {
                "active_tasks": observation.active_tasks,
                "completed_tasks": observation.completed_tasks,
                "observed_completions_per_week": observation.observed_completions_per_week,
                "overdue_tasks": observation.overdue_tasks,
                "rollover_tasks": observation.rollover_tasks,
                "focus_due_tasks": observation.focus_due_tasks,
                "github_events": observation.github_events,
                "github_event_types": dict(sorted(event_counts.items())),
            },
            "active_tasks": [_task_payload(task) for task in active],
            "recently_completed": [_task_payload(task) for task in completed],
            "repository_activity": [
                {
                    "kind": event.kind,
                    "repository": event.repository,
                    "title": event.title,
                    "url": event.url,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in sorted(
                    events, key=lambda item: item.occurred_at, reverse=True
                )[:50]
            ],
            "assessment": {
                "state": assessment.state,
                "adjustments": list(assessment.adjustments),
            },
            "planning_policy": (
                "Treat the next plan as a hypothesis. Infer sustainable load from observed "
                "execution and improve task size, order, and work in progress before changing "
                "strategic outcomes. Ask only for hard constraints, deadlines, blockers, or "
                "priority choices—not an estimate of available weekly hours. Propose changes "
                "with reasons; publishing tasks and material roadmap changes requires approval."
            ),
            "monitoring_scope": (
                "Uses Todoist status, allowlisted GitHub activity, the Current Week page, "
                "processed notes, and deliberate check-ins. It does not passively monitor "
                "screens, browser history, or applications."
            ),
        }

    async def save_execution_review_draft(
        self, window_days: int | None = None
    ) -> dict[str, object]:
        """Persist one idempotent Notion draft for the current review window."""
        review = await self.execution_review(window_days)
        window = review["window"]
        metrics = review["metrics"]
        assessment = review["assessment"]
        window_start = datetime.fromisoformat(window["start"])
        window_end = datetime.fromisoformat(window["end"])
        review_key = f"execution:{window_end.date().isoformat()}:{window['days']}"
        summary = (
            f"{assessment['state'].title()} — {metrics['completed_tasks']} completed, "
            f"{metrics['active_tasks']} active, {metrics['overdue_tasks']} overdue, "
            f"{metrics['rollover_tasks']} rollovers, {metrics['github_events']} GitHub events."
        )
        snapshot = ExecutionReviewSnapshot(
            review_key=review_key,
            window_start=window_start,
            window_end=window_end,
            assessment=assessment["state"],
            active_tasks=metrics["active_tasks"],
            completed_tasks=metrics["completed_tasks"],
            observed_completions_per_week=metrics[
                "observed_completions_per_week"
            ],
            overdue_tasks=metrics["overdue_tasks"],
            rollover_tasks=metrics["rollover_tasks"],
            github_events=metrics["github_events"],
            summary=summary,
        )
        record = await self._reviews.upsert_draft(snapshot)
        history = await self._reviews.list_recent(4)
        return {
            "review_key": review_key,
            "notion_page_id": record.id,
            "notion_url": record.url,
            "summary": summary,
            "recent_history": [
                {
                    "review_key": item.review_key,
                    "window_end": item.window_end.isoformat(),
                    "assessment": item.assessment,
                    "completed_tasks": item.completed_tasks,
                    "observed_completions_per_week": (
                        item.observed_completions_per_week
                    ),
                    "overdue_tasks": item.overdue_tasks,
                    "rollover_tasks": item.rollover_tasks,
                }
                for item in history
            ],
            "action_boundary": (
                "This saves or refreshes a Draft review only. It does not alter the roadmap "
                "or publish Todoist tasks; those changes require explicit approval."
            ),
        }

    async def save_plan_proposal(
        self,
        plan_date: date,
        cadence: PlanCadence,
        rationale: str,
        actions: tuple[PlanActionInput, ...],
    ) -> dict[str, object]:
        """Create or revise an inert, versioned executable-plan draft."""
        validate_daily_shape(
            actions,
            max_core=self._config.planning.max_core_tasks_per_day,
            max_optional=self._config.planning.max_optional_tasks_per_day,
        )
        proposal = PlanProposal(
            proposal_key=f"{cadence}:{plan_date.isoformat()}",
            plan_date=plan_date,
            cadence=cadence,
            rationale=rationale.strip(),
            actions=actions,
        )
        return _plan_payload(await self._plans.upsert_draft(proposal))

    async def latest_plan_proposal(self) -> dict[str, object]:
        """Read the latest unpublished plan for conversational review."""
        proposal = await self._plans.latest_draft()
        if proposal is None:
            return {
                "proposal": None,
                "message": "No unpublished plan proposal is available.",
            }
        return {
            "proposal": _plan_payload(proposal),
            "review_instruction": (
                "Review or edit this draft conversationally. Nothing has been added to "
                "Todoist. Publishing requires the exact approval phrase returned with the "
                "proposal."
            ),
        }

    async def process_pending_notes(self, limit: int = 10) -> dict[str, object]:
        """Process scans into extraction artifacts and Notion review drafts."""
        if not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        results = await self._note_processor.process_pending(limit)
        return {
            "results": [
                {
                    "source_uri": result.source_uri,
                    "status": result.status,
                    "extraction_uri": result.extraction_uri,
                    "notion_page_id": result.notion_page_id,
                    "error": result.error,
                }
                for result in results
            ],
            "review_required": any(
                result.status in {"processed", "failed"} for result in results
            ),
            "action_boundary": (
                "Outputs are drafts. Extracted tasks and low-confidence text require "
                "user review before becoming durable plans or Todoist tasks."
            ),
        }


def _task_payload(task: TaskRecord) -> dict[str, object]:
    return {
        "id": task.id,
        "content": task.content,
        "description": task.description,
        "due_date": task.due_date.isoformat() if task.due_date else None,
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "completed_at": (
            task.completed_at.isoformat() if task.completed_at else None
        ),
    }


def _plan_payload(proposal: PlanProposal) -> dict[str, object]:
    return {
        "proposal_key": proposal.proposal_key,
        "plan_date": proposal.plan_date.isoformat(),
        "cadence": proposal.cadence,
        "status": proposal.status,
        "version": proposal.version,
        "rationale": proposal.rationale,
        "actions": [action.model_dump(mode="json") for action in proposal.actions],
        "notion_page_id": proposal.notion_page_id,
        "notion_url": proposal.notion_url,
        "todoist_task_ids": list(proposal.todoist_task_ids),
        "published_at": (
            proposal.published_at.isoformat() if proposal.published_at else None
        ),
        "approval_phrase": f"APPROVE {proposal.proposal_key}",
        "action_boundary": (
            "Draft only. No Todoist task exists until the user gives the exact approval "
            "phrase in an interactive Hermes conversation. Scheduled jobs must never approve."
        ),
    }
