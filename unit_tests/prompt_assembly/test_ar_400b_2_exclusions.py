"""AR-400b-2-i / -ii / -iii -- sentences that are NOT instructions to use an ability: a negation, a
sentence about another specialist, a citation of an ability's file (TDD red phase).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400b-2-i.yaml, -ii.yaml, -iii.yaml. Every test drives the REAL validator CLI over a copied package
slice. Each "no finding" assertion sits next to a control row (a plain imperative in a second
specialist of the same run) that MUST produce exactly one finding, so a gate that does not exist yet
cannot pass them vacuously; each exclusion is paired with its discriminating rewrite.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _ar_400a_1_support as H  # noqa: E402
import _ar400_3a_fixtures as F  # noqa: E402

PROBE = "probe-agent"
CONTROL = "probe-control"
SIGNOFF_CITATION = ("This shape is normatively defined in `templates/skills/signoff/SKILL.md` "
                    "section 7 step 2 -- the field set below must match that definition.")


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = H.make_slice(self._tmp.name)

    def _control(self, ability: str = "a4") -> None:
        """A second specialist whose plain imperative must be flagged (proves the gate is live)."""
        F.planted_skills(self.root, ability)
        F.plant(self.root, CONTROL, [f"Load the `{ability}` skill first."])

    def _assert_control_fired(self, out: str, ability: str = "a4") -> None:
        self.assertEqual(len(F.of_kind(out, F.UNGRANTED, ability, CONTROL)), 1,
                         f"control imperative was not flagged exactly once: {out[-1200:]}")


class TestNegation(_Base):
    NEGATED = [
        "You do not invoke the `signoff` skill.",
        "Embeds design principles directly (does NOT load the legacy a1 skill).",
        "Do NOT read `.claude/skills/a2/SKILL.md` -- even if that file exists.",
    ]

    def test_three_negated_sentences_produce_no_finding(self):
        # covers: AR-400b-2-i
        # angle: criterion
        """probe-agent (grants nothing) carries the three negated sentences about existing abilities:
        no finding for any of them. Control: probe-control's plain imperative is flagged once."""
        F.planted_skills(self.root, "a1", "a2")
        F.plant(self.root, PROBE, self.NEGATED)
        self._control()
        rc, out = H.cli(self.root)
        self._assert_control_fired(out)
        self.assertEqual(F.about(out, PROBE), [], "a sentence saying NOT to use an ability is no instruction")
        self.assertEqual(rc, 1, out[-800:])

    def test_removing_the_negation_produces_a_not_granted_finding(self):
        # covers: AR-400b-2-i
        # angle: discrimination
        """The third sentence loses its negation ('Read `.claude/skills/a2/SKILL.md` -- even if that
        file exists.'): the run fails with 'not granted' for a2 on that line, and ONLY that line (the
        other two negated sentences stay silent)."""
        F.planted_skills(self.root, "a1", "a2")
        affirmed = "Read `.claude/skills/a2/SKILL.md` -- even if that file exists."
        path = F.plant(self.root, PROBE, [*self.NEGATED[:2], affirmed])
        rc, out = H.cli(self.root)
        got = F.about(out, PROBE)
        self.assertEqual(len(got), 1, f"expected exactly one finding: {got}")
        self.assertIn(F.UNGRANTED, got[0].lower())
        self.assertTrue(F.names(got[0], "a2"), got[0])
        self.assertTrue(H.names_line(got[0], F.agent_rel(PROBE), F.line_of(path, affirmed)), got[0])
        self.assertEqual(rc, 1, out[-800:])

    def test_negation_in_another_clause_does_not_suppress_the_instruction(self):
        # covers: AR-400b-2-i
        # angle: discrimination
        # must_catch: any negation word anywhere on the line suppresses the line
        """'Do not skip this step; load the `a3` skill first.' -- the negation governs a different
        clause than the instruction, so a3 is still flagged."""
        F.planted_skills(self.root, "a3")
        F.plant(self.root, PROBE, ["Do not skip this step; load the `a3` skill first."])
        rc, out = H.cli(self.root)
        got = F.of_kind(out, F.UNGRANTED, "a3", PROBE)
        self.assertEqual(len(got), 1, f"the instruction clause must be flagged: {out[-1200:]}")
        self.assertEqual(rc, 1, out[-800:])


