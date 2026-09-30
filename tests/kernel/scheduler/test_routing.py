"""
MODULE: tests.kernel.scheduler.test_routing
GOAL: Test routing through the real graph: deterministic selection, Jev choice with thresholds,
    NONE and low-confidence answers, the human clarification path, `unavailable` never being a
    gap, provider failure and the Jev budget.
BUSINESS CONTEXT: Code decides what is allowed and Jev only chooses among allowed candidates; a
    low-confidence answer must never select silently and a capability that exists but cannot run
    must never be reported as a missing capability (Rev 3 sections 6.1 and 13.4).
ARCHITECTURE: Each test builds a Rig with two semantic candidates (or a fixed one), scripts
    ScriptedJev and asserts the executors that ran, the recorded RoutingAssessment, the gap store
    and the final RunOutcome.
"""

from __future__ import annotations

import unittest

from kernel.contracts import GapType, RoutingOutcome, RunStatus
from kernel.providers.base import JevUnavailable
from kernel.providers.fakes import choice_answer
from tests.kernel.scheduler.support import Rig, descriptor, root_item, with_limits

NONE = "__NONE__"
CONTEXT = "__NEEDS_CONTEXT__"


def _semantic_rig(**config_limits) -> Rig:
    """Return a rig with two semantic root candidates and their executors bound."""
    rig = Rig([descriptor("decide.a", routing="semantic", text="Decides caching questions."),
               descriptor("decide.b", routing="semantic", text="Decides queue questions.")])
    rig.bind("decide.a")
    rig.bind("decide.b")
    if config_limits:
        rig.config = with_limits(rig.config, **config_limits)
    return rig


def _assessments(state) -> list:
    return sorted(state["routing"].values(), key=lambda a: a.created_seq)


class TestSelection(unittest.IsolatedAsyncioTestCase):
    """Eligibility first, Jev only where needed."""

    async def test_fixed_candidate_is_selected_without_calling_jev(self) -> None:
        rig = Rig([descriptor("decide.fixed")])
        rig.bind("decide.fixed")
        _, _, state = await rig.start()
        self.assertEqual(rig.jev.call_count, 0)
        assessment = _assessments(state)[0]
        self.assertEqual(assessment.outcome, RoutingOutcome.SELECTED)
        self.assertFalse(assessment.jev_called)
        self.assertEqual(state["outcome"].status, RunStatus.COMPLETED)

    async def test_jev_choice_above_thresholds_selects_that_capability(self) -> None:
        rig = _semantic_rig()
        rig.jev.script("kernel.route", "route.*", choice_answer("decide.b", 0.95, 0.9))
        _, _, state = await rig.start()
        self.assertEqual(len(rig.executors["decide.b"].invocations), 1)
        self.assertEqual(len(rig.executors["decide.a"].invocations), 0)
        assessment = _assessments(state)[0]
        self.assertEqual((assessment.outcome, assessment.selected, assessment.jev_called),
                         (RoutingOutcome.SELECTED, "decide.b", True))
        self.assertEqual(assessment.thresholds["min_selected_probability"], 0.8)
        self.assertEqual(assessment.probabilities["decide.b"], 0.95)
        self.assertEqual(state["budgets"].jev_calls, 1)

    async def test_the_question_offers_only_eligible_candidates_plus_escape_options(self) -> None:
        rig = _semantic_rig()
        rig.jev.script("kernel.route", "route.*", choice_answer("decide.a"))
        await rig.start()
        question = rig.jev.batches[0].questions[0]
        self.assertEqual(sorted(question.criteria), [CONTEXT, NONE, "decide.a", "decide.b"])
        self.assertEqual(question.template_id, "kernel.route")


