import asyncio
import json
from datetime import UTC, date, datetime

import httpx
import pytest

from personal_os.ports.tasks import TaskDraft
from personal_os.providers.todoist import TodoistError, TodoistTaskStore


def _task(task_id: str, *, completed_at: str | None = None) -> dict:
    return {
        "id": task_id,
        "content": f"Task {task_id}",
        "description": "Small next action",
        "project_id": "project-1",
        "due": {"date": "2026-10-07"},
        "added_at": "2026-10-01T08:00:00Z",
        "completed_at": completed_at,
    }


def test_list_active_tasks_follows_cursor_pagination() -> None:
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if "cursor=next" in str(request.url):
            return httpx.Response(200, json={"results": [_task("2")], "next_cursor": None})
        return httpx.Response(200, json={"results": [_task("1")], "next_cursor": "next"})

    tasks = asyncio.run(_list_active(handler))

    assert [task.id for task in tasks] == ["1", "2"]
    assert requests[0].headers["Authorization"] == "Bearer token"
    assert "project_id=project-1" in str(requests[0].url)


def test_list_completed_normalizes_completion_time() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"items": [_task("1", completed_at="2026-10-06T09:30:00Z")]},
        )

    async def run():
        client = _client(handler)
        store = TodoistTaskStore("token", client=client)
        result = await store.list_completed(
            "project-1",
            datetime(2026, 10, 1, tzinfo=UTC),
            datetime(2026, 10, 7, tzinfo=UTC),
        )
        await client.aclose()
        return result

    task = asyncio.run(run())[0]
    assert task.created_at == datetime(2026, 10, 1, 8, tzinfo=UTC)
    assert task.completed_at == datetime(2026, 10, 6, 9, 30, tzinfo=UTC)


def test_create_task_sends_only_supported_fields() -> None:
    captured = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_task("new"))

    async def run():
        client = _client(handler)
        store = TodoistTaskStore("token", client=client)
        result = await store.create_task(
            "project-1",
            TaskDraft("Task new", due_date=date(2026, 10, 7), labels=("personal-os",)),
        )
        await client.aclose()
        return result

    assert asyncio.run(run()).id == "new"
    assert captured[0]["due_date"] == "2026-10-07"
    assert captured[0]["labels"] == ["personal-os"]


def test_todoist_errors_are_translated() -> None:
    async def run():
        client = _client(lambda _: httpx.Response(401))
        store = TodoistTaskStore("bad", client=client)
        with pytest.raises(TodoistError):
            await store.list_active("project-1")
        await client.aclose()

    asyncio.run(run())


async def _list_active(handler):
    client = _client(handler)
    store = TodoistTaskStore("token", client=client)
    result = await store.list_active("project-1")
    await client.aclose()
    return result


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.todoist.com/api/v1",
    )
