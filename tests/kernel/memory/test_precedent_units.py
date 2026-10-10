"""
MODULE: tests.kernel.memory.test_precedent_units
GOAL: The pure parts of precedent handling: the lookup query (components and phase where known),
    the literal Jev question per precedent, the verdict thresholds (applicable, offered for
    reuse, never a superseded record), the evidence a precedent becomes and the links of the
    record a decision stages after the human answered.
BUSINESS CONTEXT: Precedent is evidence, never authority (ADR-060). Thresholds are configuration
    (`memory.applies_threshold`, `memory.reuse_threshold`); only a strong, current precedent is
    offered to the human, and a human who decides anew against it is recorded, not overridden.
ARCHITECTURE: Real models and the real default config; no executor and no Jev.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime

from kernel.config import load_kernel_config
from kernel.contracts.enums import EvidenceCategory
from kernel.contracts.task import Scope
from kernel.memory.models import PrecedentAction, PrecedentNote
from kernel.memory.port import DecisionHit, NullColonyMemory
from kernel.memory.precedent import (
    DECIDE_ANEW,
    REUSE,
    confirm_choices,
    confirm_text,
    final_links,
    find_precedents,
    judge,
    phases_from_constraints,
    precedent_evidence,
    precedent_query,
    precedent_questions,
    precedent_state,
    summary,
)
from tests.kernel.memory.support import CHECKOUT, make_record

CFG = load_kernel_config().memory
FIRST = "dec-0123456789abcdef"


def hit(record_id: str = FIRST, *, superseded: tuple[str, ...] = (), **overrides) -> DecisionHit:  # noqa: ANN003
    """Return a precedent hit over the fixture record (or a variant of it)."""
    return DecisionHit(record=make_record(id=record_id, **overrides), score=1.0,
                       path=f"docs/decisions/{record_id}.yaml", superseded_by=superseded)


class TestQueryAndQuestions(unittest.TestCase):
    """What is asked of the store and of Jev."""

    def test_the_query_carries_components_phase_limit_and_minimum_score(self) -> None:
        # covers: DK-600e-1
        scope = Scope(workspace_id="ws", repository_root=str(CHECKOUT), component_ids=["decision_kernel"])
        query = precedent_query("How?", scope, ["[hard] roadmap_phase: phase_1"], CFG)
        self.assertEqual((query.components, query.roadmap_phase, query.limit, query.min_score),
                         (["decision_kernel"], ["phase_1"], CFG.max_precedents,
                          CFG.min_candidate_score))

    def test_phases_are_read_from_the_constraint_texts(self) -> None:
        texts = ["[hard] roadmap_phase: phase_2", "[soft] forbid: nothing", "roadmap_phase: x"]
        self.assertEqual(phases_from_constraints(texts), ["phase_2"])

    def test_memory_off_or_zero_precedents_finds_nothing(self) -> None:
        scope = Scope(workspace_id="ws", repository_root=str(CHECKOUT))
        self.assertEqual(find_precedents(NullColonyMemory(), "q", scope, [], CFG), [])
        off = CFG.model_copy(update={"max_precedents": 0})
        self.assertEqual(find_precedents(NullColonyMemory(), "q", scope, [], off), [])

    def test_one_literal_noul_question_per_precedent(self) -> None:
        (question,) = precedent_questions([hit()])
        self.assertEqual((question.id, question.kind, question.template_id),
                         (f"precedent.{FIRST}", "noul", "decision.precedent"))
        self.assertIn(f"precedents.{FIRST}", str(question.instructions))
        self.assertIn("apply to the current `question` in its context", str(question.instructions))
        self.assertEqual(set(question.criteria or {}), {"true", "false"})

    def test_the_state_quotes_a_short_text_with_the_approver_and_date(self) -> None:
        text = precedent_state([hit()])[FIRST]
        self.assertIn("One YAML file per decision", str(text))
        self.assertIn("human:tester on 2026-10-01", str(text))
        self.assertLessEqual(len(summary(hit())), 900)

    def test_a_superseded_precedent_says_so(self) -> None:
        # covers: DK-600e-3-iii
        self.assertIn("Superseded by dec-3333333333333333",
                      summary(hit(superseded=("dec-3333333333333333",))))


class TestVerdict(unittest.TestCase):
    """applies_threshold makes evidence, reuse_threshold makes the offer, nothing else does."""

    def test_default_thresholds_are_ordered(self) -> None:
        self.assertEqual((CFG.applies_threshold, CFG.reuse_threshold), (0.5, 0.8))

    def test_below_the_applies_threshold_is_not_applicable(self) -> None:
        # covers: DK-600e-2-i
        verdict = judge([hit()], {FIRST: 0.49}, CFG, can_reuse=True)
        self.assertEqual((verdict.applicable, verdict.offer), ([], None))
        self.assertEqual([n.action for n in verdict.notes], ["not_applicable"])

    def test_between_the_thresholds_is_evidence_only(self) -> None:
        # covers: DK-600e-3-ii
        verdict = judge([hit()], {FIRST: 0.6}, CFG, can_reuse=True)
        self.assertEqual(len(verdict.applicable), 1)
        self.assertIsNone(verdict.offer)
        self.assertEqual([n.action for n in verdict.notes], ["used_as_evidence"])

    def test_exactly_at_the_applies_threshold_is_evidence(self) -> None:
        # covers: DK-600e-2
        verdict = judge([hit()], {FIRST: 0.5}, CFG, can_reuse=True)
        self.assertEqual(len(verdict.applicable), 1)
        self.assertEqual([n.action for n in verdict.notes], ["used_as_evidence"])

    def test_an_overridden_threshold_moves_the_line(self) -> None:
        # covers: DK-600e-2
        strict = CFG.model_copy(update={"applies_threshold": 0.7})
        self.assertEqual(judge([hit()], {FIRST: 0.62}, strict, can_reuse=True).applicable, [])
        loose = CFG.model_copy(update={"applies_threshold": 0.3, "reuse_threshold": 0.4})
        verdict = judge([hit()], {FIRST: 0.4}, loose, can_reuse=True)
        self.assertEqual([n.action for n in verdict.notes], ["offered_for_reuse"])

    def test_just_under_the_reuse_threshold_is_evidence_only(self) -> None:
        # covers: DK-600e-3-ii
        verdict = judge([hit()], {FIRST: 0.79}, CFG, can_reuse=True)
        self.assertEqual(len(verdict.applicable), 1)
        self.assertIsNone(verdict.offer)
        self.assertEqual([n.action for n in verdict.notes], ["used_as_evidence"])

    def test_at_the_reuse_threshold_it_is_offered(self) -> None:
        # covers: DK-600e-3
        verdict = judge([hit()], {FIRST: 0.8}, CFG, can_reuse=True)
        self.assertEqual(narrow_id(verdict.offer), FIRST)
        self.assertEqual([n.action for n in verdict.notes], ["offered_for_reuse"])

    def test_nothing_is_offered_when_the_decision_has_options_or_the_record_is_superseded(self
                                                                                          ) -> None:
        # covers: DK-600e-3-iii
        # covers: DK-600e-3-iv
        self.assertIsNone(judge([hit()], {FIRST: 0.99}, CFG, can_reuse=False).offer)
        old = hit(superseded=("dec-3333333333333333",))
        self.assertIsNone(judge([old], {FIRST: 0.99}, CFG, can_reuse=True).offer)

    def test_the_strongest_applicable_precedent_is_the_one_offered(self) -> None:
        # covers: DK-600e-3
        other = "dec-1111111111111111"
        verdict = judge([hit(), hit(other)], {FIRST: 0.85, other: 0.95}, CFG, can_reuse=True)
        self.assertEqual(narrow_id(verdict.offer), other)
        self.assertEqual({n.id: n.action for n in verdict.notes},
                         {FIRST: "used_as_evidence", other: "offered_for_reuse"})


class TestEvidenceAndQuestion(unittest.TestCase):
    """What a precedent becomes for the kernel and for the human."""

    def test_the_evidence_is_prior_decisions_with_the_record_path_and_approver(self) -> None:
        item = precedent_evidence(hit(), 0.9, datetime(2026, 10, 2, tzinfo=UTC))
        self.assertEqual(item.category, EvidenceCategory.PRIOR_DECISIONS)
        self.assertEqual(item.source.locator, f"docs/decisions/{FIRST}.yaml")
        self.assertIn("human:tester", item.source.title)
        self.assertEqual(item.provenance.relevance, 0.9)
        self.assertIsNone(item.provenance.actor)
        self.assertIn("Rationale:", item.excerpt or "")
        self.assertEqual(item.source.source_version.commit, "abc1234567")  # type: ignore[union-attr]

    def test_the_evidence_id_is_stable_for_the_same_record(self) -> None:
        a = precedent_evidence(hit(), 0.9, datetime(2026, 10, 2, tzinfo=UTC))
        b = precedent_evidence(hit(), 0.5, datetime(2026, 11, 9, tzinfo=UTC))
        self.assertEqual(a.id, b.id)

    def test_the_confirm_question_and_choices_are_literal(self) -> None:
        # covers: DK-600e-3
        record = make_record()
        self.assertEqual(confirm_text(record), (
            "Decision dec-0123456789abcdef (approved by human:tester on 2026-10-01) chose "
            "One YAML file per decision for a matching question. Reuse it, or decide anew?"))
        self.assertEqual([c.id for c in confirm_choices(record)], [REUSE, DECIDE_ANEW])


class TestFinalLinks(unittest.TestCase):
    """The links of the record staged after the human answered."""

    def notes(self, action: PrecedentAction = "offered_for_reuse"):  # noqa: ANN201
        return [PrecedentNote(id=FIRST, applicability=0.9, action=action, note="n")]

    def test_reuse_relates_without_superseding(self) -> None:
        supersedes, related, final = final_links(
            self.notes(), offer_id=FIRST, offer_title="One YAML file per decision", choice=REUSE,
            selected_title="One YAML file per decision")
        self.assertEqual((supersedes, related, final[0].action), ([], [FIRST], "reused"))

    def test_deciding_anew_to_the_same_option_relates_only(self) -> None:
        # covers: DK-600e-3-i
        # angle: criterion
        supersedes, related, final = final_links(
            self.notes(), offer_id=FIRST, offer_title="One YAML file per decision",
            choice=DECIDE_ANEW, selected_title="one yaml file per decision")
        self.assertEqual((supersedes, related, final[0].action), ([], [FIRST], "set_aside"))

    def test_deciding_anew_to_a_different_option_supersedes_and_says_why(self) -> None:
        # covers: DK-600e-3-i
        # angle: criterion
        supersedes, related, final = final_links(
            self.notes(), offer_id=FIRST, offer_title="One YAML file per decision",
            choice=DECIDE_ANEW, selected_title="A graph database")
        self.assertEqual((supersedes, related), ([FIRST], [FIRST]))
        self.assertIn("chose a different option", final[0].note)

    def test_a_precedent_judged_not_applicable_is_not_related(self) -> None:
        # covers: DK-600e-2-i
        supersedes, related, _ = final_links(
            self.notes("not_applicable"), offer_id=None, offer_title=None, choice=None,
            selected_title="x")
        self.assertEqual((supersedes, related), ([], []))


def narrow_id(found: DecisionHit | None) -> str:
    """Return the record id of an offered hit (asserting there is one)."""
    assert found is not None
    return found.record.id


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The threshold rules are tested at their edges (0.49, 0.6, 0.8) so a
#   change to a default cannot silently widen what the human is asked to reuse.
#   (#KernelDecisionStore)
# ====================================================================
