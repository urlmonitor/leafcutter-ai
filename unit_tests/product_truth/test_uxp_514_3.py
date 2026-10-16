"""
MODULE: test_uxp_514_3
GOAL: Pin UXP-514-3 (D3) -- a derived index lookup that differs from a fresh
    rebuild is reported naming the lookup AND the entries that differ; a
    matching lookup is not reported; the check states how many entries it
    compared.
BUSINESS CONTEXT: "does not match a fresh rebuild" alone produced a fourteen-way
    mismatch nobody could triage; the naming is the point of the record.
ARCHITECTURE: Real CLI over a private store copy; the count test pipes the REAL
    generator's freshly written index into the REAL validator (seam).
    `derived-indexes` in examined_by_check must equal the number of entries across
    by_component + by_entity + by_flow + by_ac (today it states a population sum).
"""
from __future__ import annotations

import unittest

from unit_tests.product_truth import _uxp_514_harness as h
from unit_tests.product_truth import _uxp_514_scenarios as sc
from unit_tests.product_truth._uxp_300_store import PT_SOURCE


class TestD3DerivedLookups(unittest.TestCase):
    def test_differing_derived_lookup_names_the_entries_that_differ(self) -> None:
        # covers: UXP-514-3
        # angle: failure
        facts = sc.d3_edited_lookup("by_ac")
        hits = [ln for ln in h.failures(facts["proc"]) if "[index]" in ln and facts["lookup"] in ln]
        self.assertEqual(facts["proc"].returncode, 1)
        self.assertEqual(len(hits), 1, hits)
        self.assertIn(facts["entry"], hits[0], "must name the differing entry, not only the lookup")
        # Only the edited entry is named: untouched entries of the same lookup are not dragged in.
        index = h.load_json(facts["store"] / "index.json")
        for key in [k for k in sorted(index["by_ac"]) if k != facts["entry"]][:5]:
            self.assertNotIn(f"'{key}'", hits[0])

    def test_matching_derived_lookup_is_not_reported(self) -> None:
        # covers: UXP-514-3
        # angle: boundary
        proc = h.baseline()
        self.assertEqual(proc.returncode, 0, h.output(proc)[-800:])
        self.assertEqual([ln for ln in h.failures(proc) if "does not match a fresh rebuild" in ln], [])
        # Control: the comparison happened and states the entries it compared.
        index = h.load_json(PT_SOURCE / "index.json")  # the baseline store is a byte copy of this one
        self.assertEqual(h.examined(proc).get("derived-indexes"), sc.lookup_entry_total(index))

    def test_compared_entry_count_rises_with_the_size_of_the_index(self) -> None:
        # covers: UXP-514-3
        # angle: seam
        base, grown = sc.d3_regenerated_baseline(), sc.d3_regenerated_with_extra_flow()
        self.assertEqual(base["generator_returncode"], 0)
        self.assertEqual(grown["generator_returncode"], 0, grown["generator_output"])
        n_base = h.examined(base["proc"]).get("derived-indexes")
        n_grown = h.examined(grown["proc"]).get("derived-indexes")
        # The stated figure is the entries of the four lookups the real generator wrote.
        self.assertEqual(n_base, sc.lookup_entry_total(base["index"]))
        self.assertEqual(n_grown, sc.lookup_entry_total(grown["index"]))
        self.assertGreater(n_grown, n_base)


if __name__ == "__main__":
    unittest.main()
