"""Behavioral tests for a completion decision taken over an EMPTY required set.

Covers:
  BO-400a-2-iv — a completion decision reached with no phase required of the
                 ticket never records it done.

THE DEFECT.

  concludeTicket (build-feature.js:823, twin build-ticket.js:751) computes

      const requiredPhases = requiredPhasesForCompletion(
        spec.basePhases, (record && record.needed_phases) || [], spec.deferredPhases);

  and hands it to completionVerdictFromRecord, which builds `outstanding` with

      for (const agentName of required) { ... }

  When `required` is `[]` that loop never runs, `outstanding` stays `[]`, and
  the verdict reads `completed: outstanding.length === 0` → TRUE. concludeTicket
  then calls writeTicketCompletion() and the ticket's own record is flipped to
  `status: done` having had ZERO phases required, ZERO dispatched and ZERO
  sign-offs. An empty collection of failures is read as proof that nothing
  failed, when it is really proof that nothing was looked at.

  Three input shapes converge on it, and a guard written against any one leaves
  the other two live:
    A. the ticket names no list of phases at all   (no `agents:` key)
    B. the ticket names an empty list              (`agents: {}`)
    C. the ticket names phases, every one not_needed

NOT A DUPLICATE of test_empty_needed_phase_set_completion.py. That module
covers the case where the required set is NON-empty — every phase already
signed_off before the drive — and asserts the write MUST happen
(BO-400a-2-ii), plus the hollow-record counter-case (BO-400a-2-iii, phases
named but no sign-off entries). This module is its missing sibling: the
required set is itself EMPTY, so every per-phase check in that record passes
vacuously and none of its assertions can fire. The control below
(test_a_ticket_signed_off_before_the_drive_still_records_done) restates that
module's positive path deliberately — it is the boundary this refusal must not
cross, and an AC whose refusals are all satisfied by "stop writing done
records" is worse than the defect.

n_location_rule is 2 — the decision lives in both twins — so every
single-ticket case runs against both drivers via subTest.

Every test EXECUTES a real driver through harness_build_ticket_guard.mjs and
asserts on the ticket .md the run left on disk. Per CLAUDE.md "Gate / Workflow
ACs — Verify Behaviorally, Not by Grep", a test that finds the guard in the
source passes on a guard that is computed and ignored.
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

THREE_PHASES = ["test-runner", "pr-reviewer", "commit"]

#: Wording that points the operator at the ticket's OWN list of phases as the
#: thing to correct. Deliberately excludes "no phase left to run" and "every
#: phase it names" — both appear in today's (wrong) completion message, so a
#: token list that matched them would pass on the unfixed driver.
_PHASE_LIST_TOKENS = (
    "agents:",
    "agents map",
    "list of phases",
    "phase list",
    "names no phase",
    "no phase is named",
    "declares no phase",
    "names none",
)

#: Remediation advice that is meaningless here: there is no phase to re-run and
#: no sign-off to add, because the ticket names no phase at all.
_MISDIRECTION_TOKENS = (
    "re-run that phase",
    "re-run the phase",
    "add the sign-off it owes",
    "add the sign-off",
)


def _serialized(result) -> str:
    return json.dumps(result, sort_keys=True) if result is not None else ""


def _payload_text(result) -> str:
    return _serialized(result).lower()


class _VacuousCompletionCase(unittest.TestCase):
    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400iv_")
        self._tmpdirs.append(path)
        return path

    # -- fixtures ----------------------------------------------------------

    def no_phase_list_at_all(self, worktree):
        """Shape A: the record carries no ``agents:`` key, and the planner
        reply states no ordered list of phases either way."""
        path = H.write_ticket_record(
            worktree,
            "01_no_phase_list.md",
            [],
            title="Ticket naming no phases at all",
            omit_agents=True,
        )
        cfg = {
            "title": "Ticket naming no phases at all",
            "has_test_requirements": True,
            "plan_reply": {"mode": "omit_ordered_phases"},
        }
        return path, cfg

    def empty_phase_list(self, worktree):
        """Shape B: an empty list rather than no list — ``agents: {}``."""
        path = H.write_ticket_record(
            worktree,
            "01_empty_phase_list.md",
            [],
            title="Ticket with an empty phase list",
        )
        cfg = {
            "title": "Ticket with an empty phase list",
            "has_test_requirements": True,
            "ordered_phases": [],
        }
        return path, cfg

    def all_not_needed(self, worktree):
        """Shape C: phases are named, and every one is marked not needed."""
        path = H.write_ticket_record(
            worktree,
            "01_all_not_needed.md",
            THREE_PHASES,
            title="Ticket whose every phase is not needed",
            agent_statuses={p: "not_needed" for p in THREE_PHASES},
        )
        cfg = {
            "title": "Ticket whose every phase is not needed",
            "has_test_requirements": True,
            "ordered_phases": [
                {"agent": p, "status": "not_needed"} for p in THREE_PHASES
            ],
        }
        return path, cfg

    # -- non-vacuity guard -------------------------------------------------

    def assert_scenario_precondition(self, ticket_path, shape):
        """The fixture must start in the state under test.

        Without this, "the record does not read done afterwards" proves
        nothing: it would hold just as well for a record that never existed,
        or one that already carried the sign-offs the decision is about.
        """
        before = H.read_record(ticket_path)
        self.assertTrue(
            before["exists"],
            f"harness precondition ({shape}): the record must exist before the drive.",
        )
        self.assertEqual(
            before["lifecycle_status"],
            "todo",
            f"harness precondition ({shape}): the record must start not-done, or "
            "'it does not read done afterwards' proves nothing.",
        )
        self.assertEqual(
            before["signed_off_agents"],
            [],
            f"harness precondition ({shape}): the record must carry NO sign-off "
            "entry, so any done write is attributable to the empty required set "
            f"and to nothing else. Got: {before['signed_off_agents']}",
        )
        needed = [a for a, s in (before.get("agents") or {}).items() if s == "needed"]
        self.assertEqual(
            needed,
            [],
            f"harness precondition ({shape}): the record must name no NEEDED "
            f"phase — that is the condition under test. Got: {needed}",
        )

    # -- the shared refusal assertion --------------------------------------

    def assert_refused(self, driver, ticket_path, observation, shape):
        result = observation["result"]
        after = H.read_record(ticket_path)

        self.assertNotEqual(
            after["lifecycle_status"],
            "done",
            f"{driver} recorded {shape} as done. Zero phases were required of "
            "this ticket, zero were dispatched and its record carries zero "
            "sign-offs, so nothing was verified — yet the completion decision "
            "said yes. An empty set of outstanding phases means nothing was "
            "looked at, not that everything passed. "
            f"Result: {_serialized(result)}",
        )
        self.assertEqual(
            after["lifecycle_status"],
            "todo",
            f"{driver} altered the recorded lifecycle state of {shape}. A "
            "refusal must leave the record exactly as the drive found it "
            f"(found: todo, now: {after['lifecycle_status']!r}).",
        )
        applied = [w for w in H.writes_for(observation, ticket_path) if w["applied"]]
        self.assertEqual(
            applied,
            [],
            f"{driver} performed a completion write for {shape} "
            f"(accepted labels: {H.ACCEPTED_WRITE_LABELS}). The write itself is "
            "the defect: no evidence was inspected, because there was no phase "
            f"to inspect evidence for. Result: {_serialized(result)}",
        )
        self.assertIsNot(
            (result or {}).get("ticket_completed"),
            True,
            f"{driver} reported {shape} as completed. `ticket_completed` is the "
            "machine-readable verdict the epic loop and every downstream caller "
            "route on, so reporting true here propagates the phantom-done claim "
            f"beyond this ticket. Result: {_serialized(result)}",
        )

    def drive(self, script, worktree, ticket_path, cfg):
        return H.run_driver(
            script, H.single_ticket_scenario(worktree, ticket_path, cfg)
        )


class TestATicketRequiringNoPhaseIsNeverRecordedDone(_VacuousCompletionCase):
    """The three input shapes that reach the completion decision with an empty
    required set. Each is a distinct input; a guard against one leaves the
    others live."""

    def test_a_ticket_naming_no_phases_at_all_is_not_recorded_done(self):
        # covers: BO-400a-2-iv
        """Shape A — the ticket carries no list of phases whatsoever.

        Its record has no ``agents:`` key and the planner reply states no
        ordered list either way, so ``claimedPhasesForCompletion`` and the
        record's ``needed_phases`` are both empty and the required set is [].
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path, cfg = self.no_phase_list_at_all(worktree)
                self.assert_scenario_precondition(ticket_path, "no phase list at all")

                observation = self.drive(script, worktree, ticket_path, cfg)
                self.assert_refused(
                    driver, ticket_path, observation, "a ticket naming no phases at all"
                )

    def test_a_ticket_with_an_empty_phase_list_is_not_recorded_done(self):
        # covers: BO-400a-2-iv
        """Shape B — an empty list, not an absent one.

        A guard written against absence (``!plan.ordered_phases``) takes the
        normal branch here, so this shape must be asserted separately.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path, cfg = self.empty_phase_list(worktree)
                self.assert_scenario_precondition(ticket_path, "empty phase list")

                observation = self.drive(script, worktree, ticket_path, cfg)
                self.assert_refused(
                    driver,
                    ticket_path,
                    observation,
                    "a ticket carrying an empty phase list",
                )

    def test_a_ticket_whose_every_phase_is_not_needed_is_not_recorded_done(self):
        # covers: BO-400a-2-iv
        """Shape C — the shape most likely to be waved through.

        The ticket DOES name phases, and every one is explicitly not_needed, so
        an implementer reads it as a ticket with nothing left to do. It is not:
        nothing was verified, and the record carries no sign-off for any of the
        three phases it names.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path, cfg = self.all_not_needed(worktree)
                self.assert_scenario_precondition(ticket_path, "all phases not_needed")

                observation = self.drive(script, worktree, ticket_path, cfg)
                self.assert_refused(
                    driver,
                    ticket_path,
                    observation,
                    "a ticket whose every named phase is not_needed",
                )


