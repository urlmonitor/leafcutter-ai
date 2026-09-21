"""Behavioral tests for BO-400e-2 -- control ticket, twin seam, reachability.

Second half of the BO-400e-2 test family, split out of test_bo_400e_2.py for
the file-size reason documented in that file's module docstring (400
content-line limit, check_file_size.py). See test_bo_400e_2.py for the full
defect description, the fixture-sharing rationale with BO-400e-1, and why
n_location_rule=2 drives every single-ticket-capable test through both twin
drivers. Shared constants (NO_CLAIM_ORDERED_PHASES, EIGHT_SIGNED_OFF_CLAIM,
NINE_SIGNED_OFF_CLAIM) are imported from that sibling file rather than
duplicated.

THIS FILE covers:
  - the control-ticket descriptor: a second ticket carried by the SAME run,
    with every named phase signed off, must be written finished -- proving
    the refusal above is a decision about one ticket's own evidence, not a
    driver that has simply stopped writing for the whole run (the failure
    mode BO-400a-2-iii already hit once).
  - the twin-seam descriptor: build-feature.js and build-ticket.js must
    refuse the SAME unaccounted-phase record identically.
  - the reachability descriptor: the refusal must actually be REACHED by a
    real execution of the driver, not merely present in its source.
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
from _bo_400e_1_support import (  # noqa: E402
    EIGHT_PHASES,
    NINE_PHASES,
    NINTH_PHASE,
    TICKET_TITLE,
    _is_refused,
    _NinePhaseRecordCase,
    _outstanding_agents,
)
from test_bo_400e_2 import (  # noqa: E402
    EIGHT_SIGNED_OFF_CLAIM,
    NINE_SIGNED_OFF_CLAIM,
    NO_CLAIM_ORDERED_PHASES,
)


# ---------------------------------------------------------------------------
# 4 -- the control case: a SECOND ticket, carried by the SAME run, whose
# record names every phase signed off, IS written finished
# ---------------------------------------------------------------------------


class TestControlTicketInTheSameRunIsWrittenFinished(unittest.TestCase):
    """Without this contrast a driver that has simply stopped writing passes
    every refusal assertion in the sibling file -- the failure mode
    BO-400a-2-iii already hit once. Necessarily epic-only: build-ticket.js
    takes exactly one ticket per invocation, so it has no 'same run' of two
    tickets to carry."""

    def setUp(self):
        if not H.node_available():
            self.skipTest("node is not available on PATH")
        self._tmpdirs = []

    def tearDown(self):
        for path in self._tmpdirs:
            shutil.rmtree(path, ignore_errors=True)

    def _worktree(self) -> str:
        path = tempfile.mkdtemp(prefix="bo400e2_")
        self._tmpdirs.append(path)
        return path

    def test_control_ticket_in_the_same_run_is_written_finished(self):
        # covers: BO-400e-2
        # angle: boundary
        """One epic run, two tickets: the first names a ninth phase
        unaccounted for and must be refused; the second names the same nine
        phases as needed and carries a real, passing sign-off for every one
        of them, and must be written finished. Both are read back after the
        SAME run, so the refusal on the first is attributable to its own
        missing evidence and not to a driver that stopped writing for
        everyone in the run."""
        worktree = self._worktree()
        epic_subdir = os.path.join(
            "tickets", "00_inbox", "epics", "EPIC-BO400e2Harness"
        )
        epic_path = os.path.join(worktree, epic_subdir)
        os.makedirs(epic_path, exist_ok=True)

        refused_path = H.write_ticket_record(
            worktree,
            "01_refused.md",
            NINE_PHASES,
            title=f"{TICKET_TITLE} (refused)",
            seeded_signoffs=[(agent, "ok") for agent in EIGHT_PHASES],
            subdir=epic_subdir,
            extra_frontmatter={"source_ac": "BO-400e-2"},
        )
        control_path = H.write_ticket_record(
            worktree,
            "02_control.md",
            NINE_PHASES,
            title=f"{TICKET_TITLE} (control)",
            seeded_signoffs=[(agent, "ok") for agent in NINE_PHASES],
            subdir=epic_subdir,
            extra_frontmatter={"source_ac": "BO-400e-2"},
        )

        tickets = {
            refused_path: {
                "title": f"{TICKET_TITLE} (refused)",
                "has_test_requirements": True,
                "ordered_phases": EIGHT_SIGNED_OFF_CLAIM,
            },
            control_path: {
                "title": f"{TICKET_TITLE} (control)",
                "has_test_requirements": True,
                "ordered_phases": NINE_SIGNED_OFF_CLAIM,
            },
        }
        present = [
            {"path": refused_path, "status": "todo"},
            {"path": control_path, "status": "todo"},
        ]
        scenario = H.epic_scenario(
            worktree,
            epic_path,
            tickets,
            [{"present": present}, {"present": present}],
        )

        observation = H.run_driver(H.BUILD_FEATURE_JS, scenario)
        self.assertIsNone(
            observation["error"],
            f"build-feature.js threw during the run: {observation['error']}",
        )
        result = observation["result"] or {}
        payload_text = json.dumps(result, sort_keys=True)

        # Use the suite's own generic helpers (_driver_harness.py,
        # BO-300a-5-ii/-iii) rather than hand-parsing completed_batches: they
        # are exactly the vocabulary this run's own contradiction-detection
        # already speaks, so a fix expressed through any of the fields those
        # helpers already understand is recognised here too.
        completed_paths = H.completed_work_paths(result)
        not_built_paths = H.paths_described_as_not_built(result)

        self.assertIn(
            control_path,
            completed_paths,
            "the control ticket -- every named phase signed off -- must be "
            "reported completed in the SAME run as the refused ticket, not "
            "merely written done in its own file while the run's own report "
            f"stays silent about it. completed work paths: {completed_paths}\n"
            f"full payload: {payload_text}",
        )
        self.assertNotIn(
            control_path,
            not_built_paths,
            "the control ticket -- which the run's own record shows was "
            "written done -- must not be described as work that was not "
            "built. A run whose report contradicts its own write is exactly "
            "'a mechanism that has simply stopped writing' from this AC's "
            f"own wording. not-built paths: {not_built_paths}\n"
            f"full payload: {payload_text}",
        )
        conflict = H.completed_and_unbuilt_conflict(result)
        self.assertEqual(
            conflict,
            [],
            "no payload may name the same piece of work both as completed "
            f"and as not built: {conflict}\nfull payload: {payload_text}",
        )
        self.assertNotIn(
            refused_path,
            completed_paths,
            "the refused ticket must NOT be reported completed, even though "
            f"a sibling ticket in the same run was. completed work paths: "
            f"{completed_paths}\nfull payload: {payload_text}",
        )

        control_record = H.read_record(control_path)
        self.assertEqual(
            control_record["lifecycle_status"],
            "done",
            "the control ticket's own record must have its lifecycle status "
            f"written done. Got: {control_record['lifecycle_status']!r}\n"
            f"full payload: {payload_text}",
        )

        refused_record = H.read_record(refused_path)
        self.assertNotEqual(
            refused_record["lifecycle_status"],
            "done",
            "the refused ticket's own record must NOT have its lifecycle "
            "status written done, even though its sibling in the same run "
            f"did finish. Got: {refused_record['lifecycle_status']!r}",
        )
        self.assertEqual(
            refused_record["agents"].get(NINTH_PHASE),
            "needed",
            f"the refused ticket must still name '{NINTH_PHASE}' needed "
            "after the same run that finished its sibling.",
        )


# ---------------------------------------------------------------------------
# 5 -- the twin seam: both drivers refuse the same record identically
# ---------------------------------------------------------------------------


class TestBothDriversRefuseTheSameRecordIdentically(_NinePhaseRecordCase):
    def test_both_drivers_refuse_the_same_record_identically(self):
        # covers: BO-400e-2
        # angle: seam
        """Drive the same unaccounted-for-ninth-phase record through
        build-feature.js and through build-ticket.js and assert both refuse,
        name the same outstanding phase, and leave the same unchanged record
        -- the twin seam BO-400a-2-ii's standing constraint holds closed for
        this AC too, not only for BO-400e-1's caller-list scenarios."""
        worktree_feature = self._worktree()
        ticket_feature = self._write_nine_phase_ticket(
            worktree_feature, "01_seam_feature.md"
        )
        obs_feature = self._drive(
            H.BUILD_FEATURE_JS,
            worktree_feature,
            ticket_feature,
            NO_CLAIM_ORDERED_PHASES,
        )

        worktree_ticket = self._worktree()
        ticket_ticket = self._write_nine_phase_ticket(
            worktree_ticket, "01_seam_ticket.md"
        )
        obs_ticket = self._drive(
            H.BUILD_TICKET_JS,
            worktree_ticket,
            ticket_ticket,
            NO_CLAIM_ORDERED_PHASES,
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
        self.assertTrue(_is_refused(result_feature), "harness precondition")

        outstanding_feature = _outstanding_agents(result_feature)
        outstanding_ticket = _outstanding_agents(result_ticket)
        self.assertEqual(
            outstanding_feature,
            outstanding_ticket,
            "build-feature.js and build-ticket.js derived DIFFERENT "
            "outstanding-phase sets for the same record.\n"
            f"build-feature.js outstanding: {outstanding_feature}\n"
            f"build-ticket.js outstanding:  {outstanding_ticket}",
        )
        self.assertEqual(
            outstanding_feature,
            [NINTH_PHASE],
            f"the shared outstanding-phase set both twins derived is not "
            f"exactly the ninth phase: {outstanding_feature}",
        )

        record_feature = H.read_record(ticket_feature)
        record_ticket = H.read_record(ticket_ticket)
        self.assertEqual(
            record_feature["agents"],
            record_ticket["agents"],
            "the two twins left the ninth phase's demand in different states "
            "-- one may have softened it while the other did not.",
        )
        self.assertNotEqual(record_feature["lifecycle_status"], "done")
        self.assertNotEqual(record_ticket["lifecycle_status"], "done")


# ---------------------------------------------------------------------------
# 6 -- reachability: the refusal is actually reached during a real close
# ---------------------------------------------------------------------------


class TestRefusalIsReachableFromARealWorkflowRun(_NinePhaseRecordCase):
    def test_refusal_is_reachable_from_a_real_workflow_run(self):
        # covers: BO-400e-2
        # angle: reachability
        """Load and execute the REAL, deployed-source workflow script
        (templates/workflows-js/build-feature.js) via
        harness_build_ticket_guard.mjs -- a node subprocess, the same way the
        production workflow engine loads it -- and confirm the guarded
        refusal is actually REACHED during a close: the record was really
        read back, and the resulting refusal is consumed in the returned
        payload's control flow, not merely computed and discarded.

        Does NOT satisfy this by invoking scripts/set_ticket_status.py
        directly, and does NOT satisfy it by importing a helper: the defect
        this angle exists to catch is precisely a driver that never routes to
        the guarded path at all, and the guarded path already passes its own
        unit tests today (BO-400a-2-i).
        """
        self.assertTrue(
            os.path.isfile(H.BUILD_FEATURE_JS),
            f"the real, deployed-source driver is missing at {H.BUILD_FEATURE_JS}",
        )

        worktree = self._worktree()
        ticket_path = self._write_nine_phase_ticket(worktree, "01_reachability.md")
        observation = self._drive(
            H.BUILD_FEATURE_JS, worktree, ticket_path, NO_CLAIM_ORDERED_PHASES
        )

        self.assertIsNone(
            observation["error"],
            f"the real workflow script threw during execution: "
            f"{observation['error']}",
        )

        readbacks = [
            rb
            for rb in observation.get("readbacks") or []
            if rb.get("ticket_path") == ticket_path
        ]
        self.assertTrue(
            readbacks,
            "the real driver run never read the ticket record back at all -- "
            "the refusal cannot have been decided against real evidence. "
            f"Accepted read-back labels: {H.ACCEPTED_READBACK_LABELS}",
        )
        self.assertTrue(
            readbacks[0].get("readable"),
            f"the real driver's own read-back of the record reported it "
            f"unreadable: {readbacks[0]}",
        )

        result = observation["result"] or {}
        self.assertTrue(
            _is_refused(result),
            "a real execution of build-feature.js against a record naming "
            "an unaccounted ninth phase must be refused. Instead got: "
            f"{json.dumps(result, sort_keys=True)}",
        )
        outstanding = _outstanding_agents(result)
        self.assertIn(
            NINTH_PHASE,
            outstanding,
            "the real run's own returned payload does not name the ninth "
            "phase as outstanding, so the refusal this AC is about was not "
            f"actually consumed by this close. outstanding={outstanding}",
        )

        applied = [
            w for w in H.writes_for(observation, ticket_path) if w["applied"]
        ]
        self.assertEqual(
            applied,
            [],
            "a real execution reached and applied a completion write despite "
            "an unaccounted-for demanded phase -- the refusal was computed "
            f"and then ignored. writes: {applied}",
        )

        record = H.read_record(ticket_path)
        self.assertNotEqual(record["lifecycle_status"], "done")


if __name__ == "__main__":
    unittest.main()
