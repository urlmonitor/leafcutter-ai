"""
MODULE: test_uxp_514_6
GOAL: Pin UXP-514-6 (D6) -- an index artifact whose copied scalar field (the
    journey description is the index `summary`) differs from its source file is
    reported with the artifact, the field and BOTH values; every copied scalar
    field is compared, not only the description; matching artifacts are not
    reported; and the check states how many artifact fields it compared.
BUSINESS CONTEXT: D3 compares only the derived lookup maps, so nothing guards
    artifacts[]; all 14 journeys of the live store carry a drifted copy today.
ARCHITECTURE: Real CLI over a private store copy whose index copies are first
    synced from their sources (the live store is drifted, so a clean fixture
    must be built, not assumed). Contract: a new `index-fields` check whose
    examined_by_check figure counts compared artifact fields.
"""
from __future__ import annotations

import unittest

from unit_tests.product_truth import _uxp_514_harness as h
from unit_tests.product_truth import _uxp_514_scenarios as sc


def _about(proc, artifact_id, field):
    return [ln for ln in h.failures(proc) if f"{artifact_id}" in ln and field in ln]


class TestD6CopiedFields(unittest.TestCase):
    def test_index_description_differing_from_the_source_is_reported_with_both_values(self) -> None:
        # covers: UXP-514-6
        # angle: failure
        f = sc.d6_summary_differs()
        hits = _about(f["proc"], f["artifact_id"], "summary")
        self.assertEqual(f["proc"].returncode, 1)
        self.assertEqual(len(hits), 1, h.output(f["proc"])[-800:])
        self.assertIn(f["index_text"], hits[0])
        self.assertIn(f["source_text"][:80], hits[0])

    def test_every_copied_scalar_field_is_compared_not_only_the_description(self) -> None:
        # covers: UXP-514-6
        # angle: seam
        f = sc.d6_every_field_edited()
        for field, (artifact_id, index_value, source_value) in f["edits"].items():
            with self.subTest(field=field):
                hits = _about(f["proc"], artifact_id, field)
                self.assertEqual(len(hits), 1, h.output(f["proc"])[-800:])
                self.assertIn(index_value, hits[0])
                self.assertIn(source_value, hits[0])

    def test_matching_copied_fields_produce_no_finding(self) -> None:
        # covers: UXP-514-6
        # angle: boundary
        f = sc.d6_synced_store()
        proc = f["proc"]
        self.assertEqual(proc.returncode, 0, h.output(proc)[-800:])
        self.assertEqual([ln for ln in h.failures(proc) if "index" in ln and "summary" in ln], [])
        # Control + count: the comparison ran, and the figure rises when an artifact is added.
        n_synced = h.examined(proc).get("index-fields")
        self.assertGreater(n_synced or 0, 0, "the check must state how many artifact fields it compared")
        grown = sc.d6_extra_artifact()
        self.assertEqual(grown["generator_returncode"], 0)
        self.assertGreater(h.examined(grown["proc"]).get("index-fields", 0), n_synced)


if __name__ == "__main__":
    unittest.main()
