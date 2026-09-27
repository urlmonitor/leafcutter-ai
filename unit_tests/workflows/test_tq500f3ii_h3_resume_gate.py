"""
MODULE: unit_tests/workflows/test_tq500f3ii_h3_resume_gate.py
GOAL: RED regression tests for pr-reviewer finding H-3 against
    templates/workflows-js/build-feature.js and its declared twin
    build-ticket.js.

THE BUG: the red-baseline gate dispatch lives entirely INSIDE the
    ``if (phaseName === "test-writer") { ... }`` branch of the per-ticket
    phase loop (driveTicketPhases in build-feature.js; the equivalent block
    in build-ticket.js) -- it only ever runs on the SAME turn the test-writer
    phase itself is dispatched. A RESUMED ticket whose test-writer phase is
    already ``signed_off`` never has "test-writer" appear in its
    ``neededPhases`` / ``pendingPhases`` set for this drive at all (only
    ``needed``/``failed`` phases are dispatched), so that branch is never
    entered -- the coder is dispatched with NO gate at all, even though a
    source_ac exists and nothing has independently re-verified the red
    baseline this run.

    TQ-500f-3-ii's own it_requirements are explicit about this exact case:
    "Resume safety: a resumed ticket whose test-writer phase is already
    signed_off re-runs the reader before the coder rather than trusting the
    earlier sign-off."

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml

Both tests drive the REAL, unmodified workflow scripts' own top-level body
via unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() and
assert on the recorded dispatch sequence, never on a string found in the
source. Per CLAUDE.md "Gate / Workflow ACs -- Verify Behaviorally, Not by
Grep".
"""

from __future__ import annotations

import sys
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

import unit_tests.workflows._tq500f3ii_fixtures as fx  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
BUILD_TICKET_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-ticket.js"

_TIMEOUT = 30

# The resumed-ticket shape: test-writer already signed_off (NOT needed this
# drive -- it will never appear in neededPhases/pendingPhases), python-coder
# still needed. This is exactly the shape TQ-500f-3-ii's "Resume safety"
# it_requirement names.
_ORDERED_PHASES_RESUMED = [
    {"agent": "test-writer", "status": "signed_off"},
    {"agent": "python-coder", "status": "needed"},
]


def _drive_resumed(driver_js, ac_id, gate_response, *, is_build_ticket):
    label_responses = fx.base_label_responses(
        ticket_path=fx.TICKET_ABS_PATH,
        worktree_path=fx.WORKTREE_ABS_PATH,
        ordered_phases=_ORDERED_PHASES_RESUMED,
        source_ac=ac_id,
        gate_response=gate_response,
    )
    args = (
        {"ticket_path": fx.TICKET_ABS_PATH, "worktree_path": fx.WORKTREE_ABS_PATH}
        if is_build_ticket
        else {"target": fx.TICKET_ABS_PATH}
    )
    return run_workflow_under_e2(
        driver_js, timeout=_TIMEOUT, label_responses=label_responses, args=args
    )


def _assert_gate_runs_on_resume(driver_js, driver_name, *, is_build_ticket):
    # PASS branch: gate re-verifies red and the coder still runs.
    result_pass = _drive_resumed(
        driver_js,
        "TQ-H3-PASS",
        fx.red_baseline_gate_response(gate_passed=True),
        is_build_ticket=is_build_ticket,
    )
    assert result_pass.error == "", f"{driver_name}: harness error: {result_pass.error}"
    dispatched_labels_pass = [c.label for c in result_pass.agent_calls]
    assert "test-writer" not in dispatched_labels_pass, (
        f"{driver_name}: this fixture's test-writer phase is already "
        f"signed_off -- it must NOT be re-dispatched this drive (that would "
        f"defeat the point of testing the RESUME path); "
        f"labels={dispatched_labels_pass}"
    )
    gate_idx = fx.first_index_with_label(result_pass, fx.RED_BASELINE_GATE_LABEL)
    coder_idx = fx.first_index_with_label(result_pass, "python-coder")
    assert gate_idx is not None, (
        f"{driver_name}: the red-baseline gate must still be dispatched on a "
        f"RESUMED ticket (test-writer already signed_off) -- TQ-500f-3-ii's "
        f"own 'Resume safety' it_requirement requires re-running the reader "
        f"before the coder rather than trusting the earlier sign-off; "
        f"labels={dispatched_labels_pass}"
    )
    assert coder_idx is not None, (
        f"{driver_name}: python-coder was never dispatched at all; "
        f"labels={dispatched_labels_pass}"
    )
    assert gate_idx < coder_idx, (
        f"{driver_name}: the gate dispatch must sit before the coder "
        f"dispatch; gate_idx={gate_idx} coder_idx={coder_idx}, "
        f"labels(in order)={dispatched_labels_pass}"
    )

    # FAIL branch: gate reports gate_passed=False -- the coder must NOT run,
    # even though test-writer's own (already-recorded) sign-off is not being
    # re-examined at all this drive.
    result_fail = _drive_resumed(
        driver_js,
        "TQ-H3-FAIL",
        fx.red_baseline_gate_response(
            gate_passed=False, reason="declared_test_refused_absence_only_red"
        ),
        is_build_ticket=is_build_ticket,
    )
    assert result_fail.error == "", f"{driver_name}: harness error: {result_fail.error}"
    coder_calls_fail = fx.calls_with_label(result_fail, "python-coder")
    assert coder_calls_fail == [], (
        f"{driver_name}: a resumed ticket must NOT reach the coder when the "
        f"independently re-run gate reports gate_passed=False, even though "
        f"test-writer's own sign-off (recorded on an earlier drive) is not "
        f"re-examined this run; dispatched labels="
        f"{[c.label for c in result_fail.agent_calls]}"
    )


def test_h3_build_feature_gate_runs_on_resumed_ticket_before_coder():
    # covers: TQ-500f-3-ii
    # angle: boundary
    """build-feature.js: a resumed ticket (test-writer already signed_off,
    coder still needed) still dispatches the red-baseline gate before the
    coder, and a gate_passed=False verdict still blocks the coder.
    """
    _assert_gate_runs_on_resume(BUILD_FEATURE_JS, "build-feature.js", is_build_ticket=False)


def test_h3_build_ticket_gate_runs_on_resumed_ticket_before_coder():
    # covers: TQ-500f-3-ii
    # angle: boundary
    """build-ticket.js (the twin): same resume-safety behaviour must hold --
    the twin cannot drift from build-feature.js on this case either.
    """
    _assert_gate_runs_on_resume(BUILD_TICKET_JS, "build-ticket.js (twin)", is_build_ticket=True)
