from personal_os.domain.planning import ExecutionObservation, assess_execution


def test_stalled_plan_diagnoses_rollovers_without_asking_for_hours() -> None:
    result = assess_execution(
        ExecutionObservation(
            active_tasks=3,
            completed_tasks=0,
            overdue_tasks=1,
            rollover_tasks=2,
            focus_due_tasks=2,
            github_events=0,
            window_days=14,
        ),
        max_daily_tasks=3,
    )

    assert result.state == "stalled"
    assert any("overdue" in item for item in result.adjustments)
    assert any("rollover" in item for item in result.adjustments)
    assert all("hours" not in item for item in result.adjustments)


def test_steady_plan_uses_observed_completion_as_load_signal() -> None:
    observation = ExecutionObservation(
        active_tasks=2,
        completed_tasks=6,
        overdue_tasks=0,
        rollover_tasks=0,
        focus_due_tasks=2,
        github_events=4,
        window_days=14,
    )

    result = assess_execution(observation, max_daily_tasks=3)

    assert result.state == "steady"
    assert observation.observed_completions_per_week == 3.0
    assert any("observed task completion" in item for item in result.adjustments)


def test_empty_plan_starts_with_one_small_action() -> None:
    result = assess_execution(
        ExecutionObservation(0, 0, 0, 0, 0, 0, 14),
        max_daily_tasks=3,
    )

    assert result.state == "insufficient_evidence"
    assert "one small" in result.adjustments[0]
