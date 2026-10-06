"""Notion-backed catalog for allowlisted source repositories."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from personal_os.ports.memory import MemoryRecordRef
from personal_os.ports.work_evidence import RepositorySnapshot
from personal_os.providers.notion import NOTION_API_VERSION


CATALOG_PROPERTIES: dict[str, dict[str, Any]] = {
    "Description": {"rich_text": {}},
    "Topics": {"multi_select": {}},
    "README Excerpt": {"rich_text": {}},
}


class NotionRepositoryCatalogError(RuntimeError):
    """Raised when the repository catalog cannot be synchronized."""


class NotionRepositoryCatalog:
    """Idempotently synchronize repository context into a Notion data source."""

    def __init__(
        self,
        token: str,
        data_source_id: str,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._data_source_id = data_source_id
        self._schema_ready = False
        self._owner = client is None
        self._client = client or httpx.AsyncClient(
            base_url="https://api.notion.com/v1", timeout=30
        )
        self._client.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json",
            }
        )

    async def upsert_repository(
        self,
        repository: RepositorySnapshot,
        readme_text: str | None,
        *,
        reviewed_at: datetime | None = None,
    ) -> MemoryRecordRef:
        await self._ensure_schema()
        existing = await self._find(repository.full_name)
        properties = _page_properties(
            repository,
            readme_text,
            reviewed_at or datetime.now(UTC),
        )
        try:
            if existing is None:
                response = await self._request(
                    "POST",
                    "/pages",
                    json={
                        "parent": {
                            "type": "data_source_id",
                            "data_source_id": self._data_source_id,
                        },
                        "properties": properties,
                    },
                )
            else:
                response = await self._request(
                    "PATCH",
                    f"/pages/{existing['id']}",
                    json={"properties": properties},
                )
            body = response.json()
            return MemoryRecordRef(id=body["id"], url=body.get("url"))
        except Exception as exc:
            raise NotionRepositoryCatalogError(
                f"Could not upsert repository {repository.full_name}"
            ) from exc

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            response = await self._request("GET", f"/data_sources/{self._data_source_id}")
            current = response.json().get("properties", {})
            missing = {
                name: schema
                for name, schema in CATALOG_PROPERTIES.items()
                if name not in current
            }
            if missing:
                await self._request(
                    "PATCH",
                    f"/data_sources/{self._data_source_id}",
                    json={"properties": missing},
                )
            self._schema_ready = True
        except Exception as exc:
            raise NotionRepositoryCatalogError(
                "Could not verify the Notion repository catalog schema"
            ) from exc

    async def _find(self, full_name: str) -> dict[str, Any] | None:
        try:
            response = await self._request(
                "POST",
                f"/data_sources/{self._data_source_id}/query",
                json={
                    "filter": {
                        "property": "Full Name",
                        "rich_text": {"equals": full_name},
                    },
                    "page_size": 2,
                },
            )
            results = response.json().get("results", [])
            if len(results) > 1:
                raise NotionRepositoryCatalogError(
                    f"Duplicate repository catalog rows found for {full_name}"
                )
            return results[0] if results else None
        except NotionRepositoryCatalogError:
            raise
        except Exception as exc:
            raise NotionRepositoryCatalogError(
                f"Could not query repository catalog for {full_name}"
            ) from exc

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        for attempt in range(4):
            response = await self._client.request(method, path, **kwargs)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            if attempt == 3:
                response.raise_for_status()
            await asyncio.sleep(float(response.headers.get("Retry-After", "1")))
        raise RuntimeError("Notion request retry loop ended unexpectedly")

    async def close(self) -> None:
        if self._owner:
            await self._client.aclose()


def _page_properties(
    repository: RepositorySnapshot,
    readme_text: str | None,
    reviewed_at: datetime,
) -> dict[str, Any]:
    return {
        "Name": _title(repository.full_name.rsplit("/", 1)[-1]),
        "Full Name": _rich_text(repository.full_name),
        "URL": {"url": repository.url},
        "Primary Language": {
            "select": {"name": repository.primary_language[:100]}
            if repository.primary_language
            else None
        },
        "Private": {"checkbox": repository.is_private},
        "Last Reviewed": {"date": {"start": reviewed_at.date().isoformat()}},
        "Description": _rich_text(repository.description or ""),
        "Topics": {
            "multi_select": [{"name": topic[:100]} for topic in repository.topics[:100]]
        },
        "README Excerpt": _rich_text((readme_text or "")[:2000]),
    }


def _title(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def _rich_text(value: str) -> dict[str, Any]:
    if not value:
        return {"rich_text": []}
    return {"rich_text": [{"type": "text", "text": {"content": value[:2000]}}]}
