import asyncio
from datetime import UTC, date, datetime

import pytest

from apps.hermes.server import mcp
from personal_os.config import PersonalOSConfig
from personal_os.domain.plans import PlanActionInput, PlanProposal
from personal_os.ports.memory import MemoryRecordRef
from personal_os.ports.reviews import ExecutionReviewSnapshot
from personal_os.ports.search import SearchResponse, SearchSource
from personal_os.ports.tasks import TaskRecord
from personal_os.ports.work_evidence import (
    DeveloperProfile,
    PortfolioRepository,
    PortfolioSnapshot,
    RepositorySnapshot,
    WorkEvent,
)
from personal_os.services.hermes_orchestration import HermesOrchestrator
from personal_os.services.process_notes import NoteProcessingResult


NOW = datetime(2026, 10, 7, 12, tzinfo=UTC)


class FakeMemory:
    def __init__(self) -> None:
        self.page_ids: list[str] = []

    async def read_page_text(self, page_id: str) -> str:
        self.page_ids.append(page_id)
        return "Current brief"

    async def create_note_draft(self, note):
        return MemoryRecordRef("page")

    async def find_note_by_source(self, source_object: str):
        return None


class FakeSearch:
    def __init__(self) -> None:
        self.query = ""

    async def search(self, query: str, *, max_sources: int = 8):
        self.query = query
        return SearchResponse(
            answer="Public recruiting page found.",
            sources=(
                SearchSource(
                    "Company careers", "https://example.com/careers", "example.com"
                ),
            ),
            queries=("site:example.com careers",),
        )


class FakeEvidence:
    async def get_repository(self, full_name: str):
        if full_name != "abhinavohri/personal-os":
            raise RuntimeError("not allowlisted")
        return RepositorySnapshot(
            full_name=full_name,
            url=f"https://github.com/{full_name}",
            description="Career and learning assistant",
            primary_language="Python",
            topics=("personal-os",),
            is_private=False,
            default_branch="main",
        )

    async def get_readme_text(self, full_name: str):
        return "# Personal OS\n" + "x" * 2000

    async def recent_activity(self, full_name: str, since: datetime):
        return (
            WorkEvent(
                kind="commit",
                repository=full_name,
                title="Add Hermes tools",
                url=f"https://github.com/{full_name}/commit/abc",
                occurred_at=NOW,
            ),
        )

    async def get_portfolio(self, limit: int = 30):
        return PortfolioSnapshot(
            profile=DeveloperProfile(
                username="abhinavohri",
                url="https://github.com/abhinavohri",
                name="Abhinav Ohri",
                bio="Builder",
                company=None,
                blog="https://example.com",
                location="India",
                followers=10,
                following=5,
                public_repositories=3,
            ),
            profile_readme="# Hello",
            repositories=(
                PortfolioRepository(
                    full_name="abhinavohri/personal-os",
                    url="https://github.com/abhinavohri/personal-os",
                    description="Career assistant",
                    primary_language="Python",
                    topics=("agents",),
                    stars=2,
                    forks=0,
                    is_archived=False,
                    is_fork=False,
                    updated_at=NOW,
                    pushed_at=NOW,
                    is_pinned=True,
                ),
            ),
        )


class FakeTasks:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, tuple]] = []

    async def list_active(self, project_id: str):
        return (
            TaskRecord(
                id="active",
                content="Review portfolio",
                project_id=project_id,
                due_date=date(2026, 10, 6),
                created_at=datetime(2026, 9, 20, tzinfo=UTC),
            ),
        )

    async def list_completed(self, project_id: str, since: datetime, until: datetime):
        return (
            TaskRecord(
                id="done",
                content="Ship uploader",
                project_id=project_id,
                completed_at=NOW,
            ),
        )

    async def create_task(self, project_id: str, draft):
        raise AssertionError("Hermes must not publish tasks")

    async def create_tasks_idempotent(self, project_id, proposal_key, drafts):
        self.published.append((project_id, proposal_key, drafts))
        return tuple(f"todoist-{index}" for index, _ in enumerate(drafts))


class FakeNotes:
    async def process_pending(self, limit: int = 10):
        return (
            NoteProcessingResult(
                source_uri="gs://notes/inbox/page.jpg",
                status="processed",
                extraction_uri="gs://notes/extracted/page.json",
                notion_page_id="notion-page",
            ),
        )


class FakeReviews:
    def __init__(self) -> None:
        self.saved: ExecutionReviewSnapshot | None = None

    async def upsert_draft(self, review: ExecutionReviewSnapshot):
        self.saved = review
        return MemoryRecordRef("review-page", "https://notion.so/review-page")

    async def list_recent(self, limit: int = 4):
        return (self.saved,) if self.saved else ()


