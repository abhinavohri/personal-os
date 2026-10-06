"""Grounded Google Search through Vertex AI."""

from typing import Any

from google import genai
from google.genai import types

from personal_os.ports.search import SearchResponse, SearchSource


class WebSearchError(RuntimeError):
    """Raised when grounded web research produces no usable answer."""


class VertexGoogleSearch:
    """Use Gemini's Google Search tool and return normalized citations."""

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

    async def search(self, query: str, *, max_sources: int = 8) -> SearchResponse:
        if max_sources < 1:
            raise ValueError("max_sources must be at least 1")
        prompt = (
            "Research the following question using Google Search. Give a concise, "
            "evidence-based answer and prefer primary sources.\n\n"
            f"Question: {query}"
        )
        try:
            response = await self._client.models.generate_content(
                model=self._model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=[types.Tool(google_search=types.GoogleSearch())]
                ),
            )
            answer = getattr(response, "text", None)
            if not answer:
                raise WebSearchError("Vertex AI returned no grounded answer")
            metadata = _grounding_metadata(response)
            return SearchResponse(
                answer=answer,
                sources=_sources(metadata, max_sources),
                queries=tuple(getattr(metadata, "web_search_queries", None) or ()),
            )
        except WebSearchError:
            raise
        except Exception as exc:
            raise WebSearchError("Vertex AI web search failed") from exc

    async def close(self) -> None:
        close = getattr(self._client, "aclose", None)
        if close is not None:
            await close()
        if self._owner is not None:
            self._owner.close()


def _grounding_metadata(response: Any) -> Any:
    candidates = getattr(response, "candidates", None) or ()
    if not candidates:
        return None
    return getattr(candidates[0], "grounding_metadata", None)


def _sources(metadata: Any, limit: int) -> tuple[SearchSource, ...]:
    chunks = getattr(metadata, "grounding_chunks", None) or ()
    sources: list[SearchSource] = []
    seen: set[str] = set()
    for chunk in chunks:
        web = getattr(chunk, "web", None)
        url = getattr(web, "uri", None) if web is not None else None
        if not url or url in seen:
            continue
        seen.add(url)
        sources.append(
            SearchSource(
                title=getattr(web, "title", None) or url,
                url=url,
                domain=getattr(web, "domain", None),
            )
        )
        if len(sources) == limit:
            break
    return tuple(sources)
