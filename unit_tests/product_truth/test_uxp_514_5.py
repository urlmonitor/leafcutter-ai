"""
MODULE: test_uxp_514_5
GOAL: Pin UXP-514-5 -- when the input set of one of the four drift checks is
    empty, that check reports it was NOT EXERCISED (naming the input it needed),
    does not also say no drift was found, the run's outcome is not the sound
    outcome, and the four checks are reported independently.
BUSINESS CONTEXT: "errors if ANY X differs" is vacuously true over an empty
    set; an empty store printed "OK ... (0 warnings)" and exit 0 on 2026-09-07.
ARCHITECTURE: Real CLI over a private store copy emptied one input at a time
    (see _uxp_514_harness.EMPTIERS). Contract: an unexercised check is absent
    from examined_by_check and is named, with "not exercised" and its input
    noun, on one output line.
"""
from __future__ import annotations

import unittest

from unit_tests.product_truth import _uxp_514_harness as h


class TestAntiVacuity(unittest.TestCase):
    def test_each_drift_check_reports_not_exercised_on_its_own_empty_input(self) -> None:
        # covers: UXP-514-5
        # angle: boundary
        for check in h.CHECKS:
            with self.subTest(check=check):
                proc = h.emptied_run(check)
                hits = h.not_exercised_lines(proc, check)
                self.assertGreaterEqual(len(hits), 1, h.output(proc)[-600:])
                self.assertTrue(any(h.INPUT_NOUN[check] in ln for ln in hits), f"must name the input: {hits}")

    def test_unexercised_drift_check_does_not_report_no_drift_found(self) -> None:
        # covers: UXP-514-5
        # angle: criterion
        for check in h.CHECKS:
            with self.subTest(check=check):
                proc = h.emptied_run(check)
                self.assertNotIn(check, h.examined(proc), "a not-exercised check must not state an examined figure")
                self.assertNotEqual(h.outcome(proc)["outcome"], "checked-and-sound")
                said_clean = [ln for ln in h.output(proc).splitlines()
                              if check in ln and any(w in ln.lower() for w in ("no drift", "in sync", "passed"))]
                self.assertEqual(said_clean, [])

    def test_three_exercised_and_one_unexercised_is_distinguishable_from_four_exercised(self) -> None:
        # covers: UXP-514-5
        # angle: boundary
        full, partial = h.baseline(), h.emptied_run("screen-refs")
        for check in h.CHECKS:
            self.assertGreater(h.examined(full).get(check, 0), 0, f"control: {check} exercised on the full store")
            self.assertEqual(h.not_exercised_lines(full, check), [])
        unexercised = [c for c in h.CHECKS if h.not_exercised_lines(partial, c)]
        self.assertEqual(unexercised, ["screen-refs"], "emptying one input must change only that check's state")
        for check in ("impl-status", "product-truth-links", "derived-indexes"):
            self.assertGreater(h.examined(partial).get(check, 0), 0, check)


if __name__ == "__main__":
    unittest.main()
