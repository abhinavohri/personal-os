from pathlib import Path

import pytest
from pydantic import ValidationError

from personal_os.config import PersonalOSConfig, RuntimeSecrets


def test_example_configuration_matches_runtime_schema() -> None:
    root = Path(__file__).parents[1]

    config = PersonalOSConfig.from_yaml(root / "config/system.example.yaml")

    assert config.web_search.provider == "vertex_google_search"
    assert config.notion.notes_inbox_data_source_id == "replace-me"
    assert config.github.allowed_repositories == ()


def test_runtime_secrets_require_all_adapter_tokens() -> None:
    with pytest.raises(ValidationError):
        RuntimeSecrets.from_environment({"NOTION_TOKEN": "only-one"})

    secrets = RuntimeSecrets.from_environment(
        {
            "NOTION_TOKEN": "notion",
            "TODOIST_API_TOKEN": "todoist",
            "GITHUB_TOKEN": "github",
        }
    )
    assert secrets.github_token == "github"
