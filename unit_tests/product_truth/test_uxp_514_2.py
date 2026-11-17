"""
MODULE: test_uxp_514_2
GOAL: Pin UXP-514-2 (D2) -- a criterion whose product_truth back-reference
    disagrees with the inversion of the journey->criterion links is reported by
    id with BOTH values; a criterion named by a step but holding no back-
    reference is reported separately as missing; an agreeing one is not reported;
    and the check states how many criteria it inverted.
BUSINESS CONTEXT: Disagreeing and missing have different causes and fixes, so
    one shared message is not actionable.
ARCHITECTURE: Real CLI over a private store copy; ACs edited via yaml.safe_dump.
    Contract: findings are FAIL lines naming the AC id; the stale one carries the
    held and the inverted node ids; the missing one contains "missing
    back-reference"; `product-truth-links` in examined_by_check counts criteria
    inverted (= len(by_ac)).
"""
from __future__ import annotations

import unittest

from unit_tests.product_truth import _uxp_514_harness as h
from unit_tests.product_truth import _uxp_514_scenarios as sc


def _ac_lines(proc, ac_id):
    return [ln for ln in h.failures(proc) if f"'{ac_id}'" in ln]


class TestD2BackReference(unittest.TestCase):
    def test_stale_back_reference_is_reported_with_held_and_inverted_values(self) -> None:
        # covers: UXP-514-2
        # angle: failure
        facts = sc.d2_stale_back_reference()
        hits = _ac_lines(facts["proc"], facts["ac_id"])
        self.assertEqual(facts["proc"].returncode, 1)
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(facts["held_node"], hits[0], "must state the back-reference the criterion holds")
        self.assertIn(facts["inverted_node"], hits[0], "must state the back-reference the inversion produces")
        # Discrimination: a stale reference is NOT a missing one.
        self.assertNotIn("missing back-reference", hits[0].lower())

    def test_missing_back_reference_is_reported_separately_from_a_stale_one(self) -> None:
        # covers: UXP-514-2
        # angle: failure
        facts = sc.d2_missing_back_reference()
        hits = _ac_lines(facts["proc"], facts["ac_id"])
        self.assertEqual(len(hits), 1, hits)
        self.assertIn("missing back-reference", hits[0].lower())

    def test_agreeing_back_reference_is_not_reported(self) -> None:
        # covers: UXP-514-2
        # angle: boundary
        proc = h.baseline()
        self.assertEqual(proc.returncode, 0, h.output(proc)[-800:])
        self.assertEqual([ln for ln in h.failures(proc) if "product_truth" in ln or "back-reference" in ln], [])
        # Control + count: the inversion really covered criteria, and states how many.
        count = h.examined(proc).get("product-truth-links")
        index = h.load_json(sc.d2_stale_back_reference()["store"] / "index.json")
        self.assertEqual(count, len(index["by_ac"]), "must state the number of criteria it inverted")


if __name__ == "__main__":
    unittest.main()
