"""Run a small live read/write check against the configured Todoist project."""

import asyncio
import os
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

from personal_os.config import PersonalOSConfig
from personal_os.ports.tasks import TaskDraft
from personal_os.providers.todoist import TodoistTaskStore


SETUP_TASK = "Review Personal OS setup check"


async def main() -> None:
    load_dotenv()
    token = os.environ.get("TODOIST_API_TOKEN")
    if not token:
        raise SystemExit("TODOIST_API_TOKEN is missing from .env")

    config = PersonalOSConfig.from_yaml("config/system.yaml")
    store = TodoistTaskStore(token)
    try:
        active_before = await store.list_active(config.todoist.project_id)
        now = datetime.now(UTC)
        completed = await store.list_completed(
            config.todoist.project_id, now - timedelta(days=7), now
        )

        task = next((item for item in active_before if item.content == SETUP_TASK), None)
        created = task is None
        if task is None:
            task = await store.create_task(
                config.todoist.project_id,
                TaskDraft(
                    content=SETUP_TASK,
                    description=(
                        "Created to verify the Todoist adapter. Complete or remove "
                        "after reviewing the setup."
                    ),
                    labels=("personal-os", "setup-check"),
                ),
            )

        active_after = await store.list_active(config.todoist.project_id)
        if not any(item.id == task.id for item in active_after):
            raise RuntimeError("Created setup task was not returned by Todoist")
    finally:
        await store.close()

    print(f"active tasks: ok ({len(active_after)})")
    print(f"completed tasks (7 days): ok ({len(completed)})")
    print(f"setup task: ok ({'created' if created else 'reused'})")
    print(f"task url: https://app.todoist.com/app/task/{task.id}")


if __name__ == "__main__":
    asyncio.run(main())
