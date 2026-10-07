"""Create the idempotent Notion structure for a Personal OS workspace."""

import json
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

from personal_os.config import PersonalOSConfig
from personal_os.providers.notion import NOTION_API_VERSION


PAGES = {
    "agent_brief_page_id": (
        "Agent Brief",
        "Canonical context read at the beginning of every planning session. Keep it concise and current.",
    ),
    "profile_page_id": (
        "Profile and Constraints",
        "Stable background, responsibilities, preferences, hard constraints, and deadlines. Sustainable load is inferred from execution.",
    ),
    "spine_page_id": (
        "Spine",
        "The central direction connecting current projects, learning, and career development.",
    ),
    "interests_and_lanes_page_id": (
        "Interests and Lanes",
        "Active interests assigned to Build, Reading, Open, or Parking Lot.",
    ),
    "current_week_page_id": (
        "Current Week",
        "A human-readable view of this week's focus, limits, risks, and proposed changes.",
    ),
    "archive_page_id": (
        "Archive",
        "Inactive context retained for reference without crowding active planning.",
    ),
}


DATABASES: dict[str, tuple[str, str, dict[str, Any]]] = {
    "roadmap_data_source_id": (
        "Roadmap",
        "Approved outcomes and milestones; daily actions belong in Todoist.",
        {
            "Name": {"title": {}},
            "Lane": {"select": {"options": [
                {"name": "Build", "color": "blue"},
                {"name": "Reading", "color": "green"},
                {"name": "Open", "color": "yellow"},
                {"name": "Parking Lot", "color": "gray"},
            ]}},
            "Status": {"select": {"options": [
                {"name": "Planned", "color": "gray"},
                {"name": "Active", "color": "blue"},
                {"name": "Blocked", "color": "red"},
                {"name": "Done", "color": "green"},
            ]}},
            "Target Date": {"date": {}},
            "Outcome": {"rich_text": {}},
        },
    ),
    "notes_inbox_data_source_id": (
        "Notes Inbox",
        "Review queue for structured drafts extracted from handwritten notes.",
        {
            "Name": {"title": {}},
            "Status": {"select": {"options": [
                {"name": "Draft", "color": "yellow"},
                {"name": "Approved", "color": "green"},
                {"name": "Archived", "color": "gray"},
            ]}},
            "Page Date": {"date": {}},
            "Confidence": {"number": {"format": "percent"}},
            "Needs Review": {"checkbox": {}},
            "Source Object": {"rich_text": {}},
        },
    ),
    "resources_data_source_id": (
        "Resources",
        "Useful books, papers, courses, tools, and references.",
        {
            "Name": {"title": {}},
            "URL": {"url": {}},
            "Type": {"select": {}},
            "Status": {"select": {"options": [
                {"name": "Inbox", "color": "yellow"},
                {"name": "Active", "color": "blue"},
                {"name": "Finished", "color": "green"},
            ]}},
        },
    ),
    "repository_catalog_data_source_id": (
        "Repository Catalog",
        "Allowlisted GitHub repositories used as background and work evidence.",
        {
            "Name": {"title": {}},
            "Full Name": {"rich_text": {}},
            "URL": {"url": {}},
            "Primary Language": {"select": {}},
            "Private": {"checkbox": {}},
            "Last Reviewed": {"date": {}},
            "Description": {"rich_text": {}},
            "Topics": {"multi_select": {}},
            "README Excerpt": {"rich_text": {}},
        },
    ),
    "decisions_data_source_id": (
        "Decision Log",
        "Important planning decisions, their rationale, and superseding decisions.",
        {
            "Name": {"title": {}},
            "Date": {"date": {}},
            "Status": {"select": {"options": [
                {"name": "Proposed", "color": "yellow"},
                {"name": "Approved", "color": "green"},
                {"name": "Superseded", "color": "gray"},
            ]}},
            "Rationale": {"rich_text": {}},
        },
    ),
    "weekly_reviews_data_source_id": (
        "Weekly Reviews",
        "Weekly evidence, reflection, proposed roadmap changes, and approved next actions.",
        {
            "Name": {"title": {}},
            "Week Start": {"date": {}},
            "Status": {"select": {"options": [
                {"name": "Draft", "color": "yellow"},
                {"name": "Approved", "color": "green"},
            ]}},
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
        },
    ),
    "plan_proposals_data_source_id": (
        "Plan Proposals",
        "Versioned executable plans. Drafts are inert until explicitly approved in Hermes.",
        {
            "Name": {"title": {}},
            "Proposal Key": {"rich_text": {}},
            "Plan Date": {"date": {}},
            "Cadence": {"select": {"options": [
                {"name": "Daily", "color": "blue"},
                {"name": "Weekly", "color": "purple"},
            ]}},
            "Status": {"select": {"options": [
                {"name": "Draft", "color": "yellow"},
                {"name": "Published", "color": "green"},
            ]}},
            "Version": {"number": {}},
            "Rationale": {"rich_text": {}},
            "Actions JSON": {"rich_text": {}},
            "Todoist Task IDs": {"rich_text": {}},
            "Published At": {"date": {}},
        },
    ),
}


