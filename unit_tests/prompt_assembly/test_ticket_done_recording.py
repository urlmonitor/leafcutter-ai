"""Behavioral tests for the ticket-completion write (BUG-22).

Covers:
  BO-400a-2-ii  — a ticket the drive carried to completion is recorded done in
                  the ticket's OWN record.
  BO-400a-2-iii — a ticket with any needed phase skipped, blocked or unrecorded
                  is never recorded done.

Every test EXECUTES a real driver (templates/workflows-js/build-feature.js and
its twin build-ticket.js) through harness_build_ticket_guard.mjs and asserts on
the ticket .md file the run left on disk. Per CLAUDE.md "Gate / Workflow ACs —
Verify Behaviorally, Not by Grep": both the broken driver and the fixed one
contain completion-reporting code, so a source-reading test cannot tell them
apart. Only reading the record back can.

n_location_rule for both ACs is 2 — the completion decision in build-feature.js
and its twin in build-ticket.js must stay identical — so every test runs against
both drivers via subTest.

Observed defect (run wf_cc2b46d9-f6f): all 13 open tickets still read
`status: todo` after a 15.5-hour drive, including four the payload named as
completed batches and which have real feature commits on the branch.
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


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _reports_ticket_completed(result) -> bool:
    """True when the drive's report presents this ticket as completed work.

    A report is 'not completed' when it either carries a non-ok status, or
    carries an explicit outstanding/unrecorded marker. A bare `status: ok`
    with a "driven to completion" message is a completion claim.
    """
    if not isinstance(result, dict):
        return False
    outstanding_keys = (
        "outstanding_phases",
        "outstanding",
        "not_completed",
        "unrecorded_phases",
        "incomplete_phases",
        "unverified_phases",
    )
    if any(result.get(k) for k in outstanding_keys):
        return False
    return result.get("status") == "ok"


class _DriverRecordCase(unittest.TestCase):
    """Base: drive one ticket through both twins against a real record file."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400_")
        self._tmpdirs.append(path)
        return path

    def drive_both_twins(
        self,
        phases,
        results,
        *,
        has_test_requirements=True,
        classify=None,
        delete_record_after_phase=None,
        seeded_signoffs=(),
    ):
        """Yield (driver_name, observation, ticket_path) for each twin.

        Each driver gets its own fresh worktree and its own freshly written
        ticket record, so the two runs cannot contaminate each other.
        """
        for driver_name, script in H.TWIN_DRIVERS.items():
            worktree = self._worktree()
            ticket_path = H.write_ticket_record(
                worktree,
                "01_record_case.md",
                phases,
                title="Record case ticket",
                seeded_signoffs=seeded_signoffs,
            )
            cfg = {
                "title": "Record case ticket",
                "phases": phases,
                "has_test_requirements": has_test_requirements,
                "results": results,
            }
            if classify:
                cfg["classify"] = classify
            if delete_record_after_phase:
                cfg["delete_record_after_phase"] = delete_record_after_phase
            scenario = H.single_ticket_scenario(worktree, ticket_path, cfg)
            observation = H.run_driver(script, scenario)
            yield driver_name, observation, ticket_path


# ---------------------------------------------------------------------------
# BO-400a-2-ii — the completion write that was missing
# ---------------------------------------------------------------------------


