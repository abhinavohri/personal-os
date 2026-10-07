"""Provider-neutral models for the mixed resource inbox."""

import re
from datetime import datetime
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator


ResourceType = Literal[
    "book",
    "youtube_playlist",
    "website",
    "roadmap",
    "topic",
    "target_job",
    "course",
    "language",
    "bookmark",
    "social_post",
    "paper",
    "video",
    "other",
]
ResourceSource = Literal[
    "manual",
    "browser_bookmark",
    "twitter_bookmark",
    "paper_note",
    "web_research",
    "import",
]
ResourceStatus = Literal["Inbox", "Active", "Reference", "Finished", "Archived"]


class ResourceCapture(BaseModel):
    """One item captured without prematurely forcing it into a learning plan."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    title: str = Field(min_length=1, max_length=500)
    resource_type: ResourceType
    url: str | None = Field(default=None, max_length=2000)
    notes: str = Field(default="", max_length=1500)
    tags: tuple[str, ...] = Field(default=(), max_length=10)
    source: ResourceSource = "manual"

    @field_validator("title", "notes")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        normalized = value.strip()
        parts = urlsplit(normalized)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("url must be an absolute http or https URL")
        return normalized


class ResourceRecord(ResourceCapture):
    resource_key: str
    status: ResourceStatus = "Inbox"
    notion_page_id: str
    notion_url: str | None = None
    added_at: datetime | None = None


def resource_key(resource: ResourceCapture) -> str:
    """Build a stable key from a canonical URL or normalized type and title."""
    if resource.url:
        return f"url:{canonical_url(resource.url)}"
    normalized_title = re.sub(r"\s+", " ", resource.title.casefold()).strip()
    return f"title:{resource.resource_type}:{normalized_title}"[:2000]


def canonical_url(value: str) -> str:
    parts = urlsplit(value.strip())
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in {"ref", "source", "fbclid", "gclid"}
    ]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(
        (
            parts.scheme.casefold(),
            parts.netloc.casefold(),
            path,
            urlencode(sorted(query), doseq=True),
            "",
        )
    )
