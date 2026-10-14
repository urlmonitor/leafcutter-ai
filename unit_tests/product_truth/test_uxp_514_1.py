"""
MODULE: test_uxp_514_1
GOAL: Pin UXP-514-1 (D1) -- a step whose stated impl_status disagrees with the
    status recomputed from the criteria it names is reported with the journey,
    the step, the stored and the recomputed status; an agreeing step is not
    reported; and the check states how many steps it recomputed.
BUSINESS CONTEXT: D1 agrees by construction on the live store, so only a store
    built to disagree proves it. The recomputed-step count is what separates a
    check that looked at every step from one that looked at nothing.
ARCHITECTURE: Real validate_product_truth.py CLI over a private, dependency-
    closed store copy (see _uxp_514_harness for the reporting contract: the
    `impl-status` entry of the final JSON line's examined_by_check counts
    steps+branches recomputed -- today it states the journey count instead).
"""
from __future__ import annotations

import unittest

from unit_tests.product_truth import _uxp_514_harness as h
from unit_tests.product_truth import _uxp_514_scenarios as sc


def _node_count(store) -> int:
    return sum(len(h.nodes(h.load_json(p))) for p in h.flow_files(store))


class TestD1ImplStatus(unittest.TestCase):
    def test_impl_status_disagreeing_with_recomputed_status_is_reported(self) -> None:
        # covers: UXP-514-1
        # angle: failure
        facts = sc.d1_flipped_status()
        proc = facts["proc"]
        hits = [ln for ln in h.failures(proc) if facts["flow_id"] in ln and f"'{facts['node_id']}'" in ln]
        self.assertEqual(proc.returncode, 1, h.output(proc)[-800:])
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(facts["new_value"], hits[0], "must state the status the record holds")
        self.assertIn(facts["stored"], hits[0], "must state the status recomputed from the criteria")
        # The check also states how many steps it recomputed: the real node count, not the journey count.
        self.assertEqual(h.examined(proc).get("impl-status"), _node_count(facts["store"]))

    def test_agreeing_impl_status_is_not_reported(self) -> None:
        # covers: UXP-514-1
        # angle: boundary
        proc = h.baseline()
        self.assertEqual(proc.returncode, 0, h.output(proc)[-800:])
        self.assertEqual([ln for ln in h.failures(proc) if "impl_status" in ln], [])
        # Control: the check really ran over steps (a silent no-op would also report nothing).
        self.assertEqual(h.examined(proc).get("impl-status"), _node_count(sc.d1_flipped_status()["store"]))

    def test_recomputed_step_count_rises_with_the_number_of_steps(self) -> None:
        # covers: UXP-514-1
        # angle: seam
        base, extra = h.baseline(), sc.d1_extra_step()["proc"]
        before, after = h.examined(base).get("impl-status"), h.examined(extra).get("impl-status")
        self.assertIsNotNone(before, "impl-status must state a count")
        self.assertEqual(after, before + 1, "one added step must raise the recomputed count by exactly one")


if __name__ == "__main__":
    unittest.main()
