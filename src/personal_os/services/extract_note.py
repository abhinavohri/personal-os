"""Use case for extracting one scanned paper note."""

from personal_os.domain.notes import ExtractedNote
from personal_os.ports.llm import ImageInput, StructuredGenerationRequest, StructuredLLM


class PaperNoteExtractor:
    """Extract notes without depending on a specific model provider."""

    def __init__(self, llm: StructuredLLM, prompt: str) -> None:
        self._llm = llm
        self._prompt = prompt

    async def extract(self, source_object: str, media_type: str) -> ExtractedNote:
        request = StructuredGenerationRequest(
            prompt=self._prompt,
            images=(ImageInput(uri=source_object, media_type=media_type),),
        )
        extracted = await self._llm.generate_structured(request, ExtractedNote)

        # The storage event, not the model, is authoritative for object identity.
        payload = extracted.model_dump()
        payload["source_object"] = source_object
        return ExtractedNote.model_validate(payload)
