"""Transparent rules for turning execution evidence into planning pressure."""

from dataclasses import dataclass
from typing import Literal


PlanningState = Literal[
    "insufficient_evidence",
    "stalled",
    "strained",
    "steady",
]


@dataclass(frozen=True)
class ExecutionObservation:
    active_tasks: int
    completed_tasks: int
    overdue_tasks: int
    rollover_tasks: int
    focus_due_tasks: int
    github_events: int
    window_days: int

    @property
    def observed_completions_per_week(self) -> float:
        return round(self.completed_tasks * 7 / self.window_days, 1)


@dataclass(frozen=True)
class PlanningAssessment:
    state: PlanningState
    adjustments: tuple[str, ...]


def assess_execution(
    observation: ExecutionObservation,
    *,
    max_daily_tasks: int,
) -> PlanningAssessment:
    """Diagnose plan pressure without pretending task counts measure hours."""
    if observation.active_tasks == 0 and observation.completed_tasks == 0:
        return PlanningAssessment(
            state="insufficient_evidence",
            adjustments=(
                "Choose one small, outcome-linked action and use its completion as the first capacity signal.",
            ),
        )

    adjustments: list[str] = []
    if observation.overdue_tasks:
        adjustments.append(
            "Resolve each overdue task before adding more work: complete it, shrink it, reschedule it with a reason, or remove it."
        )
    if observation.rollover_tasks:
        adjustments.append(
            "Classify each rollover as blocked, oversized, displaced by a deliberate priority change, or no longer important."
        )
    if observation.focus_due_tasks > max_daily_tasks:
        adjustments.append(
            f"Reduce today's committed actions to at most {max_daily_tasks}; move the rest back to the proposal queue."
        )
    if observation.completed_tasks:
        adjustments.append(
            "Use observed task completion—not a self-reported hours estimate—as the initial load prior, then adjust after the next review."
        )
    if observation.github_events and observation.completed_tasks == 0:
        adjustments.append(
            "GitHub shows work that Todoist does not; reconcile the plan so completed effort is visible instead of treating it as distraction."
        )
    adjustments.append(
        "Keep strategic outcomes stable unless repeated evidence supports changing them; first adjust task size, order, and work in progress."
    )

    if observation.completed_tasks == 0 and (
        observation.overdue_tasks or observation.rollover_tasks
    ):
        state: PlanningState = "stalled"
    elif (
        observation.overdue_tasks
        or observation.rollover_tasks > observation.completed_tasks
        or observation.focus_due_tasks > max_daily_tasks
    ):
        state = "strained"
    else:
        state = "steady"
    return PlanningAssessment(state=state, adjustments=tuple(adjustments))
