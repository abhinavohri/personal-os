"""Process pending paper-note scans into GCS artifacts and Notion drafts."""

import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv

from personal_os.config import PersonalOSConfig
from personal_os.providers.gcs import GCSObjectStore
from personal_os.providers.notion import NotionMemory
from personal_os.providers.vertex import VertexStructuredLLM
from personal_os.services.extract_note import PaperNoteExtractor
from personal_os.services.process_notes import PaperNoteProcessor


async def run(limit: int) -> int:
    project_root = Path(__file__).resolve().parents[1]
    load_dotenv(project_root / ".env")
    config = PersonalOSConfig.from_yaml(project_root / "config" / "system.yaml")
    notion_token = os.environ.get("NOTION_TOKEN", "")
    if not notion_token:
        raise RuntimeError("NOTION_TOKEN is missing from .env")

    llm = VertexStructuredLLM(
        config.gcp.project_id,
        config.vertex.location,
        config.vertex.routine_model,
    )
    memory = NotionMemory(
        notion_token,
        config.notion.notes_inbox_data_source_id,
        title_property=config.notion.notes_title_property,
    )
    prompt = (project_root / "prompts" / "paper-note-extraction.md").read_text()
    processor = PaperNoteProcessor(
        GCSObjectStore(config.gcp.project_id),
        PaperNoteExtractor(llm, prompt),
        memory,
        config.gcp.paper_notes_bucket,
    )
    try:
        results = await processor.process_pending(limit)
        if not results:
            print("No pending scans.")
        for result in results:
            detail = result.notion_page_id or result.error or "already processed"
            print(f"{result.status}: {result.source_uri} ({detail})")
        return 1 if any(result.status == "failed" for result in results) else 0
    finally:
        await memory.close()
        await llm.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    raise SystemExit(asyncio.run(run(args.limit)))


if __name__ == "__main__":
    main()