class TestTicketRecordedDoneWhenEveryPhaseSignedOff(_DriverRecordCase):
    """BO-400a-2-ii: a ticket the drive really finished is recorded done in the
    ticket's own record, triggered by the sign-offs present in that record."""

    def test_ticket_with_all_needed_phases_signed_off_is_recorded_done(self):
        # covers: BO-400a-2-ii
        """All four needed phases run and each leaves a sign-off in the record.

        The run must write the done lifecycle state into the ticket's own
        record. Asserted by re-reading the .md file off disk after the run.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})

        for driver, observation, ticket_path in self.drive_both_twins(
            FOUR_PHASES, results
        ):
            with self.subTest(driver=driver):
                self.assertIsNone(
                    observation["error"],
                    f"{driver} threw during the run: {observation['error']}",
                )
                record = H.read_record(ticket_path)

                # Precondition: the four phases really did sign off in the record.
                self.assertEqual(
                    sorted(record["signed_off_agents"]),
                    sorted(FOUR_PHASES),
                    "harness precondition: every needed phase must have left a "
                    "sign-off in the record before the completion rule applies",
                )

                self.assertEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver} finished a ticket whose record carries a sign-off "
                    f"for every needed phase ({FOUR_PHASES}), but the record on "
                    f"disk still reads status: {record['lifecycle_status']!r}. "
                    "The drive must write the done lifecycle state into the "
                    "ticket's own record (BUG-22: the observed run reported four "
                    "completed batches while the store recorded zero tickets "
                    "done, which blocks finalize-feature's archive check).",
                )

    def test_completion_write_reaches_the_ticket_record_not_only_the_run_report(self):
        # covers: BO-400a-2-ii
        """The done state must be observable by re-reading the record, not only
        present in the value the workflow returned.

        This is the exact gap between the observed run's completed-batches
        payload and the untouched store: the payload was right, the store was
        never written.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})

        for driver, observation, ticket_path in self.drive_both_twins(
            FOUR_PHASES, results
        ):
            with self.subTest(driver=driver):
                result = observation["result"] or {}

                # The run reports success — this half already works today.
                self.assertEqual(
                    result.get("status"),
                    "ok",
                    f"{driver} precondition: the run should report success for a "
                    "ticket whose phases all succeeded",
                )

                # The load-bearing half: a write actually reached the record.
                writes = H.writes_for(observation, ticket_path)
                self.assertTrue(
                    writes,
                    f"{driver} returned a completed-work report but dispatched no "
                    f"completion write for {os.path.basename(ticket_path)}. "
                    f"Accepted write labels: {H.ACCEPTED_WRITE_LABELS}. "
                    "A report is not a record — BUG-22 is precisely a run whose "
                    "payload said the work completed while the store said nothing "
                    "happened.",
                )
                self.assertTrue(
                    all(w["applied"] for w in writes),
                    f"{driver} dispatched a completion write that did not land: "
                    f"{writes}",
                )

                record = H.read_record(ticket_path)
                self.assertEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver}: re-reading {os.path.basename(ticket_path)} off "
                    "disk after the run must show the done lifecycle state. A "
                    "reader given only the ticket has to be able to tell the "
                    f"work completed; it currently reads "
                    f"{record['lifecycle_status']!r}.",
                )

    def test_completion_is_driven_by_recorded_signoffs_not_by_the_run_tally(self):
        # covers: BO-400a-2-ii
        """A ticket the workflow counts among its completed work, but whose
        record is missing one needed phase's sign-off, must not be recorded done.

        This falsifies the most attractive wrong fix: writing done from the same
        in-memory completion tally that produced the misleading report. Such an
        implementation passes the two tests above and re-creates the defect the
        first time a phase fails to record.
        """
        results = H.phase_results(
            {
                "test-writer": True,
                "python-coder": True,
                "test-runner": False,  # reports ok, leaves NO sign-off
                "commit": True,
            }
        )

        for driver, observation, ticket_path in self.drive_both_twins(
            FOUR_PHASES, results
        ):
            with self.subTest(driver=driver):
                record = H.read_record(ticket_path)

                # Precondition: the record really is missing test-runner.
                self.assertNotIn(
                    "test-runner",
                    record["signed_off_agents"],
                    "harness precondition: test-runner must have left no sign-off",
                )

                # The decision must be taken FROM THE RECORD. A driver that never
                # consults the record cannot be distinguished from one that
                # consults it and gets the answer right by luck, so the read-back
                # is asserted here too.
                self.assertGreater(
                    H.readback_count_for(observation, ticket_path),
                    0,
                    f"{driver} took a completion decision for "
                    f"{os.path.basename(ticket_path)} without ever reading the "
                    f"record back. Accepted read-back labels: "
                    f"{H.ACCEPTED_READBACK_LABELS}. The completion trigger must be "
                    "the sign-offs actually present in the record, not the drive's "
                    "own tally of phases it dispatched.",
                )

                self.assertEqual(
                    H.writes_for(observation, ticket_path),
                    [],
                    f"{driver} wrote a completion state for a ticket whose record "
                    "is missing the test-runner sign-off.",
                )
                self.assertNotEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver} recorded done while the record carries no "
                    f"test-runner sign-off (present: "
                    f"{record['signed_off_agents']}).",
                )

    def test_successful_delivery_phase_alone_does_not_record_done(self):
        # covers: BO-400a-2-ii
        """A successful commit phase proves code landed, not that the review and
        test gates ran.

        Keying completion off the delivery phase would mark done exactly the
        tickets in the observed run that were missing their test-runner and
        pr-reviewer sign-offs.
        """
        phases = ["test-writer", "python-coder", "test-runner", "pr-reviewer", "commit"]
        results = H.phase_results(
            {
                "test-writer": True,
                "python-coder": True,
                "test-runner": False,  # ran, reported ok, recorded nothing
                "pr-reviewer": False,  # ran, reported ok, recorded nothing
                "commit": True,  # the delivery gate DID record
            }
        )

        for driver, observation, ticket_path in self.drive_both_twins(phases, results):
            with self.subTest(driver=driver):
                record = H.read_record(ticket_path)

                self.assertIn(
                    "commit",
                    record["signed_off_agents"],
                    "harness precondition: the delivery gate must have recorded",
                )

                self.assertGreater(
                    H.readback_count_for(observation, ticket_path),
                    0,
                    f"{driver} must decide completion from the record, not from a "
                    "successful delivery phase. No record read-back was observed. "
                    f"Accepted labels: {H.ACCEPTED_READBACK_LABELS}.",
                )
                self.assertEqual(
                    H.writes_for(observation, ticket_path),
                    [],
                    f"{driver} recorded done off the back of a successful commit "
                    "phase while test-runner and pr-reviewer left no sign-off.",
                )
                self.assertNotEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver}: the lifecycle state must be unchanged when a "
                    "needed review or test phase left no sign-off.",
                )


