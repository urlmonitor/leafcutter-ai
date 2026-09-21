"""
MODULE: _quick_fix_harness
GOAL: Shared fixtures for the /quick-fix workflow test family
      (test_quick_fix_*.py in this directory). Split out of the former
      monolithic test_quick_fix_workflow.py (1731 content lines, over the
      400-line check-file-size budget) so each phase-focused test file only
      needs to import what it drives.

Not a test module itself (no `test_` prefix) — pytest does not collect it.

WHAT THIS PROVIDES:
  - _JS_PATH / _SKILL_PATH: paths to the workflow script and its SKILL.md.
  - _js() / _skill(): full-text readers for source-contract assertions.
  - _phase_block(): slices a named phase's text out of quick-fix.js for
    scoped source-contract assertions (e.g. "does the Guards phase prompt,
    specifically, prohibit X").
  - run_workflow_under_e2: re-exported from unit_tests/_workflow_engine_harness
    so behavioral test files need only one import line.
  - _full_success_responses(): the one shared fixture of label-keyed stub
    responses that drives quick-fix.js end-to-end to a successful close.
    Individual behavioral tests override only the single label they are
    exercising via keyword args.
  - _labels(): pulls the ordered list of agent-call labels out of a
    HarnessResult.

TICKET: EPIC-BuildPipelineTestBackfill/02_bp600_quick_fix_test_coverage.md
(shared by all ACs the split-out test files cover — see each file's own
module docstring for its specific AC subset.)

ISOLATION NOTE: this module performs ONLY additive sys.path inserts, each
guarded by a `not in sys.path` check, and never touches sys.modules. There is
nothing here to restore between test files sharing a process — the known
"evicted module never restored" trap (see
unit_tests/commit_guardian/_bp_100k_3_iii_harness.py's _restore_module) does
not apply because this module never evicts anything.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_JS_PATH = _REPO_ROOT / "templates" / "workflows-js" / "quick-fix.js"
_SKILL_PATH = _REPO_ROOT / "templates" / "skills" / "quick-fix" / "SKILL.md"

# unit_tests/ must be on sys.path so _workflow_engine_harness is importable
# from this sub-package (unit_tests/workflows/).
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

__all__ = [
    "_JS_PATH",
    "_SKILL_PATH",
    "_js",
    "_skill",
    "_phase_block",
    "_full_success_responses",
    "_labels",
    "run_workflow_under_e2",
]


# ---------------------------------------------------------------------------
# Source-contract helpers
# ---------------------------------------------------------------------------

def _js() -> str:
    """Return the full text of quick-fix.js."""
    return _JS_PATH.read_text(encoding="utf-8")


def _skill() -> str:
    """Return the full text of the quick-fix SKILL.md."""
    return _SKILL_PATH.read_text(encoding="utf-8")


def _phase_block(js: str, phase_label: str, next_phase_label: str | None = None) -> str:
    """Extract text for a named phase block.

    Returns text from phase('<phase_label>') to (but not including)
    phase('<next_phase_label>'). If next_phase_label is None, returns from
    start marker to end of file. Returns '' when start marker is absent.
    """
    start_marker = f"phase('{phase_label}')"
    start = js.find(start_marker)
    if start == -1:
        return ""
    if next_phase_label is None:
        return js[start:]
    end_marker = f"phase('{next_phase_label}')"
    end = js.find(end_marker, start)
    return js[start:] if end == -1 else js[start:end]


# ---------------------------------------------------------------------------
# Behavioral (E2 harness) helpers
# ---------------------------------------------------------------------------

def _full_success_responses(**overrides: Any) -> dict[str, Any]:
    """Label-keyed stub responses that drive quick-fix.js end-to-end to a
    successful close (status: ok, PR opened).

    Every phase after Guards depends on data threaded from an earlier phase
    (worktreeRoot, ac_id, ac_path, parent_ac_path, testFile, commit_sha,
    changelog entry_path) — this fixture is the one place that data is
    defined, so individual tests only need to override the single label they
    are exercising and can trust the rest of the run to proceed normally.
    Callers pass keyword overrides keyed by label name, e.g.:

        _full_success_responses(**{"green-verify/strict": {...}})
    """
    responses: dict[str, Any] = {
        "isolation-check": {
            "status": "ok",
            "is_repo": True,
            "session_cwd": "/repo",
            "initial_branch": "fix/some-branch",
            "needs_isolation": False,
        },
        "guard-checks": {"status": "ok", "target_file_dirty": False, "dirty_files": []},
        "ac-creation": {
            "status": "ok",
            "ac_id": "BP-9001",
            "ac_path": "docs/acceptance-criteria/build-pipeline/bp-900/BP-9001.yaml",
            "parent_ac_path": "docs/acceptance-criteria/build-pipeline/bp-900/BP-900.yaml",
            "component_id": "build_pipeline",
            "ac_title": "Fix the bug",
        },
        "test-writer": {"status": "ok", "test_file": "unit_tests/test_bp9001.py"},
        "red-verify/strict": {
            "status": "ok",
            "passed": False,
            "outcome": "failed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_bp9001.py -v"
            ),
            "failure_message": "stub AssertionError: bug not fixed",
        },
        "python-coder/fix": {"status": "ok", "modified_files": ["stub/target.py"]},
        "green-verify/strict": {
            "status": "ok",
            "passed": True,
            "outcome": "passed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_bp9001.py -v"
            ),
        },
        # BP-600c-3-i collateral-damage check. Distinct from mutation-proof:
        # that asks "is the test coupled to the fix", this asks "did the fix
        # break the neighbours".
        "related-tests/strict": {
            "status": "ok",
            "passed": True,
            "outcome": "passed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/build_pipeline/ -v"
            ),
            "output_summary": "12 passed",
        },
        "mutation-proof": {
            "status": "ok",
            "red_without_fix": True,
            "green_with_fix_restored": True,
            "fix_restored": True,
        },
        "commit": {"status": "ok", "commit_sha": "abc123fix"},
        "changelog-author": {"status": "ok", "entry_path": "changelogs/BP-9001.md"},
        "commit/changelog": {"status": "ok", "commit_sha": "def456changelog"},
        "push-and-pr": {
            "status": "ok",
            "branch": "fix/some-branch",
            "pr_url": "https://github.com/org/repo/pull/42",
            "pr_opened": True,
        },
    }
    responses.update(overrides)
    return responses


def _labels(result) -> list[str | None]:
    """Convenience: the ordered list of agent-call labels from a HarnessResult."""
    return [c.label for c in result.agent_calls]
