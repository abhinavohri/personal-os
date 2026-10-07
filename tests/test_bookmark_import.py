import json
from pathlib import Path

from personal_os.services.bookmark_import import (
    classify_bookmark,
    load_chrome_bookmarks,
    sanitize_bookmark_url,
)


def test_chrome_import_preserves_folder_and_marks_known_dsa_roadmap(tmp_path: Path) -> None:
    path = tmp_path / "Bookmarks"
    path.write_text(
        json.dumps(
            {
                "roots": {
                    "bookmark_bar": {
                        "type": "folder",
                        "name": "Bookmarks Bar",
                        "children": [
                            {
                                "type": "url",
                                "name": "Chai Prep",
                                "url": "https://dsa.chaicode.com/roadmap?token=secret#part",
                            }
                        ],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    resources = load_chrome_bookmarks(path)

    assert len(resources) == 1
    assert resources[0].url == "https://dsa.chaicode.com/roadmap"
    assert resources[0].resource_type == "roadmap"
    assert {"active", "dsa", "interview"}.issubset(resources[0].tags)
    assert "Bookmarks Bar" in resources[0].notes


def test_url_sanitizer_drops_sensitive_parameters_but_keeps_playlist_id() -> None:
    value = sanitize_bookmark_url(
        "https://youtube.com/playlist?list=abc&access_token=secret#video"
    )

    assert value == "https://youtube.com/playlist?list=abc"


def test_classifier_groups_french_and_inference_material() -> None:
    resource_type, tags = classify_bookmark(
        "Inference Engineering Course",
        "https://example.com/course",
        ("Bookmarks Bar", "french"),
    )

    assert resource_type == "course"
    assert "french" in tags
    assert "ai-inference" in tags