# ---------------------------------------------------------------------------
# BO-400a-2-iii — the fail-closed half. One negative case per condition.
# ---------------------------------------------------------------------------


class TestTicketNeverRecordedDoneWithOutstandingPhase(_DriverRecordCase):
    """BO-400a-2-iii: missing, blocked and unreadable evidence all read as
    not done. Only evidence that is present and positive produces a done record.
    """

    def test_phase_held_back_before_dispatch_blocks_the_done_record(self):
        # covers: BO-400a-2-iii
        """Condition 1 of 4: a needed phase is held back and never dispatched.

        The coder guard holds python-coder back because no tests exist. The
        drive must not record done, and its report must name the outstanding
        phase rather than presenting the ticket as completed.
        """
        phases = ["python-coder", "test-runner", "commit"]
        results = H.phase_results({p: True for p in phases})

        for driver, observation, ticket_path in self.drive_both_twins(
            phases, results, has_test_requirements=False
        ):
            with self.subTest(driver=driver):
                self.assertNotIn(
                    "python-coder",
                    observation["dispatched"],
                    "harness precondition: python-coder must have been held back",
                )
                record = H.read_record(ticket_path)
                result = observation["result"]

                self.assertNotEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver} recorded done for a ticket whose needed "
                    "python-coder phase was never dispatched.",
                )
                self.assertEqual(
                    H.writes_for(observation, ticket_path),
                    [],
                    f"{driver} dispatched a completion write for a held-back ticket.",
                )
                self.assertFalse(
                    _reports_ticket_completed(result),
                    f"{driver} reported the ticket as completed work while a "
                    f"needed phase was never dispatched: {_serialized(result)}",
                )
                self.assertIn(
                    "python-coder",
                    _serialized(result),
                    f"{driver} must name the outstanding phase in its report.",
                )

    def test_phase_reporting_a_blocker_blocks_the_done_record(self):
        # covers: BO-400a-2-iii
        """Condition 2 of 4: a needed phase is dispatched and reports a blocker.

        Classified cross_agent, so the drive continues past it — and must still
        refuse the done record and name the blocked phase as not completed.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})
        results["test-runner"] = {"status": "blocker", "record": True}

        for driver, observation, ticket_path in self.drive_both_twins(
            FOUR_PHASES, results, classify={"test-runner": "cross_agent"}
        ):
            with self.subTest(driver=driver):
                record = H.read_record(ticket_path)
                result = observation["result"]

                self.assertNotEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver} recorded done for a ticket whose test-runner phase "
                    "returned a blocker.",
                )
                self.assertEqual(
                    H.writes_for(observation, ticket_path),
                    [],
                    f"{driver} dispatched a completion write for a blocked ticket.",
                )
                self.assertFalse(
                    _reports_ticket_completed(result),
                    f"{driver} reported the ticket as completed work while "
                    f"test-runner returned a blocker: {_serialized(result)}",
                )
                self.assertIn(
                    "test-runner",
                    _serialized(result),
                    f"{driver} must name the blocked phase in its report.",
                )

    def test_phase_reporting_success_without_a_signoff_blocks_the_done_record(self):
        # covers: BO-400a-2-iii
        """Condition 3 of 4 — the condition the production run actually hit.

        Tickets 01, 03 and 09 each had at least one phase that ran, returned
        success, and left no sign-off. No completion write may occur, and the
        drive must not present the ticket as completed.
        """
        results = H.phase_results(
            {
                "test-writer": True,
                "python-coder": True,
                "test-runner": False,  # ran, returned ok, recorded nothing
                "commit": True,
            }
        )

        for driver, observation, ticket_path in self.drive_both_twins(
            FOUR_PHASES, results
        ):
            with self.subTest(driver=driver):
                record = H.read_record(ticket_path)
                result = observation["result"]

                self.assertNotEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver} recorded done while test-runner left no sign-off.",
                )
                self.assertEqual(
                    H.writes_for(observation, ticket_path),
                    [],
                    f"{driver} dispatched a completion write for a ticket whose "
                    "test-runner sign-off is absent.",
                )
                self.assertFalse(
                    _reports_ticket_completed(result),
                    f"{driver} reported the ticket as completed work although "
                    "test-runner ran and left no sign-off — the exact BUG-23 "
                    f"condition: {_serialized(result)}",
                )
                self.assertIn(
                    "test-runner",
                    _serialized(result),
                    f"{driver} must name the unrecorded phase in its report so a "
                    "reader can tell it apart from a phase that was skipped.",
                )

    def test_unreadable_ticket_record_leaves_the_state_untouched(self):
        # covers: BO-400a-2-iii
        """Condition 4 of 4: the record cannot be read back at all.

        Absence of a readable record is the strongest not-done signal there is.
        An implementation that treats an unreadable record as 'no outstanding
        phases found' converts an I/O failure into a done state.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})

        for driver, observation, ticket_path in self.drive_both_twins(
            FOUR_PHASES, results, delete_record_after_phase="commit"
        ):
            with self.subTest(driver=driver):
                self.assertFalse(
                    os.path.exists(ticket_path),
                    "harness precondition: the record must be unreadable at the "
                    "moment the completion decision is taken",
                )
                result = observation["result"]

                applied = [
                    w for w in H.writes_for(observation, ticket_path) if w["applied"]
                ]
                self.assertEqual(
                    applied,
                    [],
                    f"{driver} applied a completion write against an unreadable "
                    f"record: {applied}",
                )
                self.assertFalse(
                    _reports_ticket_completed(result),
                    f"{driver} reported the ticket as completed although its "
                    "record could not be read back. Fail closed: an unreadable "
                    "record must be reported as not completed, not assumed to "
                    f"mean the earlier phases were enough. Got: "
                    f"{_serialized(result)}",
                )

    def test_a_fully_signed_off_ticket_still_records_done(self):
        # covers: BO-400a-2-iii
        """CONTROL CASE — not optional.

        The same driver, one ticket with every needed phase signed off, must
        record done. Without this, a driver that simply never writes at all
        passes all four refusals above and looks correct — which is the state
        the store is in today.
        """
        results = H.phase_results({p: True for p in FOUR_PHASES})

        for driver, observation, ticket_path in self.drive_both_twins(
            FOUR_PHASES, results
        ):
            with self.subTest(driver=driver):
                record = H.read_record(ticket_path)
                self.assertEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver}: the four refusals in this class must be "
                    "attributable to their conditions, not to a driver that never "
                    "writes a done record at all. This control ticket has every "
                    f"needed phase signed off ({record['signed_off_agents']}) and "
                    f"still reads status: {record['lifecycle_status']!r}.",
                )


