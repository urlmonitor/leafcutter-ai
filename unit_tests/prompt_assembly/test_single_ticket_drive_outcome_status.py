"""Behavioral tests for the status a not-completed single-ticket drive reports (H-2).

Covers:
  BO-400a-2-iii — "the drive's report lists each of the three as not completed
                  and names the outstanding phase ... And a drive that cannot
                  read a ticket's record back at all leaves that ticket's state
                  untouched and reports it as not completed".

THE DEFECT.

  buildTicketOutcome (build-feature.js:686, and the identical twin in
  build-ticket.js) hardcodes ``status: "ok"`` into its base payload and then
  branches only on ``ticket_completed``:

      const base = { status: "ok", ... };
      ...
      base.ticket_completed = false;
      base.not_completed = true;

  build-feature.js:1790 returns that payload VERBATIM on the single-ticket
  branch, and build-ticket.js returns it as the whole script result. A live run
  whose ticket record was unreadable throughout therefore returned:

      {"status":"ok","completed_phases":[],"ticket_completed":false, ...}

  Every other failure exit in both drivers uses ``blocked`` or ``error`` —
  the empty-needed-set exit, the coder guard, the null-result guard, the
  retry-cap exit, the design/halt exit, the epic halt and the epic
  incomplete-member exit. ``status`` IS the machine-readable signal in these
  drivers, and this one path inverts it: the drive reports success for a ticket
  it could not confirm did anything at all.

  The epic loop compensates for its own members (it re-derives the verdict from
  ``ticket_completed`` at build-feature.js:1687). The single-ticket path has no
  such compensation, and neither does any other caller reading the payload.

NOTE ON THE THREE LEGACY TESTS that assert ``result["status"] == "ok"``
(test_test_requirements_guard.py:427, :500, :528). Those run in the harness's
NON-record mode — ``recordMode = !!scenario.tickets``
(harness_build_ticket_guard.mjs:122) — where no ticket record exists, so every
read-back returns unreadable and ``ticket_completed`` is false. They assert a
different AC (BO-2000e-2: whether the coder phase was dispatched), and the
status assertion is incidental to it. A fix that makes an unconfirmed drive
report a non-ok status will require those three assertions to be updated to
match; that is a consequence of this AC, not a reason to leave the inversion in
place. It is called out here so the coder does not read the breakage as a
regression.

n_location_rule is 2 — both twins carry buildTicketOutcome — so every test runs
against both drivers via subTest.
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

FOUR_PHASES = ["test-writer", "python-coder", "test-runner", "commit"]

#: Statuses that assert to a caller that the drive was fine.
_SUCCESS_STATUSES = {"ok", "success", "complete", "completed", "done"}

#: The failure vocabulary both drivers already use at every other exit, and the
#: set the epic loop's halted filter (build-feature.js:1636) recognises.
_FAILURE_STATUSES = {"blocked", "failed", "error", "halt"}


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


class _OutcomeStatusCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400_status_")
        self._tmpdirs.append(path)
        return path

    def drive_both_twins(self, results, **cfg_extra):
        for driver, script in H.TWIN_DRIVERS.items():
            worktree = self._worktree()
            ticket_path = H.write_ticket_record(
                worktree, "01_status_case.md", FOUR_PHASES, title="Status case ticket"
            )
            cfg = {
                "title": "Status case ticket",
                "phases": FOUR_PHASES,
                "has_test_requirements": True,
                "results": results,
            }
            cfg.update(cfg_extra)
            observation = H.run_driver(
                script, H.single_ticket_scenario(worktree, ticket_path, cfg)
            )
            yield driver, observation, ticket_path

    def assert_did_not_complete(self, result, driver):
        """Non-vacuity guard: the drive really did fail to complete the ticket.

        Asserted BEFORE the status assertion so a failure there is attributable
        to the reported status and not to a scenario that quietly succeeded.
        """
        self.assertIsInstance(
            result,
            dict,
            f"harness precondition: {driver} returned no payload at all.",
        )
        self.assertNotEqual(
            result.get("ticket_completed"),
            True,
            f"harness precondition: {driver} completed this ticket, so there is "
            f"no not-completed status to assert. Result: {_serialized(result)}",
        )


class TestNotCompletedDriveDoesNotReportOk(_OutcomeStatusCase):
    """BO-400a-2-iii: a drive that could not confirm the ticket is reported as
    not completed — including in the one field a caller reads first."""

    def test_an_unreadable_record_throughout_does_not_report_top_level_ok(self):
        # covers: BO-400a-2-iii
        """The live-observed case: the record cannot be read at any point.

        Nothing about this drive succeeded — no phase could be confirmed, no
        lifecycle state was written, the store is untouched. Reporting
        ``status: "ok"`` tells every caller the opposite.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})

        for driver, observation, ticket_path in self.drive_both_twins(
            results, delete_record_before_run=True
        ):
            with self.subTest(driver=driver):
                result = observation["result"]
                self.assertFalse(
                    os.path.exists(ticket_path),
                    "harness precondition: the record must be absent for the "
                    "whole run.",
                )
                self.assert_did_not_complete(result, driver)

                self.assertNotIn(
                    result.get("status"),
                    _SUCCESS_STATUSES,
                    f"{driver} reported status {result.get('status')!r} for a "
                    "drive in which the ticket's record could never be read, no "
                    "phase could be confirmed and nothing was written. Every "
                    "other failure exit in this driver uses blocked or error, "
                    "so status is the machine-readable signal — and this path "
                    f"inverts it. Result: {_serialized(result)}",
                )

    def test_a_gate_that_left_no_signoff_does_not_report_top_level_ok(self):
        # covers: BO-400a-2-iii
        """The BUG-23 case: the record is readable, but a gate that reported
        success left no sign-off, so the ticket cannot be recorded done.

        Distinct condition from the test above — that one is an I/O failure,
        this one is a readable record with missing evidence. A fix keyed only on
        the unreadable branch would leave this one reporting ok.
        """
        results = H.phase_results(
            {
                "test-writer": True,
                "python-coder": True,
                "test-runner": False,
                "commit": True,
            }
        )

        for driver, observation, ticket_path in self.drive_both_twins(results):
            with self.subTest(driver=driver):
                result = observation["result"]
                record = H.read_record(ticket_path)
                self.assertNotIn(
                    "test-runner",
                    record["signed_off_agents"],
                    "harness precondition: the test-runner gate must have left "
                    f"no sign-off. Record: {record['signed_off_agents']}",
                )
                self.assert_did_not_complete(result, driver)

                self.assertNotIn(
                    result.get("status"),
                    _SUCCESS_STATUSES,
                    f"{driver} reported status {result.get('status')!r} for a "
                    "ticket it explicitly refused to record complete. The same "
                    "payload carries not_completed: true and an "
                    "outstanding_phases list — the top-level status contradicts "
                    f"both. Result: {_serialized(result)}",
                )

    def test_the_not_completed_status_uses_the_drivers_own_failure_vocabulary(self):
        # covers: BO-400a-2-iii
        """The replacement status must be one a caller already recognises.

        The epic loop's halted filter (build-feature.js:1636) matches
        failed / blocked / halt / error, and every other exit in both drivers
        emits one of those. An invented status string would be as unreadable to
        a caller as ``ok`` is misleading.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})

        for driver, observation, _ticket_path in self.drive_both_twins(
            results, delete_record_before_run=True
        ):
            with self.subTest(driver=driver):
                result = observation["result"]
                self.assert_did_not_complete(result, driver)
                self.assertIn(
                    result.get("status"),
                    _FAILURE_STATUSES,
                    f"{driver} reported status {result.get('status')!r}. A "
                    "not-completed drive must report one of "
                    f"{sorted(_FAILURE_STATUSES)} — the vocabulary every other "
                    "exit in this driver already uses and every caller already "
                    f"branches on. Result: {_serialized(result)}",
                )

    def test_a_completed_single_ticket_drive_still_reports_ok(self):
        # covers: BO-400a-2-iii
        """CONTROL CASE — expected GREEN before and after the fix.

        Every phase signs off, the record is written done. This drive must still
        report ok. Without this control the cheapest way to pass the three tests
        above is to stop reporting ok at all, which would make the status field
        useless in the other direction.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})

        for driver, observation, ticket_path in self.drive_both_twins(results):
            with self.subTest(driver=driver):
                result = observation["result"]
                self.assertEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    "harness precondition: this control ticket must actually "
                    "complete, or it constrains nothing.",
                )
                self.assertEqual(
                    result.get("status"),
                    "ok",
                    f"{driver} did not report ok for a ticket it drove to "
                    "completion and recorded done. The fix must distinguish "
                    "completed from not-completed, not suppress the success "
                    f"status. Result: {_serialized(result)}",
                )


if __name__ == "__main__":
    unittest.main()
