"""
MODULE: test_uxp_514_4
GOAL: Pin UXP-514-4 (D4) -- a step naming a screen with no registered mockup is
    reported naming the journey, the step and the screen; it is a warning while
    the journey is not approved, blocks once the journey is approved, and a step
    naming a registered screen is not reported.
BUSINESS CONTEXT: The severity follows the journey's readiness; a fixed
    severity either blocks drafts or waves approved journeys through.
ARCHITECTURE: Real CLI over a private store copy; readiness is changed in the
    journey AND its index mirror so the only finding is the D4 one.
"""
from __future__ import annotations

import unittest

from unit_tests.product_truth import _uxp_514_harness as h
from unit_tests.product_truth import _uxp_514_scenarios as sc


def _about(lines, flow_id, node_id, screen):
    return [ln for ln in lines if flow_id in ln and f"'{node_id}'" in ln and screen in ln]


class TestD4ScreenResolution(unittest.TestCase):
    def test_unregistered_screen_on_an_unapproved_journey_warns(self) -> None:
        # covers: UXP-514-4
        # angle: boundary
        f = sc.d4_unregistered_on_draft()
        proc = f["proc"]
        self.assertEqual(f["generator_returncode"], 0, f["generator_output"])
        self.assertEqual(len(_about(h.warnings(proc), f["flow_id"], f["node_id"], f["screen"])), 1, h.output(proc)[-800:])
        self.assertEqual(_about(h.failures(proc), f["flow_id"], f["node_id"], f["screen"]), [])
        self.assertEqual(proc.returncode, 0, "a draft journey's unregistered screen must not stop the caller")

    def test_unregistered_screen_on_an_approved_journey_stops_the_caller(self) -> None:
        # covers: UXP-514-4
        # angle: failure
        f = sc.d4_unregistered_on_approved()
        proc = f["proc"]
        self.assertEqual(f["generator_returncode"], 0, f["generator_output"])
        self.assertEqual(len(_about(h.failures(proc), f["flow_id"], f["node_id"], f["screen"])), 1, h.output(proc)[-800:])
        self.assertEqual(_about(h.warnings(proc), f["flow_id"], f["node_id"], f["screen"]), [])
        self.assertEqual(proc.returncode, 1)

    def test_registered_screen_is_not_reported(self) -> None:
        # covers: UXP-514-4
        # angle: criterion
        f = sc.d4_registered_in_both_states_with_a_control()
        proc = f["proc"]
        self.assertEqual(f["generator_returncode"], 0, f["generator_output"])
        everything = h.failures(proc) + h.warnings(proc)
        # Neither a draft nor an approved journey is reported for the registered screen ...
        self.assertEqual([ln for ln in everything if "resolves to no registered mockup" in ln and f["registered"] in ln], [])
        # ... while the control row (same run, unregistered screen) IS reported, so silence is not a dead check.
        self.assertEqual(len(_about(h.warnings(proc), f["control_flow"], f["control_node"], sc.BOGUS_SCREEN)), 1)


if __name__ == "__main__":
    unittest.main()
