"""
MODULE: test_build_workflow_output_paths
GOAL: Regression tests for TICKET-20260602-FixWorkflowNestedClaudeDir.
    Verifies that workflow JS files land under <output_root>/workflows/
    (not <output_root>/.claude/workflows/), that install_shims() maps
    ".claude/workflows" to "workflows" (not ".claude/workflows"), and
    that _compute_output_mappings() records the correct output key.

These tests should be RED before the four-location path fix and GREEN after.
TICKET: TICKET-20260602-FixWorkflowNestedClaudeDir
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
sys.path.insert(0, str(_SCRIPTS_DIR))

import build_phases
import build_helpers


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def output_root(tmp_path):
    """Simulate .leafcutter/ — the consolidated output directory."""
    d = tmp_path / ".leafcutter"
    d.mkdir(parents=True)
    return d


@pytest.fixture
def target_root(tmp_path):
    """Simulate the consumer project root."""
    return tmp_path


@pytest.fixture
def workflows_js_fixture(tmp_path, monkeypatch):
    """Patch TEMPLATES_DIR to expose a fake workflows-js/ directory."""
    templates_dir = tmp_path / "templates"
    wf_dir = templates_dir / "workflows-js"
    wf_dir.mkdir(parents=True)
    (wf_dir / "build-feature.js").write_text(
        "// build-feature workflow\nconsole.log('build-feature');",
        encoding="utf-8",
    )
    (wf_dir / "finalize-feature.js").write_text(
        "// finalize-feature workflow\nconsole.log('finalize-feature');",
        encoding="utf-8",
    )
    monkeypatch.setattr(build_phases, "TEMPLATES_DIR", templates_dir)
    monkeypatch.setattr(build_helpers, "TEMPLATES_DIR", templates_dir, raising=False)
    return templates_dir


# ---------------------------------------------------------------------------
# Test A — build_workflow_scripts() writes to output_root/workflows/, NOT .claude/
# ---------------------------------------------------------------------------

def test_build_workflow_scripts_writes_to_output_root_workflows(
    output_root, workflows_js_fixture, monkeypatch, capsys
):
    """JS files must land at <output_root>/workflows/, not <output_root>/.claude/workflows/.

    This is the primary regression check: the function receives output_root
    (i.e. .leafcutter/) and must write into output_root/workflows/.
    """
    monkeypatch.setenv("CLAUDE_CODE_VERSION", "2.2.0")
    config = {"workflows": {"enabled": True}}

    written = build_phases.build_workflow_scripts(
        output_root, config, dry_run=False, force=True
    )

    # Correct target: output_root/workflows/build-feature.js
    assert (output_root / "workflows" / "build-feature.js").exists(), (
        "Expected JS file at output_root/workflows/build-feature.js — "
        "got nothing (path fix not applied)"
    )
    assert (output_root / "workflows" / "finalize-feature.js").exists()
    assert written == 2

    # Broken path must NOT be created
    assert not (output_root / ".claude" / "workflows").exists(), (
        "Found output_root/.claude/workflows/ — the nested .claude/ path is still present "
        "(regression: fix not applied)"
    )


# ---------------------------------------------------------------------------
# Test B — install_shims() shim_map entry for workflows uses "workflows" not ".claude/workflows"
# ---------------------------------------------------------------------------

def test_install_shims_workflows_entry_maps_to_output_root_workflows(
    target_root, output_root, capsys
):
    """install_shims() must map '.claude/workflows' to 'workflows' in shim_map.

    The source path is output_root / 'workflows' (not output_root / '.claude' / 'workflows').
    We verify by pre-creating output_root/workflows/ and confirming the shim is
    created at target_root/.claude/workflows pointing to output_root/workflows.
    """
    # Pre-create the correct source directory so the shim is not skipped.
    source_dir = output_root / "workflows"
    source_dir.mkdir(parents=True)
    (source_dir / "sample.js").write_text("// sample", encoding="utf-8")

    results = build_helpers.install_shims(
        target_root=target_root,
        output_root=output_root,
        config={},
        dry_run=False,
        force=True,
    )

    # Find the workflows shim result.
    workflows_results = [r for r in results if r.get("canonical") == ".claude/workflows"]
    assert len(workflows_results) == 1, (
        "Expected exactly one shim result for .claude/workflows"
    )
    entry = workflows_results[0]

    # The target (output_rel) must be "workflows", not ".claude/workflows"
    assert entry["target"] == "workflows", (
        f"shim_map entry for .claude/workflows has wrong target '{entry['target']}' — "
        "expected 'workflows' (the fix changes '.claude/workflows' to 'workflows')"
    )

    # The shim must exist at target_root/.claude/workflows
    shim_path = target_root / ".claude" / "workflows"
    assert shim_path.exists() or shim_path.is_symlink(), (
        "Shim at target_root/.claude/workflows was not created"
    )


# ---------------------------------------------------------------------------
# Test C — install_shims() does NOT look for output_root/.claude/workflows
# ---------------------------------------------------------------------------

def test_install_shims_does_not_use_nested_claude_path(
    target_root, output_root, capsys
):
    """When output_root/.claude/workflows/ exists but output_root/workflows/ does NOT,
    the shim for .claude/workflows must be skipped (warn-and-skip behaviour).

    This asserts that the broken path (.claude/.claude/workflows) is never probed.
    """
    # Create the OLD broken source path only — not the correct one
    broken_dir = output_root / ".claude" / "workflows"
    broken_dir.mkdir(parents=True)
    (broken_dir / "build-feature.js").write_text("// broken", encoding="utf-8")

    results = build_helpers.install_shims(
        target_root=target_root,
        output_root=output_root,
        config={},
        dry_run=False,
        force=True,
    )

    # The shim for .claude/workflows should be absent (source missing at correct path)
    workflows_results = [r for r in results if r.get("canonical") == ".claude/workflows"]
    # Either absent (skipped due to missing source) or not pointing to .claude/workflows
    for r in workflows_results:
        assert r.get("target") != ".claude/workflows", (
            "install_shims() is still using the broken '.claude/workflows' source path"
        )


# ---------------------------------------------------------------------------
# Test D — _compute_output_mappings() records output_root/workflows/<name>, not .claude/
# ---------------------------------------------------------------------------

def test_compute_output_mappings_workflow_js_uses_correct_output_key(
    tmp_path, workflows_js_fixture
):
    """_compute_output_mappings() must record workflow JS outputs under
    <target_root>/workflows/<name>, not <target_root>/.claude/workflows/<name>.
    """
    # target_root here represents output_root passed to _compute_output_mappings
    fake_target = tmp_path / ".leafcutter"
    fake_target.mkdir(parents=True)

    # We need a minimal package_root layout
    package_root = tmp_path / "leafcutter"
    package_root.mkdir()
    (package_root / "config").mkdir()
    templates_dir = workflows_js_fixture  # already patched on build_helpers

    mappings = build_helpers._compute_output_mappings(
        package_root=package_root,
        templates_dir=templates_dir,
        target_root=fake_target,
        config={},
    )

    # Collect all output keys that relate to workflow JS
    workflow_js_keys = [k for k in mappings if "build-feature.js" in k or "finalize-feature.js" in k]

    assert len(workflow_js_keys) >= 1, (
        "_compute_output_mappings() produced no entries for workflow JS files"
    )

    for key in workflow_js_keys:
        # The key should not contain '.claude/workflows' — it should be just 'workflows'
        assert ".claude/workflows" not in key, (
            f"_compute_output_mappings() emitted broken output key '{key}' containing "
            "'.claude/workflows' — fix not applied to _compute_output_mappings()"
        )
        assert "workflows/" in key, (
            f"_compute_output_mappings() output key '{key}' does not contain 'workflows/'"
        )
