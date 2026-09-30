"""Behavioral tests for BO-400e-1 -- record-unchanged, seam, and reachability.

Second half of the caller-list-criteria tests split out of the original
test_bo_400e_1.py (804 raw lines, 690 content lines -- over the 400
content-line file-size limit). The first three attempts (narrowed list,
widened list, no list) live in the sibling test_bo_400e_1.py; the
pr-reviewer H-1 regression tests live in test_bo_400e_1_i.py. Shared
constants and the ``_NinePhaseRecordCase`` base class live in
``_bo_400e_1_support.py``. See test_bo_400e_1.py's module docstring for the
full defect description and the n_location_rule=2 rationale for driving
both twin drivers.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _driver_harness as H  # noqa: E402
from _bo_400e_1_support import (  # noqa: E402
    EIGHT_PHASES,
    NARROWED_ORDERED_PHASES,
    NINTH_PHASE,
    NO_LIST_ORDERED_PHASES,
    WIDENED_ORDERED_PHASES,
    _is_refused,
    _NinePhaseRecordCase,
    _outstanding_agents,
)

# ---------------------------------------------------------------------------
# All three attempts leave the ticket's own record untouched
# ---------------------------------------------------------------------------


class TestAllThreeAttemptsLeaveTheTicketRecordUnchanged(_NinePhaseRecordCase):
    def test_all_three_attempts_leave_the_ticket_record_unchanged(self):
        # covers: BO-400e-1
        # angle: criterion
        """Drive the SAME ticket record through all three attempts in
        sequence and re-read it afterwards: still nine phases named needed,
        still no sign-off for the ninth, no lifecycle state written. A refusal
        that edits the record while refusing is not a refusal."""
        for driver, script in H.TWIN_DRIVERS.items():
            with self.subTest(driver=driver):
                worktree = self._worktree()
                ticket_path = self._write_nine_phase_ticket(
                    worktree, "01_same_ticket.md"
                )
                before = H.read_record(ticket_path)

                for ordered_phases in (
                    NARROWED_ORDERED_PHASES,
                    WIDENED_ORDERED_PHASES,
                    NO_LIST_ORDERED_PHASES,
                ):
                    observation = self._drive(
                        script, worktree, ticket_path, ordered_phases
                    )
                    self.assertIsNone(observation["error"], observation.get("error"))
                    applied = [
                        w
                        for w in H.writes_for(observation, ticket_path)
                        if w["applied"]
                    ]
                    self.assertEqual(
                        applied,
                        [],
                        f"{driver} applied a completion write against the "
                        f"nine-phase record for one of the three attempts: "
                        f"{applied}",
                    )

                after = H.read_record(ticket_path)

                self.assertEqual(
                    after["lifecycle_status"],
                    before["lifecycle_status"],
                    f"{driver}: the ticket's lifecycle status changed across "
                    "the three refused attempts "
                    f"({before['lifecycle_status']!r} -> "
                    f"{after['lifecycle_status']!r}).",
                )
                self.assertEqual(
                    after["agents"],
                    before["agents"],
                    f"{driver}: the ticket's own agents: map changed across "
                    "the three attempts.",
                )
                self.assertEqual(
                    sorted(after["signed_off_agents"]),
                    sorted(EIGHT_PHASES),
                    f"{driver}: the set of agents carrying a sign-off in the "
                    "record changed across the three attempts -- a refusal "
                    "must not add or remove sign-off entries.",
                )
                self.assertNotIn(
                    NINTH_PHASE,
                    after["signed_off_agents"],
                    f"{driver}: the ninth phase gained a sign-off entry during "
                    "one of the three refused attempts.",
                )


# ---------------------------------------------------------------------------
# The seam: both twin drivers must derive the same demanded set for the same
# record (BO-400a-2-ii's twin constraint, which this AC exists to hold closed)
# ---------------------------------------------------------------------------


class TestBothDriversDeriveTheSameDemandedSetForTheSameRecord(_NinePhaseRecordCase):
    def test_both_drivers_derive_the_same_demanded_set_for_the_same_record(self):
        # covers: BO-400e-1
        # angle: seam
        """Run the identical nine-phase record through the epic driver
        (build-feature.js) AND the single-ticket driver (build-ticket.js) and
        assert both decided against the same demanded-step set and produced
        the same refusal -- the seam BO-400a-2-ii's twin constraint exists to
        hold closed. n_location_rule is 2 precisely because these two files
        must never answer this question differently."""
        worktree_feature = self._worktree()
        ticket_feature = self._write_nine_phase_ticket(
            worktree_feature, "01_seam_feature.md"
        )
        obs_feature = self._drive(
            H.BUILD_FEATURE_JS,
            worktree_feature,
            ticket_feature,
            WIDENED_ORDERED_PHASES,
        )

        worktree_ticket = self._worktree()
        ticket_ticket = self._write_nine_phase_ticket(
            worktree_ticket, "01_seam_ticket.md"
        )
        obs_ticket = self._drive(
            H.BUILD_TICKET_JS,
            worktree_ticket,
            ticket_ticket,
            WIDENED_ORDERED_PHASES,
        )

        self.assertIsNone(obs_feature["error"], obs_feature.get("error"))
        self.assertIsNone(obs_ticket["error"], obs_ticket.get("error"))

        result_feature = obs_feature["result"] or {}
        result_ticket = obs_ticket["result"] or {}

        self.assertEqual(
            _is_refused(result_feature),
            _is_refused(result_ticket),
            "build-feature.js and build-ticket.js disagreed about whether "
            "this close should be refused for the SAME record.\n"
            f"build-feature.js: {json.dumps(result_feature, sort_keys=True)}\n"
            f"build-ticket.js:  {json.dumps(result_ticket, sort_keys=True)}",
        )

        outstanding_feature = _outstanding_agents(result_feature)
        outstanding_ticket = _outstanding_agents(result_ticket)
        self.assertEqual(
            outstanding_feature,
            outstanding_ticket,
            "build-feature.js and build-ticket.js derived DIFFERENT "
            "demanded-step sets for the same record and the same "
            "caller-supplied list.\n"
            f"build-feature.js outstanding: {outstanding_feature}\n"
            f"build-ticket.js outstanding:  {outstanding_ticket}",
        )
        self.assertEqual(
            outstanding_feature,
            [NINTH_PHASE],
            "the shared demanded-step set both twins derived is not exactly "
            f"the ninth phase: {outstanding_feature}",
        )


# ---------------------------------------------------------------------------
# Reachability -- the derivation must actually run during a close, not merely
# exist in the source (both the broken and fixed driver contain the same
# phase-list code; only running it distinguishes them).
# ---------------------------------------------------------------------------


class TestDemandedSetDerivationIsReachableFromARealWorkflowRun(_NinePhaseRecordCase):
    def test_demanded_set_derivation_is_reachable_from_a_real_workflow_run(self):
        # covers: BO-400e-1
        # angle: reachability
        """Load and execute the REAL, deployed-source workflow script
        (templates/workflows-js/build-feature.js) via
        harness_build_ticket_guard.mjs -- a node subprocess, the same way the
        production workflow engine loads it -- and confirm the demanded-set
        derivation actually ran during a close: the record was really read
        back, and the resulting decision is consumed in the returned payload's
        control flow (the refusal fields), not merely computed and discarded.

        Does NOT import requiredPhasesForCompletion or any other helper
        directly -- the whole point of this angle is that a driver whose
        derivation is dead code (computed, never consulted) would pass a
        direct-import unit test of that helper while still shipping the
        defect this AC closes.
        """
        self.assertTrue(
            os.path.isfile(H.BUILD_FEATURE_JS),
            f"the real, deployed-source driver is missing at {H.BUILD_FEATURE_JS}",
        )

        worktree = self._worktree()
        ticket_path = self._write_nine_phase_ticket(worktree, "01_reachability.md")
        observation = self._drive(
            H.BUILD_FEATURE_JS, worktree, ticket_path, WIDENED_ORDERED_PHASES
        )

        self.assertIsNone(
            observation["error"],
            f"the real workflow script threw during execution: "
            f"{observation['error']}",
        )

        # PROOF the record was actually read back during this run, not assumed.
        readbacks = [
            rb
            for rb in observation.get("readbacks") or []
            if rb.get("ticket_path") == ticket_path
        ]
        self.assertTrue(
            readbacks,
            "the real driver run never read the ticket record back at all -- "
            "the demanded-set derivation cannot have run against real "
            f"evidence. Accepted read-back labels: {H.ACCEPTED_READBACK_LABELS}",
        )
        self.assertTrue(
            readbacks[0].get("readable"),
            f"the real driver's own read-back of the record reported it "
            f"unreadable: {readbacks[0]}",
        )

        # PROOF the derivation's result is actually CONSUMED -- the returned
        # payload reflects it (refused, ninth phase named) rather than the run
        # short-circuiting to an unconditional "ok" the derivation never fed.
        result = observation["result"] or {}
        self.assertTrue(
            _is_refused(result),
            "a real execution of build-feature.js against a record naming an "
            "unaccounted ninth phase must be refused. Instead got: "
            f"{json.dumps(result, sort_keys=True)}",
        )
        outstanding = _outstanding_agents(result)
        self.assertIn(
            NINTH_PHASE,
            outstanding,
            "the real run's own returned payload does not name the ninth "
            "phase as outstanding, so the demanded-set derivation this AC is "
            f"about was not actually consumed by this close. outstanding="
            f"{outstanding}",
        )

        record = H.read_record(ticket_path)
        self.assertNotEqual(record["lifecycle_status"], "done")


if __name__ == "__main__":
    unittest.main()
