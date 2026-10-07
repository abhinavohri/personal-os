"""Durable execution-review history used by the adaptive planner."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from personal_os.ports.memory import MemoryRecordRef


@dataclass(frozen=True)
class ExecutionReviewSnapshot:
    review_key: str
    window_start: datetime
    window_end: datetime
    assessment: str
    active_tasks: int
    completed_tasks: int
    observed_completions_per_week: float
    overdue_tasks: int
    rollover_tasks: int
    github_events: int
    summary: str


class ReviewStore(Protocol):
    async def upsert_draft(
        self, review: ExecutionReviewSnapshot
    ) -> MemoryRecordRef: ...

    async def list_recent(self, limit: int = 4) -> tuple[ExecutionReviewSnapshot, ...]: ...
