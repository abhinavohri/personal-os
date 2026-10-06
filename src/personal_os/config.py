"""Validated non-secret configuration and runtime secrets."""

from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class GCPConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    project_id: str = Field(min_length=1)
    region: str = Field(min_length=1)
    paper_notes_bucket: str = Field(min_length=1)


class VertexConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    location: str = Field(min_length=1)
    routine_model: str = Field(min_length=1)
    deep_reasoning_model: str = Field(min_length=1)


class NotionConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    root_page_id: str = Field(min_length=1)
    agent_brief_page_id: str = Field(min_length=1)
    profile_page_id: str = Field(min_length=1)
    spine_page_id: str = Field(min_length=1)
    interests_and_lanes_page_id: str = Field(min_length=1)
    current_week_page_id: str = Field(min_length=1)
    archive_page_id: str = Field(min_length=1)
    notes_inbox_data_source_id: str = Field(min_length=1)
    roadmap_data_source_id: str = Field(min_length=1)
    resources_data_source_id: str = Field(min_length=1)
    repository_catalog_data_source_id: str = Field(min_length=1)
    decisions_data_source_id: str = Field(min_length=1)
    weekly_reviews_data_source_id: str = Field(min_length=1)
    notes_title_property: str = "Name"


class TodoistConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    project_id: str = Field(min_length=1)


class GitHubConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    username: str = Field(min_length=1)
    allowed_repositories: tuple[str, ...]


class WebSearchConfig(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    provider: str = "vertex_google_search"
    model: str = Field(min_length=1)


class PersonalOSConfig(BaseModel):
    """The provider settings required to construct the adapter suite."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    gcp: GCPConfig
    vertex: VertexConfig
    notion: NotionConfig
    todoist: TodoistConfig
    github: GitHubConfig
    web_search: WebSearchConfig

    @classmethod
    def from_yaml(cls, path: str | Path) -> "PersonalOSConfig":
        with Path(path).open(encoding="utf-8") as handle:
            value = yaml.safe_load(handle)
        return cls.model_validate(value)


class RuntimeSecrets(BaseModel):
    """Secrets loaded from the process environment, never from committed YAML."""

    model_config = ConfigDict(extra="ignore", frozen=True)

    notion_token: str = Field(min_length=1)
    todoist_api_token: str = Field(min_length=1)
    github_token: str = Field(min_length=1)

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> "RuntimeSecrets":
        return cls(
            notion_token=environment.get("NOTION_TOKEN", ""),
            todoist_api_token=environment.get("TODOIST_API_TOKEN", ""),
            github_token=environment.get("GITHUB_TOKEN", ""),
        )
