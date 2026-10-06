import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from personal_os.domain.notes import ExtractedNote
from personal_os.ports.llm import StructuredGenerationRequest
from personal_os.services.extract_note import PaperNoteExtractor


class FakeStructuredLLM:
    def __init__(self, response: dict[str, Any]) -> None:
        self.response = response
        self.requests: list[StructuredGenerationRequest] = []

    async def generate_structured(self, request, response_model):
        self.requests.append(request)
        return response_model.model_validate(self.response)


def test_extractor_uses_event_source_object_and_provider_neutral_request() -> None:
    llm = FakeStructuredLLM(
        {
            "source_object": "model-invented-location",
            "transcription": "Read the memory paper.",
            "summary": "Reading reminder",
            "confidence": 0.97,
            "tasks": [{"text": "Read the memory paper", "explicit_due_date": None}],
            "insights": [],
            "questions": [],
            "resources": [],
            "uncertainties": [],
        }
    )
    extractor = PaperNoteExtractor(llm, prompt="Extract the note")

    note = asyncio.run(
        extractor.extract("gs://paper-notes/inbox/page-1.jpg", "image/jpeg")
    )

    assert note.source_object == "gs://paper-notes/inbox/page-1.jpg"
    assert not note.needs_review
    assert llm.requests[0].images[0].media_type == "image/jpeg"


def test_low_confidence_or_uncertainty_requires_review() -> None:
    note = ExtractedNote(
        source_object="gs://paper-notes/inbox/page-2.jpg",
        transcription="Possible text",
        summary="Unclear note",
        confidence=0.79,
        tasks=(),
        insights=(),
        questions=(),
        resources=(),
        uncertainties=("Last line is illegible",),
    )

    assert note.needs_review


def test_confidence_is_bounded() -> None:
    with pytest.raises(ValidationError):
        ExtractedNote(
            source_object="gs://paper-notes/inbox/page-3.jpg",
            transcription="Text",
            summary="Summary",
            confidence=1.2,
            tasks=(),
            insights=(),
            questions=(),
            resources=(),
            uncertainties=(),
        )


def test_event_source_object_is_validated() -> None:
    llm = FakeStructuredLLM(
        {
            "source_object": "model-location",
            "transcription": "Text",
            "summary": "Summary",
            "confidence": 1,
            "tasks": [],
            "insights": [],
            "questions": [],
            "resources": [],
            "uncertainties": [],
        }
    )

    with pytest.raises(ValidationError):
        asyncio.run(PaperNoteExtractor(llm, "Extract").extract("", "image/jpeg"))


def test_checked_in_schema_tracks_required_domain_fields() -> None:
    schema_path = Path("schemas/extracted-note.schema.json")
    checked_in_schema = json.loads(schema_path.read_text())
    model_required = {
        name for name, field in ExtractedNote.model_fields.items() if field.is_required()
    }

    assert set(checked_in_schema["required"]) == model_required