# ---------------------------------------------------------------------------
# BO-400a-2-iii — "no outstanding phases found" and "could not look" must never
# produce the same answer. The guard-ordering regression.
# ---------------------------------------------------------------------------

#: Advice that is actively wrong when the record could not be read: it sends the
#: operator to edit the frontmatter of a file that does not exist.
_EDIT_THE_MISSING_FILE_TOKENS = (
    "edit the agents: map",
    "edit the agents map",
    "correct the ticket's own list of phases",
    "so it names the phases this ticket actually requires",
    "do not look for a failed phase or a missing sign-off",
)

#: Payload keys that would mark the record as unread. Any one of them is enough;
#: what must not happen is silence.
_UNREADABLE_MARKER_KEYS = (
    "record_unreadable",
    "unreadable",
    "record_read_error",
    "record_error",
    "read_error",
    "completion_read_error",
)

#: The read failure the harness's own record I/O produces when the .md is gone.
#: Accepted as ONE of the ways the payload may report the failure. It is not
#: required on its own: the ordinary unreadable path (a NON-empty required set)
#: reports the failure in its message and in every outstanding reason but does
#: not carry the error string either, and this AC is about parity between the
#: two paths, not about a richer diagnosis on one of them.
_ENOENT_TOKEN = "ENOENT"


