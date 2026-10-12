"""Behavioral tests for BO-400e-1 -- the three caller-list attempts.

The steps a close is checked against are the ones the ticket's own record
demands, and the caller cannot change that list.

THE DEFECT (architect-review's blast-radius read, ticket Comments):
``requiredPhasesForCompletion(drivenPhases, recordNeededPhases, deferredPhases)``
is identically implemented in both drivers as a UNION of the caller-supplied
``drivenPhases`` (what the ticket-planner reply, or the drive's own dispatch
tally, claims is needed) with the record's own needed-agents list. A caller
that supplies a WIDENED list -- phases the record never names at all -- gets
those phases added to the required set today, which is exactly the "union"
reconciliation strategy this AC forbids. The only implementation that passes
all three of the AC's attempts never reads the caller-supplied list at all.

Every test EXECUTES a real driver (templates/workflows-js/build-feature.js and
its twin build-ticket.js) through harness_build_ticket_guard.mjs and asserts on
the ticket .md file and the payload the run produced. Per CLAUDE.md "Gate /
Workflow ACs -- Verify Behaviorally, Not by Grep": the phase-list code, the
completion prompt and the parity check are ALL already present in the source
today (per the ticket's own Implementation Notes), so a test that greps for any
of them passes unchanged on the broken driver. Only running the real script and
reading back the record it wrote (or refused to write) can tell the two apart.

n_location_rule for this AC is 2 -- the completion decision in build-feature.js
and its twin in build-ticket.js must derive the demanded-step set identically
-- so every test drives both twins via subTest.

THIS FILE covers the first three of the AC's attempts (narrowed list, widened
list, no list). The remaining caller-list-criteria tests (the cross-attempt
record-unchanged check, the both-drivers seam test, and the reachability
test) live in the sibling test_bo_400e_1_ii.py -- both files were split out
of a single, now-oversized test_bo_400e_1.py; see that file's git history
for the pre-split version. The pr-reviewer H-1 regression tests live in
test_bo_400e_1_i.py. Shared constants and the ``_NinePhaseRecordCase`` base
class live in ``_bo_400e_1_support.py``.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402
from _bo_400e_1_support import (  # noqa: E402
    EXTRA_PHASES,
    NARROWED_ORDERED_PHASES,
    NINTH_PHASE,
    NO_LIST_ORDERED_PHASES,
    WIDENED_ORDERED_PHASES,
    _is_refused,
    _NinePhaseRecordCase,
    _outstanding_agents,
)

# ---------------------------------------------------------------------------
# Attempt 1 -- narrowed list (the other eight; ninth excluded from this run)
# ---------------------------------------------------------------------------


class TestNarrowedCallerListDoesNotRemoveTheUnaccountedPhase(_NinePhaseRecordCase):
    def test_caller_narrowed_list_does_not_remove_the_unaccounted_phase(self):
        # covers: BO-400e-1
        # angle: criterion
        """Attempt 1: the caller presents the other eight and describes the
        ninth as excluded from this run. The close must still be refused, and
        the refusal must still name the ninth phase -- the caller's own list
        cannot narrow the demanded set the record names."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = self._write_nine_phase_ticket(
                    worktree, "01_narrowed.md"
                )
                observation = self._drive(
                    script, worktree, ticket_path, NARROWED_ORDERED_PHASES
                )

                self.assertIsNone(
                    observation["error"],
                    f"{driver} threw during the run: {observation['error']}",
                )
                result = observation["result"] or {}

                self.assertTrue(
                    _is_refused(result),
                    f"{driver} must refuse this close (record names an "
                    f"unaccounted ninth phase). Payload: "
                    f"{json.dumps(result, sort_keys=True)}",
                )
                outstanding = _outstanding_agents(result)
                self.assertIn(
                    NINTH_PHASE,
                    outstanding,
                    f"{driver} refused the close but did not name the ninth "
                    f"phase ('{NINTH_PHASE}') as outstanding. A caller-supplied "
                    "list of the other eight must not make the ninth phase "
                    f"disappear from the decision. outstanding={outstanding}",
                )

                record = H.read_record(ticket_path)
                self.assertNotEqual(
                    record["lifecycle_status"],
                    "done",
                    f"{driver} recorded done for a ticket whose ninth phase "
                    "carries no sign-off, using a caller-supplied list that "
                    "omitted it.",
                )


# ---------------------------------------------------------------------------
# Attempt 2 -- widened list (the eight plus two phases the record never names)
# ---------------------------------------------------------------------------


