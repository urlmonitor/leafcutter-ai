"""
MODULE: test_acd_2100c_3_iv
GOAL: Behavioural RED-baseline tests for ACD-2100c-3-iv -- a resumed
    /plan-feature run (args.resume_answer set, durable pause record naming a
    gate other than covered-route-gate) must reach that paused gate on the
    route the paused run was on, not on a route freshly recomputed by Stage 0
    triage against a store that now contains the run's own output.

BUG (2026-10-21, run pf-shared-code-inliner-20261021b): the person answered
    final-gate with approve + priority high; the resumed run re-ran Stage 0
    triage, which classified the request as 'covered' (the run's own ACs are
    committed), opened covered-route-gate and returned paused_awaiting_input
    for it. The approval was never applied.

EXPECTED FIX (templates/workflows-js/plan-feature.js only): record the
    effective route in the pause context; on a resume of a non-covered gate
    take the route from the paused record and never open covered-route-gate.
    A fresh run and a resume of covered-route-gate itself keep triage.

TEST STRATEGY: drive the REAL on-disk plan-feature.js through
    harness.run_workflow_under_e2() with stubbed agent() replies (triage says
    'covered'), and observe the terminal payload and the dispatched labels.

AC: ACD-2100c-3-iv
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_UNIT_TESTS_DIR = Path(__file__).resolve().parent.parent
if str(_UNIT_TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(_UNIT_TESTS_DIR))

import _workflow_engine_harness as harness  # noqa: E402

_WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
_PLAN_FEATURE_JS = _WORKTREE_ROOT / "templates" / "workflows-js" / "plan-feature.js"
_TIMEOUT = 30

_RUN_ID = "pf-shared-code-inliner-20261021b"
_COVERED_GATE = "covered-route-gate"
_FINAL_GATE = "final-gate"


def _record(gate_id: str, context: dict) -> dict:
    return {
        "exists": True,
        "stale": False,
        "record": {
            "run_id": _RUN_ID,
            "gate_id": gate_id,
            "status": "paused_awaiting_input",
            "question": {"type": "single_choice", "gate_id": gate_id,
                         "options": ["approve", "edit", "cancel"]},
            "context": context,
        },
    }


def _label_responses(pause_reply: dict) -> dict:
    return {
        "scan-orphans-git-status": {"output": "", "exit_code": 0},
        # Triage against the CURRENT store (which holds the run's own ACs).
        "stage-0-triage": {"route": "covered", "existing_acs": ["ACD-9101"],
                           "parent_l1_id": None, "rationale": "own output"},
        "peek-pause-record": pause_reply,
        "read-pause-record": pause_reply,
        "clear-pause-record": {"ok": True},
        "clear-pause-record-verify": {"exists": False, "stale": False, "record": None},
        "pause-persist-verify": {"exists": True, "stale": False, "record": {"run_id": _RUN_ID}},
    }


def _run(pause_reply: dict, args: dict):
    return harness.run_workflow_under_e2(
        _PLAN_FEATURE_JS,
        timeout=_TIMEOUT,
        label_responses=_label_responses(pause_reply),
        args=args,
    )


def _terminal(result):
    assert result.error == "", f"Harness error: {result.error} stderr={result.stderr!r}"
    assert isinstance(result.result, dict), f"no terminal payload: {result.result!r} stderr={result.stderr!r}"
    return result.result


def _answer(gate_id: str, action: str) -> dict:
    return {"run_id": _RUN_ID,
            "resume_answer": {"gate_id": gate_id, "type": "single_choice",
                              "action": action, "channel": "person"}}


class TestResumeKeepsPausedRoute(unittest.TestCase):

    def test_resume_of_final_gate_never_opens_covered_route_gate(self):
        # covers: ACD-2100c-3-iv
        # angle: criterion
        """Resuming final-gate while triage now says 'covered' must not open
        covered-route-gate.

        RED today: Stage 0 triage is re-run, route == 'covered', and the run
        pauses at covered-route-gate instead of applying the final-gate answer.
        """
        record = _record(_FINAL_GATE, {"stage": "final", "route": "behavioral"})
        result = _run(record, _answer(_FINAL_GATE, "approve"))
        terminal = _terminal(result)
        labels = [c.label for c in result.agent_calls]
        self.assertNotEqual(
            terminal.get("gate_id"), _COVERED_GATE,
            f"resume was re-routed to covered-route-gate. terminal={terminal!r}",
        )
        self.assertNotIn(
            _COVERED_GATE, labels,
            f"covered-route-gate was dispatched on a resume of {_FINAL_GATE}. labels={labels}",
        )

    def test_resume_route_comes_from_record_not_from_fresh_triage(self):
        # covers: ACD-2100c-3-iv
        # angle: discrimination
        """Same resume, but the record carries no covered-route-gate hint at
        all: a wrong fix that merely special-cases the gate name only after
        triage already ran would still dispatch stage-0-triage-driven gating;
        the covered gate must stay unopened and no pause record may name it.

        RED today: a 'pause-persist' dispatch carries covered-route-gate.
        """
        record = _record(_FINAL_GATE, {"stage": "final", "route": "technical"})
        result = _run(record, _answer(_FINAL_GATE, "approve"))
        _terminal(result)
        offenders = [c.prompt for c in result.agent_calls
                     if c.label == "pause-persist" and _COVERED_GATE in c.prompt]
        self.assertEqual(offenders, [], "a pause record naming covered-route-gate was persisted")

    def test_resume_of_covered_route_gate_itself_still_uses_triage(self):
        # covers: ACD-2100c-3-iv
        # angle: boundary
        """Negative control: resuming covered-route-gate itself keeps today's
        behaviour -- triage runs, the gate consumes the 'cancel' answer and
        the run ends 'ok' with covered_by.
        """
        record = _record(_COVERED_GATE, {"route": "covered", "existing_acs": ["ACD-9101"]})
        result = _run(record, _answer(_COVERED_GATE, "cancel"))
        terminal = _terminal(result)
        labels = [c.label for c in result.agent_calls]
        self.assertIn("stage-0-triage", labels)
        self.assertEqual(terminal.get("status"), "ok", f"terminal={terminal!r}")
        self.assertEqual(terminal.get("covered_by"), ["ACD-9101"], f"terminal={terminal!r}")

    def test_fresh_run_with_covered_route_still_opens_covered_route_gate(self):
        # covers: ACD-2100c-3-iv
        # angle: boundary
        """Negative control: no resume_answer -> covered triage still pauses
        at covered-route-gate exactly as before.
        """
        record = {"exists": False, "stale": False, "record": None}
        result = _run(record, {"run_id": _RUN_ID})
        terminal = _terminal(result)
        self.assertEqual(terminal.get("gate_id"), _COVERED_GATE, f"terminal={terminal!r}")
        self.assertEqual(terminal.get("status"), "paused_awaiting_input")


if __name__ == "__main__":
    unittest.main()
