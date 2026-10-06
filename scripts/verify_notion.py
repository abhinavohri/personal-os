"""Run a small live read/write check against the configured Notion workspace."""

import asyncio
import os

from dotenv import load_dotenv

from personal_os.config import PersonalOSConfig
from personal_os.domain.notes import ExtractedNote
from personal_os.providers.notion import NotionMemory


async def main() -> None:
    load_dotenv()
    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("NOTION_TOKEN is missing from .env")

    config = PersonalOSConfig.from_yaml("config/system.yaml")
    memory = NotionMemory(
        token,
        config.notion.notes_inbox_data_source_id,
        title_property=config.notion.notes_title_property,
    )
    try:
        brief = await memory.read_page_text(config.notion.agent_brief_page_id)
        draft = await memory.create_note_draft(
            ExtractedNote(
                source_object="gs://personal-os/setup-check",
                title="Personal OS setup check",
                transcription="Notion adapter live verification.",
                summary="The Personal OS connection can create reviewable drafts.",
                confidence=1,
                tasks=(),
                insights=(),
                questions=(),
                resources=(),
                uncertainties=(),
            )
        )
    finally:
        await memory.close()

    print(f"agent brief: ok ({len(brief)} characters)")
    print(f"notes inbox draft: ok ({draft.url or draft.id})")


if __name__ == "__main__":
    asyncio.run(main())
