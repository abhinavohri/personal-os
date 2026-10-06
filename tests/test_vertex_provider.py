import asyncio
from types import SimpleNamespace

import pytest

from personal_os.domain.notes import ExtractedNote
from personal_os.ports.llm import ImageInput, StructuredGenerationRequest
from personal_os.providers.vertex import (
    StructuredGenerationError,
    VertexStructuredLLM,
)


VALID_NOTE = {
    "source_object": "gs://paper-notes/inbox/page.jpg",
    "transcription": "A note",
    "summary": "Summary",
    "confidence": 0.95,
    "tasks": [],
    "insights": [],
    "questions": [],
    "resources": [],
    "uncertainties": [],
}


class FakeModels:
    def __init__(self, response, error=None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response) -> None:
        self.models = FakeModels(response)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def build_provider(response):
    client = FakeClient(response)
    provider = VertexStructuredLLM(
        project_id="project",
        location="us-central1",
        model="gemini-test",
        client=client,
    )
    return provider, client


def test_vertex_adapter_builds_multimodal_structured_request() -> None:
    provider, client = build_provider(SimpleNamespace(parsed=VALID_NOTE, text=None))
    request = StructuredGenerationRequest(
        prompt="Extract the note",
        images=(ImageInput("gs://paper-notes/inbox/page.jpg", "image/jpeg"),),
    )

    result = asyncio.run(provider.generate_structured(request, ExtractedNote))

    assert isinstance(result, ExtractedNote)
    call = client.models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["contents"][0].text == "Extract the note"
    assert call["contents"][1].file_data.file_uri == request.images[0].uri
    assert call["config"].response_mime_type == "application/json"
    assert call["config"].response_schema is ExtractedNote


def test_vertex_adapter_falls_back_to_json_text() -> None:
    response = SimpleNamespace(parsed=None, text=ExtractedNote(**VALID_NOTE).model_dump_json())
    provider, _ = build_provider(response)

    result = asyncio.run(
        provider.generate_structured(StructuredGenerationRequest("Extract"), ExtractedNote)
    )

    assert result.summary == "Summary"


def test_vertex_adapter_rejects_empty_response() -> None:
    provider, _ = build_provider(SimpleNamespace(parsed=None, text=None))

    with pytest.raises(StructuredGenerationError):
        asyncio.run(
            provider.generate_structured(
                StructuredGenerationRequest("Extract"), ExtractedNote
            )
        )


def test_vertex_adapter_translates_sdk_errors() -> None:
    client = FakeClient(SimpleNamespace(parsed=None, text=None))
    client.models.error = TimeoutError("provider timeout")
    provider = VertexStructuredLLM(
        project_id="project",
        location="us-central1",
        model="gemini-test",
        client=client,
    )

    with pytest.raises(StructuredGenerationError) as error:
        asyncio.run(
            provider.generate_structured(
                StructuredGenerationRequest("Extract"), ExtractedNote
            )
        )

    assert isinstance(error.value.__cause__, TimeoutError)


def test_vertex_adapter_closes_client() -> None:
    provider, client = build_provider(SimpleNamespace(parsed=VALID_NOTE, text=None))

    asyncio.run(provider.close())

    assert client.closed
