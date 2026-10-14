"""
MODULE: test_uxp_514
GOAL: Pin the UXP-514 umbrella -- validate_product_truth.py errors (non-zero
    exit) on derived-vs-source drift in impl_status (D1), product_truth back-
    references (D2), the four derived index lookups (D3) and screen->mockup
    resolution (D4, severity gated on the journey's approval), and each finding
    names the check that fired.
BUSINESS CONTEXT: The record was marked done with no test driving any check;
    the live store agrees by construction, so each negative is a store built to
    disagree. Per-check depth (counts, separate messages) lives in the
    UXP-514-1..6 files; this file pins the umbrella contract through the same
    real CLI and shares their memoised runs.
ARCHITECTURE: Real validate_product_truth.py subprocess over a private,
    dependency-closed store copy (_uxp_514_harness / _uxp_514_scenarios).
"""
from __future__ import annotations

import unittest

from unit_tests.product_truth import _uxp_514_harness as h
from unit_tests.product_truth import _uxp_514_scenarios as sc


class TestUmbrellaDrift(unittest.TestCase):
    def test_validator_errors_when_stored_impl_status_diverges_from_recomputed(self) -> None:
        # covers: UXP-514
        # angle: real_artifact
        f = sc.d1_flipped_status()
        hits = [ln for ln in h.failures(f["proc"]) if f["flow_id"] in ln and f"'{f['node_id']}'" in ln]
        self.assertEqual(f["proc"].returncode, 1)
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(f["new_value"], hits[0])
        self.assertIn(f["stored"], hits[0])
        # The run also states how many steps it recomputed (the umbrella's non-vacuity floor).
        self.assertGreater(h.examined(f["proc"]).get("impl-status", 0), len(h.flow_files(f["store"])))

    def test_validator_errors_on_product_truth_that_the_inversion_does_not_support(self) -> None:
        # covers: UXP-514
        # angle: real_artifact
        stale, orphan = sc.d2_stale_back_reference(), sc.d2_orphan_back_reference()
        stale_hits = [ln for ln in h.failures(stale["proc"]) if f"'{stale['ac_id']}'" in ln]
        orphan_hits = [ln for ln in h.failures(orphan["proc"]) if f"'{orphan['ac_id']}'" in ln]
        self.assertEqual(len(stale_hits), 1, stale_hits)
        self.assertEqual(len(orphan_hits), 1, orphan_hits)
        self.assertIn(stale["held_node"], stale_hits[0], "a disagreeing block states the value it holds")
        self.assertNotEqual(stale_hits[0].split(":", 1)[-1], orphan_hits[0].split(":", 1)[-1],
                            "the two defects are each their own named error")
        self.assertEqual(orphan["proc"].returncode, 1)

    def test_validator_errors_when_a_derived_index_diverges_from_a_fresh_rebuild(self) -> None:
        # covers: UXP-514
        # angle: real_artifact
        for key in sc.LOOKUPS:
            with self.subTest(lookup=key):
                f = sc.d3_edited_lookup(key)
                hits = [ln for ln in h.failures(f["proc"]) if "[index]" in ln and key in ln]
                self.assertEqual(f["proc"].returncode, 1)
                self.assertEqual(len(hits), 1, hits)
                self.assertIn(f["entry"], hits[0], "must name the entry that differs, not only the lookup")
                others = [k for k in sc.LOOKUPS if k != key]
                self.assertFalse(any(o in hits[0] for o in others), "a divergence in one lookup names only that key")

    def test_unresolvable_screen_warns_on_a_draft_flow_and_errors_on_an_approved_one(self) -> None:
        # covers: UXP-514
        # angle: real_artifact
        draft, approved = sc.d4_unregistered_on_draft(), sc.d4_unregistered_on_approved()
        self.assertEqual((draft["generator_returncode"], approved["generator_returncode"]), (0, 0))

        def about(lines, f):
            return [ln for ln in lines if f["flow_id"] in ln and f"'{f['node_id']}'" in ln and f["screen"] in ln]
        self.assertEqual(len(about(h.warnings(draft["proc"]), draft)), 1)
        self.assertEqual(about(h.failures(draft["proc"]), draft), [])
        self.assertEqual(len(about(h.failures(approved["proc"]), approved)), 1)
        self.assertEqual(about(h.warnings(approved["proc"]), approved), [])
        self.assertEqual((draft["proc"].returncode, approved["proc"].returncode), (0, 1))

    def test_each_check_reports_which_one_fired_rather_than_a_bare_exit_code(self) -> None:
        # covers: UXP-514
        # angle: real_artifact
        d1, d4 = sc.d1_flipped_status(), sc.d4_unregistered_on_approved()
        self.assertEqual(d1["proc"].returncode, d4["proc"].returncode, "same exit code: only the text can tell them apart")
        d1_text = " ".join(h.failures(d1["proc"]))
        d4_text = " ".join(h.failures(d4["proc"]))
        self.assertIn("impl_status", d1_text)
        self.assertNotIn("[screen]", d1_text)
        self.assertIn("[screen]", d4_text)
        self.assertNotIn("impl_status", d4_text)
        # The machine-readable run payload says it too: the firing check is the only one whose figure moved.
        self.assertEqual(h.examined(d1["proc"]).get("impl-status"),
                         sum(len(h.nodes(h.load_json(p))) for p in h.flow_files(d1["store"])))


if __name__ == "__main__":
    unittest.main()
