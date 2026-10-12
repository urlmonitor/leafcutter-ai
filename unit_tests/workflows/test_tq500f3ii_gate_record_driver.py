"""
MODULE: unit_tests/workflows/test_tq500f3ii_gate_record_driver.py
GOAL: RED tests for the DRIVER side of TQ-500f-3-ii's record/reuse and
    ``green_at_baseline`` rules (ticket 03), over BOTH twins (build-feature.js
    and build-ticket.js, parametrised over TWIN_DRIVERS).

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml

Each test drives the REAL, unmodified workflow under
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() (a real
Node.js subprocess) with the gate executor's reply scripted -- the established
pattern of test_tq500f3ii_gate_driver_contract.py -- and asserts on the
RECORDED dispatches and the terminal payload, never on driver source text.

The decision logic (record, reuse, halt classification, remedy text) lives in
the Python gate; the JS twins only pass ``--ticket`` and echo the verdict's
``halt_classification`` and ``remedy`` inside their existing halt return. These
tests pin exactly that echo; the Python side is pinned by
unit_tests/build_orchestration/test_tq500f3ii_gate_record_reuse.py.

TODAY (unmodified code): the gate command has no ``--ticket``; the halt for
all-green tests is the generic ``classification: "halt"`` with no remedy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))
sys.path.insert(0, str(_UNIT_TESTS_DIR / "prompt_assembly"))

import _driver_harness  # noqa: E402
import unit_tests.workflows._tq500f3ii_fixtures as fx  # noqa: E402
import unit_tests.workflows.test_tq500f3ii_gate_driver_contract as contract  # noqa: E402

TWIN_DRIVERS = _driver_harness.TWIN_DRIVERS

_GREEN_NODE_A = "tests/test_delivered.py::test_already_delivered_one"
_GREEN_NODE_B = "tests/test_delivered.py::test_already_delivered_two"
_REMEDY = (
    "REMEDY-SENTINEL: these newly added tests are green before any coding: "
    f"{_GREEN_NODE_A}, {_GREEN_NODE_B}. Set the coder phase to not_needed with a "
    "comment naming the commit that delivered the behaviour."
)


def _scripted_reply(*, gate_passed: bool, reason: str | None = None, **extra) -> dict:
    """The gate executor's reply: the shared fixture envelope plus extra verdict keys."""
    reply = fx.red_baseline_gate_response(gate_passed=gate_passed, reason=reason)
    verdict = json.loads(reply["output"])
    verdict.update(extra)
    reply["output"] = json.dumps(verdict)
    return reply


@pytest.mark.parametrize("driver", sorted(TWIN_DRIVERS))
def test_both_twins_gate_command_carries_ticket_flag(driver):
    # covers: TQ-500f-3-ii
    # angle: reachability
    """Both twins pass ``--ticket <this drive's ticket path>`` on the gate command,
    and the fast lane's verify_red_baseline command stays free of it."""
    result = contract._drive_twin(driver, "TQ-FIX-3II-TICKETFLAG", _scripted_reply(gate_passed=True))
    assert result.error == "", f"{driver}: harness error: {result.error}"
    gate_calls = fx.calls_with_label(result, fx.RED_BASELINE_GATE_LABEL)
    assert gate_calls, f"{driver}: no gate dispatch; labels={[c.label for c in result.agent_calls]}"
    command = fx.extract_gate_invocation(contract._prompt_text(gate_calls[0]))
    assert command is not None, f"{driver}: no gate command in {contract._prompt_text(gate_calls[0])!r}"
    assert "heavy_lane_gate" in command, command
    assert f"--ticket {fx.TICKET_ABS_PATH}" in command, (
        f"{driver}: the gate command must carry the ticket path; command={command!r}"
    )

    fast = contract._drive_fast_lane_to_coder()
    fast_cmds = [
        fx.extract_gate_invocation(contract._prompt_text(c))
        for c in fast.agent_calls
        if "verify_red_baseline" in contract._prompt_text(c)
    ]
    fast_cmds = [c for c in fast_cmds if c]
    assert fast_cmds, "fast-lane-ship.js dispatched no verify_red_baseline command"
    assert all("--ticket" not in c for c in fast_cmds), f"fast lane unchanged; {fast_cmds!r}"


