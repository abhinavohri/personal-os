import asyncio
import json
from datetime import UTC, date, datetime

import httpx
import pytest

from personal_os.domain.plans import PlanActionInput, PlanProposal
from personal_os.providers.notion_plans import NotionPlanStore, NotionPlanStoreError


PROPOSAL = PlanProposal(
    proposal_key="daily:2026-10-07",
    plan_date=date(2026, 10, 7),
    cadence="daily",
    rationale="Keep the load small.",
    actions=(
        PlanActionInput(
            content="Review the repository",
            description="Identify one bounded improvement.",
            due_date=date(2026, 10, 7),
            labels=("personal-os",),
        ),
    ),
)


def test_plan_draft_is_created_then_read_as_latest() -> None:
    query_count = 0
    created: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal query_count
        path = request.url.path
        if request.method == "GET":
            return httpx.Response(200, json={"properties": _schema()})
        if request.method == "POST" and path.endswith("/query"):
            query_count += 1
            if query_count == 1:
                return httpx.Response(200, json={"results": []})
            return httpx.Response(200, json={"results": [_page()]})
        if request.method == "POST" and path == "/v1/pages":
            created.update(json.loads(request.content)["properties"])
            return httpx.Response(
                200, json={"id": "plan-page", "url": "https://notion.so/plan-page"}
            )
        raise AssertionError((request.method, path))

    async def run():
        client = _client(handler)
        store = NotionPlanStore("token", "plans", client=client)
        saved = await store.upsert_draft(PROPOSAL)
        latest = await store.latest_draft()
        await client.aclose()
        return saved, latest

    saved, latest = asyncio.run(run())
    assert saved.notion_page_id == "plan-page"
    assert saved.version == 1
    assert latest == PROPOSAL.model_copy(
        update={
            "notion_page_id": "plan-page",
            "notion_url": "https://notion.so/plan-page",
        }
    )
    assert created["Proposal Key"]["rich_text"][0]["text"]["content"] == PROPOSAL.proposal_key


def test_published_plan_cannot_be_overwritten() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"properties": _schema()})
        if request.method == "POST" and request.url.path.endswith("/query"):
            return httpx.Response(200, json={"results": [_page(status="Published")]})
        raise AssertionError((request.method, request.url.path))

    async def run():
        client = _client(handler)
        store = NotionPlanStore("token", "plans", client=client)
        with pytest.raises(NotionPlanStoreError, match="cannot be overwritten"):
            await store.upsert_draft(PROPOSAL)
        await client.aclose()

    asyncio.run(run())


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.notion.com/v1",
    )


def _schema() -> dict:
    return {
        "Name": {"title": {}},
        "Proposal Key": {"rich_text": {}},
        "Plan Date": {"date": {}},
        "Cadence": {"select": {}},
        "Status": {"select": {}},
        "Version": {"number": {}},
        "Rationale": {"rich_text": {}},
        "Actions JSON": {"rich_text": {}},
        "Todoist Task IDs": {"rich_text": {}},
        "Published At": {"date": {}},
    }


def _page(*, status: str = "Draft") -> dict:
    def rich_text(value: str):
        return {"rich_text": [{"plain_text": value}]}

    actions = json.dumps([action.model_dump(mode="json") for action in PROPOSAL.actions])
    return {
        "id": "plan-page",
        "url": "https://notion.so/plan-page",
        "properties": {
            "Proposal Key": rich_text(PROPOSAL.proposal_key),
            "Plan Date": {"date": {"start": PROPOSAL.plan_date.isoformat()}},
            "Cadence": {"select": {"name": "Daily"}},
            "Status": {"select": {"name": status}},
            "Version": {"number": 1},
            "Rationale": rich_text(PROPOSAL.rationale),
            "Actions JSON": rich_text(actions),
            "Todoist Task IDs": rich_text("[]"),
            "Published At": {
                "date": (
                    {"start": datetime(2026, 10, 7, 3, tzinfo=UTC).isoformat()}
                    if status == "Published"
                    else None
                )
            },
        },
    }
