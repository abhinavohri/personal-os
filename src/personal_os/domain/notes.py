"""Domain models for handwritten-note extraction."""

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class ExtractedTask(BaseModel):
    """A task explicitly present or reasonably inferred from a note."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str = Field(min_length=1)
    explicit_due_date: date | None = None


class ExtractedNote(BaseModel):
    """Normalized result of processing one scanned note object."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_object: str = Field(min_length=1)
    page_date: date | None = None
    title: str | None = None
    transcription: str
    summary: str
    confidence: float = Field(ge=0, le=1)
    tasks: tuple[ExtractedTask, ...]
    insights: tuple[str, ...]
    questions: tuple[str, ...]
    resources: tuple[str, ...]
    diagrams: tuple[str, ...] = ()
    uncertainties: tuple[str, ...]
    contains_sensitive_content: bool = False

    @property
    def needs_review(self) -> bool:
        """Return whether the extraction should stay in the manual-review queue."""

        return self.confidence < 0.8 or bool(self.uncertainties)
