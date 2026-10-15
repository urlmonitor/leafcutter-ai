"""AR-400a-2 -- a shared guide that tells its reader to use an ability that does not exist
stops the build too (TDD red phase).

Guides are every scanned .md that is not an agent definition: the catalogue's own
templates/skills/README.md and each ability body. Each (guide, line) is its own finding.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402

SENTENCE = f"Load `.claude/skills/{H.GHOST}/SKILL.md` and apply the decision tree"
README = "templates/skills/README.md"
PROBE = "templates/skills/probe-skill/SKILL.md"


class TestSharedGuides(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)

    def _plant_two(self):
        H.put_line(self.root / README, 12, SENTENCE)
        H.plant_skill(self.root, "probe-skill", sentence=SENTENCE, line=12)

    def test_nonexistent_ability_in_two_shared_guides_yields_two_findings(self):
        # covers: AR-400a-2
        # angle: criterion
        """Identical text on line 12 of the catalogue README and of a new ability body: the
        CLI exits 1 with exactly TWO ghost-ability errors -- one per guide, each naming its
        own file, line 12 and kind 'ability does not exist' (no de-duplication by ability
        id; guides are scanned at all). Control: the slice before planting exits 0."""
        rc0, out0 = H.cli(self.root)
        self.assertEqual(rc0, 0, out0)
        self._plant_two()
        rc, out = H.cli(self.root)
        hits = H.findings(out, H.GHOST)
        self.assertEqual(len(hits), 2, f"expected one finding per guide: {out}")
        self.assertTrue(all(h.startswith("ERROR:") for h in hits), hits)
        self.assertEqual(len([h for h in hits if H.names_line(h, README, 12)]), 1, hits)
        self.assertEqual(len([h for h in hits if H.names_line(h, PROBE, 12)]), 1, hits)
        self.assertEqual(rc, 1, out)

    def test_guides_examined_is_reported_separately_from_definitions(self):
        # covers: AR-400a-2
        # angle: boundary
        """The run states a guides-examined figure distinct from definitions-examined (both
        equal to the independently derived counts, which differ); and when every
        non-definition .md is removed the guides population is zero and the run FAILS
        naming zero guides (AR-400a-1-i), while the definitions population is untouched."""
        defs, guides = H.expected_counts(self.root)
        self.assertNotEqual(defs, guides)
        rc, out = H.cli(self.root)
        self.assertEqual(rc, 0, out)
        self.assertIn(defs, H.reported(out, "definition"), out)
        self.assertIn(guides, H.reported(out, "guide"), out)
        keep = {p.resolve() for p in (self.root / "templates" / "agents").glob("*.md")
                if p.name != "README.md" and not p.name.startswith("_")}
        for md in list((self.root / "templates").rglob("*.md")):
            if md.resolve() not in keep:
                md.unlink()
        self.assertEqual(H.expected_counts(self.root)[1], 0)
        rc, out = H.cli(self.root)
        self.assertNotEqual(rc, 0, out)
        zero = [ln for ln in H.lines_of(out) if H.is_zero_message(ln, "guide", self.root / "templates")]
        self.assertTrue(zero, f"no 'zero guides examined' error naming the templates location: {out}")
        self.assertEqual([ln for ln in H.lines_of(out)
                          if H.is_zero_message(ln, "definition", self.root / "templates" / "agents")], [])

    def test_removing_sentence_from_both_guides_passes(self):
        # covers: AR-400a-2
        # angle: discrimination
        """Wrong version caught: findings that never clear. Paired: with the sentence in both
        guides the run fails with two findings; with a plain line restored in both the same
        run exits 0 with no ghost-ability finding."""
        self._plant_two()
        rc, out = H.cli(self.root)
        self.assertEqual((rc, len(H.findings(out, H.GHOST))), (1, 2), out)
        H.put_line(self.root / README, 12, H.FILLER)
        H.put_line(self.root / PROBE, 12, H.FILLER)
        rc, out = H.cli(self.root)
        self.assertEqual(rc, 0, out)
        self.assertEqual(H.findings(out, H.GHOST), [], out)


if __name__ == "__main__":
    unittest.main()
