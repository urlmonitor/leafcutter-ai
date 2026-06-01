"""
MODULE: test_build_changelog_placeholder
GOAL: Verify that build.py correctly injects changelogs_dir from commit_guardian.json
    as changelog_folder in the config dict, and that the changelog-agent template
    resolves {{config.changelog_folder}} during compilation.
BUSINESS CONTEXT: These tests guard the placeholder-injection fix added by
    TICKET-20260530-ChangelogAgentPlaceholderFix. They confirm that the changelog-agent
    template uses the project-configured directory rather than the hardcoded "changelogs/"
    literal, preventing silent version-bump failures when a consumer uses a different
    changelog directory.
ARCHITECTURE: Tests import build.py and template_compiler.py helpers directly.
    Filesystem writes are isolated to tmp_path. The _inject_changelogs_dir function is
    tested in isolation (unit tests) and the full placeholder resolution is tested via
    compile_agent_template (integration-style).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_TEMPLATES_DIR = _REPO_ROOT / "templates"

# Ensure scripts/ is importable
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 — after sys.path setup
from template_compiler import compile_agent_template  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cg_json(tmp_path: Path, changelogs_dir: str) -> Path:
    """Create a minimal commit_guardian.json in the expected location.

    Lays out the file at the primary path read by _inject_changelogs_dir:
    ``<package_root>/templates/scripts/commit_guardian/commit_guardian.json``.
    """
    cg_dir = tmp_path / "templates" / "scripts" / "commit_guardian"
    cg_dir.mkdir(parents=True)
    cg_file = cg_dir / "commit_guardian.json"
    cg_file.write_text(
        json.dumps({"changelogs_dir": changelogs_dir}),
        encoding="utf-8",
    )
    return tmp_path  # return the fake package_root


# ---------------------------------------------------------------------------
# Unit tests — _inject_changelogs_dir
# ---------------------------------------------------------------------------


def test_inject_changelogs_dir_reads_from_commit_guardian(tmp_path: Path) -> None:
    """_inject_changelogs_dir reads changelogs_dir from commit_guardian.json.

    Given a commit_guardian.json with {"changelogs_dir": "changelogs"},
    the config dict must have changelog_folder == "changelogs/".
    """
    package_root = _make_cg_json(tmp_path, "changelogs")
    config: dict = {}
    _build._inject_changelogs_dir(config, package_root)
    assert config["changelog_folder"] == "changelogs/", (
        f"Expected 'changelogs/' but got {config.get('changelog_folder')!r}"
    )


def test_inject_changelogs_dir_custom_path(tmp_path: Path) -> None:
    """_inject_changelogs_dir supports a custom changelogs_dir value.

    Given a commit_guardian.json with {"changelogs_dir": "release_notes"},
    the config dict must have changelog_folder == "release_notes/".
    """
    package_root = _make_cg_json(tmp_path, "release_notes")
    config: dict = {}
    _build._inject_changelogs_dir(config, package_root)
    assert config["changelog_folder"] == "release_notes/", (
        f"Expected 'release_notes/' but got {config.get('changelog_folder')!r}"
    )


def test_inject_changelogs_dir_trailing_slash_normalised(tmp_path: Path) -> None:
    """_inject_changelogs_dir normalises a trailing slash (no double slash).

    Given {"changelogs_dir": "changelogs/"} (already has trailing slash),
    the config dict must have changelog_folder == "changelogs/" (not "changelogs//").
    """
    package_root = _make_cg_json(tmp_path, "changelogs/")
    config: dict = {}
    _build._inject_changelogs_dir(config, package_root)
    assert config["changelog_folder"] == "changelogs/", (
        f"Expected 'changelogs/' (no double slash) but got {config.get('changelog_folder')!r}"
    )


def test_inject_changelogs_dir_fallback_when_json_absent() -> None:
    """_inject_changelogs_dir falls back to 'changelogs/' when JSON is absent.

    When package_root points to a nonexistent directory, no exception is raised
    and changelog_folder defaults to 'changelogs/'.
    """
    config: dict = {}
    _build._inject_changelogs_dir(config, Path("/nonexistent_package_root_xyz"))
    assert config["changelog_folder"] == "changelogs/", (
        f"Expected fallback 'changelogs/' but got {config.get('changelog_folder')!r}"
    )


# ---------------------------------------------------------------------------
# Integration tests — compile_agent_template resolves the placeholder
# ---------------------------------------------------------------------------


def test_changelog_folder_placeholder_resolved_in_compiled_template() -> None:
    """Compiled changelog-agent template must not contain raw {{config.changelog_folder}}.

    After compilation with changelog_folder='changelogs/' the placeholder must be
    replaced with the literal value, and 'changelogs/' must appear in the output.
    """
    template_path = _TEMPLATES_DIR / "agents" / "changelog-agent.md"
    if not template_path.exists():
        pytest.skip(f"Template not found: {template_path}")

    config = {
        "changelog_folder": "changelogs/",
        "changelog_categories_path": ".claude/changelog_categories.md",
    }
    compiled = compile_agent_template(template_path, config)

    assert "{{config.changelog_folder}}" not in compiled, (
        "Raw placeholder '{{config.changelog_folder}}' found in compiled template — "
        "injection did not occur."
    )
    assert "changelogs/" in compiled, (
        "Expected literal 'changelogs/' in compiled output but it was absent."
    )


def test_changelog_folder_custom_path_resolved_in_compiled_template() -> None:
    """Compiled changelog-agent template resolves a custom changelog_folder correctly.

    With changelog_folder='release_notes/', the emit_entry.py call and git add line
    must contain 'release_notes/' and must NOT contain 'changelogs/' in those positions.
    """
    template_path = _TEMPLATES_DIR / "agents" / "changelog-agent.md"
    if not template_path.exists():
        pytest.skip(f"Template not found: {template_path}")

    config = {
        "changelog_folder": "release_notes/",
        "changelog_categories_path": ".claude/changelog_categories.md",
    }
    compiled = compile_agent_template(template_path, config)

    assert "{{config.changelog_folder}}" not in compiled, (
        "Raw placeholder '{{config.changelog_folder}}' found in compiled template — "
        "injection did not occur."
    )
    assert "release_notes/" in compiled, (
        "Expected 'release_notes/' in compiled output but it was absent."
    )
    # Specifically check the emit_entry.py invocation and git add do not have hardcoded changelogs/
    # by verifying changelogs/ does NOT appear in lines that reference emit_entry.py or git add
    lines_with_emit = [
        ln for ln in compiled.splitlines()
        if "emit_entry.py" in ln or "changelog-dir" in ln or ('git add' in ln and 'changelogs' in ln.lower())
    ]
    for line in lines_with_emit:
        assert "changelogs/" not in line, (
            f"Found hardcoded 'changelogs/' in a coder-injected line: {line!r}"
        )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-30 [test-writer/TICKET-20260530-ChangelogAgentPlaceholderFix]:
#   Created module. Six tests cover the four acceptance criteria:
#   _inject_changelogs_dir reads from commit_guardian.json (default and custom paths),
#   normalises trailing slashes, falls back when JSON is absent,
#   and the compile_agent_template integration confirms placeholder resolution
#   for both default and custom changelog_folder values.
# ====================================================================
