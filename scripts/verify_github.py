"""Run a live, read-only check against each allowlisted GitHub repository."""

import asyncio
import os
from collections import Counter
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv

from personal_os.config import PersonalOSConfig
from personal_os.providers.github import GitHubWorkEvidence


async def main() -> None:
    load_dotenv()
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("GITHUB_TOKEN is missing from .env")

    config = PersonalOSConfig.from_yaml("config/system.yaml")
    if not config.github.allowed_repositories:
        raise SystemExit("github.allowed_repositories is empty in config/system.yaml")

    evidence = GitHubWorkEvidence(
        token,
        config.github.username,
        config.github.allowed_repositories,
        allow_private=config.github.include_private_repositories,
    )
    try:
        since = datetime.now(UTC) - timedelta(days=30)
        for full_name in config.github.allowed_repositories:
            repository = await evidence.get_repository(full_name)
            activity = await evidence.recent_activity(full_name, since)
            counts = Counter(event.kind for event in activity)
            summary = ", ".join(
                f"{kind}={counts.get(kind, 0)}"
                for kind in ("commit", "pull_request", "issue", "release")
            )
            visibility = "private" if repository.is_private else "public"
            print(
                f"{repository.full_name}: ok "
                f"({visibility}, language={repository.primary_language or 'unknown'})"
            )
            print(f"30-day activity: {summary}")
    finally:
        await evidence.close()


if __name__ == "__main__":
    asyncio.run(main())
