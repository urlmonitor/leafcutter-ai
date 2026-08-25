"""Behavioral tests for a ticket that has no needed phase left (H-1).

Covers:
  BO-400a-2-ii  — the completion write happens when the ticket's OWN record
                  proves every needed phase carries a passing sign-off.
  BO-400a-2-iii — a ticket that is NOT recorded done has the outstanding phase
                  named, in its record and in the drive's report.

THE DEFECT.

  build-feature.js:1015-1023 (and its twin build-ticket.js:855-862) early-return
  as soon as the needed-phase set is empty:

      if (neededPhases.length === 0) {
        return {
          status: "ok",
          message: `No phases to run for ticket "${title}". All agents are
                    already signed_off or not_needed.`,
          ticket_path: worktreeTicketPath,
          resolved_target: resolvedTarget,
        };
      }

  That payload carries no `ticket_completed` key. The epic loop at
  build-feature.js:1687 filters on `ticket_completed === true`, so the ticket
  lands in `incompleteTickets` and the whole epic returns `blocked` — with
  `outstanding_phases: []` and `unverified_phases: []`. Nothing is named, so
  nothing can be fixed, and a re-run is byte-identical.

  The trap closes on our own remediation advice. buildTicketOutcome's
  suggested_action tells the operator to "add the sign-off it owes"; doing so
  flips that agent to signed_off, empties the needed set, and blocks the epic
  permanently. It is also reachable from a transient completion-write failure,
  and from an epic member whose only remaining needed phase is pull-request —
  selectDispatchPhases (build-feature.js:370) drops that phase for epic members
  BEFORE the length check, and no amount of sign-off editing can undo it.

WHAT MUST HAPPEN INSTEAD. A ticket with no needed phase is not a ticket to skip:
it is a ticket whose record already carries the evidence. It must be read back,
adjudicated against that record, and recorded done through the same completion
path as any other ticket — never bypass it.

NOT A DUPLICATE of test_ticket_done_recording.py's
``test_a_fully_signed_off_ticket_still_records_done``: that test drives four
phases that are NEEDED and that sign off during the drive. This is the other
case — phases already signed_off BEFORE the drive, so the needed set is empty
and the phase loop never runs.

n_location_rule is 2 — both twins carry the early return — so the single-ticket
tests run against both drivers via subTest.

Every test EXECUTES a real driver through harness_build_ticket_guard.mjs and
asserts on the ticket .md the run left on disk.
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
EPIC_GATES = ["test-runner", "commit"]


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _not_completed_entries(result) -> list:
    """Every member the epic output presents as not-completed work.

    Read from BOTH lists on purpose. A member that could not be recorded
    complete surfaces today in ``incomplete_tickets``; once the per-ticket
    payload carries a non-ok status for an incomplete ticket (see
    test_single_ticket_drive_outcome_status.py — H-2) the same member surfaces
    in ``halted_tickets`` instead. The contract asserted here is identical in
    both cases, so neither branch may be used to sidestep it.
    """
    entries: list = []
    for key in ("incomplete_tickets", "halted_tickets"):
        entries.extend((result or {}).get(key) or [])
    return entries


def _entry_names_a_phase(entry) -> bool:
    """True when a not-completed entry tells the operator which phase to fix."""
    if list(entry.get("outstanding_phases") or []) or list(
        entry.get("unverified_phases") or []
    ):
        return True
    prose = " ".join(
        str(entry.get(key) or "") for key in ("detail", "error", "message")
    )
    return any(phase in prose for phase in H.canonical_phase_order())


def _signed_off_record(worktree, name, phases, *, title=None, subdir=None, needed=()):
    """A record whose phases are already signed_off before the drive starts.

    ``needed`` names phases left as needed (used for the pull-request case).
    Every signed_off phase also carries a real passing sign-off entry in
    ## Comments, so the record genuinely proves the work happened.
    """
    kwargs = {}
    if subdir is not None:
        kwargs["subdir"] = subdir
    return H.write_ticket_record(
        worktree,
        name,
        phases,
        title=title or name,
        agent_statuses={p: ("needed" if p in needed else "signed_off") for p in phases},
        seeded_signoffs=[(p, "ok") for p in phases if p not in needed],
        **kwargs,
    )


def _planner_phases(phases, needed=()):
    """The planner reply for such a record — verbatim ordered_phases."""
    return [
        {"agent": p, "status": ("needed" if p in needed else "signed_off")}
        for p in phases
    ]


class _EmptyNeededSetCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400_empty_")
        self._tmpdirs.append(path)
        return path

    def assert_scenario_precondition(self, ticket_path, expected_signoffs):
        """Non-vacuity guard: the record must start in the state under test.

        If the record does not begin as `todo` with the sign-offs already
        present, a later failure would be attributable to the fixture rather
        than to the driver.
        """
        before = H.read_record(ticket_path)
        self.assertEqual(
            before["lifecycle_status"],
            "todo",
            "harness precondition: the record must start not-done, or 'it reads "
            "done afterwards' proves nothing.",
        )
        self.assertEqual(
            sorted(before["signed_off_agents"]),
            sorted(expected_signoffs),
            "harness precondition: the record must already carry the sign-off "
            f"entries under test. Got: {before['signed_off_agents']}",
        )


class TestTicketWithNoNeededPhaseIsStillAdjudicated(_EmptyNeededSetCase):
    """BO-400a-2-ii: the trigger is the sign-offs present in the record — which
    is exactly what a ticket with an empty needed set already has."""

    def test_a_fully_presigned_ticket_is_read_back_and_recorded_done(self):
        # covers: BO-400a-2-ii
        """Every phase was signed off by an earlier drive, so nothing is needed.

        The record proves the work completed. The drive must read it back,
        adjudicate it, and write done — not bypass the completion path with a
        bare `status: ok` that leaves the store saying nothing happened.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = _signed_off_record(
                    worktree, "01_presigned.md", FOUR_PHASES, title="Presigned ticket"
                )
                self.assert_scenario_precondition(ticket_path, FOUR_PHASES)

                observation = H.run_driver(
                    script,
                    H.single_ticket_scenario(
                        worktree,
                        ticket_path,
                        {
                            "title": "Presigned ticket",
                            "phases": FOUR_PHASES,
                            "has_test_requirements": True,
                            "ordered_phases": _planner_phases(FOUR_PHASES),
                            "results": H.phase_results({p: True for p in FOUR_PHASES}),
                        },
                    ),
                )
                result = observation["result"]

                self.assertEqual(
                    H.phase_dispatch_labels(observation),
                    [],
                    f"{driver} dispatched a phase agent although every phase is "
                    "already signed_off. Nothing here asks for work to be redone.",
                )
                self.assertGreaterEqual(
                    H.readback_count_for(observation, ticket_path),
                    1,
                    f"{driver} never read the ticket's record back. A ticket with "
                    "no needed phase is not a ticket to skip — its record is the "
                    "evidence the completion decision must be taken from "
                    f"(accepted labels: {H.ACCEPTED_READBACK_LABELS}). "
                    f"Result: {_serialized(result)}",
                )
                applied = [
                    w for w in H.writes_for(observation, ticket_path) if w["applied"]
                ]
                self.assertTrue(
                    applied,
                    f"{driver} performed no completion write "
                    f"(accepted labels: {H.ACCEPTED_WRITE_LABELS}). Every phase "
                    "this ticket names carries a passing sign-off in its own "
                    "record, which is precisely the trigger BO-400a-2-ii "
                    f"specifies. Result: {_serialized(result)}",
                )
                self.assertEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver} left the record reading todo although its own "
                    "record proves every phase passed. A reader given only this "
                    "ticket cannot tell the work completed.",
                )
                self.assertEqual(
                    (result or {}).get("ticket_completed"),
                    True,
                    f"{driver} returned no `ticket_completed: true`. The epic "
                    "loop filters on exactly that key, so its absence puts a "
                    "finished ticket into the incomplete set and blocks the "
                    f"epic. Result: {_serialized(result)}",
                )

    def test_a_presigned_ticket_with_no_signoff_entries_is_not_recorded_done(self):
        # covers: BO-400a-2-iii
        """The counter-case that keeps the fix honest.

        The frontmatter agents: map says signed_off but the record carries no
        sign-off entry for any of them — the exact BUG-23 signature, where a
        gate reported success and left nothing behind. The needed set is empty
        here too, so the cheapest fix for the test above ('empty needed set →
        write done') would mark this ticket done and convert an
        inverse-phantom-done defect into a real one.

        Only evidence that is present and positive may produce a done record.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = H.write_ticket_record(
                    worktree,
                    "01_hollow.md",
                    FOUR_PHASES,
                    title="Hollow ticket",
                    agent_statuses={p: "signed_off" for p in FOUR_PHASES},
                    seeded_signoffs=(),
                )
                before = H.read_record(ticket_path)
                self.assertEqual(
                    before["signed_off_agents"],
                    [],
                    "harness precondition: this record must carry NO sign-off "
                    "entries, only signed_off frontmatter flags.",
                )

                observation = H.run_driver(
                    script,
                    H.single_ticket_scenario(
                        worktree,
                        ticket_path,
                        {
                            "title": "Hollow ticket",
                            "phases": FOUR_PHASES,
                            "has_test_requirements": True,
                            "ordered_phases": _planner_phases(FOUR_PHASES),
                            "results": H.phase_results({p: True for p in FOUR_PHASES}),
                        },
                    ),
                )
                result = observation["result"]

                self.assertNotEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver} recorded done a ticket whose record carries no "
                    "sign-off entry for any phase. A frontmatter flag is the "
                    "claim; the ## Comments entry is the evidence. Marking this "
                    "done makes the store assert work that left no trace.",
                )
                self.assertTrue(
                    any(
                        (result or {}).get(key)
                        for key in ("outstanding_phases", "not_completed")
                    ),
                    f"{driver} did not report this ticket as not completed, and "
                    "named no outstanding phase, so the operator has nothing to "
                    f"act on. Result: {_serialized(result)}",
                )


class TestEmptyNeededSetDoesNotBlockTheEpic(_EmptyNeededSetCase):
    """BO-400a-2-ii / -iii at the epic level: an empty needed set must not
    become an unnameable, unrecoverable epic block."""

    def _drive_epic(self, worktree, members):
        """members: {name: (phases, needed, ticket_cfg_extra)}"""
        epic_subdir = os.path.join("tickets", "00_inbox", "epics", "EPIC-EmptySet")
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)

        paths = {}
        tickets = {}
        for name, (phases, needed, extra) in members.items():
            path = _signed_off_record(
                worktree, name, phases, title=name, subdir=epic_subdir, needed=needed
            )
            paths[name] = path
            cfg = {
                "title": name,
                "phases": phases,
                "has_test_requirements": True,
                "ordered_phases": _planner_phases(phases, needed=needed),
                "results": H.phase_results({p: True for p in phases}),
            }
            cfg.update(extra)
            tickets[path] = cfg

        present = [{"path": p, "status": "todo"} for p in paths.values()]
        observation = H.run_driver(
            H.BUILD_FEATURE_JS,
            H.epic_scenario(
                worktree,
                epic_path,
                tickets,
                [{"present": present}, {"present": present}],
            ),
        )
        return observation, paths

    def test_an_epic_member_with_no_needed_phase_completes_instead_of_blocking(self):
        # covers: BO-400a-2-ii
        """One epic member, every phase already signed_off.

        Today the per-ticket driver early-returns with no `ticket_completed`
        key, the epic loop counts the member as incomplete, and the epic returns
        blocked naming nothing. The member's own record proves the work is done,
        so the epic must not be blocked by it.
        """
        worktree = self._worktree()
        observation, paths = self._drive_epic(
            worktree, {"01_presigned.md": (EPIC_GATES, (), {})}
        )
        result = observation["result"]
        ticket_path = paths["01_presigned.md"]

        self.assertEqual(
            H.read_record(ticket_path)["lifecycle_status"],
            "done",
            "the epic member's record still reads todo although every phase it "
            "names carries a passing sign-off in that record. Result: "
            f"{_serialized(result)}",
        )
        self.assertNotIn(
            ticket_path,
            [e.get("ticket_path") for e in _not_completed_entries(result)],
            "a member whose record proves every phase passed was counted as "
            "not completed, blocking the epic. Re-running changes nothing and "
            "there is no sign-off left to add. Result: "
            f"{_serialized(result)}",
        )

    def test_a_member_whose_only_needed_phase_is_pull_request_is_not_stranded(self):
        # covers: BO-400a-2-ii
        """The route no operator can fix by hand.

        selectDispatchPhases drops pull-request for epic members (the single
        epic PR is opened by finalize-feature) BEFORE the empty-set check, so a
        member whose last needed phase is pull-request has an empty dispatch set
        by construction. requiredPhasesForCompletion already defers that phase,
        so the completion decision has everything it needs — if it is reached.
        """
        worktree = self._worktree()
        phases = EPIC_GATES + ["pull-request"]
        observation, paths = self._drive_epic(
            worktree, {"01_pr_only.md": (phases, ("pull-request",), {})}
        )
        result = observation["result"]
        ticket_path = paths["01_pr_only.md"]

        self.assertEqual(
            H.read_record(ticket_path)["lifecycle_status"],
            "done",
            "the only phase this member still names as needed is pull-request, "
            "which the driver itself defers to finalize-feature. It can never be "
            "satisfied per ticket, so leaving the member not-done strands it "
            f"permanently. Result: {_serialized(result)}",
        )
        self.assertNotIn(
            ticket_path,
            [e.get("ticket_path") for e in _not_completed_entries(result)],
            "a member held open solely by the deferred pull-request phase was "
            f"counted as not completed. Result: {_serialized(result)}",
        )

    def test_every_incomplete_member_the_epic_reports_names_an_actionable_phase(self):
        # covers: BO-400a-2-iii
        """Two members: one fully pre-signed, one whose gate leaves no sign-off.

        The epic is legitimately blocked by the second member, so this test is
        non-vacuous both before and after the fix. What it forbids is a blocked
        report that names nothing: today the pre-signed member appears in
        incomplete_tickets with `outstanding_phases: []` and
        `unverified_phases: []`, giving the operator an epic that is blocked on
        a ticket with no stated problem.
        """
        worktree = self._worktree()
        observation, paths = self._drive_epic(
            worktree,
            {
                "01_presigned.md": (EPIC_GATES, (), {}),
                "02_silent_gate.md": (
                    EPIC_GATES,
                    tuple(EPIC_GATES),
                    {"results": H.phase_results({"test-runner": False, "commit": True})},
                ),
            },
        )
        result = observation["result"]
        entries = _not_completed_entries(result)

        self.assertTrue(
            entries,
            "harness precondition: one member's test-runner gate reported "
            "success and left no sign-off, so the epic must report at least one "
            f"member as not completed. Result: {_serialized(result)}",
        )
        for entry in entries:
            self.assertTrue(
                _entry_names_a_phase(entry),
                f"the epic reports {entry.get('ticket_path')} as not completed "
                "while naming no outstanding phase, no unverified phase, and no "
                "phase in its detail text. There is nothing for the operator to "
                "fix and a re-run is byte-identical — an unrecoverable block. "
                f"Entry: {json.dumps(entry, sort_keys=True)}",
            )


if __name__ == "__main__":
    unittest.main()
