"""Safe, provider-neutral capabilities exposed to Hermes."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from personal_os.config import PersonalOSConfig
from personal_os.ports.memory import DurableMemory
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
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._config = config
        self._memory = memory
        self._web_search = web_search
        self._work_evidence = work_evidence
        self._tasks = tasks
        self._note_processor = note_processor
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
        "completed_at": (
            task.completed_at.isoformat() if task.completed_at else None
        ),
    }
