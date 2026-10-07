"""Todoist task store adapter."""

from datetime import date, datetime
from typing import Any

import httpx

from personal_os.ports.tasks import TaskDraft, TaskRecord


class TodoistError(RuntimeError):
    """Raised when Todoist cannot complete a task operation."""


class TodoistTaskStore:
    """Read progress and publish user-approved next actions to Todoist."""

    def __init__(self, token: str, *, client: httpx.AsyncClient | None = None) -> None:
        self._owner = client is None
        self._client = client or httpx.AsyncClient(
            base_url="https://api.todoist.com/api/v1", timeout=30
        )
        self._client.headers.update({"Authorization": f"Bearer {token}"})

    async def list_active(self, project_id: str) -> tuple[TaskRecord, ...]:
        return tuple(
            _task(item)
            for item in await self._get_all(
                "/tasks", params={"project_id": project_id, "limit": 200}, key="results"
            )
        )

    async def list_completed(
        self, project_id: str, since: datetime, until: datetime
    ) -> tuple[TaskRecord, ...]:
        params = {
            "project_id": project_id,
            "since": _iso_z(since),
            "until": _iso_z(until),
            "limit": 200,
        }
        return tuple(
            _task(item)
            for item in await self._get_all(
                "/tasks/completed/by_completion_date", params=params, key="items"
            )
        )

    async def create_task(self, project_id: str, draft: TaskDraft) -> TaskRecord:
        payload: dict[str, Any] = {
            "content": draft.content,
            "description": draft.description,
            "project_id": project_id,
            "labels": list(draft.labels),
        }
        if draft.due_date is not None:
            payload["due_date"] = draft.due_date.isoformat()
        try:
            response = await self._client.post("/tasks", json=payload)
            response.raise_for_status()
            return _task(response.json())
        except Exception as exc:
            raise TodoistError("Could not create Todoist task") from exc

    async def _get_all(
        self, path: str, *, params: dict[str, Any], key: str
    ) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        cursor: str | None = None
        try:
            while True:
                page_params = dict(params)
                if cursor:
                    page_params["cursor"] = cursor
                response = await self._client.get(path, params=page_params)
                response.raise_for_status()
                body = response.json()
                results.extend(body.get(key, []))
                cursor = body.get("next_cursor")
                if not cursor:
                    return results
        except Exception as exc:
            raise TodoistError(f"Could not read Todoist endpoint {path}") from exc

    async def close(self) -> None:
        if self._owner:
            await self._client.aclose()


def _task(value: dict[str, Any]) -> TaskRecord:
    due = value.get("due") or {}
    due_value = due.get("date")
    created = value.get("added_at") or value.get("created_at")
    completed = value.get("completed_at")
    return TaskRecord(
        id=str(value["id"]),
        content=value["content"],
        project_id=str(value["project_id"]),
        description=value.get("description") or "",
        due_date=date.fromisoformat(due_value[:10]) if due_value else None,
        created_at=datetime.fromisoformat(created.replace("Z", "+00:00"))
        if created
        else None,
        completed_at=datetime.fromisoformat(completed.replace("Z", "+00:00"))
        if completed
        else None,
    )


def _iso_z(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")
