"""Install or remove the macOS user service for the local scan uploader."""

import argparse
import os
import plistlib
import subprocess
from pathlib import Path
from typing import Any


LABEL = "com.personal-os.uploader"


def service_definition(project_root: Path, user_home: Path) -> dict[str, Any]:
    log_dir = user_home / "Library" / "Logs" / "PersonalOS"
    return {
        "Label": LABEL,
        "ProgramArguments": [
            str(project_root / ".venv" / "bin" / "python"),
            str(project_root / "scripts" / "start_uploader.py"),
        ],
        "WorkingDirectory": str(project_root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "ThrottleInterval": 10,
        "StandardOutPath": str(log_dir / "uploader.log"),
        "StandardErrorPath": str(log_dir / "uploader-error.log"),
    }


def install(project_root: Path, user_home: Path) -> Path:
    python = project_root / ".venv" / "bin" / "python"
    if not python.exists():
        raise RuntimeError("Run 'uv sync' before installing the uploader service")

    log_dir = user_home / "Library" / "Logs" / "PersonalOS"
    log_dir.mkdir(parents=True, exist_ok=True)
    destination = user_home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file:
        plistlib.dump(service_definition(project_root, user_home), file, sort_keys=False)
    destination.chmod(0o600)

    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", f"{domain}/{LABEL}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["launchctl", "bootstrap", domain, str(destination)], check=True)
    return destination


def uninstall(user_home: Path) -> None:
    domain = f"gui/{os.getuid()}"
    subprocess.run(
        ["launchctl", "bootout", f"{domain}/{LABEL}"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    destination = user_home / "Library" / "LaunchAgents" / f"{LABEL}.plist"
    destination.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uninstall", action="store_true")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parents[1]
    user_home = Path.home()
    if args.uninstall:
        uninstall(user_home)
        print(f"Removed {LABEL}")
        return

    destination = install(project_root, user_home)
    print(f"Installed and started {LABEL} from {destination}")


if __name__ == "__main__":
    main()