class TestNoneAndLowConfidence(unittest.IsolatedAsyncioTestCase):
    """NONE is a gap; low confidence and NEEDS_CONTEXT are never a silent selection."""

    async def test_none_records_an_unsupported_gap_and_blocks(self) -> None:
        rig = _semantic_rig()
        rig.jev.script("kernel.route", "route.*", choice_answer(NONE, 0.9, 0.9))
        _, _, state = await rig.start()
        self.assertEqual(_assessments(state)[0].outcome, RoutingOutcome.NO_MATCH)
        self.assertEqual([g.gap_type for g in rig.gap_store.observations], [GapType.UNSUPPORTED])
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertTrue(any("no_capability" in t for t in state["outcome"].limitations))
        self.assertEqual(len(rig.executors["decide.a"].invocations), 0)

    async def test_low_probability_is_insufficient_context_not_a_selection(self) -> None:
        rig = _semantic_rig()
        rig.config = rig.config.model_copy(update={"routing": rig.config.routing.model_copy(
            update={"on_insufficient_context": "block"})})
        rig.jev.script("kernel.route", "route.*", choice_answer("decide.a", 0.55, 0.9))
        _, _, state = await rig.start()
        assessment = _assessments(state)[0]
        self.assertEqual(assessment.outcome, RoutingOutcome.INSUFFICIENT_CONTEXT)
        self.assertIn("low_confidence", assessment.reason_codes)
        self.assertEqual(len(rig.executors["decide.a"].invocations), 0)
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertEqual([g.gap_type for g in rig.gap_store.observations], [GapType.AMBIGUOUS])

    async def test_low_provider_confidence_is_not_a_selection(self) -> None:
        rig = _semantic_rig()
        rig.config = rig.config.model_copy(update={"routing": rig.config.routing.model_copy(
            update={"on_insufficient_context": "block"})})
        rig.jev.script("kernel.route", "route.*", choice_answer("decide.a", 0.99, 0.1))
        _, _, state = await rig.start()
        self.assertEqual(_assessments(state)[0].outcome, RoutingOutcome.INSUFFICIENT_CONTEXT)

    async def test_needs_context_with_human_policy_pauses_on_a_human_question(self) -> None:
        rig = _semantic_rig()
        rig.jev.script("kernel.route", "route.*", choice_answer(CONTEXT, 0.9, 0.9))
        _, _, state = await rig.start()
        self.assertEqual(state["status"], RunStatus.WAITING_HUMAN)
        head = state["interactions"][state["interaction_queue"][0]]
        self.assertIn("Which approach or capability", head.question)
        self.assertEqual(len(rig.executors["decide.a"].invocations), 0)


class TestUnavailableAndProviderFailure(unittest.IsolatedAsyncioTestCase):
    """Existing-but-unusable capabilities and provider failures are never gaps."""

    async def test_unavailable_is_not_a_gap(self) -> None:
        rig = Rig([descriptor("decide.down", availability={"status": "unavailable",
                                                            "reason": "maintenance"})])
        rig.bind("decide.down")
        _, _, state = await rig.start()
        self.assertEqual(_assessments(state)[0].outcome, RoutingOutcome.UNAVAILABLE)
        self.assertEqual(rig.gap_store.observations, [])
        self.assertEqual(rig.jev.call_count, 0)
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertTrue(any("unavailable" in t for t in state["outcome"].limitations))

    async def test_no_candidate_for_the_request_shape_is_a_gap(self) -> None:
        rig = Rig([descriptor("decide.other", kinds=("options",))])
        rig.bind("decide.other")
        _, _, state = await rig.start()
        self.assertEqual(_assessments(state)[0].outcome, RoutingOutcome.NO_MATCH)
        self.assertEqual([g.gap_type for g in rig.gap_store.observations], [GapType.UNSUPPORTED])
        self.assertEqual(rig.jev.call_count, 0)

    async def test_provider_unavailable_fails_without_gap(self) -> None:
        rig = _semantic_rig()
        rig.jev.fail_next(JevUnavailable("down"))
        _, _, state = await rig.start()
        outcome = state["outcome"]
        self.assertEqual(outcome.status, RunStatus.FAILED)
        self.assertEqual(outcome.errors[0].code, "provider_unavailable")
        self.assertEqual(rig.gap_store.observations, [])
        self.assertEqual(_assessments(state)[0].outcome, RoutingOutcome.UNAVAILABLE)

    async def test_choice_outside_the_offered_candidates_is_an_invalid_response(self) -> None:
        rig = _semantic_rig()
        rig.jev.script("kernel.route", "route.*", choice_answer("decide.zzz"))
        _, _, state = await rig.start()
        self.assertEqual(state["outcome"].errors[0].code, "invalid_provider_response")
        self.assertEqual(rig.gap_store.observations, [])

    async def test_exhausted_jev_budget_blocks_without_calling_jev(self) -> None:
        rig = _semantic_rig(max_jev_calls=0)
        _, _, state = await rig.start()
        self.assertEqual(rig.jev.call_count, 0)
        self.assertEqual(state["outcome"].status, RunStatus.BLOCKED)
        self.assertTrue(any("budget_exhausted" in t for t in state["outcome"].limitations))
        self.assertEqual(rig.gap_store.observations, [])
        self.assertEqual(root_item(state).status.value, "blocked")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:40 [python-coder]: Low-confidence tests use policy `block` so the assertion
#   is the outcome itself; the `human` policy has its own test. (#KernelBootstrapV0/P4)
# ====================================================================
