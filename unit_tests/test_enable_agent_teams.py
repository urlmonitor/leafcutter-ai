"""
Tests for the Agent Teams feature enablement in templates/settings.json.

Verifies that:
- templates/settings.json contains the CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS env var
- The env block is at the top level of the JSON object
- templates/settings.json remains valid JSON after the env block addition
- build_claude_settings() copies the env block to the target settings.json
- docs/reference/agent-teams-constraints.md exists with all required sections
"""
from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SETTINGS_TEMPLATE = REPO_ROOT / "templates" / "settings.json"
AGENT_TEAMS_DOC = REPO_ROOT / "docs" / "reference" / "agent-teams-constraints.md"

# Required sections in the constraints reference doc (headings, case-insensitive substring match)
REQUIRED_DOC_SECTIONS = [
    "experimental",
    "one team",
    "nested",
    "token",
    "permission",
    "version",
    "workflow",
]


def _load_settings() -> dict[str, Any]:
    """Load and return the parsed settings.json template."""
    return json.loads(SETTINGS_TEMPLATE.read_text(encoding="utf-8"))


def test_settings_json_is_valid_json_after_env_addition() -> None:
    """templates/settings.json must remain valid JSON after adding the env block."""
    assert SETTINGS_TEMPLATE.exists(), (
        f"templates/settings.json not found at {SETTINGS_TEMPLATE}"
    )
    data = _load_settings()
    assert isinstance(data, dict), "settings.json root must be a JSON object"


def test_settings_template_contains_agent_teams_env_var() -> None:
    """templates/settings.json must contain CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS='1' in env block."""
    data = _load_settings()
    assert "env" in data, (
        "settings.json is missing the top-level 'env' key. "
        "Add: \"env\": {\"CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS\": \"1\"}"
    )
    env_block = data["env"]
    assert isinstance(env_block, dict), "'env' must be a JSON object"
    assert "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS" in env_block, (
        "settings.json env block is missing 'CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS'. "
        f"Current env keys: {list(env_block.keys())}"
    )
    assert env_block["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"] == "1", (
        "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS must be set to '1' (string), "
        f"got: {env_block['CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS']!r}"
    )


def test_env_block_is_at_top_level() -> None:
    """The env block must be a top-level key in settings.json, not nested."""
    data = _load_settings()
    assert "env" in data, (
        "settings.json is missing the top-level 'env' key."
    )
    # Confirm it is NOT nested inside hooks or allowedTools
    hooks = data.get("hooks", {})
    assert "env" not in hooks, (
        "'env' block must be at the top level, not inside 'hooks'."
    )


def test_build_claude_settings_deploys_env_block() -> None:
    """build_claude_settings() must copy the full template including the env block."""
    import sys
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    from build_claude_settings import build_claude_settings  # noqa: PLC0415

    with tempfile.TemporaryDirectory() as tmp_dir:
        target_root = Path(tmp_dir)
        # Run the build phase
        written = build_claude_settings(
            target_root=target_root,
            config={},
            dry_run=False,
            force=True,
        )
        assert written == 1, (
            f"build_claude_settings should write exactly 1 file, wrote {written}"
        )
        deployed_settings = target_root / "settings.json"
        assert deployed_settings.exists(), (
            "build_claude_settings did not create settings.json in target root"
        )
        deployed_data = json.loads(deployed_settings.read_text(encoding="utf-8"))
        assert "env" in deployed_data, (
            "Deployed settings.json is missing the 'env' block. "
            "build_claude_settings must copy the full template."
        )
        assert deployed_data["env"].get("CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS") == "1", (
            "Deployed settings.json env block is missing or incorrect "
            "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS value."
        )


def test_reference_doc_covers_all_constraints() -> None:
    """docs/reference/agent-teams-constraints.md must exist and cover all required sections."""
    assert AGENT_TEAMS_DOC.exists(), (
        f"Reference doc not found at {AGENT_TEAMS_DOC}. "
        "documentation-expert must create it."
    )
    content = AGENT_TEAMS_DOC.read_text(encoding="utf-8").lower()
    for section_keyword in REQUIRED_DOC_SECTIONS:
        assert section_keyword.lower() in content, (
            f"Reference doc is missing content about '{section_keyword}'. "
            f"Required keywords: {REQUIRED_DOC_SECTIONS}"
        )