class FakePlans:
    def __init__(self) -> None:
        self.saved: PlanProposal | None = None

    async def upsert_draft(self, proposal: PlanProposal):
        version = (self.saved.version + 1) if self.saved else 1
        self.saved = proposal.model_copy(
            update={
                "version": version,
                "notion_page_id": "plan-page",
                "notion_url": "https://notion.so/plan-page",
            }
        )
        return self.saved

    async def latest_draft(self):
        return self.saved

    async def get(self, proposal_key: str):
        return self.saved if self.saved and self.saved.proposal_key == proposal_key else None

    async def mark_published(self, proposal_key, task_ids, published_at):
        assert self.saved is not None
        self.saved = self.saved.model_copy(
            update={
                "status": "Published",
                "todoist_task_ids": task_ids,
                "published_at": published_at,
            }
        )
        return self.saved


def _config() -> PersonalOSConfig:
    return PersonalOSConfig.model_validate(
        {
            "system": {"name": "personal-os", "timezone": "Asia/Kolkata"},
            "gcp": {
                "project_id": "project",
                "region": "global",
                "paper_notes_bucket": "notes",
            },
            "vertex": {
                "location": "global",
                "routine_model": "flash",
                "deep_reasoning_model": "pro",
            },
            "notion": {
                "root_page_id": "root",
                "agent_brief_page_id": "brief",
                "profile_page_id": "profile",
                "spine_page_id": "spine",
                "interests_and_lanes_page_id": "lanes",
                "current_week_page_id": "week",
                "archive_page_id": "archive",
                "notes_inbox_data_source_id": "notes-db",
                "roadmap_data_source_id": "roadmap-db",
                "resources_data_source_id": "resources-db",
                "repository_catalog_data_source_id": "repos-db",
                "decisions_data_source_id": "decisions-db",
                "weekly_reviews_data_source_id": "reviews-db",
                "plan_proposals_data_source_id": "plans-db",
            },
            "todoist": {"project_id": "todoist-project"},
            "github": {
                "username": "abhinavohri",
                "allowed_repositories": ["abhinavohri/personal-os"],
            },
            "web_search": {"model": "flash"},
        }
    )


def _orchestrator():
    memory = FakeMemory()
    search = FakeSearch()
    service = HermesOrchestrator(
        _config(),
        memory,
        search,
        FakeEvidence(),
        FakeTasks(),
        FakeNotes(),
        FakeReviews(),
        FakePlans(),
        clock=lambda: NOW,
    )
    return service, memory, search


def test_context_reads_only_configured_named_pages() -> None:
    service, memory, _ = _orchestrator()

    result = asyncio.run(service.read_context("agent_brief"))

    assert result == {"section": "agent_brief", "text": "Current brief"}
    assert memory.page_ids == ["brief"]
    with pytest.raises(ValueError, match="Unsupported context"):
        asyncio.run(service.read_context("arbitrary"))


def test_career_research_forbids_guessed_or_private_contacts() -> None:
    service, _, search = _orchestrator()

    result = asyncio.run(
        service.research_web("Find the recruiter for Example", "career", 5)
    )

    assert "Never guess an email pattern" in search.query
    assert "private address" in search.query
    assert result["sources"][0]["url"] == "https://example.com/careers"
    assert "explicit user approval" in result["action_boundary"]


def test_repository_evidence_is_bounded_and_read_only() -> None:
    service, _, _ = _orchestrator()

    result = asyncio.run(
        service.inspect_repository("abhinavohri/personal-os", readme_limit=1000)
    )

    assert result["repository"]["primary_language"] == "Python"
    assert result["readme_truncated"] is True
    assert result["activity"][0]["kind"] == "commit"
    assert "Read-only" in result["action_boundary"]
    assert "concrete feature" in result["coaching_scope"]
    assert "smallest credible milestone" in result["coaching_scope"]


def test_portfolio_evidence_supports_profile_and_pin_coaching() -> None:
    service, _, _ = _orchestrator()

    result = asyncio.run(service.portfolio_evidence())

    assert result["profile"]["username"] == "abhinavohri"
    assert result["profile_readme"] == "# Hello"
    assert result["repositories"][0]["is_pinned"] is True
    assert "feature additions" in result["coaching_scope"]
    assert "only then new project ideas" in result["coaching_scope"]
    assert "explicit user approval" in result["coaching_scope"]


def test_task_progress_never_uses_write_method() -> None:
    service, _, _ = _orchestrator()

    result = asyncio.run(service.task_progress(14))

    assert result["active"][0]["content"] == "Review portfolio"
    assert result["completed"][0]["content"] == "Ship uploader"
    assert "explicitly approved" in result["action_boundary"]


