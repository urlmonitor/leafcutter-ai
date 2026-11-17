"""
MODULE: unit_tests/workflows/test_bo2400f5iii_declined_step_core.py
GOAL: RED behavioural tests for BO-2400f-5-iii, covering test_spec entries 1
      and 2 — the floor "every step halts as declined_step, naming the step,
      the agent, and the quoted reason" criterion, and the discrimination
      between a declined step, genuine claim contention, a gate failure, and
      the BO-2400f-12 unproducible-set refusal.

=== Why this is RED today ===
templates/workflows-js/fast-lane-ship.js has no `halt_kind` field anywhere
(confirmed: `grep -n "halt_kind" templates/workflows-js/fast-lane-ship.js`
returns nothing) and no shared reply classifier. Every guard in the file is
its own bespoke falsy-check, so a decline-shaped reply at any step is
currently read as SOME existing halt/refusal/no-op shape that never carries
`halt_kind: 'declined_step'` — the assertion these tests make on that key is
what fails today, at every parametrised label, for the same reason.

=== Not a grep test ===
Every assertion drives fast-lane-ship.js through
unit_tests/_workflow_engine_harness.py's run_workflow_under_e2(), which
executes the script's real top-level control flow in a Node.js subprocess and
records every agent() dispatch verbatim, plus the script's own terminal
return value. See _bo2400f5iii_fixtures.py for the shared happy-path stub set,
the discovery helper, and the assumed payload/classifier API.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from unit_tests.workflows._fast_lane_claim_fixtures import claim_ran  # noqa: E402
from unit_tests.workflows._bo2400f5iii_fixtures import (  # noqa: E402
    AC_ID,
    BRANCH,
    CONTENTION_MARKERS,
    WORKTREE_PATH,
    calls_with_label,
    decline_reply_for,
    discover_step_dispatches,
    run_lane,
)


class TestDeclinedStepHaltsNamingStepAgentAndQuotedReason(unittest.TestCase):
    """test_spec[0] (angle: criterion).

    Parametrised over every label the lane ACTUALLY dispatches on a real
    happy-path run (discovered, not hand-listed — see
    discover_step_dispatches()'s own docstring), so a step added later to
    fast-lane-ship.js is covered without editing this test.
    """

    def test_declined_step_halts_naming_step_agent_and_quoted_reason(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: criterion
        #
        # NOTE: deliberately NOT using unittest's subTest() here. Under this
        # repo's pytest version, a subTest() failure is reported as a
        # separate "SUBFAILED" outcome while the OUTER test nodeid itself is
        # still recorded PASSED — invisible to fast_lane.py's
        # verify_red_baseline text-output parser, which reads the outer
        # nodeid's own PASSED/FAILED line. Accumulating problems and raising
        # ONE assertion at the end makes the outer nodeid itself fail
        # whenever any label is wrong, while still reporting every failing
        # label in one message.
        step_dispatches = discover_step_dispatches()
        self.assertTrue(step_dispatches, "Discovery found no step labels — fixture is broken.")

        problems: list[str] = []
        for label, agent_type in step_dispatches:
            decline_text = decline_reply_for(agent_type)
            result = run_lane({label: decline_text})
            if result.result is None:
                problems.append(f"[{label}] no terminal payload. stderr={result.stderr!r}")
                continue
            payload = result.result

            if payload.get("halt_kind") != "declined_step":
                problems.append(f"[{label}] halt_kind != 'declined_step'. Got: {payload}")
                continue
            if payload.get("step") != label:
                problems.append(f"[{label}] step must name the declined step. Got: {payload}")
            if payload.get("agent") != agent_type:
                problems.append(
                    f"[{label}] agent must be {agent_type!r} (the real dispatched "
                    f"agentType). Got: {payload}"
                )
            if payload.get("reason") != decline_text.strip():
                problems.append(
                    f"[{label}] reason must quote the agent's stated reason "
                    f"verbatim. Got: {payload}"
                )

            target = payload.get("target")
            if not isinstance(target, dict):
                problems.append(f"[{label}] target must be a dict. Got: {payload}")
            else:
                if target.get("workspace") != WORKTREE_PATH:
                    problems.append(f"[{label}] target.workspace mismatch. Got: {payload}")
                if target.get("branch") != BRANCH:
                    problems.append(f"[{label}] target.branch mismatch. Got: {payload}")
                if target.get("ac_id") != AC_ID:
                    problems.append(f"[{label}] target.ac_id mismatch. Got: {payload}")

        self.assertEqual(problems, [], "\n".join(problems))


class TestDeclinedWorkspaceStepEndsTheRunBeforeAnythingElseIsDispatched(unittest.TestCase):
    """The maker step (BO-4300c-3) is not part of the declined_step sweep above: its decline ends the run as
    an error quoting the reply, and nothing is dispatched after it (no resolve, no claim)."""

    def test_declined_workspace_step_ends_the_run_quoting_the_reply(self) -> None:
        # covers: BO-2400f-5-iii
        # angle: failure
        decline_text = decline_reply_for("shell-runner")
        result = run_lane({"workspace-ensure": decline_text})
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error", payload)
        self.assertIn("I can't help with that", payload.get("message", ""), payload)
        self.assertNotEqual(payload.get("halt_kind"), "declined_step", payload)
        for later in ("resolve-connected", "claim-connected", "test-writer-connected"):
            self.assertFalse(calls_with_label(result, later), f"{later} was dispatched after a declined workspace step")


class TestDeclinedMakerPathProbeEndsTheRunBeforeAnythingElseIsDispatched(unittest.TestCase):
    """The maker-path probe (BO-4300a-1-ia, part of the workspace step) ends the run as an error quoting the
    reply when it is declined, and nothing is dispatched after it (consumer_drift: it joined the sweep above)."""

    def test_declined_maker_path_probe_ends_the_run_quoting_the_reply(self) -> None:
        # covers: BO-4300a-1-ia
        # angle: failure
        decline_text = decline_reply_for("shell-runner")
        result = run_lane({"resolve-maker-path": decline_text})
        payload = result.result or {}
        self.assertEqual(payload.get("status"), "error", payload)
        self.assertIn("I can't help with that", payload.get("message", ""), payload)
        self.assertNotEqual(payload.get("halt_kind"), "declined_step", payload)
        for later in ("workspace-ensure", "resolve-connected", "claim-connected", "test-writer-connected"):
            self.assertFalse(calls_with_label(result, later), f"{later} was dispatched after a declined probe")


class TestDeclinedStepIsClassifiedApartFromContentionGateFailureAndUnproducible(
    unittest.TestCase
):
    """test_spec[1] (angle: discrimination).

    Four scenarios at four different guards, each must produce its OWN
    halt-kind reading, and only the genuine-contention one may carry
    contention wording. A fix that folds every one of these into the same
    bucket (all declined_step, or all contention, or all "gate failure")
    fails this test.
    """

    def test_declined_step_is_classified_apart_from_contention_gate_failure_and_unproducible(
        self,
    ) -> None:
        # covers: BO-2400f-5-iii
        # angle: discrimination
        declined_claim = run_lane({"claim-connected": decline_reply_for("worktree-agent")})
        genuine_contention = run_lane(
            {
                "claim-connected": claim_ran(
                    claimed=[],
                    excluded_claimed=[AC_ID],
                    target_refused=True,
                    message=f"{AC_ID} is already in_progress, held by run wf_abc123.",
                )
            }
        )
        gate_failure = run_lane(
            {
                "test-writer-connected": {
                    "status": "ok",
                    "tests_written": [],
                    "gate_passed": False,
                    "reason": "no newly-added scoped test is red",
                    "green_at_baseline": ["unit_tests/stub/test_stub.py"],
                    "message": "gate failed",
                }
            }
        )
        unproducible = run_lane(
            {
                "check-producibility": {
                    "producible": False,
                    "unproducible": [
                        {
                            "ac_id": AC_ID,
                            "declared_producer": None,
                            "declared_proof": "test_required: false",
                            "reason": "no phase in this run's roster produces this deliverable",
                        }
                    ],
                }
            }
        )

        declined_payload = declined_claim.result or {}
        contention_payload = genuine_contention.result or {}
        gate_payload = gate_failure.result or {}
        unproducible_payload = unproducible.result or {}

        self.assertEqual(
            declined_payload.get("halt_kind"),
            "declined_step",
            f"A declined claim must be classified declined_step. Got: {declined_payload}",
        )
        for name, payload in (
            ("genuine_contention", contention_payload),
            ("gate_failure", gate_payload),
            ("unproducible", unproducible_payload),
        ):
            self.assertNotEqual(
                payload.get("halt_kind"),
                "declined_step",
                f"[{name}] must NOT be classified declined_step. Got: {payload}",
            )

        declined_text = str(declined_payload).lower()
        gate_text = str(gate_payload).lower()
        unproducible_text = str(unproducible_payload).lower()
        for marker in CONTENTION_MARKERS:
            self.assertNotIn(marker, declined_text, declined_payload)
            self.assertNotIn(marker, gate_text, gate_payload)
            self.assertNotIn(marker, unproducible_text, unproducible_payload)

        contention_text = str(contention_payload).lower()
        self.assertTrue(
            any(marker in contention_text for marker in CONTENTION_MARKERS),
            f"Genuine contention must still carry contention wording. Got: {contention_payload}",
        )

        self.assertTrue(
            calls_with_label(genuine_contention, "claim-connected"),
            "Sanity: the contention scenario must have actually dispatched claim-connected.",
        )


if __name__ == "__main__":
    unittest.main()
