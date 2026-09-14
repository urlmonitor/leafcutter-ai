"""
MODULE: test_quick_fix_guard_halts
GOAL: /quick-fix (BP-600 ACs) coverage for the Guards phase's halt
      conditions: the dirty-target-file guard (BP-600a-3), the
      unrelated-dirty-files carve-out (BP-600a-3-i), and the harness-driven
      behavioral proof that a 'blocked' guard/isolation response actually
      halts the run rather than merely being mentioned in a prompt no branch
      inspects.

Split out of the former monolithic test_quick_fix_workflow.py (1731 content
lines) — see _quick_fix_harness.py's module docstring for the shared-fixture
rationale and the sibling files covering the rest of the BP-600 AC set.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
ACs: BP-600a-3, BP-600a-3-i
"""

from __future__ import annotations

import sys
from pathlib import Path

# unit_tests/workflows/ must be on sys.path so the flat sibling import below
# resolves — this package has __init__.py, so pytest's rootdir insertion
# does not add it automatically (mirrors the unit_tests/ insertion pattern
# _quick_fix_harness.py itself uses for _workflow_engine_harness).
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _quick_fix_harness import (  # noqa: E402
    _JS_PATH,
    _full_success_responses,
    _js,
    _labels,
    _phase_block,
    _skill,
    run_workflow_under_e2,
)


# ===========================================================================
# BP-600a-3 — halts when target file has uncommitted changes
# ===========================================================================

class TestBP600a3UncommittedChangesGuard:
    """BP-600a-3: Halts when target file has uncommitted changes."""

    def test_ac_bp600a3_returns_blocked_when_dirty(self):
        # covers: BP-600a-3
        """quick-fix.js must return status:'blocked' when target file is dirty."""
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        assert "status: 'blocked'" in guards_block or '"blocked"' in guards_block, (
            "Guards phase must return blocked status when target file is dirty (BP-600a-3)."
        )

    def test_ac_bp600a3_skill_suggests_commit_or_stash(self):
        # covers: BP-600a-3
        """SKILL.md must suggest commit or stash when target file is dirty."""
        skill = _skill()
        assert "commit or stash" in skill or "stash" in skill, (
            "SKILL.md must suggest 'commit or stash' when target file is dirty (BP-600a-3)."
        )

    def test_ac_bp600a3_guard_schema_has_dirty_flag(self):
        # covers: BP-600a-3
        """GUARD_SCHEMA in quick-fix.js must include target_file_dirty property."""
        js = _js()
        assert "target_file_dirty" in js, (
            "GUARD_SCHEMA must include target_file_dirty property for BP-600a-3 check."
        )


# ===========================================================================
# BP-600a-3-i — proceeds when only unrelated files are dirty
# ===========================================================================

class TestBP600a3iUnrelatedDirtyFiles:
    """BP-600a-3-i: Proceeds when only unrelated files are dirty."""

    def test_ac_bp600a3i_check_scoped_to_target_file(self):
        # covers: BP-600a-3-i
        """Guard must scope dirty-file check to the target file, not all files."""
        js = _js()
        guards_block = _phase_block(js, "Guards", "AC Creation")
        # The guard checks if target_file appears in git status output — not all dirty files
        assert "target_file" in guards_block, (
            "Guards must scope the uncommitted-changes check to target_file only, "
            "allowing unrelated dirty files to exist (BP-600a-3-i)."
        )

    def test_ac_bp600a3i_skill_commit_stages_three_files_only(self):
        # covers: BP-600a-3-i
        """SKILL.md Phase 5 must stage exactly three specified files only."""
        skill = _skill()
        assert "Stage and commit exactly these three files" in skill or \
               "Do not stage any other files" in skill, (
            "SKILL.md commit phase must be explicit about staging only the quick-fix "
            "files (AC YAML, test file, fix) — unrelated dirty files must not be staged "
            "(BP-600a-3-i)."
        )


# ===========================================================================
# Behavioral (harness-driven) coverage
#
# Supersedes test_ac_bp600a3_checks_git_status_for_target, which grepped
# the Guards prompt text for the string 'git status --porcelain' — a string
# that could remain in a prompt no branch of the control flow ever
# inspects the response of. These tests drive the workflow with 'blocked'
# guard/isolation responses and confirm the run actually halts and does not
# proceed to the next phase.
# ===========================================================================

class TestBP600WorkflowGuardsHalt:
    """Behavioral coverage for guard halts: BP-600a-3 (dirty target file) and
    the two isolation halts.
    """

    def test_ac_bp600a3_dirty_target_file_halts_before_ac_creation(self):
        # covers: BP-600a-3
        """A guard-checks response reporting the target file dirty must halt
        the run with status: blocked, and must not reach AC Creation."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses=_full_success_responses(
                **{
                    "guard-checks": {
                        "status": "blocked",
                        "target_file_dirty": True,
                        "dirty_files": ["stub/target.py"],
                        "message": "target file has uncommitted changes",
                    }
                }
            ),
        )
        assert result.result is not None and result.result.get("status") == "blocked", (
            f"Expected status: blocked, got: {result.result}"
        )
        labels = _labels(result)
        assert "ac-creation" not in labels, (
            "AC Creation must not be dispatched when the guard reports the "
            f"target file dirty (BP-600a-3). Labels dispatched: {labels}"
        )

    def test_ac_bp600a2_blocked_isolation_check_halts_with_no_downstream_dispatch(self):
        # covers: BP-600a-2
        """A 'blocked' isolation-check response must halt immediately — no
        self-isolate, no guard-checks, nothing downstream."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses={
                "isolation-check": {
                    "status": "blocked",
                    "is_repo": True,
                    "session_cwd": "/repo",
                    "needs_isolation": False,
                    "message": "isolation-check refused to proceed",
                }
            },
        )
        assert result.result is not None and result.result.get("status") == "blocked"
        assert result.dispatch_count == 1, (
            "A blocked isolation-check must halt before any further dispatch "
            f"(BP-600a-2). Labels dispatched: {_labels(result)}"
        )

    def test_ac_bp600a2_blocked_self_isolate_halts_with_no_downstream_dispatch(self):
        # covers: BP-600a-2
        """A 'blocked' self-isolate response must halt immediately with
        halt_reason 'isolation_failed' — no guard-checks, nothing downstream."""
        result = run_workflow_under_e2(
            _JS_PATH,
            label_responses={
                "isolation-check": {
                    "status": "ok",
                    "is_repo": False,
                    "session_cwd": "/untracked/workspace",
                    "initial_branch": "",
                    "needs_isolation": True,
                },
                "self-isolate": {
                    "status": "blocked",
                    "worktree_root": "",
                    "branch": "",
                    "message": "worktree creation failed",
                },
            },
        )
        assert result.result is not None
        assert result.result.get("status") == "blocked"
        assert result.result.get("halt_reason") == "isolation_failed"
        assert result.dispatch_count == 2, (
            "A blocked self-isolate must halt before guard-checks or any later "
            f"phase. Labels dispatched: {_labels(result)}"
        )
