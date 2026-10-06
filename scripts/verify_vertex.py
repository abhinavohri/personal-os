"""Run small live checks against the configured Vertex AI models."""

import asyncio
from typing import Literal

from pydantic import BaseModel, ConfigDict

from personal_os.config import PersonalOSConfig
from personal_os.ports.llm import StructuredGenerationRequest
from personal_os.providers.vertex import VertexStructuredLLM
from personal_os.providers.vertex_search import VertexGoogleSearch


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["ok"]
    purpose: str


async def main() -> None:
    config = PersonalOSConfig.from_yaml("config/system.yaml")
    routine = VertexStructuredLLM(
        config.gcp.project_id,
        config.vertex.location,
        config.vertex.routine_model,
    )
    deep = VertexStructuredLLM(
        config.gcp.project_id,
        config.vertex.location,
        config.vertex.deep_reasoning_model,
    )
    search = VertexGoogleSearch(
        config.gcp.project_id,
        config.vertex.location,
        config.web_search.model,
    )
    try:
        routine_result = await routine.generate_structured(
            StructuredGenerationRequest(
                "Return status 'ok' and describe your purpose as routine Personal OS work."
            ),
            HealthResponse,
        )
        deep_result = await deep.generate_structured(
            StructuredGenerationRequest(
                "Return status 'ok' and describe your purpose as difficult planning and reasoning."
            ),
            HealthResponse,
        )
        search_result = await search.search(
            "What is the official Google Cloud model ID for Gemini 3.8 Flash?",
            max_sources=3,
        )
    finally:
        await routine.close()
        await deep.close()
        await search.close()

    print(f"routine: {routine_result.status} ({config.vertex.routine_model})")
    print(f"deep: {deep_result.status} ({config.vertex.deep_reasoning_model})")
    print(f"search: ok ({len(search_result.sources)} grounded sources)")


if __name__ == "__main__":
    asyncio.run(main())
