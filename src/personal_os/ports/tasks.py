"""Provider-neutral task system contracts."""

from dataclasses import dataclass
from datetime import date, datetime
from typing import Protocol


@dataclass(frozen=True)
class TaskDraft:
    content: str
    description: str = ""
    due_date: date | None = None
    labels: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskRecord:
    id: str
    content: str
    project_id: str
    description: str = ""
    due_date: date | None = None
    completed_at: datetime | None = None


class TaskStore(Protocol):
    async def list_active(self, project_id: str) -> tuple[TaskRecord, ...]: ...

    async def list_completed(
        self, project_id: str, since: datetime, until: datetime
    ) -> tuple[TaskRecord, ...]: ...

    async def create_task(self, project_id: str, draft: TaskDraft) -> TaskRecord: ...
