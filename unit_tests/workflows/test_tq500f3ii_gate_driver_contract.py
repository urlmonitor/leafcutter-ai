"""
MODULE: unit_tests/workflows/test_tq500f3ii_gate_driver_contract.py
GOAL: RED tests for TQ-500f-3-ii's DRIVER-SIDE gate contract: how the three
    workflows (build-feature.js, build-ticket.js, fast-lane-ship.js) launch
    the red-baseline reader (``fast_lane.py``) and how the twins report a
    gate refusal.

AC: docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/TQ-500f-3-ii.yaml

BUSINESS CONTEXT: pytest runs as ``sys.executable -m pytest``, so the
    interpreter that launches the gate decides which environment the new tests
    see. ``python3`` on a Windows venv resolves to the Windows Store Python,
    every test ERRORs, and the verdict reads ``no_red_outcome_among_new_tests``
    with the real cause hidden. ``python`` is the project's interpreter
    convention (every hook uses it), and both lanes must start the reader with
    the SAME command form.

Every test drives the REAL, unmodified workflow script under
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2() (a real
Node.js subprocess) and asserts on the RECORDED agent dispatches -- never on
text found in the driver source.

TODAY (unmodified code): the heavy lane launches ``python3 ... heavy_lane_gate``
and every fast_lane.py call in fast-lane-ship.js starts with ``python3``; the
halt message carries the reason but never the verdict's interpreter.

This file is shared with the next tickets of EPIC-BuildToolingRunsThrough,
which add further gate driver-contract tests; keep the helpers neutral.
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))
sys.path.insert(0, str(_UNIT_TESTS_DIR / "prompt_assembly"))

from _workflow_engine_harness import run_workflow_under_e2  # noqa: E402

import _driver_harness  # noqa: E402
import unit_tests.workflows._tq500f3ii_fixtures as fx  # noqa: E402
import workflows._fast_lane_claim_fixtures as claim_fx  # noqa: E402

TWIN_DRIVERS = _driver_harness.TWIN_DRIVERS

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
FAST_LANE_SHIP_JS = _REPO_ROOT / "templates" / "workflows-js" / "fast-lane-ship.js"

_TIMEOUT = 30
_ORDERED_PHASES = [
    {"agent": "test-writer", "status": "needed"},
    {"agent": "python-coder", "status": "needed"},
]

# "<interpreter-token> <path>/fast_lane.py <subcommand>", wherever it sits in a
# prompt (start of a line, indented, or inside a quoted JSON "command" value).
_FAST_LANE_COMMAND_RE = re.compile(
    r"""(?:^|[\s"'])([^\s"']+)\s+[^\s"']*fast_lane\.py\s+(\w+)""", re.MULTILINE
)


def _twin_args(driver_name: str) -> dict:
    if driver_name == "build-feature.js":
        return {"target": fx.TICKET_ABS_PATH}
    return {"ticket_path": fx.TICKET_ABS_PATH, "worktree_path": fx.WORKTREE_ABS_PATH}


def _drive_twin(driver_name: str, ac_id: str, gate_response: dict):
    label_responses = fx.base_label_responses(
        ticket_path=fx.TICKET_ABS_PATH,
        worktree_path=fx.WORKTREE_ABS_PATH,
        ordered_phases=_ORDERED_PHASES,
        source_ac=ac_id,
        gate_response=gate_response,
    )
    return run_workflow_under_e2(
        Path(TWIN_DRIVERS[driver_name]),
        timeout=_TIMEOUT,
        label_responses=label_responses,
        args=_twin_args(driver_name),
    )


def _prompt_text(call) -> str:
    prompt = call.prompt
    return prompt if isinstance(prompt, str) else json.dumps(prompt)


def _fast_lane_commands(result) -> list[tuple[str, str]]:
    """Every (interpreter_token, subcommand) pair for a fast_lane.py command
    found in any recorded dispatch prompt of the run."""
    found: list[tuple[str, str]] = []
    for call in result.agent_calls:
        found.extend(_FAST_LANE_COMMAND_RE.findall(_prompt_text(call)))
    return found


def _drive_fast_lane_to_coder():
    """fast-lane-ship.js driven past its test-writer gate into the coder's
    green/coverage step, so every fast_lane.py invocation the lane builds is
    dispatched at least once."""
    ac_id = "TQ-STUB-1"
    with tempfile.TemporaryDirectory() as tmp:
        worktree_root = Path(tmp)
        (worktree_root / "docs" / "acceptance-criteria").mkdir(parents=True)
        label_responses = {
            "fastlane-worktree": {
                "outcome": "opened",
                "worktree_path": str(worktree_root),
                "branch": f"fast-lane/{ac_id}",
                "created": True,
                "base_commit": "a" * 40,
                "base_matches_origin_main": True,
            },
            "resolve-connected": {"ac_ids": [ac_id], "message": "1 to build"},
            "claim-connected": claim_fx.claim_ran([ac_id]),
            "test-writer-connected": {
                "status": "ok",
                "gate_passed": True,
                "tests_written": ["tests/test_stub.py"],
                "red": ["tests/test_stub.py::test_a"],
            },
            "coder-connected": {"status": "ok", "message": "implemented"},
        }
        return run_workflow_under_e2(
            FAST_LANE_SHIP_JS,
            timeout=_TIMEOUT,
            label_responses=label_responses,
            args={"ac": ac_id},
        )


def test_heavy_and_fast_lane_gate_commands_share_the_python_token():
    # covers: TQ-500f-3-ii
    # angle: seam
    """Lane parity at the command line: the red-baseline command each twin
    dispatches and the verify_red_baseline command fast-lane-ship.js hands its
    test-writer start with the SAME interpreter token, and it is ``python``.
    """
    tokens: dict[str, str] = {}
    for name in TWIN_DRIVERS:
        result = _drive_twin(
            name, "TQ-FIX-3II-TOKEN", fx.red_baseline_gate_response(gate_passed=True)
        )
        assert result.error == "", f"{name}: harness error: {result.error}"
        gate_calls = fx.calls_with_label(result, fx.RED_BASELINE_GATE_LABEL)
        assert gate_calls, (
            f"{name}: no red-baseline-gate dispatch recorded; "
            f"labels={[c.label for c in result.agent_calls]}"
        )
        gate_cmds = [
            tok
            for tok, sub in _FAST_LANE_COMMAND_RE.findall(_prompt_text(gate_calls[0]))
            if sub == "heavy_lane_gate"
        ]
        assert gate_cmds, (
            f"{name}: no heavy_lane_gate command in the gate prompt: "
            f"{_prompt_text(gate_calls[0])!r}"
        )
        tokens[name] = gate_cmds[0]

    fast_result = _drive_fast_lane_to_coder()
    assert fast_result.error == "", f"fast-lane-ship.js harness error: {fast_result.error}"
    fast_tokens = [
        tok for tok, sub in _fast_lane_commands(fast_result) if sub == "verify_red_baseline"
    ]
    assert fast_tokens, (
        "fast-lane-ship.js dispatched no verify_red_baseline command; "
        f"labels={[c.label for c in fast_result.agent_calls]}"
    )
    tokens["fast-lane-ship.js"] = fast_tokens[0]

    assert set(tokens.values()) == {"python"}, (
        "both lanes must launch the reader with the project interpreter token "
        f"'python' (identical in all three drivers); got {tokens!r}"
    )


def test_fast_lane_ship_never_launches_fast_lane_py_with_python3():
    # covers: TQ-500f-3-ii
    # angle: criterion
    """Every fast_lane.py command the fast lane builds -- select_connected,
    check_producibility, claim, verify_red_baseline, verify_green_and_coverage,
    release -- starts with ``python``, never ``python3``."""
    result = _drive_fast_lane_to_coder()
    assert result.error == "", f"harness error: {result.error}"

    commands = _fast_lane_commands(result)
    subcommands = {sub for _tok, sub in commands}
    assert {"verify_red_baseline", "verify_green_and_coverage"} <= subcommands, (
        "the run must reach both gate steps for this check to mean anything; "
        f"subcommands seen={sorted(subcommands)}"
    )
    offenders = [(tok, sub) for tok, sub in commands if tok != "python"]
    assert offenders == [], (
        "every fast_lane.py invocation in fast-lane-ship.js must start with "
        f"'python'; offending (token, subcommand) pairs: {offenders!r}"
    )


def test_gate_halt_message_names_interpreter_and_reason():
    # covers: TQ-500f-3-ii
    # angle: failure
    """The gate reports an unusable test interpreter: both twins halt before
    python-coder is dispatched and the halt message names the interpreter AND
    the reason, so the operator sees which environment failed."""
    interpreter = "/x/venv/python"
    reason = "test_interpreter_unusable"
    reply = fx.red_baseline_gate_response(gate_passed=False, reason=reason)
    verdict = json.loads(reply["output"])
    verdict["interpreter"] = interpreter
    reply["output"] = json.dumps(verdict)

    for name in TWIN_DRIVERS:
        result = _drive_twin(name, "TQ-FIX-3II-HALT", reply)
        assert result.error == "", f"{name}: harness error: {result.error}"
        assert fx.calls_with_label(result, "python-coder") == [], (
            f"{name}: the coder must not be dispatched when the gate fails; "
            f"labels={[c.label for c in result.agent_calls]}"
        )
        message = (result.result or {}).get("message", "")
        assert reason in message, f"{name}: halt message must name the reason: {message!r}"
        assert interpreter in message, (
            f"{name}: halt message must name the interpreter from the verdict "
            f"({interpreter!r}): {message!r}"
        )
