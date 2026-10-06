"""Provider-neutral evidence from software work."""

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


WorkEventKind = Literal["commit", "pull_request", "issue", "release"]


@dataclass(frozen=True)
class RepositorySnapshot:
    full_name: str
    url: str
    description: str | None
    primary_language: str | None
    topics: tuple[str, ...]
    is_private: bool
    default_branch: str


@dataclass(frozen=True)
class WorkEvent:
    kind: WorkEventKind
    repository: str
    title: str
    url: str
    occurred_at: datetime


class WorkEvidence(Protocol):
    async def get_repository(self, full_name: str) -> RepositorySnapshot: ...

    async def get_readme_text(self, full_name: str) -> str | None: ...

    async def recent_activity(
        self, full_name: str, since: datetime
    ) -> tuple[WorkEvent, ...]: ...
