"""BO-400e-1: pr-reviewer's H-1 regression (2026-09-14).

A phase whose frontmatter reads `failed` and that left NO ## Comments trace
at all must still count as demanded. Deleting `claimedPhasesForCompletion`
(the caller-supplied `orderedPhases` union this AC's own fix removes,
correctly, per the three caller-list attempts covered in the sibling
test_bo_400e_1.py / test_bo_400e_1_ii.py) also deleted the safety net that
used to catch this case: `demandedPhasesFromRecord`'s original two-field
union (`needed_phases` + `signed_off_agents`) drops a `failed`-with-no-comment
phase entirely, since its status is neither `needed` nor sign-off-bearing.
`record.failed_phases` closes exactly that gap. Reproduces pr-reviewer's own
fixture, verbatim, against BOTH twins.

Split out of what was originally a single test_bo_400e_1.py (804 raw lines,
690 content lines -- over the 400 content-line file-size limit); pr-reviewer
itself suggested this file name for this family of tests. Shared helpers
(`_is_refused`, `_outstanding_agents`) live in `_bo_400e_1_support.py`.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402
from _bo_400e_1_support import _is_refused, _outstanding_agents  # noqa: E402

H1_PHASES = ["test-writer", "python-coder"]
H1_FAILED_PHASE = "python-coder"
H1_TICKET_TITLE = "Two-phase ticket (BO-400e-1 pr-reviewer H-1 fixture)"


class _FailedPhaseNoTraceCase(unittest.TestCase):
    """Base: drive a two-phase ticket whose one phase reads `failed` in its
    frontmatter, reproducing pr-reviewer's exact H-1 fixture."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400e1_h1_")
        self._tmpdirs.append(path)
        return path

    def _write_ticket(self, worktree: str, name: str, *, seed_failed_comment: bool):
        """test-writer is `signed_off` with a real passing signoff;
        python-coder is `failed` in the frontmatter. ``seed_failed_comment``
        controls whether python-coder ALSO carries a real
        ``(status: blocker)`` ## Comments heading -- the control case -- or
        leaves NO trace anywhere in the record -- the bug fixture, per
        pr-reviewer's exact H-1 report (the BUG-23 divergence: a phase agent
        that reports a blocker but leaves nothing on disk)."""
        seeded = [("test-writer", "ok")]
        if seed_failed_comment:
            seeded.append(("python-coder", "blocker"))
        return H.write_ticket_record(
            worktree,
            name,
            H1_PHASES,
            title=H1_TICKET_TITLE,
            agent_statuses={"test-writer": "signed_off", "python-coder": "failed"},
            seeded_signoffs=seeded,
            extra_frontmatter={"source_ac": "BO-400e-1"},
        )

    def _drive(self, script: str, worktree: str, ticket_path: str):
        """Run the close attempt: python-coder is re-dispatched (a `failed`
        status is dispatchable per selectDispatchableByStatus), returns a
        blocker with NO record written (record: False -- the BUG-23 shape),
        and the failure-classifier reports `cross_agent` -- pr-reviewer's
        exact fixture, verbatim. `has_test_requirements: True` so the
        coder-guard (BO-2000e-2) does not intercept the dispatch before it
        reaches the classifier."""
        cfg = {
            "title": H1_TICKET_TITLE,
            "has_test_requirements": True,
            "ordered_phases": [
                {"agent": "test-writer", "status": "signed_off"},
                {"agent": "python-coder", "status": "failed"},
            ],
            "results": {
                "python-coder": {"status": "blocker", "record": False},
            },
            "classify": {"python-coder": "cross_agent"},
        }
        scenario = H.single_ticket_scenario(worktree, ticket_path, cfg)
        return H.run_driver(script, scenario)


