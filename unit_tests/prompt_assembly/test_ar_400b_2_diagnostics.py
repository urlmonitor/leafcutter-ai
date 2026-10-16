"""AR-400b-2-v / -vi -- the two diagnostics: a wrong-letter-case ability name ("differs only in
case", naming the canonical id) and a specialist named as an ability ("names an agent, not an
ability", stating the hand-off relationship) (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400b-2-v.yaml and AR-400b-2-vi.yaml. Every test drives the REAL validator CLI over a copied
package slice. Each "passes" row is paired with a control (a second specialist whose same fault MUST
be reported), so an absent gate cannot pass it vacuously.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402

MISCASED = "Step 1 -- Load the Write-C4-Diagram Skill"
CORRECT = "Step 1 -- Load the write-c4-diagram Skill"
SQL_AS_SKILL = "Use the `sql-query` skill if available to scaffold the object"
SQL_HAND_OFF = "Hand the scaffolding to the `sql-query` sub-agent"


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)


class TestCaseDiagnostic(_Base):
    def test_miscased_heading_yields_one_case_finding_with_canonical_id(self):
        # covers: AR-400b-2-v
        # angle: criterion
        # must_catch: case-folded match silently passes
        # must_catch: the miscased text is reported as 'ability does not exist'
        """probe-author grants write-c4-diagram and has the heading 'Load the Write-C4-Diagram
        Skill'. The CLI fails with EXACTLY ONE finding, kind 'differs only in case', naming
        probe-author, the text as written, the canonical id, the file and the line -- not 'does not
        exist' and not 'not granted' (the case kind takes precedence over a folded grant match)."""
        path = F.plant(self.root, "probe-author", [MISCASED], grants=("write-c4-diagram",))
        rc, out = H.cli(self.root)
        got = F.about(out, "probe-author")
        self.assertEqual(len(got), 1, f"expected exactly one finding: {got}")
        self.assertIn(F.CASE, got[0].lower())
        self.assertIn("Write-C4-Diagram", got[0], "must name the text as written")
        self.assertTrue(F.names(got[0], "write-c4-diagram"), "must name the canonical identifier")
        self.assertTrue(H.names_line(got[0], F.agent_rel("probe-author"), F.line_of(path, MISCASED)), got[0])
        for other in (F.NONEXIST, F.UNGRANTED):
            self.assertNotIn(other, got[0].lower())
        self.assertEqual(rc, 1, out[-800:])

    def test_correctly_cased_heading_passes(self):
        # covers: AR-400b-2-v
        # angle: discrimination
        """Negative control: 'Load the write-c4-diagram Skill' makes probe-author pass with no
        finding. Control row in the same run: probe-control keeps the miscased heading and MUST be
        reported once as a case fault."""
        F.plant(self.root, "probe-author", [CORRECT], grants=("write-c4-diagram",))
        F.plant(self.root, "probe-control", [MISCASED], grants=("write-c4-diagram",))
        rc, out = H.cli(self.root)
        self.assertEqual(len(F.of_kind(out, F.CASE, "Write-C4-Diagram", "probe-control")), 1, out[-1200:])
        self.assertEqual(F.about(out, "probe-author"), [])
        self.assertEqual(rc, 1, out[-800:])


class TestAgentDiagnostic(_Base):
    def _coder(self, body: str, spawn: tuple[str, ...] = ("sql-query",)):
        return F.plant(self.root, "probe-coder", [body], spawn=spawn)

    def test_specialist_named_as_ability_yields_names_an_agent_finding(self):
        # covers: AR-400b-2-vi
        # angle: criterion
        # must_catch: the finding is classified 'ability does not exist'
        """probe-coder's spawn_allowlist declares sql-query and its body says 'Use the `sql-query`
        skill if available' (no ability sql-query exists). One finding, kind 'names an agent, not an
        ability', naming probe-coder, sql-query, the file and the line, stating sql-query is a
        specialist probe-coder may hand work to; never classified 'does not exist'."""
        path = self._coder(SQL_AS_SKILL)
        rc, out = H.cli(self.root)
        got = F.about(out, "probe-coder")
        self.assertEqual(len(got), 1, f"expected exactly one finding: {got}")
        self.assertIn(F.AGENT, got[0].lower())
        self.assertNotIn(F.NONEXIST, got[0].lower())
        self.assertTrue(F.names(got[0], "sql-query"), got[0])
        self.assertTrue(H.names_line(got[0], F.agent_rel("probe-coder"), F.line_of(path, SQL_AS_SKILL)), got[0])
        self.assertRegex(got[0].lower(), r"hand[- ]?(?:off|work)", "must state the hand-off relationship")
        self.assertIsNone(re.search(r"not in[^\n]*hand[- ]?off", got[0].lower()), "sql-query IS in the hand-off list")
        self.assertEqual(rc, 1, out[-800:])

    def test_hand_off_sentence_passes(self):
        # covers: AR-400b-2-vi
        # angle: discrimination
        """'Hand the scaffolding to the `sql-query` sub-agent' passes with no finding. Control row
        in the same run: probe-control uses the skill phrasing and MUST be reported once."""
        self._coder(SQL_HAND_OFF)
        F.plant(self.root, "probe-control", [SQL_AS_SKILL], spawn=("sql-query",))
        rc, out = H.cli(self.root)
        self.assertEqual(len(F.of_kind(out, F.AGENT, "sql-query", "probe-control")), 1, out[-1200:])
        self.assertEqual(F.about(out, "probe-coder"), [])
        self.assertEqual(rc, 1, out[-800:])

    def test_names_an_agent_outside_hand_off_list_says_so(self):
        # covers: AR-400b-2-vi
        # angle: boundary
        """With sql-query removed from probe-coder's spawn_allowlist the finding is still 'names an
        agent' (not 'does not exist') and additionally states sql-query is not in probe-coder's
        hand-off list."""
        self._coder(SQL_AS_SKILL, spawn=())
        rc, out = H.cli(self.root)
        got = F.of_kind(out, F.AGENT, "sql-query", "probe-coder")
        self.assertEqual(len(got), 1, out[-1200:])
        self.assertNotIn(F.NONEXIST, got[0].lower())
        self.assertRegex(got[0].lower(), r"not in[^\n]*hand[- ]?off", "must say sql-query is outside the hand-off list")
        self.assertEqual(rc, 1, out[-800:])


if __name__ == "__main__":
    unittest.main()