class TestTheRefusalReasonIsActionable(_VacuousCompletionCase):
    """The refusal must tell the operator something they can act on."""

    def test_the_not_completed_reason_names_the_missing_phase_list_not_a_missing_signoff(
        self,
    ):
        # covers: BO-400a-2-iv
        """The existing not-completed wording names nothing that exists here.

        buildTicketOutcome's suggested_action tells the operator to "re-run that
        phase (or add the sign-off it owes)". With no phase at all that names
        nothing they can do, and sends them looking for a phase failure that
        never happened. The reason for this case must point at the ticket's own
        list of phases as the thing to correct.

        Asserted on shapes B and C only. Shape A (no list stated at all) is also
        an unusable plan reply under BO-1900a-4-ii and is held back one step
        earlier, with the planning failure — not the phase list — as its reason.
        """
        shapes = {
            "empty phase list": self.empty_phase_list,
            "all phases not_needed": self.all_not_needed,
        }
        for driver, script in H.TWIN_DRIVERS.items():
            for shape, builder in shapes.items():
                with self.subTest(driver=driver, shape=shape):
                    worktree = self._worktree()
                    ticket_path, cfg = builder(worktree)
                    self.assert_scenario_precondition(ticket_path, shape)

                    observation = self.drive(script, worktree, ticket_path, cfg)
                    result = observation["result"]
                    text = _payload_text(result)

                    self.assertIsNot(
                        (result or {}).get("ticket_completed"),
                        True,
                        f"{driver} reported a {shape} ticket as completed, so it "
                        "states no reason at all. There is nothing here for the "
                        f"operator to read. Result: {_serialized(result)}",
                    )
                    self.assertTrue(
                        any(token in text for token in _PHASE_LIST_TOKENS),
                        f"{driver} refused a {shape} ticket without pointing the "
                        "operator at the ticket's own list of phases as the thing "
                        "to correct. Expected the output to name it (one of "
                        f"{list(_PHASE_LIST_TOKENS)}). "
                        f"Result: {_serialized(result)}",
                    )
                    found_misdirection = [
                        token for token in _MISDIRECTION_TOKENS if token in text
                    ]
                    self.assertEqual(
                        found_misdirection,
                        [],
                        f"{driver} told the operator to {found_misdirection} for a "
                        f"{shape} ticket. Neither exists to act on: no phase ran, "
                        "and no phase is named that could owe a sign-off. That "
                        "advice sends them looking for a phase failure that never "
                        f"happened. Result: {_serialized(result)}",
                    )


