import pytest

from scripts.run_plan import find_job_id


def test_friendly_plan_name_resolves_active_job() -> None:
    store = {
        "jobs": [
            {"id": "daily-id", "name": "Revise today's plan", "enabled": True},
            {"id": "old-id", "name": "Revise today's plan", "enabled": False},
        ]
    }

    assert find_job_id(store, "Revise today's plan") == "daily-id"


def test_missing_or_duplicate_active_job_is_rejected() -> None:
    with pytest.raises(RuntimeError, match="No active"):
        find_job_id({"jobs": []}, "Review and replan the week")

    duplicate = {
        "jobs": [
            {"id": "one", "name": "Review and replan the week", "enabled": True},
            {"id": "two", "name": "Review and replan the week", "enabled": True},
        ]
    }
    with pytest.raises(RuntimeError, match="Multiple active"):
        find_job_id(duplicate, "Review and replan the week")
