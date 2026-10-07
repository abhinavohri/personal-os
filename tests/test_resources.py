import pytest
from pydantic import ValidationError

from personal_os.domain.resources import ResourceCapture, canonical_url, resource_key


def test_resource_key_removes_tracking_and_normalizes_urls() -> None:
    first = ResourceCapture(
        title="Example",
        resource_type="website",
        url="HTTPS://Example.COM/path/?utm_source=x&b=2&a=1#section",
    )
    second = ResourceCapture(
        title="Renamed",
        resource_type="bookmark",
        url="https://example.com/path?a=1&b=2",
    )

    assert canonical_url(first.url) == "https://example.com/path?a=1&b=2"
    assert resource_key(first) == resource_key(second)


def test_resources_without_urls_dedupe_by_type_and_title() -> None:
    first = ResourceCapture(title="  Learn   French ", resource_type="language")
    second = ResourceCapture(title="learn french", resource_type="language")

    assert resource_key(first) == resource_key(second)


def test_resource_urls_must_be_absolute_web_urls() -> None:
    with pytest.raises(ValidationError, match="absolute http or https"):
        ResourceCapture(title="Bad", resource_type="website", url="javascript:alert(1)")