class NotionBootstrap:
    def __init__(self, token: str) -> None:
        self.client = httpx.Client(
            base_url="https://api.notion.com/v1",
            headers={
                "Authorization": f"Bearer {token}",
                "Notion-Version": NOTION_API_VERSION,
                "Content-Type": "application/json",
            },
            timeout=30,
        )

    def request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        for attempt in range(4):
            response = self.client.request(method, path, **kwargs)
            if response.status_code != 429:
                response.raise_for_status()
                return response.json()
            if attempt == 3:
                response.raise_for_status()
            time.sleep(float(response.headers.get("Retry-After", "1")))
        raise RuntimeError("Notion request retry loop ended unexpectedly")

    def children(self, page_id: str) -> dict[str, tuple[str, str]]:
        result: dict[str, tuple[str, str]] = {}
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            body = self.request("GET", f"/blocks/{page_id}/children", params=params)
            for block in body.get("results", []):
                block_type = block.get("type")
                if block_type in {"child_page", "child_database"}:
                    title = block[block_type].get("title")
                    if title:
                        result[title] = (block_type, block["id"])
            cursor = body.get("next_cursor")
            if not cursor:
                return result

    def create_page(self, parent_id: str, title: str, description: str) -> str:
        body = self.request(
            "POST",
            "/pages",
            json={
                "parent": {"type": "page_id", "page_id": parent_id},
                "properties": {
                    "title": {
                        "type": "title",
                        "title": [{"type": "text", "text": {"content": title}}],
                    }
                },
                "children": [{
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": description}}]
                    },
                }],
            },
        )
        return body["id"]

    def create_database(
        self,
        parent_id: str,
        title: str,
        description: str,
        properties: dict[str, Any],
    ) -> tuple[str, str]:
        body = self.request(
            "POST",
            "/databases",
            json={
                "parent": {"type": "page_id", "page_id": parent_id},
                "title": [{"type": "text", "text": {"content": title}}],
                "description": [
                    {"type": "text", "text": {"content": description}}
                ],
                "is_inline": False,
                "initial_data_source": {"properties": properties},
            },
        )
        return body["id"], self.data_source_id(body["id"], body)

    def data_source_id(
        self, database_id: str, database: dict[str, Any] | None = None
    ) -> str:
        body = database or self.request("GET", f"/databases/{database_id}")
        sources = body.get("data_sources") or body.get("dataSources") or []
        if not sources:
            body = self.request("GET", f"/databases/{database_id}")
            sources = body.get("data_sources") or body.get("dataSources") or []
        if not sources:
            raise RuntimeError(f"Notion returned no data source for database {database_id}")
        return sources[0]["id"]

    def close(self) -> None:
        self.client.close()


def main() -> None:
    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("NOTION_TOKEN is missing from .env")

    config = PersonalOSConfig.from_yaml("config/system.yaml")
    bootstrap = NotionBootstrap(token)
    ids: dict[str, str] = {"root_page_id": config.notion.root_page_id}
    try:
        children = bootstrap.children(config.notion.root_page_id)
        for key, (title, description) in PAGES.items():
            existing = children.get(title)
            ids[key] = (
                existing[1]
                if existing and existing[0] == "child_page"
                else bootstrap.create_page(config.notion.root_page_id, title, description)
            )
            time.sleep(0.35)

        children = bootstrap.children(config.notion.root_page_id)
        for key, (title, description, properties) in DATABASES.items():
            existing = children.get(title)
            if existing and existing[0] == "child_database":
                ids[key] = bootstrap.data_source_id(existing[1])
            else:
                _, ids[key] = bootstrap.create_database(
                    config.notion.root_page_id, title, description, properties
                )
            time.sleep(0.35)
    finally:
        bootstrap.close()

    print(json.dumps(ids, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
