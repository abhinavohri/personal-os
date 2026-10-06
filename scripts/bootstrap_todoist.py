"""Create or find the dedicated Todoist project used by Personal OS."""

import json
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv


PROJECT_NAME = "Personal OS"


class TodoistBootstrap:
    """Small synchronous client for one-time Todoist project setup."""

    def __init__(self, token: str) -> None:
        self.client = httpx.Client(
            base_url="https://api.todoist.com/api/v1",
            headers={"Authorization": f"Bearer {token}"},
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
        raise RuntimeError("Todoist request retry loop ended unexpectedly")

    def projects(self) -> list[dict[str, Any]]:
        projects: list[dict[str, Any]] = []
        cursor: str | None = None
        while True:
            params: dict[str, Any] = {"limit": 200}
            if cursor:
                params["cursor"] = cursor
            body = self.request("GET", "/projects", params=params)
            projects.extend(body.get("results", []))
            cursor = body.get("next_cursor")
            if not cursor:
                return projects

    def ensure_project(self) -> tuple[dict[str, Any], bool]:
        for project in self.projects():
            if project.get("name", "").casefold() == PROJECT_NAME.casefold():
                return project, False

        project = self.request(
            "POST",
            "/projects",
            json={
                "name": PROJECT_NAME,
                "description": (
                    "Approved next actions generated from the Personal OS roadmap."
                ),
                "is_favorite": True,
                "view_style": "list",
            },
        )
        return project, True

    def close(self) -> None:
        self.client.close()


def main() -> None:
    load_dotenv()
    token = os.environ.get("TODOIST_API_TOKEN")
    if not token:
        raise SystemExit("TODOIST_API_TOKEN is missing from .env")

    bootstrap = TodoistBootstrap(token)
    try:
        project, created = bootstrap.ensure_project()
    finally:
        bootstrap.close()

    print(json.dumps({"project_id": str(project["id"]), "created": created}, indent=2))


if __name__ == "__main__":
    main()
