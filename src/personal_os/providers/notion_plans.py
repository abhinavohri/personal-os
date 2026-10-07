"""Notion-backed plan proposals with version and publication receipts."""

import asyncio
import json
from datetime import datetime
from typing import Any

import httpx

from personal_os.domain.plans import PlanActionInput, PlanProposal
from personal_os.providers.notion import NOTION_API_VERSION


PLAN_PROPERTIES: dict[str, dict[str, Any]] = {
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


class NotionPlanStoreError(RuntimeError):
    """Raised when a plan proposal cannot be read or written safely."""


class NotionPlanStore:
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

    async def upsert_draft(self, proposal: PlanProposal) -> PlanProposal:
        await self._ensure_schema()
        existing_page = await self._find_page(proposal.proposal_key)
        existing = _proposal(existing_page) if existing_page else None
        if existing and existing.status == "Published":
            raise NotionPlanStoreError("Published proposals cannot be overwritten")
        version = (existing.version + 1) if existing else 1
        saved = proposal.model_copy(update={"version": version, "status": "Draft"})
        properties = _properties(saved)
        try:
            if existing_page:
                response = await self._request(
                    "PATCH",
                    f"/pages/{existing_page['id']}",
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
            body = response.json()
            return saved.model_copy(
                update={
                    "notion_page_id": body["id"],
                    "notion_url": body.get("url"),
                }
            )
        except Exception as exc:
            raise NotionPlanStoreError("Could not save plan proposal") from exc

    async def get(self, proposal_key: str) -> PlanProposal | None:
        await self._ensure_schema()
        page = await self._find_page(proposal_key)
        return _proposal(page) if page else None

    async def latest_draft(self) -> PlanProposal | None:
        await self._ensure_schema()
        try:
            response = await self._request(
                "POST",
                f"/data_sources/{self._data_source_id}/query",
                json={
                    "filter": {"property": "Status", "select": {"equals": "Draft"}},
                    "sorts": [
                        {"property": "Plan Date", "direction": "descending"},
                        {"timestamp": "last_edited_time", "direction": "descending"},
                    ],
                    "page_size": 1,
                },
            )
            results = response.json().get("results", [])
            return _proposal(results[0]) if results else None
        except Exception as exc:
            raise NotionPlanStoreError("Could not read latest plan proposal") from exc

    async def mark_published(
        self,
        proposal_key: str,
        task_ids: tuple[str, ...],
        published_at: datetime,
    ) -> PlanProposal:
        await self._ensure_schema()
        page = await self._find_page(proposal_key)
        if page is None:
            raise NotionPlanStoreError(f"Unknown proposal: {proposal_key}")
        current = _proposal(page)
        if current.status == "Published":
            return current
        try:
            response = await self._request(
                "PATCH",
                f"/pages/{page['id']}",
                json={
                    "properties": {
                        "Status": {"select": {"name": "Published"}},
                        "Todoist Task IDs": _rich_text(json.dumps(task_ids)),
                        "Published At": {"date": {"start": published_at.isoformat()}},
                    }
                },
            )
            body = response.json()
            return current.model_copy(
                update={
                    "status": "Published",
                    "todoist_task_ids": task_ids,
                    "published_at": published_at,
                    "notion_page_id": body["id"],
                    "notion_url": body.get("url") or current.notion_url,
                }
            )
        except Exception as exc:
            raise NotionPlanStoreError("Could not record proposal publication") from exc

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        try:
            response = await self._request("GET", f"/data_sources/{self._data_source_id}")
            current = response.json().get("properties", {})
            missing = {
                name: schema for name, schema in PLAN_PROPERTIES.items() if name not in current
            }
            if missing:
                await self._request(
                    "PATCH",
                    f"/data_sources/{self._data_source_id}",
                    json={"properties": missing},
                )
            self._schema_ready = True
        except Exception as exc:
            raise NotionPlanStoreError("Could not verify plan-proposal schema") from exc

    async def _find_page(self, proposal_key: str) -> dict[str, Any] | None:
        response = await self._request(
            "POST",
            f"/data_sources/{self._data_source_id}/query",
            json={
                "filter": {
                    "property": "Proposal Key",
                    "rich_text": {"equals": proposal_key},
                },
                "page_size": 2,
            },
        )
        results = response.json().get("results", [])
        if len(results) > 1:
            raise NotionPlanStoreError(f"Duplicate plan proposals found for {proposal_key}")
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


def _properties(proposal: PlanProposal) -> dict[str, Any]:
    actions_json = json.dumps(
        [action.model_dump(mode="json") for action in proposal.actions],
        separators=(",", ":"),
    )
    if len(actions_json) > 1900:
        raise ValueError("serialized actions exceed Notion's safe property size")
    return {
        "Name": _title(f"{proposal.cadence.title()} plan — {proposal.plan_date}"),
        "Proposal Key": _rich_text(proposal.proposal_key),
        "Plan Date": {"date": {"start": proposal.plan_date.isoformat()}},
        "Cadence": {"select": {"name": proposal.cadence.title()}},
        "Status": {"select": {"name": "Draft"}},
        "Version": {"number": proposal.version},
        "Rationale": _rich_text(proposal.rationale),
        "Actions JSON": _rich_text(actions_json),
        "Todoist Task IDs": _rich_text(""),
        "Published At": {"date": None},
    }


def _proposal(page: dict[str, Any]) -> PlanProposal:
    properties = page["properties"]
    raw_actions = json.loads(_text(properties["Actions JSON"]) or "[]")
    task_ids = tuple(json.loads(_text(properties["Todoist Task IDs"]) or "[]"))
    published = properties["Published At"].get("date")
    return PlanProposal(
        proposal_key=_text(properties["Proposal Key"]),
        plan_date=properties["Plan Date"]["date"]["start"][:10],
        cadence=(_select(properties["Cadence"]) or "daily").lower(),
        status=_select(properties["Status"]) or "Draft",
        version=int(properties["Version"].get("number") or 1),
        rationale=_text(properties["Rationale"]),
        actions=tuple(PlanActionInput.model_validate(item) for item in raw_actions),
        notion_page_id=page["id"],
        notion_url=page.get("url"),
        todoist_task_ids=task_ids,
        published_at=(
            datetime.fromisoformat(published["start"].replace("Z", "+00:00"))
            if published
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
    return "".join(item.get("plain_text") or item.get("text", {}).get("content", "") for item in values)


def _select(property_value: dict[str, Any]) -> str | None:
    selected = property_value.get("select")
    return selected.get("name") if selected else None

