"""Regression tests (pr-reviewer findings M-2, M-3, M-4) for BO-2400f-5-iii's
`classifyStepReply`, run against the REAL on-disk function under node.

No subTest(): problems are accumulated and asserted once, so a failing case
cannot leave the outer test id reading PASSED to the red-gate text parser.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.workflows._bo2400f5iii_fixtures import (  # noqa: E402
    calls_with_label,
    classify_in_node,
    run_lane,
)

_CMD = {"step": "claim-connected", "agent": "command-step-runner", "isCommandStep": True}
_PLAIN = {"step": "fastlane-commit", "agent": "commit", "isCommandStep": False}


class TestCommandStepPrecedence(unittest.TestCase):
    """M-3: a readable exit_status decides; an unreadable one is a decline."""

    def test_exit_status_beats_refusal_wording_on_a_command_step(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: discrimination
        verdict = classify_in_node("({exit_status: 1, reason: 'declined'})", _CMD)
        self.assertEqual(
            verdict.get("kind"), "failed",
            f"A command step with a readable non-zero exit_status is the "
            f"command's own failure, even if its text says 'declined'. Got: {verdict}",
        )

    def test_unreadable_exit_status_is_a_no_readable_result_decline(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: boundary
        problems: list[str] = []
        for js in (
            "({exit_status: NaN})",
            "({exit_status: Infinity})",
            "({exit_status: 1.5})",
            "({exit_status: null})",
            "({exit_status: '1'})",
        ):
            verdict = classify_in_node(js, _CMD)
            reason = str(verdict.get("reason") or "").lower()
            if verdict.get("kind") != "declined":
                problems.append(f"{js}: expected declined, got {verdict}")
            elif "no readable" not in reason:
                problems.append(f"{js}: reason lacks no-readable-result wording: {verdict}")
        self.assertEqual(problems, [], "\n".join(problems))


class TestExplicitDeclinesOnNonCommandSteps(unittest.TestCase):
    """M-4: explicit decline signals and every text field are honoured."""

    def test_explicit_decline_shapes_classify_as_declined(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: criterion
        problems: list[str] = []
        for js in (
            "({declined: true, reason: 'not my role'})",
            "({status: 'declined'})",
            "({status: 'blocker', message: 'this is outside of my role'})",
            "({reason: 'all good', message: 'I refuse to do this'})",
            "({reason: 'all good', message: 'fine', detail: 'I refuse to do this'})",
        ):
            verdict = classify_in_node(js, _PLAIN)
            if verdict.get("kind") != "declined":
                problems.append(f"{js}: expected declined, got {verdict}")
        self.assertEqual(problems, [], "\n".join(problems))

    def test_declined_resolve_reply_halts_and_is_not_the_empty_set_noop(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: reachability
        result = run_lane(
            {"resolve-connected": {"declined": True, "reason": "not my role"}}
        )
        payload = result.result or {}
        self.assertEqual(
            payload.get("halt_kind"), "declined_step",
            f"An explicit decline at resolve must halt as declined_step, never "
            f"the empty-set no-op. Got: {payload}; stderr={result.stderr!r}",
        )
        self.assertFalse(calls_with_label(result, "check-producibility"))


class TestRunnerDeclineReasonIsVerbatim(unittest.TestCase):
    """M-2: the agent's own reason, trimmed of surrounding whitespace only."""

    def test_runner_decline_reason_is_quoted_exactly(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: discrimination
        text = "I am a different agent; this command is not mine to run"
        problems: list[str] = []
        for raw in (text, f"  {text}\n"):
            result = run_lane(
                {
                    "claim-connected": {
                        "declined": True,
                        "step": "claim-connected",
                        "agent": "command-step-runner",
                        "reason": raw,
                    }
                }
            )
            payload = result.result or {}
            if payload.get("halt_kind") != "declined_step":
                problems.append(f"{raw!r}: not a declined_step halt: {payload}")
            elif payload.get("reason") != text:
                problems.append(f"{raw!r}: reason {payload.get('reason')!r} != {text!r}")
        self.assertEqual(problems, [], "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
