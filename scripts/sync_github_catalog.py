"""Synchronize allowlisted GitHub repositories into the Notion catalog."""

import asyncio
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from personal_os.config import PersonalOSConfig
from personal_os.providers.github import GitHubWorkEvidence
from personal_os.providers.notion_repository_catalog import NotionRepositoryCatalog


async def main() -> None:
    load_dotenv()
    github_token = os.environ.get("GITHUB_TOKEN")
    notion_token = os.environ.get("NOTION_TOKEN")
    if not github_token:
        raise SystemExit("GITHUB_TOKEN is missing from .env")
    if not notion_token:
        raise SystemExit("NOTION_TOKEN is missing from .env")

    config = PersonalOSConfig.from_yaml("config/system.yaml")
    if not config.github.allowed_repositories:
        raise SystemExit("github.allowed_repositories is empty in config/system.yaml")

    github = GitHubWorkEvidence(
        github_token,
        config.github.username,
        config.github.allowed_repositories,
        allow_private=config.github.include_private_repositories,
    )
    catalog = NotionRepositoryCatalog(
        notion_token,
        config.notion.repository_catalog_data_source_id,
    )
    try:
        for full_name in config.github.allowed_repositories:
            repository = await github.get_repository(full_name)
            readme = await github.get_readme_text(full_name)
            record = await catalog.upsert_repository(
                repository,
                readme,
                reviewed_at=datetime.now(ZoneInfo(config.system.timezone)),
            )
            print(f"{full_name}: synced ({record.url or record.id})")
    finally:
        await github.close()
        await catalog.close()


if __name__ == "__main__":
    asyncio.run(main())
