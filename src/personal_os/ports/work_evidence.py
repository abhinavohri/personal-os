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


@dataclass(frozen=True)
class DeveloperProfile:
    username: str
    url: str
    name: str | None
    bio: str | None
    company: str | None
    blog: str | None
    location: str | None
    followers: int
    following: int
    public_repositories: int


@dataclass(frozen=True)
class PortfolioRepository:
    full_name: str
    url: str
    description: str | None
    primary_language: str | None
    topics: tuple[str, ...]
    stars: int
    forks: int
    is_archived: bool
    is_fork: bool
    updated_at: datetime
    pushed_at: datetime | None
    is_pinned: bool


@dataclass(frozen=True)
class PortfolioSnapshot:
    profile: DeveloperProfile
    profile_readme: str | None
    repositories: tuple[PortfolioRepository, ...]


class WorkEvidence(Protocol):
    async def get_repository(self, full_name: str) -> RepositorySnapshot: ...

    async def get_readme_text(self, full_name: str) -> str | None: ...

    async def recent_activity(
        self, full_name: str, since: datetime
    ) -> tuple[WorkEvent, ...]: ...

    async def get_portfolio(self, limit: int = 30) -> PortfolioSnapshot: ...
