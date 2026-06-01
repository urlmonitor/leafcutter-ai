"""
MODULE: test_build_workflow_phase
GOAL: Unit tests for build_workflow_scripts phase — verifying opt-in flag gate,
    version detection logic, file copying, and compare-before-write idempotency.
TICKET: EPIC-FlattenSupervisorChain/01_build_workflow_phase.md
"""

from __future__ import annotations

import sys
from pathlib import Path
import tempfile

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def target_root(tmp_path):
    """Fresh temporary target directory."""
    return tmp_path / "target"


@pytest.fixture
def workflows_js_dir(tmp_path, monkeypatch):
    """Patch TEMPLATES_DIR so build_workflow_scripts sees a fake workflows-js/."""
    templates_dir = tmp_path / "templates"
    wf_dir = templates_dir / "workflows-js"
    wf_dir.mkdir(parents=True)

    # Seed two dummy JS workflow scripts.
    (wf_dir / "build-feature.js").write_text(
        "// build-feature workflow\nconsole.log('build-feature');",
        encoding="utf-8",
    )
    (wf_dir / "finalize-feature.js").write_text(
        "// finalize-feature workflow\nconsole.log('finalize-feature');",
        encoding="utf-8",
    )

    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)
    return wf_dir


# ---------------------------------------------------------------------------
# Test 1 — opt-in flag absent or false → phase skipped
# ---------------------------------------------------------------------------

def test_workflow_scripts_skipped_when_not_enabled(
    target_root, workflows_js_dir, capsys
):
    """When skills_config workflows.enabled is false or absent, skip silently."""
    # Case A: key absent entirely.
    config_absent = {}
    written = build_phases.build_workflow_scripts(
        target_root, config_absent, dry_run=False, force=True
    )
    captured = capsys.readouterr()
    assert written == 0
    assert not (target_root / ".claude" / "workflows").exists()
    assert "skipped (not enabled" in captured.out

    # Case B: workflows.enabled explicitly false.
    config_false = {"workflows": {"enabled": False}}
    written = build_phases.build_workflow_scripts(
        target_root, config_false, dry_run=False, force=True
    )
    captured = capsys.readouterr()
    assert written == 0
    assert not (target_root / ".claude" / "workflows").exists()
    assert "skipped (not enabled" in captured.out


# ---------------------------------------------------------------------------
# Test 2 — enabled + version ok → JS files installed
# ---------------------------------------------------------------------------

def test_workflow_scripts_installed_when_enabled_and_version_ok(
    target_root, workflows_js_dir, monkeypatch, capsys
):
    """When enabled and Claude Code version >= 2.1.154, JS files are copied."""
    monkeypatch.setenv("CLAUDE_CODE_VERSION", "2.1.154")
    config = {"workflows": {"enabled": True}}

    written = build_phases.build_workflow_scripts(
        target_root, config, dry_run=False, force=True
    )
    captured = capsys.readouterr()

    assert written == 2
    assert (target_root / ".claude" / "workflows" / "build-feature.js").exists()
    assert (target_root / ".claude" / "workflows" / "finalize-feature.js").exists()
    assert "Workflow scripts:" in captured.out
    assert "installed" in captured.out


# ---------------------------------------------------------------------------
# Test 3 — enabled + version below minimum → warning, files NOT installed
# ---------------------------------------------------------------------------

def test_workflow_scripts_skipped_when_version_below_minimum(
    target_root, workflows_js_dir, monkeypatch, capsys
):
    """When Claude Code version < 2.1.154, warn and skip file copying."""
    monkeypatch.setenv("CLAUDE_CODE_VERSION", "2.0.0")
    config = {"workflows": {"enabled": True}}

    written = build_phases.build_workflow_scripts(
        target_root, config, dry_run=False, force=True
    )
    captured = capsys.readouterr()

    assert written == 0
    workflows_dir = target_root / ".claude" / "workflows"
    assert not workflows_dir.exists() or list(workflows_dir.glob("*.js")) == []
    assert "Claude Code >= 2.1.154 required" in captured.out


# ---------------------------------------------------------------------------
# Test 4 — enabled + version unknown (env absent, subprocess fails) → fail-open
# ---------------------------------------------------------------------------

def test_workflow_scripts_installed_when_version_unknown(
    target_root, workflows_js_dir, monkeypatch, capsys
):
    """When version is undetectable, emit warning and install files (fail-open)."""
    monkeypatch.delenv("CLAUDE_CODE_VERSION", raising=False)

    # Mock subprocess to simulate `claude --version` failing.
    import subprocess as _subprocess

    def _failing_run(*args, **kwargs):
        raise FileNotFoundError("claude not found")

    monkeypatch.setattr(_subprocess, "run", _failing_run)

    config = {"workflows": {"enabled": True}}

    written = build_phases.build_workflow_scripts(
        target_root, config, dry_run=False, force=True
    )
    captured = capsys.readouterr()

    # Files should be installed (fail-open).
    assert written == 2
    assert (target_root / ".claude" / "workflows" / "build-feature.js").exists()
    # Warning must be present.
    assert "version unknown" in captured.out.lower() or "unknown" in captured.out.lower()


# ---------------------------------------------------------------------------
# Test 5 — idempotency: second run produces no writes
# ---------------------------------------------------------------------------

def test_build_workflow_phase_idempotent(
    target_root, workflows_js_dir, monkeypatch
):
    """Running the phase twice with unchanged source files writes 0 files on run 2."""
    monkeypatch.setenv("CLAUDE_CODE_VERSION", "2.2.0")
    config = {"workflows": {"enabled": True}}

    # First run — should write 2 files.
    written_first = build_phases.build_workflow_scripts(
        target_root, config, dry_run=False, force=True
    )
    assert written_first == 2

    # Reset the uptodate counter so we can measure it.
    build_phases.reset_uptodate_count()

    # Second run — content identical, compare-before-write should skip.
    written_second = build_phases.build_workflow_scripts(
        target_root, config, dry_run=False, force=True
    )
    assert written_second == 0
    # The uptodate counter should reflect 2 skipped files.
    assert build_phases.get_uptodate_count() == 2