class TestUnreadableRecordIsNotFoldedIntoTheEmptyPhaseListPath(_DriverRecordCase):
    """BO-400a-2-iii, the fail-closed clause, against a guard-ordering defect.

    THE DEFECT. `completionVerdictFromRecord` (build-feature.js:539, twin
    build-ticket.js:412) now takes its empty-required-set refusal FIRST:

        if (required.length === 0) {           // BO-400a-2-iv, added later
          return { completed: false, unreadable: false,
                   noPhaseRequired: true, outstanding: [], duplicates: [] };
        }
        if (!record || record.readable !== true) {   // BO-400a-2-iii, older
          return { completed: false, unreadable: true, ... };
        }

    A ticket that is BOTH unreadable AND has an empty required set therefore
    reports `noPhaseRequired` and DISCARDS the read failure — `unreadable: false`
    on a record nobody could open. A reviewer probed exactly that (every phase
    `not_needed`, the record deleted before the run) and got:

        "no_phase_required": true, "outstanding_phases": [],
        "suggested_action": "Correct the ticket's own list of phases: edit the
                             agents: map in its frontmatter ... Do not look for
                             a failed phase or a missing sign-off"

    The operator is told to edit the frontmatter of a file that does not exist,
    and NOTHING in the payload names the ENOENT — no unreadable marker, no error
    string. The driver HAS the error (`record.error` is passed into this very
    function) and drops it on the floor.

    This is BO-400a-2-iii being violated by a guard added for a later record:
    "an unreadable record must be handled as its own case, not folded into the
    empty-list path", because "no outstanding phases found" and "could not look"
    must never produce the same answer. Both refusals are correct in isolation;
    the defect is only which one answers first, which is why it survived two
    green suites.

    Both twins, because n_location_rule is 2 and the two files carry the same
    function verbatim.
    """

    THREE_PHASES = ["test-writer", "python-coder", "commit"]

    # -- fixtures ----------------------------------------------------------

    def drive_unreadable_with_empty_required_set(self, script):
        """Every phase not_needed AND the record gone before the drive starts.

        The two conditions the defect needs, set up independently: the required
        set is empty because the ticket claims no phase, and the record is
        unreadable because it is not there. Mirrors the reviewer's probe.
        """
        # The fixture's own title and filename are deliberately NEUTRAL: an
        # earlier draft called them "unreadable…", and the driver echoes the
        # title into its message, so the test's own fixture satisfied the
        # "does the payload mention the read failure?" assertion and the case
        # passed green against the defect.
        worktree = self._worktree()
        ticket_path = H.write_ticket_record(
            worktree,
            "01_gone_and_no_phase.md",
            self.THREE_PHASES,
            title="Ticket naming no needed phase",
            agent_statuses={p: "not_needed" for p in self.THREE_PHASES},
        )
        cfg = {
            "title": "Ticket naming no needed phase",
            "has_test_requirements": True,
            "ordered_phases": [
                {"agent": p, "status": "not_needed"} for p in self.THREE_PHASES
            ],
            "delete_record_before_run": True,
        }
        observation = H.run_driver(
            script, H.single_ticket_scenario(worktree, ticket_path, cfg)
        )
        return observation, ticket_path

    def drive_unreadable_with_a_required_set(self, script):
        """CONTROL fixture: unreadable, but the required set is NOT empty.

        The record vanishes after the last phase, so the completion decision is
        taken against a record it cannot read while four phases are required of
        it. This is the ordinary unreadable case, and the fix is a reordering —
        a reordering that changes the ordinary case is a regression.
        """
        worktree = self._worktree()
        ticket_path = H.write_ticket_record(
            worktree,
            "01_gone_with_phases.md",
            FOUR_PHASES,
            title="Ticket naming needed phases",
        )
        cfg = {
            "title": "Ticket naming needed phases",
            "phases": FOUR_PHASES,
            "has_test_requirements": True,
            "results": H.phase_results({p: True for p in FOUR_PHASES}),
            "delete_record_after_phase": "commit",
        }
        observation = H.run_driver(
            script, H.single_ticket_scenario(worktree, ticket_path, cfg)
        )
        return observation, ticket_path

    # -- non-vacuity guards ------------------------------------------------

    def assert_the_record_really_was_unreadable(self, driver, observation, ticket_path):
        """PROVE the drive actually failed to read the record back.

        Everything below is about how a READ FAILURE is reported. If the record
        was readable, or was never read at all, the assertions would pass or
        fail for reasons that have nothing to do with this AC.
        """
        self.assertIsNone(
            observation["error"],
            f"{driver} threw during the run rather than returning a payload: "
            f"{observation['error']}",
        )
        self.assertFalse(
            os.path.exists(ticket_path),
            f"{driver} precondition: the record must be absent at the moment the "
            "completion decision is taken, or there is no read failure to report.",
        )
        readbacks = [
            rb
            for rb in observation.get("readbacks") or []
            if rb.get("ticket_path") == ticket_path
        ]
        self.assertTrue(
            readbacks,
            f"{driver} precondition: the drive never read the record back at all "
            f"(accepted labels: {H.ACCEPTED_READBACK_LABELS}), so it never "
            "reached the read failure this test is about.",
        )
        # The LAST read-back is the one the completion decision is taken
        # against. Earlier per-phase read-backs may legitimately have succeeded
        # (the record vanishes mid-drive in the control fixture); what matters
        # is that the record was unreadable at the moment the verdict was formed.
        self.assertIs(
            readbacks[-1]["readable"],
            False,
            f"{driver} precondition: the final read-back — the one the completion "
            "decision is taken against — must have reported the record "
            f"unreadable. Got: {readbacks[-1]}",
        )

    def assert_still_refused_and_nothing_written(
        self, driver, observation, ticket_path, shape
    ):
        """REGRESSION GUARD, green today and after the fix.

        The fix restores a diagnosis. It must not buy that diagnosis by turning
        an unreadable record into a done record — the strongest not-done signal
        there is becoming a completion claim would be a far worse defect than
        the missing diagnosis.
        """
        result = observation["result"] or {}
        self.assertIsNot(
            result.get("ticket_completed"),
            True,
            f"{driver} reported {shape} as completed work although its record "
            f"could not be read back. Payload: {_serialized(result)}",
        )
        self.assertFalse(
            _reports_ticket_completed(result),
            f"{driver} presented {shape} as completed work although its record "
            f"could not be read back. Payload: {_serialized(result)}",
        )
        applied = [w for w in H.writes_for(observation, ticket_path) if w["applied"]]
        self.assertEqual(
            applied,
            [],
            f"{driver} applied a completion write for {shape} against a record it "
            f"could not read: {applied}",
        )
        self.assertFalse(
            os.path.exists(ticket_path),
            f"{driver} created or restored a record file for {shape}. A refusal "
            "must leave the store exactly as the drive found it.",
        )

    # -- the two red cases -------------------------------------------------

    def test_unreadable_record_with_an_empty_required_set_reports_the_read_failure(
        self,
    ):
        # covers: BO-400a-2-iii
        """The read failure must survive the empty required set.

        "No outstanding phases found" and "could not look" must never produce
        the same answer — and here they produce not merely the same answer but
        the WRONG one: the payload asserts the ticket names no phase, which is a
        statement about the contents of a file the drive could not open.

        The driver holds the diagnosis: `record.error` carries the ENOENT and is
        passed straight into `completionVerdictFromRecord`. It is discarded by
        the branch that answers first.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                observation, ticket_path = self.drive_unreadable_with_empty_required_set(
                    script
                )
                self.assert_the_record_really_was_unreadable(
                    driver, observation, ticket_path
                )
                self.assert_still_refused_and_nothing_written(
                    driver,
                    observation,
                    ticket_path,
                    "a ticket that is unreadable and names no needed phase",
                )

                result = observation["result"] or {}
                payload_text = _serialized(result)
                message = str(result.get("message") or "").lower()

                markers = [k for k in _UNREADABLE_MARKER_KEYS if result.get(k)]
                says_so = "could not be read" in message or "unreadable" in message
                carries_error = _ENOENT_TOKEN in payload_text

                self.assertTrue(
                    markers or says_so or carries_error,
                    f"{driver} took a completion decision against a record it "
                    "could not open and the payload says NOTHING about the read "
                    "failure: no unreadable marker (looked for "
                    f"{list(_UNREADABLE_MARKER_KEYS)}), no message naming the "
                    "failure, and not a trace of the error the read-back "
                    f"returned ({_ENOENT_TOKEN}). The empty-required-set refusal "
                    "answers first and discards `record.error`, so an I/O failure "
                    "is reported as a statement about the contents of the file "
                    f"that could not be read. Payload: {payload_text}",
                )

    def test_unreadable_record_is_not_reported_as_a_ticket_naming_no_phase(self):
        # covers: BO-400a-2-iii
        """The refusal must not advise editing a file that could not be read.

        `no_phase_required` is a claim about what the ticket's frontmatter says,
        and its remediation advice — "edit the agents: map in its frontmatter",
        "do not look for a failed phase or a missing sign-off" — is actionable
        only if the file exists. Handed to an operator whose record is gone it is
        worse than silence: it names a cause that was never established and
        sends them to a file that is not there.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                observation, ticket_path = self.drive_unreadable_with_empty_required_set(
                    script
                )
                self.assert_the_record_really_was_unreadable(
                    driver, observation, ticket_path
                )
                self.assert_still_refused_and_nothing_written(
                    driver,
                    observation,
                    ticket_path,
                    "a ticket that is unreadable and names no needed phase",
                )

                result = observation["result"] or {}
                advice = (
                    str(result.get("suggested_action") or "")
                    + " "
                    + str(result.get("message") or "")
                ).lower()
                offending = [t for t in _EDIT_THE_MISSING_FILE_TOKENS if t in advice]

                self.assertEqual(
                    offending,
                    [],
                    f"{driver} tells the operator to {offending} for a ticket "
                    "whose record could not be opened. The drive never read that "
                    "frontmatter, so it cannot know the ticket names no phase — "
                    "it only knows it could not look. Advice that names an "
                    "unestablished cause is worse than no advice: it stops the "
                    "operator looking for the real one. Payload: "
                    f"{_serialized(result)}",
                )
                self.assertIsNot(
                    result.get("no_phase_required"),
                    True,
                    f"{driver} asserts `no_phase_required: true` about a record it "
                    "could not read. That field is a claim about the contents of "
                    "the file, and no reading of it took place. Payload: "
                    f"{_serialized(result)}",
                )

    # -- the control -------------------------------------------------------

    def test_unreadable_record_with_a_required_set_reports_exactly_what_it_does_today(
        self,
    ):
        # covers: BO-400a-2-iii
        """CONTROL — not optional. The fix is a REORDERING.

        A reordering that changes the ordinary case is a regression, and the
        ordinary case is the one that runs on every drive: an unreadable record
        with phases required of it. It must keep reporting the outstanding
        phases, the read failure in its message, and the error the read-back
        returned — and must NOT start reporting `no_phase_required`.

        GREEN today, and must stay green after the fix.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                observation, ticket_path = self.drive_unreadable_with_a_required_set(
                    script
                )
                self.assert_the_record_really_was_unreadable(
                    driver, observation, ticket_path
                )
                self.assert_still_refused_and_nothing_written(
                    driver,
                    observation,
                    ticket_path,
                    "a ticket that is unreadable and names needed phases",
                )

                result = observation["result"] or {}
                payload_text = _serialized(result)

                self.assertIsNot(
                    result.get("no_phase_required"),
                    True,
                    f"{driver}: this ticket required phases, so the empty-set "
                    "refusal must not claim it. Payload: " + payload_text,
                )
                self.assertTrue(
                    result.get("outstanding_phases"),
                    f"{driver}: the ordinary unreadable case must still name every "
                    "phase it could not confirm. Payload: " + payload_text,
                )
                self.assertIn(
                    "could not be read",
                    str(result.get("message") or "").lower(),
                    f"{driver}: the ordinary unreadable case must still say in its "
                    "message that the record could not be read back. Payload: "
                    + payload_text,
                )
                self.assertEqual(
                    [t for t in _EDIT_THE_MISSING_FILE_TOKENS if t in payload_text.lower()],
                    [],
                    f"{driver}: the ordinary unreadable case must not start "
                    "advising the operator to edit the frontmatter of a file that "
                    "could not be read. Payload: " + payload_text,
                )


if __name__ == "__main__":
    unittest.main()
