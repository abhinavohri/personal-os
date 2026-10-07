import asyncio
from datetime import UTC, date, datetime

import pytest

from apps.hermes.server import mcp
from personal_os.config import PersonalOSConfig
from personal_os.ports.memory import MemoryRecordRef
from personal_os.ports.search import SearchResponse, SearchSource
from personal_os.ports.tasks import TaskRecord
from personal_os.ports.work_evidence import RepositorySnapshot, WorkEvent
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


class FakeTasks:
    async def list_active(self, project_id: str):
        return (
            TaskRecord(
                id="active",
                content="Review portfolio",
                project_id=project_id,
                due_date=date(2026, 10, 8),
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


def test_task_progress_never_uses_write_method() -> None:
    service, _, _ = _orchestrator()

    result = asyncio.run(service.task_progress(14))

    assert result["active"][0]["content"] == "Review portfolio"
    assert result["completed"][0]["content"] == "Ship uploader"
    assert "explicitly approved" in result["action_boundary"]


def test_note_processing_is_bounded_to_ten_and_returns_review_drafts() -> None:
    service, _, _ = _orchestrator()

    result = asyncio.run(service.process_pending_notes(10))

    assert result["results"][0]["notion_page_id"] == "notion-page"
    assert result["review_required"] is True
    with pytest.raises(ValueError, match="between 1 and 10"):
        asyncio.run(service.process_pending_notes(11))


def test_mcp_surface_contains_no_consequential_write_tool() -> None:
    tools = asyncio.run(mcp.list_tools())
    names = {tool.name for tool in tools}

    assert names == {
        "personal_os_read_context",
        "personal_os_research_web",
        "personal_os_inspect_repository",
        "personal_os_task_progress",
        "personal_os_process_pending_notes",
    }
