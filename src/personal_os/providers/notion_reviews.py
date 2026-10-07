"""Notion-backed versioned execution-review drafts."""

import asyncio
from datetime import datetime
from typing import Any

import httpx

from personal_os.ports.memory import MemoryRecordRef
from personal_os.ports.reviews import ExecutionReviewSnapshot
from personal_os.providers.notion import NOTION_API_VERSION


REVIEW_PROPERTIES: dict[str, dict[str, Any]] = {
    "Review Key": {"rich_text": {}},
    "Window Start": {"date": {}},
    "Window End": {"date": {}},
    "Assessment": {"select": {}},
    "Active Tasks": {"number": {}},
    "Completed Tasks": {"number": {}},
    "Observed Weekly Completion": {"number": {}},
    "Overdue Tasks": {"number": {}},
    "Rollover Tasks": {"number": {}},
    "GitHub Events": {"number": {}},
}


class NotionReviewStoreError(RuntimeError):
    """Raised when execution-review history cannot be read or written."""


class NotionReviewStore:
    """Upsert one draft per review window and retain comparable metrics."""

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

    async def upsert_draft(
        self, review: ExecutionReviewSnapshot
    ) -> MemoryRecordRef:
        await self._ensure_schema()
        existing = await self._find(review.review_key)
        properties = _properties(review)
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
            raise NotionReviewStoreError("Could not save execution-review draft") from exc

    async def list_recent(
        self, limit: int = 4
    ) -> tuple[ExecutionReviewSnapshot, ...]:
        if not 1 <= limit <= 20:
            raise ValueError("limit must be between 1 and 20")
        await self._ensure_schema()
        try:
            response = await self._request(
                "POST",
                f"/data_sources/{self._data_source_id}/query",
                json={
                    "filter": {
                        "property": "Review Key",
                        "rich_text": {"is_not_empty": True},
                    },
                    "sorts": [{"property": "Window End", "direction": "descending"}],
                    "page_size": limit,
                },
            )
            return tuple(_snapshot(item) for item in response.json().get("results", []))
        except Exception as exc:
            raise NotionReviewStoreError("Could not read execution-review history") from exc

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            response = await self._request(
                "GET", f"/data_sources/{self._data_source_id}"
            )
            current = response.json().get("properties", {})
            missing = {
                name: schema
                for name, schema in REVIEW_PROPERTIES.items()
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
            raise NotionReviewStoreError(
                "Could not verify execution-review schema"
            ) from exc

    async def _find(self, review_key: str) -> dict[str, Any] | None:
        response = await self._request(
            "POST",
            f"/data_sources/{self._data_source_id}/query",
            json={
                "filter": {
                    "property": "Review Key",
                    "rich_text": {"equals": review_key},
                },
                "page_size": 2,
            },
        )
        results = response.json().get("results", [])
        if len(results) > 1:
            raise NotionReviewStoreError(
                f"Duplicate execution reviews found for {review_key}"
            )
        return results[0] if results else None

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


def _properties(review: ExecutionReviewSnapshot) -> dict[str, Any]:
    return {
        "Name": _title(f"Execution review — {review.window_end.date().isoformat()}"),
        "Week Start": {"date": {"start": review.window_start.date().isoformat()}},
        "Status": {"select": {"name": "Draft"}},
        "Summary": _rich_text(review.summary),
        "Review Key": _rich_text(review.review_key),
        "Window Start": {"date": {"start": review.window_start.isoformat()}},
        "Window End": {"date": {"start": review.window_end.isoformat()}},
        "Assessment": {"select": {"name": review.assessment.title()}},
        "Active Tasks": {"number": review.active_tasks},
        "Completed Tasks": {"number": review.completed_tasks},
        "Observed Weekly Completion": {
            "number": review.observed_completions_per_week
        },
        "Overdue Tasks": {"number": review.overdue_tasks},
        "Rollover Tasks": {"number": review.rollover_tasks},
        "GitHub Events": {"number": review.github_events},
    }


def _snapshot(page: dict[str, Any]) -> ExecutionReviewSnapshot:
    properties = page["properties"]
    return ExecutionReviewSnapshot(
        review_key=_text(properties["Review Key"]),
        window_start=_date(properties["Window Start"]),
        window_end=_date(properties["Window End"]),
        assessment=(_select(properties["Assessment"]) or "unknown").lower(),
        active_tasks=_number(properties["Active Tasks"]),
        completed_tasks=_number(properties["Completed Tasks"]),
        observed_completions_per_week=float(
            properties["Observed Weekly Completion"].get("number") or 0
        ),
        overdue_tasks=_number(properties["Overdue Tasks"]),
        rollover_tasks=_number(properties["Rollover Tasks"]),
        github_events=_number(properties["GitHub Events"]),
        summary=_text(properties["Summary"]),
    )


def _title(value: str) -> dict[str, Any]:
    return {"title": [{"type": "text", "text": {"content": value[:2000]}}]}


def _rich_text(value: str) -> dict[str, Any]:
    return {
        "rich_text": [{"type": "text", "text": {"content": value[:2000]}}]
        if value
        else []
    }


def _text(value: dict[str, Any]) -> str:
    content = value.get("rich_text") or value.get("title") or []
    return "".join(item.get("plain_text", "") for item in content)


def _date(value: dict[str, Any]) -> datetime:
    return datetime.fromisoformat(value["date"]["start"].replace("Z", "+00:00"))


def _select(value: dict[str, Any]) -> str | None:
    selected = value.get("select")
    return selected.get("name") if selected else None


def _number(value: dict[str, Any]) -> int:
    return int(value.get("number") or 0)