def test_execution_review_infers_load_and_diagnoses_plan_pressure() -> None:
    service, _, _ = _orchestrator()

    result = asyncio.run(service.execution_review(14))

    assert result["metrics"]["completed_tasks"] == 1
    assert result["metrics"]["observed_completions_per_week"] == 0.5
    assert result["metrics"]["overdue_tasks"] == 1
    assert result["metrics"]["rollover_tasks"] == 1
    assert result["metrics"]["github_event_types"] == {"commit": 1}
    assert result["assessment"]["state"] == "strained"
    assert "weekly hours" in result["planning_policy"]
    assert "does not passively monitor" in result["monitoring_scope"]


def test_execution_review_draft_is_idempotently_keyed_and_does_not_publish() -> None:
    service, _, _ = _orchestrator()

    result = asyncio.run(service.save_execution_review_draft(14))

    assert result["review_key"] == "execution:2026-10-07:14"
    assert result["notion_page_id"] == "review-page"
    assert result["recent_history"][0]["assessment"] == "strained"
    assert "does not alter the roadmap" in result["action_boundary"]


def test_note_processing_is_bounded_to_ten_and_returns_review_drafts() -> None:
    service, _, _ = _orchestrator()

    result = asyncio.run(service.process_pending_notes(10))

    assert result["results"][0]["notion_page_id"] == "notion-page"
    assert result["review_required"] is True
    with pytest.raises(ValueError, match="between 1 and 10"):
        asyncio.run(service.process_pending_notes(11))


def test_plan_proposal_is_versioned_bounded_and_inert() -> None:
    service, _, _ = _orchestrator()
    actions = (
        PlanActionInput(
            content="Review one repository",
            due_date=date(2026, 10, 7),
            kind="core",
        ),
        PlanActionInput(
            content="Revise interview notes",
            due_date=date(2026, 10, 7),
            kind="optional",
        ),
    )

    first = asyncio.run(
        service.save_plan_proposal(
            date(2026, 10, 7), "daily", "Keep the day intentionally small.", actions
        )
    )
    second = asyncio.run(
        service.save_plan_proposal(
            date(2026, 10, 7), "daily", "Revise after check-in.", actions
        )
    )
    latest = asyncio.run(service.latest_plan_proposal())

    assert first["proposal_key"] == "daily:2026-10-07"
    assert first["version"] == 1
    assert second["version"] == 2
    assert latest["proposal"]["status"] == "Draft"
    assert latest["proposal"]["approval_phrase"] == "APPROVE daily:2026-10-07"
    assert "No Todoist task exists" in first["action_boundary"]


def test_plan_proposal_rejects_excess_core_actions() -> None:
    service, _, _ = _orchestrator()
    actions = tuple(
        PlanActionInput(content=f"Core {index}", due_date=date(2026, 10, 7))
        for index in range(3)
    )

    with pytest.raises(ValueError, match="at most 2 core"):
        asyncio.run(
            service.save_plan_proposal(
                date(2026, 10, 7), "daily", "Too much work.", actions
            )
        )


def test_plan_publication_requires_exact_phrase_and_is_receipted() -> None:
    tasks = FakeTasks()
    plans = FakePlans()
    service = HermesOrchestrator(
        _config(),
        FakeMemory(),
        FakeSearch(),
        FakeEvidence(),
        tasks,
        FakeNotes(),
        FakeReviews(),
        plans,
        clock=lambda: NOW,
    )
    actions = (
        PlanActionInput(content="Ship the slice", due_date=date(2026, 10, 7)),
    )
    asyncio.run(
        service.save_plan_proposal(
            date(2026, 10, 7), "daily", "One bounded outcome.", actions
        )
    )

    with pytest.raises(ValueError, match="must exactly equal"):
        asyncio.run(service.publish_plan_proposal("daily:2026-10-07", "okay"))
    result = asyncio.run(
        service.publish_plan_proposal(
            "daily:2026-10-07", "APPROVE daily:2026-10-07"
        )
    )
    repeated = asyncio.run(
        service.publish_plan_proposal(
            "daily:2026-10-07", "APPROVE daily:2026-10-07"
        )
    )

    assert result["result"] == "published"
    assert result["created_task_ids"] == ["todoist-0"]
    assert repeated["result"] == "already_published"
    assert len(tasks.published) == 1
    assert tasks.published[0][2][0].labels == ("personal-os",)


def test_mcp_surface_contains_draft_tools_but_no_publication_tool() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert names == {
        "personal_os_read_context",
        "personal_os_research_web",
        "personal_os_inspect_repository",
        "personal_os_portfolio_evidence",
        "personal_os_task_progress",
        "personal_os_execution_review",
        "personal_os_save_execution_review_draft",
        "personal_os_save_plan_proposal",
        "personal_os_latest_plan_proposal",
        "personal_os_publish_plan_proposal",
        "personal_os_process_pending_notes",
    }
