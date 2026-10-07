import asyncio
from datetime import UTC, datetime

import httpx

from personal_os.ports.reviews import ExecutionReviewSnapshot
from personal_os.providers.notion_reviews import NotionReviewStore


REVIEW = ExecutionReviewSnapshot(
    review_key="execution:2026-10-07:14",
    window_start=datetime(2026, 9, 23, 12, tzinfo=UTC),
    window_end=datetime(2026, 10, 7, 12, tzinfo=UTC),
    assessment="strained",
    active_tasks=3,
    completed_tasks=2,
    observed_completions_per_week=1.0,
    overdue_tasks=1,
    rollover_tasks=1,
    github_events=4,
    summary="Strained — execution evidence.",
)


def test_review_draft_creates_schema_and_page_then_reads_history() -> None:
    requests: list[httpx.Request] = []
    created_properties = {}

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        path = request.url.path
        if request.method == "GET" and path == "/v1/data_sources/reviews":
            return httpx.Response(
                200,
                json={
                    "properties": {
                        "Name": {"title": {}},
                        "Week Start": {"date": {}},
                        "Status": {"select": {}},
                        "Summary": {"rich_text": {}},
                    }
                },
            )
        if request.method == "PATCH" and path == "/v1/data_sources/reviews":
            return httpx.Response(200, json={})
        if request.method == "POST" and path == "/v1/data_sources/reviews/query":
            if len([item for item in requests if item.url.path == path]) == 1:
                return httpx.Response(200, json={"results": []})
            return httpx.Response(200, json={"results": [_page()]})
        if request.method == "POST" and path == "/v1/pages":
            import json

            created_properties.update(json.loads(request.content)["properties"])
            return httpx.Response(
                200,
                json={"id": "review-page", "url": "https://notion.so/review-page"},
            )
        raise AssertionError((request.method, path))

    async def run():
        client = _client(handler)
        store = NotionReviewStore("token", "reviews", client=client)
        record = await store.upsert_draft(REVIEW)
        history = await store.list_recent()
        await client.aclose()
        return record, history

    record, history = asyncio.run(run())
    assert record.id == "review-page"
    assert created_properties["Review Key"]["rich_text"][0]["text"]["content"] == REVIEW.review_key
    assert history == (REVIEW,)
    assert any(
        request.method == "PATCH" and request.url.path.endswith("/data_sources/reviews")
        for request in requests
    )


def test_existing_review_is_updated_instead_of_duplicated() -> None:
    methods: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        methods.append((request.method, request.url.path))
        path = request.url.path
        if request.method == "GET":
            return httpx.Response(200, json={"properties": _schema()})
        if request.method == "POST" and path.endswith("/query"):
            return httpx.Response(200, json={"results": [{"id": "existing"}]})
        if request.method == "PATCH" and path == "/v1/pages/existing":
            return httpx.Response(200, json={"id": "existing"})
        raise AssertionError((request.method, path))

    async def run():
        client = _client(handler)
        store = NotionReviewStore("token", "reviews", client=client)
        result = await store.upsert_draft(REVIEW)
        await client.aclose()
        return result

    assert asyncio.run(run()).id == "existing"
    assert ("POST", "/v1/pages") not in methods


def _client(handler) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.MockTransport(handler),
        base_url="https://api.notion.com/v1",
    )


def _schema() -> dict:
    return {
        "Name": {"title": {}},
        "Week Start": {"date": {}},
        "Status": {"select": {}},
        "Summary": {"rich_text": {}},
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


def _page() -> dict:
    def rich_text(value: str):
        return {"rich_text": [{"plain_text": value}]}

    return {
        "properties": {
            "Review Key": rich_text(REVIEW.review_key),
            "Window Start": {"date": {"start": REVIEW.window_start.isoformat()}},
            "Window End": {"date": {"start": REVIEW.window_end.isoformat()}},
            "Assessment": {"select": {"name": "Strained"}},
            "Active Tasks": {"number": REVIEW.active_tasks},
            "Completed Tasks": {"number": REVIEW.completed_tasks},
            "Observed Weekly Completion": {
                "number": REVIEW.observed_completions_per_week
            },
            "Overdue Tasks": {"number": REVIEW.overdue_tasks},
            "Rollover Tasks": {"number": REVIEW.rollover_tasks},
            "GitHub Events": {"number": REVIEW.github_events},
            "Summary": rich_text(REVIEW.summary),
        }
    }
