"""
Tests for TQ-600a-13-xii (entrant robustness) -- the lane-entrant section must not flood the notice.

Source of truth: docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-13-xii.yaml

1. A previous verdict whose ``collected_ids`` is absent or not a list of strings (an old-schema or hand-edited
   artifact) establishes no membership: it is "no previous", so no entrants, and a WARNING says why. Without that
   every current id would read as new.
2. The rendered entrant lines are capped like the failing list (``MAX_FAILING_SHOWN``), with an explicit
   "... and N more" line.
"""

from __future__ import annotations

import unittest

from scripts.ci._notice_entrants import Entrant, find_entrants, render_entrant_lines
from scripts.ci._notice_render import MAX_FAILING_SHOWN

HEAD = "a" * 40
PREVIOUS_HEAD = "b" * 40
CURRENT = {"collected_ids": ["t.py::a", "t.py::b"], "head_sha": HEAD}


class TestTq600a13XiiEntrantRobustness(unittest.TestCase):
    def test_tq600a_13_xii_a_previous_verdict_without_usable_ids_names_no_entrants(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """Missing, non-list and non-string-list ``collected_ids`` each give no entrants and one WARNING."""
        unusable = {
            "missing": {"head_sha": PREVIOUS_HEAD},
            "null": {"head_sha": PREVIOUS_HEAD, "collected_ids": None},
            "string": {"head_sha": PREVIOUS_HEAD, "collected_ids": "t.py::a"},
            "mixed list": {"head_sha": PREVIOUS_HEAD, "collected_ids": ["t.py::a", 7]},
        }
        for label, previous in unusable.items():
            with self.subTest(label), self.assertLogs("post_merge_notice", level="WARNING") as logs:
                self.assertEqual([], find_entrants(CURRENT, previous, "/nonexistent-repo"))
            self.assertTrue(any("collected_ids" in line for line in logs.output), logs.output)

    def test_tq600a_13_xii_an_empty_previous_list_is_still_a_real_comparison(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """Control: a genuine empty list (lane was empty) is usable, so every current id is an entrant."""
        previous = {"head_sha": PREVIOUS_HEAD, "collected_ids": [], "verdict": "did_not_complete", "stage": "empty_selection"}
        found = find_entrants(CURRENT, previous, "/nonexistent-repo")
        self.assertEqual(["t.py::a", "t.py::b"], [entrant.node_id for entrant in found])

    def test_tq600a_13_xii_the_entrant_lines_are_capped_with_an_explicit_remainder(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """More entrants than the failing-list cap: the cap's worth of bullets, then one '... and N more' line."""
        extra = 30
        entrants = [Entrant(f"t.py::test_{n:04d}", None) for n in range(MAX_FAILING_SHOWN + extra)]
        lines = render_entrant_lines(entrants)
        bullets = [line for line in lines if line.startswith("- `")]
        self.assertEqual(MAX_FAILING_SHOWN, len(bullets))
        self.assertIn(f"- ... and {extra} more", lines)
        self.assertNotIn(f"`t.py::test_{MAX_FAILING_SHOWN:04d}`", "\n".join(lines))

    def test_tq600a_13_xii_entrants_at_the_cap_have_no_remainder_line(self):
        # covers: TQ-600a-13-xii
        # angle: boundary
        """Control: exactly the cap's worth of entrants prints them all and no '... and N more' line."""
        lines = render_entrant_lines([Entrant(f"t.py::test_{n:04d}", None) for n in range(MAX_FAILING_SHOWN)])
        self.assertEqual(MAX_FAILING_SHOWN, len([line for line in lines if line.startswith("- `")]))
        self.assertFalse([line for line in lines if "more" in line.split("`")[0] and line.startswith("- ...")])


if __name__ == "__main__":
    unittest.main()
