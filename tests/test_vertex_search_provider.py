import asyncio
from types import SimpleNamespace

import pytest

from personal_os.providers.vertex_search import VertexGoogleSearch, WebSearchError


class FakeModels:
    def __init__(self, response=None, error=None) -> None:
        self.response = response
        self.error = error
        self.calls = []

    async def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.response


class FakeClient:
    def __init__(self, response=None, error=None) -> None:
        self.models = FakeModels(response, error)
        self.closed = False

    async def aclose(self) -> None:
        self.closed = True


def _response():
    metadata = SimpleNamespace(
        web_search_queries=["current Vertex AI grounding"],
        grounding_chunks=[
            SimpleNamespace(
                web=SimpleNamespace(
                    title="Vertex AI docs",
                    uri="https://cloud.google.com/vertex-ai/docs",
                    domain="cloud.google.com",
                )
            ),
            SimpleNamespace(
                web=SimpleNamespace(
                    title="Duplicate",
                    uri="https://cloud.google.com/vertex-ai/docs",
                    domain="cloud.google.com",
                )
            ),
        ],
    )
    return SimpleNamespace(
        text="Vertex AI supports grounded search.",
        candidates=[SimpleNamespace(grounding_metadata=metadata)],
    )


def test_search_enables_google_search_and_normalizes_sources() -> None:
    client = FakeClient(_response())
    provider = VertexGoogleSearch("project", "us-central1", "gemini-test", client=client)

    result = asyncio.run(provider.search("Does grounding work?"))

    assert result.answer == "Vertex AI supports grounded search."
    assert len(result.sources) == 1
    assert result.sources[0].domain == "cloud.google.com"
    assert result.queries == ("current Vertex AI grounding",)
    call = client.models.calls[0]
    assert call["model"] == "gemini-test"
    assert call["config"].tools[0].google_search is not None


def test_search_rejects_empty_answer() -> None:
    client = FakeClient(SimpleNamespace(text=None, candidates=[]))
    provider = VertexGoogleSearch("project", "us-central1", "gemini-test", client=client)

    with pytest.raises(WebSearchError, match="no grounded answer"):
        asyncio.run(provider.search("Question"))


def test_search_translates_sdk_errors() -> None:
    client = FakeClient(error=TimeoutError("timeout"))
    provider = VertexGoogleSearch("project", "us-central1", "gemini-test", client=client)

    with pytest.raises(WebSearchError) as error:
        asyncio.run(provider.search("Question"))

    assert isinstance(error.value.__cause__, TimeoutError)


def test_search_closes_client() -> None:
    client = FakeClient(_response())
    provider = VertexGoogleSearch("project", "us-central1", "gemini-test", client=client)

    asyncio.run(provider.close())

    assert client.closed
