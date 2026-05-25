import pytest
import base64
from extractor import capture_screenshots


def test_capture_screenshots_returns_list():
    shots = capture_screenshots("https://example.com")
    assert isinstance(shots, list)
    assert len(shots) >= 1


def test_capture_screenshots_are_valid_base64():
    shots = capture_screenshots("https://example.com")
    for shot in shots:
        decoded = base64.b64decode(shot)
        assert len(decoded) > 1000


def test_capture_screenshots_invalid_url_raises():
    with pytest.raises(Exception):
        capture_screenshots("not-a-valid-url")
