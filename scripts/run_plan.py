"""Manually trigger a named Personal OS planning job."""

import argparse
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any


JOB_NAMES = {
    "daily": "Revise today's plan",
    "weekly": "Review and replan the week",
}


def find_job_id(store: dict[str, Any], name: str) -> str:
    matches = [
        str(job["id"])
        for job in store.get("jobs", [])
        if isinstance(job, dict) and job.get("name") == name and job.get("enabled")
    ]
    if not matches:
        raise RuntimeError(f"No active Hermes cron job named {name!r}")
    if len(matches) > 1:
        raise RuntimeError(f"Multiple active Hermes cron jobs named {name!r}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cadence", choices=tuple(JOB_NAMES))
    args = parser.parse_args()

    hermes_home = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    store_path = hermes_home / "cron" / "jobs.json"
    if not store_path.exists():
        raise SystemExit(f"Hermes cron store not found: {store_path}")
    store = json.loads(store_path.read_text(encoding="utf-8"))
    try:
        job_id = find_job_id(store, JOB_NAMES[args.cadence])
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc

    command = shutil.which("hermes") or str(Path.home() / ".local" / "bin" / "hermes")
    subprocess.run([command, "cron", "run", job_id], check=True)


if __name__ == "__main__":
    main()
