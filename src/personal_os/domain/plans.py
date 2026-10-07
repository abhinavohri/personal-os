"""Provider-neutral models and rules for executable plan proposals."""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


PlanCadence = Literal["daily", "weekly"]
PlanActionKind = Literal["core", "optional"]
PlanStatus = Literal["Draft", "Published"]


class PlanActionInput(BaseModel):
    """One proposed Todoist action supplied by Hermes."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str = Field(min_length=1, max_length=500)
    description: str = Field(default="", max_length=1000)
    due_date: date
    kind: PlanActionKind = "core"
    labels: tuple[str, ...] = ()


class PlanProposal(BaseModel):
    """A versioned proposal that is inert until explicitly published."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    proposal_key: str = Field(min_length=1, max_length=200)
    plan_date: date
    cadence: PlanCadence
    rationale: str = Field(min_length=1, max_length=1500)
    actions: tuple[PlanActionInput, ...] = Field(min_length=1, max_length=3)
    version: int = Field(default=1, ge=1)
    status: PlanStatus = "Draft"
    notion_page_id: str | None = None
    notion_url: str | None = None
    todoist_task_ids: tuple[str, ...] = ()
    published_at: datetime | None = None


def validate_daily_shape(
    actions: tuple[PlanActionInput, ...],
    *,
    max_core: int,
    max_optional: int,
) -> None:
    """Keep the executable batch intentionally small for either cadence."""
    core = sum(action.kind == "core" for action in actions)
    optional = sum(action.kind == "optional" for action in actions)
    if core > max_core:
        raise ValueError(f"plan may contain at most {max_core} core actions")
    if optional > max_optional:
        raise ValueError(f"plan may contain at most {max_optional} optional actions")

