"""Vertex AI implementation of structured multimodal generation."""

from typing import Any

from google import genai
from google.genai import types

from personal_os.ports.llm import (
    ResponseT,
    StructuredGenerationRequest,
)


class StructuredGenerationError(RuntimeError):
    """Raised when a provider returns no usable structured response."""


class VertexStructuredLLM:
    """Generate validated domain models through Vertex AI."""

    def __init__(
        self,
        project_id: str,
        location: str,
        model: str,
        *,
        client: Any | None = None,
    ) -> None:
        self._model = model
        self._owner = None
        if client is not None:
            self._client = client
        else:
            self._owner = genai.Client(
                vertexai=True,
                project=project_id,
                location=location,
                http_options=types.HttpOptions(api_version="v1"),
            )
            self._client = self._owner.aio

    async def generate_structured(
        self,
        request: StructuredGenerationRequest,
        response_model: type[ResponseT],
    ) -> ResponseT:
        contents = [types.Part.from_text(text=request.prompt)]
        contents.extend(
            types.Part.from_uri(file_uri=image.uri, mime_type=image.media_type)
            for image in request.images
        )

        try:
            response = await self._client.models.generate_content(
                model=self._model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_model,
                ),
            )

            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, response_model):
                return parsed
            if parsed is not None:
                return response_model.model_validate(parsed)

            text = getattr(response, "text", None)
            if text:
                return response_model.model_validate_json(text)
        except StructuredGenerationError:
            raise
        except Exception as exc:
            raise StructuredGenerationError(
                "Vertex AI structured generation failed"
            ) from exc

        raise StructuredGenerationError("Vertex AI returned no structured content")

    async def close(self) -> None:
        """Release the SDK client's network resources when supported."""

        close = getattr(self._client, "aclose", None)
        if close is not None:
            await close()
        if self._owner is not None:
            self._owner.close()
