"""
MODULE: unit_tests/workflows/test_inf_700a_1_i.py
GOAL: RED behavioral test baseline for INF-700a-1-i — "No way of finishing
    work is left quietly without a routing step" (the anti-partial-wiring
    criterion).

AC: docs/acceptance-criteria/infrastructure/INF-400-agent-learning/INF-700a-1-i.yaml

CONTRACT THIS TEST FILE ESTABLISHES FOR python-coder (TDD: this is the spec):

  Per this AC's own it_requirements ("PER-PATH BEHAVIOURAL COVERAGE, not one
  test times five names"), every completion path that is wired must dispatch
  its own knowledge-routing-step agent() call — the SAME label contract
  test_inf_700a_1.py establishes for fast-lane-ship.js — before the phase
  that publishes its own output. This module is deliberately PARAMETRISED
  (one test method per script, not a loop hidden inside one assertion), and
  drives two of the five named completion paths for which this repository
  already has an established, exercised full-success E2 harness fixture
  (fast-lane-ship.js, quick-fix.js). The remaining three
  (build-epic.js, build-ticket.js, finalize-feature.js) need their own
  full-success fixtures built out before they can be added here in the same
  parametrised shape — see the NOTE at the bottom of this file.

  Per this AC's it_requirements ("THE MECHANISM THAT FAILS ... A BUILD-TIME
  GUARD"), a second module (unit_tests/build_guards/
  test_inf_700a_1_i_completion_path_guard.py) specifies the companion
  build-time guard: a pure function, modelled on
  scripts/build_phases.py's check_command_reachability
  (unit_tests/build_guards/test_command_reachability_guard.py), that
  enumerates templates/workflows-js/*.js and blocks the build when an
  artefact is neither wired nor listed as excluded (with a reason) in
  config/guardrail_gates.yaml.

RED baseline: no "knowledge-routing-step" label is dispatched anywhere
today, and no completion-path guard function exists yet.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import HarnessResult, run_workflow_under_e2  # noqa: E402

_FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"
_QUICK_FIX_JS = _REPO_ROOT / "templates" / "workflows-js" / "quick-fix.js"
_TIMEOUT = 30


def _calls_with_label(result: HarnessResult, label: str) -> list:
    return [c for c in result.agent_calls if c.label == label]


def _dispatched_labels(result: HarnessResult) -> list:
    return [c.label for c in result.agent_calls]


def _fast_lane_ship_full_success(ac_id: str) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """(script_path, label_responses, args) driving fast-lane-ship.js to a
    successful close. See test_inf_700a_1.py for the full derivation of this
    fixture; kept in sync deliberately by hand (each completion path is a
    genuinely different script with its own phase names)."""
    label_responses: dict[str, Any] = {
        "fastlane-worktree": {
            "worktree_path": "/tmp/inf700a1i-fastlane-worktree",
            "branch": "fast-lane/test-inf700a1i",
            "ac_store_path": "/tmp/inf700a1i-fastlane-worktree/docs/acceptance-criteria",
            "created": True,
        },
        "resolve-connected": {"ac_ids": [ac_id], "message": "1 to build"},
        "claim-connected": {
            "claimed": [ac_id],
            "excluded_claimed": [],
            "target_refused": False,
            "message": "claimed 1 AC",
        },
        "test-writer-connected": {
            "status": "ok",
            "tests_written": ["unit_tests/x/test_stub.py"],
            "gate_passed": True,
            "reason": None,
            "green_at_baseline": [],
            "message": "red baseline established",
        },
        "coder-connected": {
            "status": "ok",
            "files_modified": [],
            "green": True,
            "coverage_ok": True,
            "uncovered_ac_ids": [],
            "message": "implemented",
        },
        "fastlane-review": {
            "verdict_obtained": True,
            "high_findings": [],
            "medium_findings": [],
            "low_suppressed_count": 0,
            "message": "clean review",
        },
        "fastlane-commit": {
            "status": "ok",
            "branch": "fast-lane/test-inf700a1i",
            "message": "committed",
        },
        "fastlane-pr": {
            "status": "ok",
            "pr_url": "https://github.com/example/example/pull/1",
            "message": "PR opened",
        },
    }
    return _FAST_LANE_SHIP_JS, label_responses, {"ac": ac_id}


def _quick_fix_full_success() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    """(script_path, label_responses, args) driving quick-fix.js to a
    successful close. Mirrors _full_success_responses() in
    unit_tests/workflows/test_quick_fix_workflow.py."""
    label_responses: dict[str, Any] = {
        "isolation-check": {
            "status": "ok",
            "is_repo": True,
            "session_cwd": "/repo",
            "initial_branch": "fix/inf700a1i-branch",
            "needs_isolation": False,
        },
        "guard-checks": {"status": "ok", "target_file_dirty": False, "dirty_files": []},
        "ac-creation": {
            "status": "ok",
            "ac_id": "INF-9114",
            "ac_path": "docs/acceptance-criteria/infrastructure/INF-9114.yaml",
            "parent_ac_path": "docs/acceptance-criteria/infrastructure/INF-9114-parent.yaml",
            "component_id": "infrastructure",
            "ac_title": "Fixture fix",
        },
        "test-writer": {"status": "ok", "test_file": "unit_tests/test_inf9114.py"},
        "red-verify/strict": {
            "status": "ok",
            "passed": False,
            "outcome": "failed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_inf9114.py -v"
            ),
            "failure_message": "stub AssertionError: bug not fixed",
        },
        "python-coder/fix": {"status": "ok", "modified_files": ["stub/target.py"]},
        "green-verify/strict": {
            "status": "ok",
            "passed": True,
            "outcome": "passed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/test_inf9114.py -v"
            ),
        },
        "related-tests/strict": {
            "status": "ok",
            "passed": True,
            "outcome": "passed",
            "strict_command_run": (
                "AC_ENFORCE_STRICT=1 python -m pytest unit_tests/infrastructure/ -v"
            ),
            "output_summary": "12 passed",
        },
        "mutation-proof": {
            "status": "ok",
            "red_without_fix": True,
            "green_with_fix_restored": True,
            "fix_restored": True,
        },
        "commit": {"status": "ok", "commit_sha": "abc123inf700a1i"},
        "changelog-author": {"status": "ok", "entry_path": "changelogs/INF-9114.md"},
        "commit/changelog": {"status": "ok", "commit_sha": "def456inf700a1i"},
        "push-and-pr": {
            "status": "ok",
            "branch": "fix/inf700a1i-branch",
            "pr_url": "https://github.com/org/repo/pull/99",
            "pr_opened": True,
        },
    }
    return _QUICK_FIX_JS, label_responses, {}


# ---------------------------------------------------------------------------
# Per-path table: (script name, fixture builder, the "publish" label the
# knowledge-routing-step dispatch must precede).
# ---------------------------------------------------------------------------

_ROUTING_LABEL = "knowledge-routing-step"

_PATH_CASES: dict[str, tuple[Any, str]] = {
    "fast-lane-ship": (lambda: _fast_lane_ship_full_success("INF-9115a"), "fastlane-commit"),
    "quick-fix": (lambda: _quick_fix_full_success(), "commit"),
}


class TestEachCompletionPathWritesTheLearningToItsDestination(unittest.TestCase):
    """AC INF-700a-1-i: parametrised over completion paths (per-path
    behavioural coverage, NOT one test naming five paths). For each, drive
    the path to completion under the engine harness and assert a
    knowledge-routing-step dispatch occurs before the path's own publish
    step."""

    def test_fast_lane_ship_dispatches_knowledge_routing_before_publish(self) -> None:
        # covers: INF-700a-1-i
        # angle: criterion
        self._assert_path_dispatches_routing("fast-lane-ship")

    def test_quick_fix_dispatches_knowledge_routing_before_publish(self) -> None:
        # covers: INF-700a-1-i
        # angle: criterion
        self._assert_path_dispatches_routing("quick-fix")

    def _assert_path_dispatches_routing(self, case_name: str) -> None:
        fixture_builder, publish_label = _PATH_CASES[case_name]
        script_path, label_responses, args = fixture_builder()
        label_responses[_ROUTING_LABEL] = {
            "read": 1,
            "written": 1,
            "unwritten": 0,
            "case": "completed",
        }
        result = run_workflow_under_e2(
            script_path, timeout=_TIMEOUT, label_responses=label_responses, args=args
        )
        self.assertEqual(
            result.error, "", f"[{case_name}] Harness error: {result.error}"
        )

        routing_calls = _calls_with_label(result, _ROUTING_LABEL)
        self.assertGreaterEqual(
            len(routing_calls),
            1,
            f"[{case_name}] Expected a '{_ROUTING_LABEL}' dispatch — none "
            f"found. Dispatched labels: {_dispatched_labels(result)}",
        )

        publish_calls = _calls_with_label(result, publish_label)
        self.assertGreaterEqual(
            len(publish_calls),
            1,
            f"[{case_name}] Sanity check failed: '{publish_label}' was not "
            f"dispatched. Dispatched labels: {_dispatched_labels(result)}",
        )

        self.assertLess(
            routing_calls[0].call_index,
            publish_calls[0].call_index,
            f"[{case_name}] '{_ROUTING_LABEL}' must be dispatched BEFORE "
            f"'{publish_label}' (INF-700a-1-i requires the SAME ordering "
            "contract on every completion path, not only the one path a "
            "single-path fix might wire). Dispatched labels in order: "
            f"{_dispatched_labels(result)}",
        )


# ---------------------------------------------------------------------------
# NOTE for python-coder / a follow-up test-writer pass:
#
# This module currently parametrises 2 of the 5 completion paths named in
# INF-700a-1-i's it_requirements (build-epic, build-ticket, fast-lane-ship,
# quick-fix, finalize-feature). fast-lane-ship and quick-fix were chosen
# because this repository already has established, exercised full-success E2
# harness fixtures for them (test_bo2400f_10i_release_wiring.py,
# test_quick_fix_workflow.py) to build from. build-epic.js, build-ticket.js,
# and finalize-feature.js each need their OWN full-success fixture built out
# (build-ticket.js's existing BO-3000 fixture only drives as far as
# pr-reviewer, never to an actual commit) before a symmetric case can be
# added to _PATH_CASES above. Per this AC's it_requirements ("PARTIAL WIRING
# IS THE PREDICTED FAILURE"), closing this gap is exactly what the
# build-time guard below exists to catch even where the per-path unit test
# coverage lags: the guard enumerates the *artefacts*, so a completion path
# that ships without a routing-step dispatch is caught even for a script
# this file does not (yet) drive to completion.
# ---------------------------------------------------------------------------


if __name__ == "__main__":
    unittest.main()
