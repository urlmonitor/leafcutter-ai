"""
MODULE: tests.kernel.intent.test_classify
GOAL: Test the answer-kind classification: the literal Jev question, the threshold
    interpretation, a provider failure keeping the default and the effective goal after a
    clarification.
BUSINESS CONTEXT: The root request must pick a supported output contract (Rev 3 section 7.11) and
    Jev may only choose among kinds the kernel supplies (section 9): a low-confidence answer must
    never select, and no threshold may be hard-coded in the logic (they come from `config.intent`).
ARCHITECTURE: Pure functions and the one async function over ScriptedJev; thresholds are taken from
    the default config and then replaced to show the code follows the configuration.
"""

from __future__ import annotations

import unittest

from kernel.config import load_kernel_config
from kernel.contracts import CorrelationIds, RoutingOutcome
from kernel.intent import (
    ANSWER_KINDS,
    ClarificationAnswer,
    assess_intent,
    chosen_kind,
    effective_goal,
)
from kernel.intent.classify import INTENT_PURPOSE, INTENT_QUESTION_ID, NEEDS_CONTEXT_ID, interpret
from kernel.providers.base import JevInvalidResponse, JevUnavailable
from kernel.providers.fakes import ScriptedJev, choice_answer
from tests.kernel.helpers import as_json, narrow

CFG = load_kernel_config().intent
CORR = CorrelationIds()


def _assess(jev: ScriptedJev, goal: str = "Where are tests saved?", answers=None, cfg=CFG):
    return assess_intent(jev, goal, answers or [], ["decision_kernel"], cfg, CORR)


class TestThresholds(unittest.IsolatedAsyncioTestCase):
    """The configured thresholds decide between a kind and a clarification."""

    async def test_confident_answer_selects_the_kind(self) -> None:
        jev = ScriptedJev().script(INTENT_PURPOSE, "intent.*", choice_answer("evidence", 0.9, 0.8))
        result = await _assess(jev)
        self.assertEqual((result.outcome, result.kind), (RoutingOutcome.SELECTED, "evidence"))
        self.assertEqual(result.probabilities["evidence"], 0.9)
        self.assertEqual(result.confidence, 0.8)
        self.assertTrue(result.jev_called)
        self.assertEqual(result.usage[0].provider, "jev")

    async def test_low_probability_asks_for_clarification(self) -> None:
        jev = ScriptedJev().script(INTENT_PURPOSE, "intent.*", choice_answer("evidence", 0.5, 0.9))
        result = await _assess(jev)
        self.assertEqual(result.outcome, RoutingOutcome.INSUFFICIENT_CONTEXT)
        self.assertIsNone(result.kind)
        self.assertEqual(result.reason_codes, ["low_confidence"])

    async def test_low_confidence_or_missing_confidence_never_selects(self) -> None:
        for confidence in (0.1, None):
            jev = ScriptedJev().script(INTENT_PURPOSE, "intent.*",
                                       choice_answer("change", 0.99, confidence))
            result = await _assess(jev)
            self.assertEqual(result.outcome, RoutingOutcome.INSUFFICIENT_CONTEXT)

    async def test_needs_context_asks_for_clarification(self) -> None:
        jev = ScriptedJev().script(INTENT_PURPOSE, "intent.*",
                                   choice_answer(NEEDS_CONTEXT_ID, 0.8, 0.8))
        result = await _assess(jev)
        self.assertEqual((result.outcome, result.reason_codes),
                         (RoutingOutcome.INSUFFICIENT_CONTEXT, ["jev_needs_context"]))

    async def test_thresholds_come_from_the_configuration(self) -> None:
        strict = CFG.model_copy(update={"min_selected_probability": 0.99})
        jev = ScriptedJev().script(INTENT_PURPOSE, "intent.*", choice_answer("decision", 0.95, 0.9))
        self.assertEqual((await _assess(jev, cfg=CFG)).outcome, RoutingOutcome.SELECTED)
        self.assertEqual((await _assess(jev, cfg=strict)).outcome,
                         RoutingOutcome.INSUFFICIENT_CONTEXT)

    async def test_an_unoffered_kind_is_an_invalid_response(self) -> None:
        with self.assertRaises(JevInvalidResponse):
            interpret(choice_answer("weather", 0.9, 0.9), CFG)


