"""
MODULE: unit_tests/workflows/test_tq500f3ii_gate_reply_fail_closed.py
GOAL: RED test stub for TQ-500f-3-ii's fail-closed requirement when the
    red-baseline-gate dispatch ITSELF returns a REFUSAL / unparseable reply
    rather than a real {"output": ..., "exit_code": ...} envelope.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml

BACKGROUND (observed in live runs today, not a hypothetical): the depth-1
executor agents this gate's pinned contract dispatches to (status-checker /
python-coder, see _tq500f3ii_fixtures.py's docstring) have been seen
REFUSING shell-running dispatches with a "this is not my role" reply
instead of executing the command and returning its output. TQ-500f-3-ii's
own it_requirements already forbid treating a missing/failed gate verdict as
a pass ("the workflow must consume the reader's JSON verdict in control
flow... the test writer's claim is never a substitute"). This test pins the
sharper, adjacent case: when the gate dispatch's OWN reply cannot be
interpreted as a verdict at all -- no parseable JSON body, no "exit_code",
just a refusal/blocker message -- the drive must fail CLOSED: halt before
the coder with a reason naming the gate as not verified, never proceed as
if gate_passed were true.

WRONG VERSION THIS TEST CATCHES: "unparseable gate reply treated as
gate_passed" -- an implementation that falls through to the happy path on
ANY reply shape it cannot parse would let an executor's refusal silently
pass every ticket's gate, which is worse than having no gate at all: it
LOOKS enforced while enforcing nothing.

TODAY (unmodified code): no red-baseline-gate dispatch exists at all in
either driver (see test_tq500f3ii_heavy_lane_red_baseline_gate.py), so the
coder is dispatched UNCONDITIONALLY regardless of what this fixture's
"red-baseline-gate" label response contains -- the degenerate case of
exactly the wrong version this test is written to catch. RED today for that
reason in both drivers.
"""

from __future__ import annotations

import json
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
_ORDERED_PHASES = [
    {"agent": "test-writer", "status": "needed"},
    {"agent": "python-coder", "status": "needed"},
]

# Pinned contract (this file's own proposed wording, like the sibling
# family's REFUSAL_REASON / RED_BASELINE_GATE_LABEL constants): the halt
# payload must say the gate reply could not be verified. Any wording is
# accepted as long as it says the gate was NOT verified -- see the
# "not verified" fallback in the assertions below.
_FAIL_CLOSED_PHRASE = "red-baseline gate reply could not be verified"

# The real observed shape: a blocker/refusal message, no "output" key, no
# "exit_code" key -- NOT the {"output": "<json>", "exit_code": N} envelope
# every other fixture in this family supplies.
_REFUSAL_GATE_REPLY = {
    "status": "blocker",
    "message": (
        "Running arbitrary shell commands is not my role as a "
        "status-checker agent. Please dispatch a script-executor for this."
    ),
}


def _assert_fails_closed(result, driver_name):
    assert result.error == "", f"{driver_name}: harness error: {result.error}"
    coder_calls = fx.calls_with_label(result, "python-coder")
    assert coder_calls == [], (
        f"{driver_name} must NOT dispatch the coder when the "
        "red-baseline-gate reply is a refusal/unparseable shape ('not my "
        "role', no output/exit_code) -- proceeding here is exactly the "
        "wrong version 'unparseable gate reply treated as gate_passed'; "
        f"dispatched labels={[c.label for c in result.agent_calls]}"
    )
    payload_text = json.dumps(result.result or {}).lower()
    assert _FAIL_CLOSED_PHRASE in payload_text or "not verified" in payload_text, (
        f"{driver_name}'s halt payload must name the red-baseline gate as "
        f"NOT verified when its reply could not be interpreted; result={result.result!r}"
    )


def test_build_feature_and_build_ticket_fail_closed_on_unparseable_gate_reply():
    # covers: TQ-500f-3-ii
    # angle: failure
    """Drive both build-feature.js and its declared twin build-ticket.js
    with the SAME refusal-shaped red-baseline-gate reply: neither may
    dispatch the coder, and both must record the gate as unverified.
    """
    ac_id = "TQ-FIX-3II-UNPARSEABLE"

    label_responses_bf = fx.base_label_responses(
        ticket_path=fx.TICKET_ABS_PATH,
        worktree_path=fx.WORKTREE_ABS_PATH,
        ordered_phases=_ORDERED_PHASES,
        source_ac=ac_id,
        gate_response=_REFUSAL_GATE_REPLY,
    )
    result_bf = run_workflow_under_e2(
        BUILD_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses_bf,
        args={"target": fx.TICKET_ABS_PATH},
    )
    _assert_fails_closed(result_bf, "build-feature.js")

    label_responses_bt = fx.base_label_responses(
        ticket_path=fx.TICKET_ABS_PATH,
        worktree_path=fx.WORKTREE_ABS_PATH,
        ordered_phases=_ORDERED_PHASES,
        source_ac=ac_id,
        gate_response=_REFUSAL_GATE_REPLY,
    )
    result_bt = run_workflow_under_e2(
        BUILD_TICKET_JS,
        timeout=_TIMEOUT,
        label_responses=label_responses_bt,
        args={"ticket_path": fx.TICKET_ABS_PATH, "worktree_path": fx.WORKTREE_ABS_PATH},
    )
    _assert_fails_closed(result_bt, "build-ticket.js (twin)")
