"""Behavioral tests for BO-400e-1-i: a handoff that was actually picked up.

Part 1 of the BO-400e-1-i family (see _bo_400e_1_i_fixtures.py for the shared
ticket-record builders, the base TestCase, and the full defect writeup this
family exercises). This file covers the RESOLVED case and its three REQUIRED
counter-cases. Part 2 (test_bo_400e_1_i_handoff_seam_and_unrelated_pass.py)
covers the twin-agreement seam and the unrelated-later-pass hole -- split out
solely to keep each file under the 400 CONTENT-line cap; there is no
behavioral reason these five-plus-one tests could not live in one file.
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
# The resolved case -- currently RED. This is the deadlock itself.
# ---------------------------------------------------------------------------


class TestResolvedHandoffCountsAsAccountedFor(_HandoffResolutionCase):
    def test_resolved_handoff_counts_as_accounted_for(self):
        # covers: BO-400e-1-i
        # angle: criterion
        """python-coder's latest entry is a handoff naming test-writer; the
        sibling it named recorded a passing entry AFTERWARDS; nothing since
        has returned work to python-coder.

        The phase must count as accounted for and the close must proceed. This
        is the exact shape of the observed deadlock: expected to FAIL against
        the current drivers, which refuse solely because the latest entry for
        'python-coder' reads 'handoff'.
        """
        agents = ["python-coder", "test-writer"]
        history = [("python-coder", "handoff"), ("test-writer", "ok")]

        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _handoff_history_ticket(
                    worktree, "01_resolved.md", agents, history,
                    title="Resolved handoff ticket",
                    handoff_targets={0: "test-writer"},
                )
                self.assert_history_precondition(ticket_path, history)

                observation = H.run_driver(
                    script,
                    _scenario_for(worktree, ticket_path, agents, "Resolved handoff ticket"),
                )
                result = observation["result"]

                self.assertEqual(
                    H.phase_dispatch_labels(observation),
                    [],
                    f"{driver}: no phase agent should be dispatched -- every "
                    "agent's frontmatter already reads signed_off.",
                )
                self.assertNotIn(
                    "python-coder",
                    _outstanding_agents(result),
                    f"{driver}: python-coder handed off and test-writer -- the "
                    "sibling it named -- recorded 'ok' afterwards, so python-coder "
                    "must not be reported outstanding. "
                    f"Result: {result!r}",
                )
                self.assertEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver}: the record was not recorded done although the "
                    "handing phase's sibling passed after the handover. "
                    f"Result: {result!r}",
                )
                self.assertEqual(
                    (result or {}).get("ticket_completed"),
                    True,
                    f"{driver}: `ticket_completed` was not true although the "
                    f"resolved handover should have let the close proceed. "
                    f"Result: {result!r}",
                )


# ---------------------------------------------------------------------------
# The three counter-cases -- currently GREEN. Blanket-accepting `handoff`
# would turn every one of these into a phantom-done write.
# ---------------------------------------------------------------------------


class TestUnresolvedHandoffsStillBlockTheClose(_HandoffResolutionCase):
    def test_dangling_handoff_still_blocks_the_close(self):
        # covers: BO-400e-1-i
        # angle: boundary
        """python-coder handed off; test-writer recorded NOTHING afterwards.

        A dangling handover -- work handed to a sibling that never ran -- must
        still refuse the close, naming python-coder. Without this counter-case
        the fix is indistinguishable from blanket-accepting `handoff`, which is
        a phantom-done vector strictly worse than the deadlock it replaces.
        """
        agents = ["python-coder", "test-writer"]
        history = [("python-coder", "handoff")]

        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _handoff_history_ticket(
                    worktree, "01_dangling.md", agents, history,
                    title="Dangling handoff ticket",
                )
                self.assert_history_precondition(ticket_path, history)

                observation = H.run_driver(
                    script,
                    _scenario_for(worktree, ticket_path, agents, "Dangling handoff ticket"),
                )
                result = observation["result"]

                self.assertIn(
                    "python-coder",
                    _outstanding_agents(result),
                    f"{driver}: test-writer never recorded anything after "
                    "python-coder's handoff, so python-coder must still be "
                    f"named outstanding. Result: {result!r}",
                )
                self.assertNotEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver}: a DANGLING handover -- no sibling entry at all "
                    "after it -- was recorded done. That is a phantom-done "
                    f"write. Result: {result!r}",
                )

    def test_handoff_whose_recipient_failed_still_blocks_the_close(self):
        # covers: BO-400e-1-i
        # angle: boundary
        """python-coder handed off; test-writer recorded a BLOCKER afterwards.

        A baton picked up and dropped is not a baton delivered -- the close
        must still be refused, naming python-coder.
        """
        agents = ["python-coder", "test-writer"]
        history = [("python-coder", "handoff"), ("test-writer", "blocker")]

        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _handoff_history_ticket(
                    worktree, "01_recipient_failed.md", agents, history,
                    title="Failed recipient ticket",
                )
                self.assert_history_precondition(ticket_path, history)

                observation = H.run_driver(
                    script,
                    _scenario_for(worktree, ticket_path, agents, "Failed recipient ticket"),
                )
                result = observation["result"]

                self.assertIn(
                    "python-coder",
                    _outstanding_agents(result),
                    f"{driver}: test-writer's entry after python-coder's handoff "
                    "is a blocker, not a passing outcome, so python-coder must "
                    f"still be named outstanding. Result: {result!r}",
                )
                self.assertNotEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver}: the named recipient's entry is a blocker, yet "
                    f"the record was recorded done. Result: {result!r}",
                )

    def test_work_handed_back_leaves_the_phase_outstanding(self):
        # covers: BO-400e-1-i
        # angle: criterion
        """python-coder handed off; test-writer passed; pr-reviewer THEN handed
        work back, and python-coder has recorded nothing since.

        Guards an implementation that finds any later passing entry by the
        named recipient and ignores what happened after it: the LAST thing
        the record says is that somebody wanted more, so python-coder must
        still be reported outstanding.
        """
        agents = ["python-coder", "test-writer", "pr-reviewer"]
        history = [
            ("python-coder", "handoff"),
            ("test-writer", "ok"),
            ("pr-reviewer", "handoff"),
        ]

        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _handoff_history_ticket(
                    worktree, "01_handed_back.md", agents, history,
                    title="Handed-back ticket",
                )
                self.assert_history_precondition(ticket_path, history)

                observation = H.run_driver(
                    script,
                    _scenario_for(worktree, ticket_path, agents, "Handed-back ticket"),
                )
                result = observation["result"]

                self.assertIn(
                    "python-coder",
                    _outstanding_agents(result),
                    f"{driver}: test-writer's passing entry was itself followed "
                    "by pr-reviewer handing work back -- the record's own last "
                    "word is that more was wanted, so python-coder must still "
                    f"be named outstanding. Result: {result!r}",
                )
                self.assertNotEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver}: work was handed back after the sibling's pass, "
                    f"yet the record was recorded done. Result: {result!r}",
                )


if __name__ == "__main__":
    import unittest

    unittest.main()
