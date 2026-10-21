"""
MODULE: unit_tests/build_orchestration/test_bo_400e_3_vi_listing.py
GOAL: RED test for BO-400e-3-vi -- the derive reply carries a ready-to-show `listing_text`: a header
      '<n> ticket(s), <m> acceptance criteria' then one line per record '<id>  <path>  <status>' in set
      order. The workflow only displays it (no formatting logic in finalize-feature.js).
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bo400e3_support import A02, ac_rel, epic_store  # noqa: E402


class TestListingText(unittest.TestCase):
    def test_listing_text_has_one_line_per_record_and_counts(self):
        # covers: BO-400e-3-vi
        # angle: criterion
        """The EPIC-Alpha fixture states 1 ticket and 1 acceptance criterion and has exactly one line each
        for alpha-02.md and BO-9100a-2 with their current status."""
        s = epic_store(self)
        reply = s.derive(branch="EPIC-Alpha")
        lines = [ln for ln in (reply.get("listing_text") or "").splitlines() if ln.strip()]
        self.assertEqual(len(lines), 3, lines)
        self.assertEqual(lines[0], "1 ticket(s), 1 acceptance criteria")
        ticket_lines = [ln for ln in lines[1:] if A02 in ln]
        ac_lines = [ln for ln in lines[1:] if ac_rel("BO-9100a-2") in ln]
        self.assertEqual((len(ticket_lines), len(ac_lines)), (1, 1), lines)
        self.assertTrue(ticket_lines[0].endswith("  todo"), ticket_lines)
        self.assertTrue(ac_lines[0].startswith("BO-9100a-2  "), ac_lines)
        self.assertTrue(ac_lines[0].endswith("  todo"), ac_lines)
        self.assertEqual(lines[1:], [ticket_lines[0], ac_lines[0]], "lines are not in set order")


if __name__ == "__main__":
    unittest.main()
