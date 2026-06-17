"""
Tests for templates/settings.json allowedTools allowlist.

Verifies that the settings.json template ships a well-formed, safe
allowedTools block containing the minimum required entries for workflow
phase agents, and excludes any destructive command patterns.
"""
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_TEMPLATE = REPO_ROOT / "templates" / "settings.json"

# Minimum required allowedTools entries per acceptance criteria
REQUIRED_ENTRIES = [
    "Bash(git status*)",
    "Bash(git commit*)",
    "Bash(gh pr create*)",
    "Bash(python -m pytest*)",
]

# Forbidden patterns that must never appear in the allowlist
FORBIDDEN_PATTERNS = [
    "git push --force",
    "git reset --hard",
    "rm -rf",
]


def _load_settings() -> dict:
    """Load and return the parsed settings.json template."""
    return json.loads(SETTINGS_TEMPLATE.read_text(encoding="utf-8"))


def test_settings_json_is_valid_json() -> None:
    """templates/settings.json must parse without error."""
    assert SETTINGS_TEMPLATE.exists(), (
        f"templates/settings.json not found at {SETTINGS_TEMPLATE}"
    )
    data = _load_settings()
    assert isinstance(data, dict), "settings.json root must be a JSON object"


def test_settings_json_contains_allowedTools() -> None:
    """templates/settings.json must have a non-empty allowedTools list."""
    data = _load_settings()
    assert "allowedTools" in data, (
        "settings.json is missing the 'allowedTools' key"
    )
    allowed = data["allowedTools"]
    assert isinstance(allowed, list), "'allowedTools' must be a JSON array"
    assert len(allowed) > 0, "'allowedTools' must be a non-empty list"


def test_settings_json_contains_required_entries() -> None:
    """allowedTools must include at minimum the entries required by acceptance criteria."""
    data = _load_settings()
    allowed: list[str] = data.get("allowedTools", [])
    for entry in REQUIRED_ENTRIES:
        assert entry in allowed, (
            f"Required allowedTools entry '{entry}' not found in settings.json. "
            f"Current entries: {allowed}"
        )


def test_settings_json_no_dangerous_commands() -> None:
    """allowedTools must NOT contain patterns matching destructive commands."""
    data = _load_settings()
    allowed: list[str] = data.get("allowedTools", [])
    allowed_str = " ".join(allowed)
    for pattern in FORBIDDEN_PATTERNS:
        assert pattern not in allowed_str, (
            f"Forbidden pattern '{pattern}' found in allowedTools. "
            "Destructive commands must not be pre-approved."
        )
