"""AR-400a-1-ii -- a retired ability named inside a recorded DECISION HISTORY comment is not
an instruction and does not stop the build; the same sentence in live text does
(TDD red phase).

The two tests are one experiment: the SAME sentence moved across the comment boundary must
flip the verdict, which only a positional exclusion (not a name allow-list) can do.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402

LOAD = "Load `.claude/skills/create-ac/SKILL.md`"
HISTORY = ["<!--", "DECISION HISTORY", "- create-ac was retired into plan-feature.", f"- it used to say: {LOAD}", "-->"]


class TestDecisionHistoryExclusion(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)
        self.guide = H.plant_skill(self.root, "probe-skill")
        self.rel = "templates/skills/probe-skill/SKILL.md"

    def _write(self, *lines: str) -> None:
        head = self.guide.read_text(encoding="utf-8").split("\n---\n", 1)[0] + "\n---\n\n"
        self.guide.write_text(head + "\n".join(lines) + "\n", encoding="utf-8")

    def test_retired_ability_inside_decision_history_comment_is_not_a_finding(self):
        # covers: AR-400a-1-ii
        # angle: criterion
        """The commented history names create-ac and carries the Load sentence: the validator
        CLI passes with no finding about create-ac -- AND the run demonstrably EXAMINED this
        guide (the stated guides count equals the tree's, which includes it), so the pass
        is not the absence of a check. The real plan-feature SKILL.md (same shape) is in the
        population too."""
        self.assertFalse((self.root / "templates" / "skills" / "create-ac").exists())
        self._write("Probe guide.", *HISTORY, "Nothing live here.")
        rc, out = H.cli(self.root)
        self.assertEqual(H.findings(out, "create-ac"), [], out)
        self.assertEqual(rc, 0, out)
        _defs, guides = H.expected_counts(self.root)
        self.assertIn(guides, H.reported(out, "guide"), f"guides examined not stated / not including the probe guide: {out}")

    def test_same_sentence_in_live_text_fails_naming_guide_ability_and_line(self):
        # covers: AR-400a-1-ii
        # angle: discrimination
        """Wrong versions caught: an allow-list of retired names (create-ac suppressed
        everywhere) and comment stripping that shifts line numbers. The sentence sits AFTER
        a five-line comment block, so a stripped-and-collapsed scan reports the wrong line.
        Paired: the commented form passes, the live form fails with the exact line."""
        self._write("Probe guide.", *HISTORY, "Nothing live here.")
        rc_hist, out_hist = H.cli(self.root)
        self.assertEqual(H.findings(out_hist, "create-ac"), [], out_hist)
        self._write("Probe guide.", *HISTORY, "Nothing live here.", LOAD)
        live_line = self.guide.read_text(encoding="utf-8").splitlines().index(LOAD) + 1  # 1-based, from the file itself
        rc, out = H.cli(self.root)
        hits = H.findings(out, "create-ac")
        self.assertEqual(len(hits), 1, f"live Load sentence must be exactly one finding: {out}")
        self.assertTrue(hits[0].startswith("ERROR:"), hits[0])
        self.assertTrue(H.names_line(hits[0], self.rel, live_line), f"want {self.rel} line {live_line}: {hits[0]}")
        self.assertEqual(rc, 1, out)
        self.assertGreater(live_line, len(HISTORY) + 5, "fixture degenerate: sentence is not below the comment block")


if __name__ == "__main__":
    unittest.main()