class TestFailedPhaseWithNoCommentTraceStillBlocksCompletion(_FailedPhaseNoTraceCase):
    def test_failed_phase_with_no_comment_trace_still_blocks_completion(self):
        # covers: BO-400e-1
        # angle: failure
        """pr-reviewer H-1: a phase whose frontmatter reads `failed` and that
        leaves NO ## Comments heading anywhere in the record (here on the
        failure/cross_agent-skip path, the same self-report-vs-persisted-
        evidence divergence the success path already guards against) must
        still be counted as demanded and named outstanding -- not silently
        dropped from the set because it is neither `needed` nor sign-off-
        bearing.

        THE REGRESSION THIS PINS CLOSED: before `record.failed_phases` was
        added to `demandedPhasesFromRecord`'s union, this exact fixture made
        both drivers write `status: done` with `skipped_phases` naming
        python-coder and `completed_phases: []` -- a ticket recorded done
        having had a phase actively fail and leave zero evidence, which is
        the phantom-done signature this entire epic exists to close.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = self._write_ticket(
                    worktree, "01_h1_no_trace.md", seed_failed_comment=False
                )
                observation = self._drive(script, worktree, ticket_path)

                self.assertIsNone(
                    observation["error"],
                    f"{driver} threw during the run: {observation['error']}",
                )
                result = observation["result"] or {}

                self.assertTrue(
                    _is_refused(result),
                    f"{driver} recorded this ticket done despite python-coder "
                    "carrying `failed` status with zero ## Comments trace -- "
                    f"the exact H-1 phantom-done regression. Payload: "
                    f"{json.dumps(result, sort_keys=True)}",
                )
                outstanding = _outstanding_agents(result)
                self.assertIn(
                    H1_FAILED_PHASE,
                    outstanding,
                    f"{driver} refused the close but did not name "
                    f"'{H1_FAILED_PHASE}' as outstanding -- a failed phase "
                    "with no comment trace must still count as demanded. "
                    f"outstanding={outstanding}",
                )

                record = H.read_record(ticket_path)
                self.assertNotEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver} wrote `status: done` to the ticket record for "
                    "a ticket whose python-coder phase actively failed and "
                    "left no evidence -- the H-1 phantom-done regression.",
                )


class TestFailedPhaseWithPreSeededBlockerCommentAlsoBlocksCompletion(
    _FailedPhaseNoTraceCase
):
    def test_failed_phase_with_pre_seeded_blocker_comment_also_blocks_completion(
        self,
    ):
        # covers: BO-400e-1
        # angle: failure
        """Control case (pr-reviewer's own control): the SAME fixture, but
        with a pre-seeded `(status: blocker)` ## Comments heading for
        python-coder. This was never the gap H-1 found -- `signed_off_agents`
        already picks up the heading regardless of its status value, so the
        per-phase loop already marks it non-passing -- but it must keep
        refusing after the H-1 fix, showing the fix is additive rather than a
        second regression in the opposite direction (e.g. the `failed_phases`
        union somehow suppressing a real, already-caught blocker)."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = self._write_ticket(
                    worktree, "01_h1_control.md", seed_failed_comment=True
                )
                observation = self._drive(script, worktree, ticket_path)

                self.assertIsNone(
                    observation["error"],
                    f"{driver} threw during the run: {observation['error']}",
                )
                result = observation["result"] or {}

                self.assertTrue(
                    _is_refused(result),
                    f"{driver} recorded this ticket done despite python-coder "
                    "carrying a `(status: blocker)` sign-off heading -- not a "
                    f"passing outcome. Payload: {json.dumps(result, sort_keys=True)}",
                )
                outstanding = _outstanding_agents(result)
                self.assertIn(
                    H1_FAILED_PHASE,
                    outstanding,
                    f"{driver} refused the close but did not name "
                    f"'{H1_FAILED_PHASE}' as outstanding. outstanding={outstanding}",
                )

                record = H.read_record(ticket_path)
                self.assertNotEqual(record["lifecycle_status"], "done")


if __name__ == "__main__":
    unittest.main()