@pytest.mark.parametrize("driver", sorted(TWIN_DRIVERS))
def test_green_at_baseline_halt_lists_tests_and_suggests_not_needed(driver):
    # covers: TQ-500f-3-ii
    # angle: criterion
    """K4: an all-green verdict halts before python-coder with classification
    green_at_baseline; the halt message carries the gate's remedy (both tests, the
    not_needed advice); the drive never flips the coder phase itself."""
    reply = _scripted_reply(
        gate_passed=False,
        reason="all_new_tests_green_at_baseline",
        green_at_baseline=[
            {"nodeid": _GREEN_NODE_A, "ac_id": "TQ-K4", "outcome": "PASSED"},
            {"nodeid": _GREEN_NODE_B, "ac_id": "TQ-K4", "outcome": "PASSED"},
        ],
        halt_classification="green_at_baseline",
        remedy=_REMEDY,
    )

    result = contract._drive_twin(driver, "TQ-K4", reply)

    assert result.error == "", f"{driver}: harness error: {result.error}"
    labels = [c.label for c in result.agent_calls]
    assert fx.calls_with_label(result, "python-coder") == [], f"{driver}: coder dispatched; {labels}"
    payload = result.result or {}
    assert payload.get("classification") == "green_at_baseline", f"{driver}: payload={payload!r}"
    message = payload.get("message", "")
    assert _REMEDY in message, f"{driver}: the halt message must carry the remedy: {message!r}"
    assert _GREEN_NODE_A in message and _GREEN_NODE_B in message, f"{driver}: {message!r}"
    flips = [
        c for c in result.agent_calls
        if "set_ticket_status" in contract._prompt_text(c) and "not_needed" in contract._prompt_text(c)
    ]
    assert flips == [], f"{driver}: the driver must never set the coder phase itself; {labels}"


@pytest.mark.parametrize("driver", sorted(TWIN_DRIVERS))
def test_reused_pass_dispatches_coder_and_reports_reuse(driver):
    # covers: TQ-500f-3-ii
    # angle: criterion
    """A reused pass dispatches the coder and the drive's outcome names recorded_at and
    head; an unrecorded pass reports its record_error."""
    recorded_at, head = "2026-10-06T10:15:00Z", "abc1234def5678"
    reused = _scripted_reply(
        gate_passed=True,
        reused=True,
        outcome=f"red-baseline gate reused the recorded pass (recorded_at {recorded_at}, head {head})",
    )
    unrecorded = _scripted_reply(
        gate_passed=True,
        recorded=False,
        record_error="ticket not found: /nope.md",
        outcome="red-baseline gate passed; no record written: ticket not found: /nope.md",
    )
    for reply, needles in ((reused, (recorded_at, head, "reused")), (unrecorded, ("no record written", "ticket not found"))):
        result = contract._drive_twin(driver, "TQ-FIX-3II-REUSE", reply)
        assert result.error == "", f"{driver}: harness error: {result.error}"
        assert fx.calls_with_label(result, "python-coder"), f"{driver}: a passed gate must reach the coder"
        outcome_text = json.dumps(result.result or {})
        for needle in needles:
            assert needle in outcome_text, f"{driver}: outcome must name {needle!r}: {outcome_text}"


@pytest.mark.parametrize("driver", sorted(TWIN_DRIVERS))
def test_halt_without_wrapper_keys_stays_a_generic_halt(driver):
    # covers: TQ-500f-3-ii
    # angle: discrimination
    """Only a verdict that carries halt_classification halts as green_at_baseline: a
    different refusal (absence-only red) keeps classification "halt" and gains no remedy,
    so the driver cannot hard-code the green_at_baseline label for every refusal."""
    reply = _scripted_reply(gate_passed=False, reason="declared_test_refused_absence_only_red")

    result = contract._drive_twin(driver, "TQ-FIX-3II-GENERIC", reply)

    assert result.error == "", f"{driver}: harness error: {result.error}"
    assert fx.calls_with_label(result, "python-coder") == []
    payload = result.result or {}
    assert payload.get("classification") == "halt", f"{driver}: payload={payload!r}"
    assert "not_needed" not in payload.get("message", ""), f"{driver}: {payload!r}"
