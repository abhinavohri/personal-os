"""Notion adapter for a deduplicated mixed-resource inbox."""

import asyncio
from datetime import UTC, datetime
from typing import Any

import httpx

from personal_os.domain.resources import (
    ResourceCapture,
    ResourceRecord,
    ResourceStatus,
    resource_key,
)
from personal_os.providers.notion import NOTION_API_VERSION


RESOURCE_PROPERTIES: dict[str, dict[str, Any]] = {
    "Resource Key": {"rich_text": {}},
    "Notes": {"rich_text": {}},
    "Tags": {"multi_select": {}},
    "Source": {"select": {}},
    "Added At": {"date": {}},
}


class NotionResourceInboxError(RuntimeError):
    """Raised when the resource inbox cannot be safely read or written."""


class NotionResourceInbox:
    def __init__(
        self,
        token: str,
        data_source_id: str,
        *,
        client: httpx.AsyncClient | None = None,
        clock=None,
    ) -> None:
        self._data_source_id = data_source_id
        self._schema_ready = False
        self._owner = client is None
        self._clock = clock or (lambda: datetime.now(UTC))
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

    async def upsert_many(
        self,
        resources: tuple[ResourceCapture, ...],
        *,
        replace_tags: bool = False,
    ) -> tuple[ResourceRecord, ...]:
        if not 1 <= len(resources) <= 25:
            raise ValueError("resources must contain between 1 and 25 items")
        await self._ensure_schema()
        keyed = {resource_key(resource): resource for resource in resources}
        existing = await self._find_many(tuple(keyed))
        records: list[ResourceRecord] = []
        try:
            for key, resource in keyed.items():
                page = existing.get(key)
                current = _record(page) if page else None
                merged = resource.model_copy(
                    update={
                        "url": resource.url or (current.url if current else None),
                        "notes": resource.notes or (current.notes if current else ""),
                        "tags": (
                            resource.tags
                            if replace_tags
                            else tuple(
                                dict.fromkeys(
                                    (*((current.tags if current else ())), *resource.tags)
                                )
                            )[:10]
                        ),
                    }
                )
                properties = _properties(
                    merged,
                    key,
                    (current.added_at if current else None) or self._clock(),
                    status=current.status if current else "Inbox",
                )
                if page:
                    response = await self._request(
                        "PATCH",
                        f"/pages/{page['id']}",
                        json={"properties": properties},
                    )
                else:
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
                records.append(_record(response.json()))
            return tuple(records)
        except Exception as exc:
            raise NotionResourceInboxError("Could not save resource inbox") from exc

    async def list_inbox(self, limit: int = 100) -> tuple[ResourceRecord, ...]:
        return await self.list_by_status("Inbox", limit)

    async def list_by_status(
        self,
        status: ResourceStatus,
        limit: int = 100,
    ) -> tuple[ResourceRecord, ...]:
        if not 1 <= limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        await self._ensure_schema()
        try:
            results: list[dict[str, Any]] = []
            cursor: str | None = None
            while len(results) < limit:
                body: dict[str, Any] = {
                    "filter": {"property": "Status", "select": {"equals": status}},
                    "sorts": [{"property": "Added At", "direction": "descending"}],
                    "page_size": min(100, limit - len(results)),
                }
                if cursor:
                    body["start_cursor"] = cursor
                response = await self._request(
                    "POST",
                    f"/data_sources/{self._data_source_id}/query",
                    json=body,
                )
                page = response.json()
                results.extend(page.get("results", []))
                cursor = page.get("next_cursor")
                if not cursor:
                    break
            return tuple(_record(page) for page in results[:limit])
        except Exception as exc:
            raise NotionResourceInboxError("Could not read resource inbox") from exc

    async def set_status(
        self,
        resource_keys: tuple[str, ...],
        status: ResourceStatus,
    ) -> tuple[ResourceRecord, ...]:
        if not 1 <= len(resource_keys) <= 25:
            raise ValueError("resource_keys must contain between 1 and 25 items")
        if len(set(resource_keys)) != len(resource_keys):
            raise ValueError("resource_keys must not contain duplicates")
        await self._ensure_schema()
        pages = await self._find_many(resource_keys)
        missing = [key for key in resource_keys if key not in pages]
        if missing:
            raise NotionResourceInboxError(
                f"Unknown resource keys: {', '.join(missing)}"
            )
        records: list[ResourceRecord] = []
        try:
            for key in resource_keys:
                response = await self._request(
                    "PATCH",
                    f"/pages/{pages[key]['id']}",
                    json={"properties": {"Status": {"select": {"name": status}}}},
                )
                records.append(_record(response.json()))
            return tuple(records)
        except Exception as exc:
            raise NotionResourceInboxError("Could not update resource status") from exc

    async def _find_many(self, keys: tuple[str, ...]) -> dict[str, dict[str, Any]]:
        filters = [
            {"property": "Resource Key", "rich_text": {"equals": key}}
            for key in keys
        ]
        response = await self._request(
            "POST",
            f"/data_sources/{self._data_source_id}/query",
            json={
                "filter": filters[0] if len(filters) == 1 else {"or": filters},
                "page_size": 100,
            },
        )
        result: dict[str, dict[str, Any]] = {}
        for page in response.json().get("results", []):
            key = _text(page["properties"]["Resource Key"])
            if key in result:
                raise NotionResourceInboxError(f"Duplicate resources found for {key}")
            result[key] = page
        return result

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            response = await self._request("GET", f"/data_sources/{self._data_source_id}")
            current = response.json().get("properties", {})
            missing = {
                name: schema
                for name, schema in RESOURCE_PROPERTIES.items()
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
            raise NotionResourceInboxError("Could not verify resource schema") from exc

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


def _properties(
    resource: ResourceCapture,
    key: str,
    added_at: datetime,
    *,
    status: str | None,
) -> dict[str, Any]:
    return {
        "Name": _title(resource.title),
        "URL": {"url": resource.url},
        "Type": {"select": {"name": resource.resource_type}},
        "Status": {"select": {"name": status or "Inbox"}},
        "Resource Key": _rich_text(key),
        "Notes": _rich_text(resource.notes),
        "Tags": {
            "multi_select": [{"name": tag[:100]} for tag in resource.tags]
        },
        "Source": {"select": {"name": resource.source}},
        "Added At": {"date": {"start": added_at.isoformat()}},
    }


def _record(page: dict[str, Any]) -> ResourceRecord:
    properties = page["properties"]
    date_value = properties["Added At"].get("date")
    return ResourceRecord(
        title=_text(properties["Name"]),
        resource_type=_select(properties["Type"]) or "other",
        url=properties["URL"].get("url"),
        notes=_text(properties["Notes"]),
        tags=tuple(
            item["name"] for item in properties["Tags"].get("multi_select", [])
        ),
        source=_select(properties["Source"]) or "manual",
        resource_key=_text(properties["Resource Key"]),
        status=_select(properties["Status"]) or "Inbox",
        notion_page_id=page["id"],
        notion_url=page.get("url"),
        added_at=(
            datetime.fromisoformat(date_value["start"].replace("Z", "+00:00"))
            if date_value
            else None
        ),
    )


def _title(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def _rich_text(value: str) -> dict[str, Any]:
    return {
        "rich_text": [{"type": "text", "text": {"content": value[:2000]}}]
        if value
        else []
    }


def _text(property_value: dict[str, Any]) -> str:
    values = property_value.get("rich_text") or property_value.get("title") or []
    return "".join(
        item.get("plain_text") or item.get("text", {}).get("content", "")
        for item in values
    )


def _select(property_value: dict[str, Any]) -> str | None:
    selected = property_value.get("select")
    return selected.get("name") if selected else None
