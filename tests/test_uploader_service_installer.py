from pathlib import Path

from scripts.install_uploader_service import LABEL, service_definition


def test_service_runs_uploader_from_project_virtual_environment() -> None:
    project_root = Path("/workspace/personal-os")
    user_home = Path("/Users/person")

    service = service_definition(project_root, user_home)

    assert service["Label"] == LABEL
    assert service["ProgramArguments"] == [
        "/workspace/personal-os/.venv/bin/python",
        "/workspace/personal-os/scripts/start_uploader.py",
    ]
    assert service["WorkingDirectory"] == "/workspace/personal-os"
    assert service["RunAtLoad"] is True
    assert service["KeepAlive"] is True
    assert service["StandardErrorPath"] == (
        "/Users/person/Library/Logs/PersonalOS/uploader-error.log"
    )