class TestWidenedCallerListDoesNotAddPhasesTheRecordNeverNames(_NinePhaseRecordCase):
    def test_caller_widened_list_does_not_add_phases_the_record_never_names(self):
        # covers: BO-400e-1
        # angle: boundary
        """Attempt 2: the caller presents ten phases -- the eight plus two the
        ticket's record never names anywhere. Those two must be treated as
        demanded in neither the decision nor the refusal message, and the
        refusal must still name only the ninth.

        THE LIVE BUG: requiredPhasesForCompletion unions the caller's list
        with the record's, so today the two extras ARE added to the required
        set and the refusal names three outstanding phases, not one.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = self._write_nine_phase_ticket(
                    worktree, "01_widened.md"
                )
                observation = self._drive(
                    script, worktree, ticket_path, WIDENED_ORDERED_PHASES
                )

                self.assertIsNone(
                    observation["error"],
                    f"{driver} threw during the run: {observation['error']}",
                )
                result = observation["result"] or {}
                payload_text = json.dumps(result, sort_keys=True)

                self.assertTrue(
                    _is_refused(result),
                    f"{driver} must refuse this close. Payload: {payload_text}",
                )

                outstanding = _outstanding_agents(result)
                for extra in EXTRA_PHASES:
                    self.assertNotIn(
                        extra,
                        outstanding,
                        f"{driver} treated caller-supplied phase '{extra}' -- "
                        "which the ticket's own record never names -- as "
                        f"demanded. outstanding={outstanding}",
                    )
                    self.assertNotIn(
                        extra,
                        payload_text,
                        f"{driver}'s refusal payload mentions '{extra}', a "
                        "phase the ticket's record never names anywhere. The "
                        f"caller's widened list must not leak into the "
                        f"decision or its message. Payload: {payload_text}",
                    )

                self.assertEqual(
                    outstanding,
                    [NINTH_PHASE],
                    f"{driver}: the demanded-step set must be exactly the "
                    "record's own nine phases (only the ninth outstanding), "
                    "not the caller's widened list. This is the union bug: "
                    f"outstanding={outstanding}",
                )

                record = H.read_record(ticket_path)
                self.assertNotEqual(record["lifecycle_status"], "done")


# ---------------------------------------------------------------------------
# Attempt 3 -- no caller-supplied list at all; must match the other two exactly
# ---------------------------------------------------------------------------


class TestNoCallerListReadsTheRecordAndRefusesIdentically(_NinePhaseRecordCase):
    def test_close_with_no_caller_list_reads_the_record_and_refuses_identically(
        self,
    ):
        # covers: BO-400e-1
        # angle: criterion
        """Attempt 3: the caller supplies no list of phases whatsoever. The
        answer must be BYTE-IDENTICAL to both the narrowed and the widened
        attempts.

        This is the test that closes the wrong fix that looks most attractive:
        'fall back to the record only when no list is offered, and consult the
        caller's list any other time' -- an implementation shaped like that
        passes the narrowed and widened attempts' own individual assertions
        (each in isolation only checks the ninth is named / the extras are
        not) but fails HERE, because its widened-attempt answer differs from
        its no-list answer the moment it ever reads the caller's list at all.
        The only implementation that survives this comparison never reads it.
        """
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree_narrow = self._worktree()
                ticket_narrow = self._write_nine_phase_ticket(
                    worktree_narrow, "01_narrowed.md"
                )
                obs_narrow = self._drive(
                    script, worktree_narrow, ticket_narrow, NARROWED_ORDERED_PHASES
                )

                worktree_wide = self._worktree()
                ticket_wide = self._write_nine_phase_ticket(
                    worktree_wide, "01_widened.md"
                )
                obs_wide = self._drive(
                    script, worktree_wide, ticket_wide, WIDENED_ORDERED_PHASES
                )

                worktree_none = self._worktree()
                ticket_none = self._write_nine_phase_ticket(
                    worktree_none, "01_no_list.md"
                )
                obs_none = self._drive(
                    script, worktree_none, ticket_none, NO_LIST_ORDERED_PHASES
                )

                for obs in (obs_narrow, obs_wide, obs_none):
                    self.assertIsNone(obs["error"], obs.get("error"))

                result_narrow = obs_narrow["result"] or {}
                result_wide = obs_wide["result"] or {}
                result_none = obs_none["result"] or {}

                # ticket_path (and, nested under resolved_target,
                # ticket_path/worktree_path) differ across the three fixtures
                # (three separate worktrees, used purely for test isolation)
                # -- strip all of them before the byte-identical comparison so
                # that incidental difference doesn't mask (or fake) the real
                # one. Only these path fields are incidental; every
                # decision-bearing field (outstanding_phases, message,
                # status, etc.) must still compare byte-identical.
                def _comparable(result):
                    projected = dict(result)
                    projected.pop("ticket_path", None)
                    resolved_target = projected.get("resolved_target")
                    if isinstance(resolved_target, dict):
                        projected["resolved_target"] = {
                            k: v
                            for k, v in resolved_target.items()
                            if k not in ("ticket_path", "worktree_path")
                        }
                    return json.dumps(projected, sort_keys=True)

                serialized_narrow = _comparable(result_narrow)
                serialized_wide = _comparable(result_wide)
                serialized_none = _comparable(result_none)

                self.assertEqual(
                    serialized_none,
                    serialized_narrow,
                    f"{driver}: the no-caller-list attempt must answer exactly "
                    "as the narrowed-list attempt does.\n"
                    f"no-list:  {serialized_none}\n"
                    f"narrowed: {serialized_narrow}",
                )
                self.assertEqual(
                    serialized_none,
                    serialized_wide,
                    f"{driver}: the no-caller-list attempt must answer exactly "
                    "as the widened-list attempt does -- the thing that "
                    "differed between the three attempts (the caller's list) "
                    "was never an input to the decision.\n"
                    f"no-list: {serialized_none}\n"
                    f"widened: {serialized_wide}",
                )


if __name__ == "__main__":
    unittest.main()
