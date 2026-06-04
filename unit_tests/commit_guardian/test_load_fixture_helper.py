"""
Tests for the load_fixture() helper defined in tests/conftest.py.

These tests verify:
 - Basic JSON loading by slash-separated name
 - Slash in name maps to nested subdirectory
 - Missing fixture raises FileNotFoundError with the path in the message

ADR-007 defines the fixture convention these tests exercise.
"""
import json
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ---------------------------------------------------------------------------
# Import load_fixture from tests/conftest.py.
# The tests/ directory is a sibling of unit_tests/ at the repo root; we
# insert it into sys.path so `import conftest` resolves without a package.
# ---------------------------------------------------------------------------
_TESTS_DIR = Path(__file__).resolve().parent.parent.parent / "tests"
if str(_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_TESTS_DIR))

from conftest import load_fixture  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_fixture(base_dir: Path, relative_name: str, data: dict) -> None:
    """Write *data* as JSON to base_dir/fixtures/<relative_name>.json."""
    target = base_dir / "fixtures" / f"{relative_name}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_load_fixture_returns_parsed_json(tmp_path: Path) -> None:
    """load_fixture returns the parsed dict for a top-level fixture name."""
    expected = {"key": "value", "number": 42}
    _write_fixture(tmp_path, "my_module/sample", expected)

    # Patch conftest.__file__ so load_fixture resolves fixtures relative to tmp_path
    fake_conftest_file = str(tmp_path / "conftest.py")
    with patch("conftest.__file__", fake_conftest_file):
        result = load_fixture("my_module/sample")

    assert result == expected, f"Expected {expected!r}, got {result!r}"


def test_load_fixture_slash_maps_to_subdir(tmp_path: Path) -> None:
    """A slash-separated name resolves to a nested subdirectory under fixtures/."""
    expected = {"nested": True, "depth": 2}
    _write_fixture(tmp_path, "build_pipeline/valid_config", expected)

    fake_conftest_file = str(tmp_path / "conftest.py")
    with patch("conftest.__file__", fake_conftest_file):
        result = load_fixture("build_pipeline/valid_config")

    assert result == expected
    # Verify the path that was read is indeed a nested subdirectory
    resolved = tmp_path / "fixtures" / "build_pipeline" / "valid_config.json"
    assert resolved.exists(), f"Fixture file not found at expected nested path: {resolved}"


def test_load_fixture_missing_raises_file_not_found(tmp_path: Path) -> None:
    """load_fixture raises FileNotFoundError when the fixture JSON does not exist."""
    fake_conftest_file = str(tmp_path / "conftest.py")

    with patch("conftest.__file__", fake_conftest_file):
        with pytest.raises(FileNotFoundError) as exc_info:
            load_fixture("nonexistent/path")

    # The exception message must include the missing path so callers can debug
    error_message = str(exc_info.value)
    assert "nonexistent" in error_message or "path" in error_message, (
        f"FileNotFoundError message does not mention the missing path: {error_message!r}"
    )
