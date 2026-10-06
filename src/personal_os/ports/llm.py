"""Minimal LLM boundary used by Personal OS services."""

from dataclasses import dataclass
from typing import Protocol, TypeVar

from pydantic import BaseModel


ResponseT = TypeVar("ResponseT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ImageInput:
    """A provider-neutral image reference."""

    uri: str
    media_type: str


@dataclass(frozen=True, slots=True)
class StructuredGenerationRequest:
    """Inputs required for structured multimodal generation."""

    prompt: str
    images: tuple[ImageInput, ...] = ()


class StructuredLLM(Protocol):
    """Capability implemented by Vertex AI or a future LLM provider."""

    async def generate_structured(
        self,
        request: StructuredGenerationRequest,
        response_model: type[ResponseT],
    ) -> ResponseT:
        """Generate and validate one structured response."""

        ...
