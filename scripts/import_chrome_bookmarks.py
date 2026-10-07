"""Preview or import one local Chrome profile into the Notion Resources inbox."""

import argparse
import asyncio
import os
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

from personal_os.config import PersonalOSConfig
from personal_os.providers.notion_resources import NotionResourceInbox
from personal_os.services.bookmark_import import load_chrome_bookmarks


DEFAULT_BOOKMARKS = Path.home() / "Library/Application Support/Google/Chrome/Default/Bookmarks"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bookmarks", type=Path, default=DEFAULT_BOOKMARKS)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args()


async def run(args: argparse.Namespace) -> None:
    resources = load_chrome_bookmarks(args.bookmarks)
    types = Counter(resource.resource_type for resource in resources)
    groups = Counter(tag for resource in resources for tag in resource.tags)
    print(f"Bookmarks ready: {len(resources)}")
    print("Types:", ", ".join(f"{key}={value}" for key, value in sorted(types.items())))
    print("Groups:", ", ".join(f"{key}={value}" for key, value in groups.most_common()))
    if not args.apply:
        print("Preview only. Pass --apply to write to Notion.")
        return

    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("NOTION_TOKEN is missing from .env")
    config = PersonalOSConfig.from_yaml("config/system.yaml")
    store = NotionResourceInbox(token, config.notion.resources_data_source_id)
    saved = 0
    try:
        for offset in range(0, len(resources), 25):
            records = await store.upsert_many(resources[offset : offset + 25])
            saved += len(records)
    finally:
        await store.close()
    print(f"Imported or updated: {saved}")


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