class TestOtherSpecialistSubject(_Base):
    NOTE = ("**Note:** `frontend-coder` may invoke the `webapp-testing` skill internally as part of "
            "its own phase.")
    OTHER_NOTE = "**Note:** `research-agent` may invoke the `webapp-testing` skill internally as part of its own phase."
    IMPERATIVE = "Invoke the `webapp-testing` skill before dispatching frontend-coder."

    def test_sentence_with_other_specialist_as_subject_is_not_an_instruction(self):
        # covers: AR-400b-2-ii
        # angle: criterion
        """probe-supervisor grants only building-epics; its body has the frontend-coder/webapp-testing
        note, plus the same note about ANOTHER specialist id (the rule is data-driven, never keyed on
        the literal name): no finding about webapp-testing. Control: probe-control is flagged once."""
        F.plant(self.root, "probe-supervisor", [self.NOTE, self.OTHER_NOTE], grants=("building-epics",))
        self._control("a4")
        rc, out = H.cli(self.root)
        self._assert_control_fired(out)
        self.assertEqual(F.about(out, "probe-supervisor"), [], "a sentence about another specialist is no instruction")
        self.assertEqual(rc, 1, out[-800:])

    def test_imperative_mentioning_another_specialist_is_still_an_instruction(self):
        # covers: AR-400b-2-ii
        # angle: discrimination
        # must_catch: any sentence containing another agent id is exempt
        # must_catch: the exemption is keyed on the literal name frontend-coder
        """'Invoke the `webapp-testing` skill before dispatching frontend-coder.' addresses the
        reader: probe-supervisor / webapp-testing is 'not granted' on that line."""
        path = F.plant(self.root, "probe-supervisor", [self.IMPERATIVE], grants=("building-epics",))
        rc, out = H.cli(self.root)
        got = F.of_kind(out, F.UNGRANTED, "webapp-testing", "probe-supervisor")
        self.assertEqual(len(got), 1, out[-1200:])
        self.assertTrue(H.names_line(got[0], F.agent_rel("probe-supervisor"), F.line_of(path, self.IMPERATIVE)), got[0])
        self.assertEqual(rc, 1, out[-800:])


class TestCitation(_Base):
    SEE = "See signoff section 2b for the required format."
    LOAD = "Load `templates/skills/signoff/SKILL.md` and follow section 7."
    GHOST = "The record layout is as defined in `templates/skills/ghost-ability/SKILL.md`."

    def test_citations_of_existing_ability_produce_no_finding(self):
        # covers: AR-400b-2-iii
        # angle: criterion
        """probe-agent (grants nothing) carries the two citation sentences about signoff: no finding.
        Control: probe-control's plain imperative is flagged once."""
        F.plant(self.root, PROBE, [SIGNOFF_CITATION, self.SEE])
        self._control()
        rc, out = H.cli(self.root)
        self._assert_control_fired(out)
        self.assertEqual(F.about(out, PROBE), [], "a citation of an ability's file is exempt from the grant check")
        self.assertEqual(rc, 1, out[-800:])

    def test_load_instruction_of_same_file_is_not_granted(self):
        # covers: AR-400b-2-iii
        # angle: discrimination
        """The first citation rewritten as 'Load `templates/skills/signoff/SKILL.md` and follow
        section 7.' is an instruction: 'not granted' for probe-agent / signoff on that line."""
        path = F.plant(self.root, PROBE, [self.LOAD, self.SEE])
        rc, out = H.cli(self.root)
        got = F.of_kind(out, F.UNGRANTED, "signoff", PROBE)
        self.assertEqual(len(got), 1, out[-1200:])
        self.assertTrue(H.names_line(got[0], F.agent_rel(PROBE), F.line_of(path, self.LOAD)), got[0])
        self.assertEqual(F.about(out, PROBE), got, "the 'See signoff section 2b' citation must stay silent")
        self.assertEqual(rc, 1, out[-800:])

    def test_citation_of_nonexistent_ability_fails_existence(self):
        # covers: AR-400b-2-iii
        # angle: discrimination
        # must_catch: citations are exempt from both checks
        """A citation naming an ability that does not exist is reported 'ability does not exist': a
        citation is exempt from the grant check, never from the existence check."""
        path = F.plant(self.root, PROBE, [self.GHOST])
        rc, out = H.cli(self.root)
        got = F.of_kind(out, F.NONEXIST, "ghost-ability", PROBE)
        self.assertEqual(len(got), 1, out[-1200:])
        self.assertTrue(H.names_line(got[0], F.agent_rel(PROBE), F.line_of(path, self.GHOST)), got[0])
        self.assertEqual(rc, 1, out[-800:])


if __name__ == "__main__":
    unittest.main()
