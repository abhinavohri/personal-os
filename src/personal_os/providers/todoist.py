"""Todoist task store adapter."""

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid5

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

    async def create_tasks_idempotent(
        self,
        project_id: str,
        proposal_key: str,
        drafts: tuple[TaskDraft, ...],
    ) -> tuple[str, ...]:
        """Create a proposal batch once using stable Sync API command UUIDs."""
        if not drafts:
            raise ValueError("at least one task draft is required")

        active = await self.list_active(project_id)
        existing = {
            marker: task.id
            for task in active
            for marker in (_proposal_marker_from(task.description),)
            if marker is not None
        }
        task_ids: list[str | None] = [None] * len(drafts)
        commands: list[dict[str, Any]] = []
        temp_ids: dict[str, int] = {}
        for index, draft in enumerate(drafts):
            marker = _proposal_marker(proposal_key, index)
            if marker in existing:
                task_ids[index] = existing[marker]
                continue
            command_id = str(uuid5(_IDEMPOTENCY_NAMESPACE, f"command:{marker}"))
            temp_id = str(uuid5(_IDEMPOTENCY_NAMESPACE, f"temporary:{marker}"))
            args: dict[str, Any] = {
                "content": draft.content,
                "description": _description_with_marker(draft.description, marker),
                "project_id": project_id,
                "labels": list(draft.labels),
            }
            if draft.due_date is not None:
                args["due"] = {"date": draft.due_date.isoformat()}
            commands.append(
                {
                    "type": "item_add",
                    "uuid": command_id,
                    "temp_id": temp_id,
                    "args": args,
                }
            )
            temp_ids[temp_id] = index

        if commands:
            try:
                response = await self._client.post(
                    "/sync", data={"commands": json.dumps(commands)}
                )
                response.raise_for_status()
                body = response.json()
                statuses = body.get("sync_status", {})
                failures = {
                    command["uuid"]: statuses.get(command["uuid"])
                    for command in commands
                    if statuses.get(command["uuid"]) != "ok"
                }
                if failures:
                    raise TodoistError(f"Todoist rejected plan commands: {failures}")
                for temp_id, task_id in body.get("temp_id_mapping", {}).items():
                    if temp_id in temp_ids:
                        task_ids[temp_ids[temp_id]] = str(task_id)
            except TodoistError:
                raise
            except Exception as exc:
                raise TodoistError("Could not publish Todoist plan") from exc

        if any(task_id is None for task_id in task_ids):
            raise TodoistError("Todoist did not return every published task ID")
        return tuple(str(task_id) for task_id in task_ids)

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


_IDEMPOTENCY_NAMESPACE = UUID("97fb33ca-3cca-4eef-8b86-e40b7952839e")
_MARKER_PREFIX = "personal-os-proposal:"


def _proposal_marker(proposal_key: str, index: int) -> str:
    return f"{_MARKER_PREFIX}{proposal_key}:{index}"


def _description_with_marker(description: str, marker: str) -> str:
    prefix = description.strip()
    return f"{prefix}\n\n[{marker}]" if prefix else f"[{marker}]"


def _proposal_marker_from(description: str) -> str | None:
    for line in reversed(description.splitlines()):
        stripped = line.strip()
        if stripped.startswith(f"[{_MARKER_PREFIX}") and stripped.endswith("]"):
            return stripped[1:-1]
    return None