class TestTheRefusalDoesNotBreakLegitimateCompletion(_VacuousCompletionCase):
    """CONTROL. The boundary the refusal must not cross."""

    def test_a_ticket_signed_off_before_the_drive_still_records_done(self):
        # covers: BO-400a-2-iv
        """A NON-empty required set whose every phase carries a real sign-off.

        This is BO-400a-2-ii's behaviour, restated here as this AC's control.
        It is load-bearing, not decorative: the cheapest way to pass all three
        refusals above is to stop writing done records at all — the exact state
        this AC family started in — and every resumed drive produces this shape.
        A fix that suppresses the write whenever no phase ran during THIS drive
        breaks all of them, and only this test sees it.

        GREEN on the current code, and must stay green after the fix.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = H.write_ticket_record(
                    worktree,
                    "01_presigned.md",
                    THREE_PHASES,
                    title="Ticket signed off before the drive",
                    agent_statuses={p: "signed_off" for p in THREE_PHASES},
                    seeded_signoffs=[(p, "ok") for p in THREE_PHASES],
                )
                before = H.read_record(ticket_path)
                self.assertEqual(
                    before["lifecycle_status"],
                    "todo",
                    "harness precondition: the record must start not-done.",
                )
                self.assertEqual(
                    sorted(before["signed_off_agents"]),
                    sorted(THREE_PHASES),
                    "harness precondition: this control's required set must be "
                    "NON-empty and every phase in it must already carry a real "
                    "sign-off entry — that is what distinguishes it from the "
                    f"three refusals. Got: {before['signed_off_agents']}",
                )

                observation = self.drive(
                    script,
                    worktree,
                    ticket_path,
                    {
                        "title": "Ticket signed off before the drive",
                        "has_test_requirements": True,
                        "ordered_phases": [
                            {"agent": p, "status": "signed_off"} for p in THREE_PHASES
                        ],
                    },
                )
                result = observation["result"]

                self.assertEqual(
                    H.read_record(ticket_path)["lifecycle_status"],
                    "done",
                    f"{driver} refused a genuine completion. Every phase this "
                    "ticket names carries a passing sign-off in its own record, "
                    "which is a non-empty required set that was fully satisfied. "
                    "A refusal here means the empty-set guard was written as "
                    "'nothing ran during this drive', which strands every "
                    f"resumed drive. Result: {_serialized(result)}",
                )
                self.assertEqual(
                    (result or {}).get("ticket_completed"),
                    True,
                    f"{driver} did not report this ticket as completed although "
                    "its record proves every named phase passed. "
                    f"Result: {_serialized(result)}",
                )


class TestBothTwinsRefuseIdentically(_VacuousCompletionCase):
    """The twin obligation, verified rather than asserted in a file header."""

    def test_both_drivers_refuse_the_vacuous_completion_identically(self):
        # covers: BO-400a-2-iv
        """Run the no-phase scenario against each twin as it exists on disk.

        Both must leave the record untouched, and both must agree. The two
        drivers carry the same completion decision by copy, so a fix applied to
        one and not the other is invisible to any test that drives only one.
        """
        outcomes = {}
        for driver, script in H.TWIN_DRIVERS.items():
            worktree = self._worktree()
            ticket_path, cfg = self.no_phase_list_at_all(worktree)
            self.assert_scenario_precondition(ticket_path, "no phase list at all")

            observation = self.drive(script, worktree, ticket_path, cfg)
            outcomes[driver] = {
                "lifecycle_status": H.read_record(ticket_path)["lifecycle_status"],
                "completion_writes_applied": len(
                    [w for w in H.writes_for(observation, ticket_path) if w["applied"]]
                ),
                # Recorded as a boolean, not the raw value: a refusing driver
                # may legitimately report `false` or omit the key entirely, and
                # both are refusals. Only `true` is the defect.
                "claims_completed": (observation["result"] or {}).get(
                    "ticket_completed"
                )
                is True,
            }

        distinct = {json.dumps(v, sort_keys=True) for v in outcomes.values()}
        self.assertEqual(
            len(distinct),
            1,
            "the two twin drivers behaved DIFFERENTLY on a ticket that names no "
            "phase. They carry the same completion decision by copy, so the "
            "refusal must land in both in the same change. Outcomes: "
            f"{json.dumps(outcomes, sort_keys=True)}",
        )
        for driver, outcome in outcomes.items():
            self.assertEqual(
                outcome,
                {
                    "lifecycle_status": "todo",
                    "completion_writes_applied": 0,
                    "claims_completed": False,
                },
                f"{driver} did not refuse the vacuous completion. Expected the "
                "record left at todo, no completion write applied, and no "
                "`ticket_completed: true`. Outcomes: "
                f"{json.dumps(outcomes, sort_keys=True)}",
            )


if __name__ == "__main__":
    unittest.main()