class TestQuestion(unittest.IsolatedAsyncioTestCase):
    """One literal choice question over exactly the supplied kinds."""

    async def test_the_batch_offers_the_five_kinds_and_needs_context(self) -> None:
        jev = ScriptedJev().script(INTENT_PURPOSE, "intent.*", choice_answer("decision"))
        await _assess(jev, goal="Pick a cache")
        (batch,) = jev.batches
        (question,) = batch.questions
        self.assertEqual((batch.purpose, question.id, question.kind),
                         (INTENT_PURPOSE, INTENT_QUESTION_ID, "choice"))
        self.assertEqual(sorted(narrow(question.criteria)), sorted([*ANSWER_KINDS, NEEDS_CONTEXT_ID]))
        self.assertEqual(as_json(batch.state)["task"]["goal"], "Pick a cache")

    async def test_the_clarified_goal_is_what_jev_classifies(self) -> None:
        jev = ScriptedJev().script(INTENT_PURPOSE, "intent.*", choice_answer("decision"))
        answers = [ClarificationAnswer("Decide which criterion to implement next.")]
        await _assess(jev, goal="Implement a critical acceptance criterion.", answers=answers)
        goal = as_json(jev.batches[0].state)["task"]["goal"]
        self.assertTrue(goal.startswith("Decide which criterion to implement next."))
        self.assertIn("Implement a critical acceptance criterion.", goal)


class TestFailures(unittest.IsolatedAsyncioTestCase):
    """A provider failure is `unavailable`, never an invented kind."""

    async def test_unavailable_provider(self) -> None:
        jev = ScriptedJev().fail_next(JevUnavailable("down"))
        result = await _assess(jev)
        self.assertEqual((result.outcome, result.kind, result.reason_codes),
                         (RoutingOutcome.UNAVAILABLE, None, ["provider_unavailable"]))

    async def test_unscripted_question_is_invalid(self) -> None:
        result = await _assess(ScriptedJev())
        self.assertEqual(result.reason_codes, ["invalid_provider_response"])


class TestEffectiveGoal(unittest.TestCase):
    """The answer is the primary statement of intent."""

    def test_without_answers_the_goal_is_unchanged(self) -> None:
        self.assertEqual(effective_goal("Do X", []), "Do X")

    def test_the_latest_answer_leads_and_the_original_follows(self) -> None:
        text = effective_goal("Do X", [ClarificationAnswer("old"), ClarificationAnswer("Decide Y")])
        self.assertEqual(text, "Decide Y (original request: Do X)")

    def test_a_blank_answer_keeps_the_original(self) -> None:
        self.assertEqual(effective_goal("Do X", [ClarificationAnswer("  ")]), "Do X")

    def test_the_result_stays_within_the_goal_limit(self) -> None:
        self.assertLessEqual(len(effective_goal("g" * 4000, [ClarificationAnswer("a" * 50)])), 4000)

    def test_a_chosen_answer_kind_is_recognised(self) -> None:
        answers = [ClarificationAnswer("text"), ClarificationAnswer("Find facts", "evidence")]
        self.assertEqual(chosen_kind(answers), "evidence")
        self.assertIsNone(chosen_kind([ClarificationAnswer("free")]))
        self.assertIsNone(chosen_kind([ClarificationAnswer("x", "retrieve.repository")]))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: Thresholds are exercised by replacing them in the config
#   copy, proving the logic carries no number of its own. (#KernelBootstrapV0/INTENT)
# ====================================================================
