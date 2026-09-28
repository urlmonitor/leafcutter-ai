"""Behavioral tests for BO-400e-1-i, part 2 of 2.

See _bo_400e_1_i_fixtures.py for the shared ticket-record builders, the base
TestCase, and the full defect writeup this family exercises, and
test_bo_400e_1_i_handoff_resolution.py (part 1) for the resolved case and its
three required counter-cases. Split solely to keep each file under the 400
CONTENT-line cap.

This file covers:

  * the BO-400a-2-ii twin-agreement seam over a resolved handoff, and
  * the REJECTED-FIRST-IMPLEMENTATION hole: a dangling handoff followed by an
    UNRELATED agent's later pass must NOT read as resolved. The original
    implementation resolved a handover whenever the record's globally-last
    entry was a pass by anyone other than the handing agent, so an unrelated
    later pass silently discharged work that was never picked up. None of the
    counter-cases in part 1 catch this, because all three put the dangling
    handoff LAST in the record -- this test puts an unrelated pass after it.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402
from _bo_400e_1_i_fixtures import (  # noqa: E402
    _HandoffResolutionCase,
    _handoff_history_ticket,
    _outstanding_agents,
    _scenario_for,
)

# ---------------------------------------------------------------------------
# BO-400a-2-ii twin seam: both drivers must decide a resolved handoff the
# same way, and that shared decision must be the correct (resolved) one.
# ---------------------------------------------------------------------------


class TestBothDriversAgreeOnAResolvedHandoff(_HandoffResolutionCase):
    def test_both_drivers_decide_a_resolved_handoff_identically(self):
        # covers: BO-400e-1-i
        # angle: seam
        """The SAME resolved-handoff record, fed through build-feature.js AND
        build-ticket.js, must produce the identical -- and correct -- close
        decision. Asserting agreement alone would pass on two drivers that
        agree by both being wrong, which is exactly today's state (both
        currently refuse), so this test also pins the shared answer to
        `completed`.
        """
        agents = ["python-coder", "test-writer"]
        history = [("python-coder", "handoff"), ("test-writer", "ok")]

        decisions = {}
        for driver, script in H.TWIN_DRIVERS.items():
            worktree = self._worktree()
            ticket_path = _handoff_history_ticket(
                worktree, "01_twin_resolved.md", agents, history,
                title="Twin resolved handoff ticket",
                handoff_targets={0: "test-writer"},
            )
            observation = H.run_driver(
                script,
                _scenario_for(worktree, ticket_path, agents, "Twin resolved handoff ticket"),
            )
            result = observation["result"]
            decisions[driver] = (
                H.read_record(ticket_path)["lifecycle_status"] == "done",
                "python-coder" not in _outstanding_agents(result),
            )

        self.assertEqual(
            len(set(decisions.values())),
            1,
            "build-feature.js and build-ticket.js decided this resolved "
            f"handover DIFFERENTLY, which BO-400a-2-ii forbids: {decisions!r}",
        )
        shared = next(iter(decisions.values()))
        self.assertEqual(
            shared,
            (True, True),
            "both drivers agree with each other, but not on the correct "
            "answer: a resolved handover (sibling passed afterwards) must "
            f"let the close proceed. Decisions: {decisions!r}",
        )


# ---------------------------------------------------------------------------
# The hole the first implementation shipped with: an UNRELATED later pass
# must not discharge a dangling handoff.
# ---------------------------------------------------------------------------


class TestUnrelatedLaterPassDoesNotResolveHandoff(_HandoffResolutionCase):
    def test_unrelated_later_pass_does_not_resolve_dangling_handoff(self):
        # covers: BO-400e-1-i
        # angle: boundary
        """python-coder hands off to test-writer, which never runs; some
        UNRELATED agent (documentation-expert) later records 'ok' on its own,
        unconnected work.

        A structural ("whoever spoke last") reading of the record would see a
        passing entry after the handover and call python-coder's handoff
        resolved -- which is exactly the phantom-done hole the first
        implementation of this fix shipped with. The named recipient
        (test-writer) never ran, so python-coder must still be reported
        outstanding regardless of what anyone else recorded afterwards.
        """
        # test-writer -- the named recipient -- is deliberately NOT one of
        # this ticket's own required phases: it never ran, so it must play no
        # part in the required set at all. Folding it in would add its own
        # permanent "never dispatched" outstanding entry regardless of the
        # handoff fix, diluting what this test actually isolates.
        agents = ["python-coder", "documentation-expert"]
        history = [
            ("python-coder", "handoff"),
            ("documentation-expert", "ok"),
        ]

        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _handoff_history_ticket(
                    worktree, "01_unrelated_pass.md", agents, history,
                    title="Dangling handoff with unrelated later pass",
                    handoff_targets={0: "test-writer"},
                )
                self.assert_history_precondition(ticket_path, history)

                observation = H.run_driver(
                    script,
                    _scenario_for(
                        worktree, ticket_path, agents,
                        "Dangling handoff with unrelated later pass",
                    ),
                )
                result = observation["result"]

                self.assertIn(
                    "python-coder",
                    _outstanding_agents(result),
                    f"{driver}: python-coder handed off to test-writer, which "
                    "never ran -- documentation-expert's later 'ok' is on "
                    "unrelated work and must not discharge THIS handoff, so "
                    f"python-coder must still be named outstanding. "
                    f"Result: {result!r}",
                )
                self.assertNotEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver}: an unrelated agent's later pass resolved a "
                    "dangling handoff whose named recipient never ran -- that "
                    f"is a phantom-done write. Result: {result!r}",
                )


if __name__ == "__main__":
    import unittest

    unittest.main()
