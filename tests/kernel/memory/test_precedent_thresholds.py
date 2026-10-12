"""
MODULE: tests.kernel.memory.test_precedent_thresholds
GOAL: The edges of the two precedent thresholds through the real DecisionExecutor: a precedent
    scored exactly at `memory.applies_threshold` is cited as evidence, an overridden threshold
    moves that line, a precedent just under `memory.reuse_threshold` is cited without a reuse
    question, and at most `memory.max_precedents` candidates are judged.
BUSINESS CONTEXT: Precedent is evidence, never authority (ADR-060). The thresholds are
    configuration, so a change to a default or an override must move exactly the behaviour the
    acceptance criteria describe (DK-600e-2, DK-600e-3-ii) and nothing else.
ARCHITECTURE: PrecedentCase (a real file memory with one approved record and a scripted Jev) with
    a `memory` config override; the score Jev gives every precedent comes from `params`.
"""

from __future__ import annotations

from dataclasses import replace

from kernel.config import load_kernel_config
from kernel.contracts.enums import EvidenceCategory, RequestKind, ResultStatus
from kernel.contracts.payloads import HumanQuestionRequestPayload
from tests.kernel.helpers import make_context
from tests.kernel.memory.support import make_record
from tests.kernel.memory.test_decision_precedent import PRECEDENT_ID, QUESTION, PrecedentCase


class ThresholdCase(PrecedentCase):
    """A precedent store whose `memory` configuration the test overrides."""

    memory_config: dict = {}

    def ctx(self, evidence=None, **overrides):  # noqa: ANN001, ANN201
        base = load_kernel_config()
        config = base.model_copy(update={
            "memory": base.memory.model_copy(update=self.memory_config)})
        built = make_context(self.root, jev=self.jev, config=config,
                             evidence=self.evidence if evidence is None else evidence)
        return replace(built, memory=self.memory, **overrides)


class TestTheAppliesThresholdEdge(ThresholdCase):
    """A precedent scored at the applies threshold is cited, one under it is not."""

    def test_a_precedent_scored_exactly_at_the_default_threshold_is_cited(self) -> None:
        # covers: DK-600e-2
        self.params["applies"] = 0.5
        _, _, waiting = self.goal()
        (item,) = waiting.evidence
        self.assertEqual(item.category, EvidenceCategory.PRIOR_DECISIONS)
        self.assertEqual(item.source.locator, f"docs/decisions/{PRECEDENT_ID}.yaml")
        self.assertIn("approved by human:tester", item.source.title)
        self.assertIn("2026-10-01", item.source.title)
        self.assertEqual(waiting.decisions[0].precedent_ids, [PRECEDENT_ID])
        self.assertEqual(self.jev.questions_asked("decision.precedent"),
                         [f"precedent.{PRECEDENT_ID}"])

    def test_a_precedent_just_under_the_default_threshold_is_not_cited(self) -> None:
        # covers: DK-600e-2
        self.params["applies"] = 0.49
        _, _, waiting = self.goal()
        self.assertEqual(waiting.evidence, [])
        self.assertEqual(waiting.decisions[0].precedent_ids, [])

    def test_a_raised_threshold_stops_citing_a_score_the_default_would_cite(self) -> None:
        # covers: DK-600e-2
        self.memory_config = {"applies_threshold": 0.7}
        self.params["applies"] = 0.62
        _, _, waiting = self.goal()
        self.assertEqual(waiting.evidence, [])
        notes = waiting.continuation_state["precedents"]
        self.assertEqual([(n["id"], n["action"]) for n in notes],
                         [(PRECEDENT_ID, "not_applicable")])

    def test_a_lowered_threshold_cites_a_score_the_default_would_not(self) -> None:
        # covers: DK-600e-2
        self.memory_config = {"applies_threshold": 0.3}
        self.params["applies"] = 0.4
        _, _, waiting = self.goal()
        self.assertEqual([e.source.locator for e in waiting.evidence],
                         [f"docs/decisions/{PRECEDENT_ID}.yaml"])

    def test_a_score_at_the_threshold_is_cited_when_the_threshold_is_overridden(self) -> None:
        # covers: DK-600e-2
        self.memory_config = {"applies_threshold": 0.7}
        self.params["applies"] = 0.7
        _, _, waiting = self.goal()
        self.assertEqual(len(waiting.evidence), 1)


class TestAtMostMaxPrecedentsAreJudged(ThresholdCase):
    """memory.max_precedents bounds the candidates sent to Jev."""

    def test_five_matching_records_with_a_limit_of_two_judge_two(self) -> None:
        # covers: DK-600e-2
        self.memory_config = {"max_precedents": 2}
        self.write(*(make_record(id=f"dec-{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}{n}",
                                 question=QUESTION) for n in (1, 2, 3, 4)))
        self.params["applies"] = 0.62
        _, _, waiting = self.goal()
        asked = self.jev.questions_asked("decision.precedent")
        self.assertEqual(len(asked), 2)
        self.assertTrue(all(q.startswith("precedent.dec-") for q in asked))
        self.assertEqual(len(waiting.evidence), 2)


class TestJustUnderTheReuseThreshold(ThresholdCase):
    """A precedent scored 0.79 is cited as evidence and never offered for reuse."""

    def test_a_precedent_scored_0_79_is_cited_without_a_reuse_question(self) -> None:
        # covers: DK-600e-3-ii
        self.params["applies"] = 0.79
        _, _, waiting = self.goal()
        self.assertEqual(waiting.status, ResultStatus.WAITING)
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)  # the flow continues
        for request in waiting.requests:
            if request.kind is RequestKind.HUMAN:  # nobody is asked to reuse anything
                question = HumanQuestionRequestPayload.model_validate(request.payload)
                self.assertNotIn("Reuse it", question.question)
        self.assertNotEqual(waiting.continuation_state["phase"], "awaiting_precedent")
        self.assertEqual([e.source.locator for e in waiting.evidence],
                         [f"docs/decisions/{PRECEDENT_ID}.yaml"])
        self.assertEqual([(n["id"], n["action"]) for n in waiting.continuation_state["precedents"]],
                         [(PRECEDENT_ID, "used_as_evidence")])
        self.assertIsNone(waiting.decisions[0].selected_option_id)

    def test_a_precedent_scored_0_8_is_offered_so_0_79_is_the_boundary(self) -> None:
        # covers: DK-600e-3-ii
        self.params["applies"] = 0.8
        _, _, waiting = self.goal()
        self.assertEqual(waiting.requests[0].kind, RequestKind.HUMAN)
        self.assertEqual(waiting.continuation_state["phase"], "awaiting_precedent")


if __name__ == "__main__":
    import unittest

    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 [python-coder]: The exact applies threshold (0.5), an overridden threshold, the
#   max_precedents bound and the 0.79 boundary partner of the reuse threshold, each through the
#   real executor. (#DecisionKernelACTestGaps)
# ====================================================================
