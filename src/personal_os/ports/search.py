"""Provider-neutral web research contracts."""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchSource:
    title: str
    url: str
    domain: str | None = None


@dataclass(frozen=True)
class SearchResponse:
    answer: str
    sources: tuple[SearchSource, ...]
    queries: tuple[str, ...] = ()


class WebSearch(Protocol):
    async def search(self, query: str, *, max_sources: int = 8) -> SearchResponse: ...
