"""
MODULE: test_fail_closed_agent_results
GOAL: Behavioral proof that the workflow runtime treats an agent result it
    cannot use as a FAILURE rather than a success.
BUSINESS CONTEXT: KI-SS-001. A subagent has no idle state — emitting text with
    no tool call ends the agent, and that text becomes its result. So an agent
    that parks ("waiting for the completion notification…") returns prose with
    no status, and agent() itself resolves to null when an agent dies or is
    stopped. Both were previously read as success:
      - build-epic.js coerced a missing status to "ok" (`: "ok"`), so a dead
        ticket-supervisor became a completed ticket;
      - build-epic.js reduced a dead planner to a blank plan and then reported
        `status: "ok"` — "Epic complete. All tickets are done." — having
        dispatched nothing;
      - both drivers' null guards tested truthiness, so an unrecognised but
        truthy status ("complete") passed the guard and then matched no branch,
        landing back in silent success.
    The failure is shaped exactly like success, which is why it survived: no
    gate fires, because no gate runs.
ARCHITECTURE: Executes the real workflow scripts under the E2 stub harness
    (Node subprocess, mocked agent()) and asserts on the workflow's TERMINAL
    RETURN PAYLOAD. Per CLAUDE.md "Gate / Workflow ACs — Verify Behaviorally,
    Not by Grep", these assert observable behaviour under a simulated dead
    agent — not the presence of a string in the source.
"""

from __future__ import annotations

import unittest
from pathlib import Path

from _workflow_engine_harness import run_workflow_under_e2

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOWS = _REPO_ROOT / "templates" / "workflows-js"
_BUILD_EPIC = _WORKFLOWS / "build-epic.js"

# A status that must never be reported when nothing actually ran.
_SUCCESS = "ok"


class TestDeadPlannerIsNotEpicComplete(unittest.TestCase):
    """A planner that returns nothing must not be read as 'epic complete'."""

    def test_null_planner_reply_does_not_report_success(self):
        """agent() returning null must not become 'Epic complete'.

        This is the two-step reduction the fix removes:
            const plan = plannerResult || {};      // dead planner -> blank plan
            const batches = plan.batches || [];    // blank plan  -> no batches
            if (batches.length === 0) return { status: "ok", ... }
        Each line looks defensive; in sequence they manufacture a completion
        claim from an agent that never answered.
        """
        result = run_workflow_under_e2(
            _BUILD_EPIC,
            label_responses={"epic-planner": None},
            args={"target": "tickets/00_inbox/epics/EPIC-Example"},
        )

        payload = result.result
        self.assertIsNotNone(
            payload,
            f"workflow returned no terminal payload; stderr={result.stderr}",
        )
        self.assertNotEqual(
            payload.get("status"),
            _SUCCESS,
            "a dead planner was reported as a successful run — the epic would "
            f"be recorded complete having dispatched nothing. payload={payload}",
        )
        self.assertEqual(payload.get("status"), "undetermined")

    def test_null_planner_message_does_not_claim_completion(self):
        """The message must not tell the reader the epic is done."""
        result = run_workflow_under_e2(
            _BUILD_EPIC,
            label_responses={"epic-planner": None},
            args={"target": "tickets/00_inbox/epics/EPIC-Example"},
        )

        payload = result.result or {}
        message = str(payload.get("message", "")).lower()
        self.assertNotIn(
            "all tickets are done",
            message,
            f"a dead planner produced a completion claim: {message!r}",
        )

    def test_planner_reply_missing_batches_key_is_undetermined(self):
        """A reply that omits `batches` is not an answer, so it is not empty."""
        result = run_workflow_under_e2(
            _BUILD_EPIC,
            label_responses={"epic-planner": {"title": "EPIC-Example"}},
            args={"target": "tickets/00_inbox/epics/EPIC-Example"},
        )

        payload = result.result or {}
        self.assertEqual(
            payload.get("status"),
            "undetermined",
            "a planner reply with no batches array must be undetermined, not "
            f"an empty (and therefore complete) epic. payload={payload}",
        )


class TestGuardDoesNotOverfire(unittest.TestCase):
    """The fail-closed guard must not swallow a legitimate empty plan."""

    def test_affirmatively_empty_batches_still_reports_ok(self):
        """`batches: []` is a real answer meaning everything is already done.

        Without this test the fix could 'pass' by making every run undetermined,
        which would trade a false green for a false red.
        """
        result = run_workflow_under_e2(
            _BUILD_EPIC,
            label_responses={
                "epic-planner": {"title": "EPIC-Example", "batches": []}
            },
            args={"target": "tickets/00_inbox/epics/EPIC-Example"},
        )

        payload = result.result or {}
        self.assertEqual(
            payload.get("status"),
            _SUCCESS,
            "an affirmatively empty plan is a completed epic and must still "
            f"report ok. payload={payload}",
        )


class TestDeadTicketSupervisorHaltsBatch(unittest.TestCase):
    """A ticket whose supervisor returns nothing must halt, not be counted."""

    def test_null_ticket_result_does_not_complete_the_epic(self):
        """The `: "ok"` coercion turned a dead supervisor into a done ticket."""
        ticket_path = "tickets/00_inbox/epics/EPIC-Example/01_thing.md"
        result = run_workflow_under_e2(
            _BUILD_EPIC,
            label_responses={
                "epic-planner": {
                    "title": "EPIC-Example",
                    "batches": [
                        {"batch_number": 1, "tickets": [{"path": ticket_path}]}
                    ],
                },
                # The dead/parked supervisor.
                f"ticket:{ticket_path}": None,
            },
            args={"target": "tickets/00_inbox/epics/EPIC-Example"},
        )

        payload = result.result or {}
        self.assertNotEqual(
            payload.get("status"),
            _SUCCESS,
            "a ticket whose supervisor returned nothing was counted as "
            f"completed. payload={payload}",
        )


if __name__ == "__main__":
    unittest.main()
