"""Small composition root for concrete Personal OS adapters."""

from dataclasses import dataclass

from personal_os.config import PersonalOSConfig, RuntimeSecrets
from personal_os.providers.gcs import GCSObjectStore
from personal_os.providers.github import GitHubWorkEvidence
from personal_os.providers.notion import NotionMemory
from personal_os.providers.todoist import TodoistTaskStore
from personal_os.providers.vertex import VertexStructuredLLM
from personal_os.providers.vertex_search import VertexGoogleSearch


@dataclass(frozen=True)
class AdapterSuite:
    """Concrete adapters available to the eventual Hermes tool layer."""

    object_store: GCSObjectStore
    memory: NotionMemory
    tasks: TodoistTaskStore
    work_evidence: GitHubWorkEvidence
    llm: VertexStructuredLLM
    web_search: VertexGoogleSearch

    async def close(self) -> None:
        await self.memory.close()
        await self.tasks.close()
        await self.work_evidence.close()
        await self.llm.close()
        await self.web_search.close()


def build_adapters(config: PersonalOSConfig, secrets: RuntimeSecrets) -> AdapterSuite:
    """Build the default providers without hiding them behind a plugin framework."""

    if config.web_search.provider != "vertex_google_search":
        raise ValueError(f"Unsupported web search provider: {config.web_search.provider}")

    return AdapterSuite(
        object_store=GCSObjectStore(config.gcp.project_id),
        memory=NotionMemory(
            secrets.notion_token,
            config.notion.notes_inbox_data_source_id,
            title_property=config.notion.notes_title_property,
        ),
        tasks=TodoistTaskStore(secrets.todoist_api_token),
        work_evidence=GitHubWorkEvidence(
            secrets.github_token,
            config.github.username,
            config.github.allowed_repositories,
        ),
        llm=VertexStructuredLLM(
            config.gcp.project_id,
            config.vertex.location,
            config.vertex.routine_model,
        ),
        web_search=VertexGoogleSearch(
            config.gcp.project_id,
            config.vertex.location,
            config.web_search.model,
        ),
    )
