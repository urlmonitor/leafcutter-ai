"""
MODULE: tests.kernel.decision_research.test_batch_allowance
GOAL: Tests of the budget side of deeper reranking (N3): the Jev calls left beyond the research
    plan and the requester's reserve become extra rerank batches per need, every retrieval child
    carries that allowance, and a decision-driven round can never spend into the decision's final
    assessment.
BUSINESS CONTEXT: A retrieval child only sees its own even share of the run's remaining Jev calls,
    not the reserve the decision keeps for its final assessment; letting a need judge up to three
    batches would therefore have eaten the reserve that round E introduced to guarantee the ranked
    question.
ARCHITECTURE: call_costs.batch_allowance is an arithmetic table; the research planner is run with
    a ShareBudget and the children it emits are read back (`max_rerank_batches`).
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from kernel.capabilities.call_costs import (
    batch_allowance,
    judgement_calls,
    rerank_calls,
    work_items_available,
)
from kernel.config import load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, Priority
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import ResearchRequestPayload, RetrievalRequestPayload
from kernel.scheduler.nodes_execute import ShareBudget
from tests.kernel.capabilities.support import invocation
from tests.kernel.capabilities.test_research_graph import ResearchCase

CFG = load_kernel_config()


def need(category: EvidenceCategory) -> EvidenceNeed:
    """A required need of a category."""
    return EvidenceNeed(id=f"need.{category.value}", category=category, priority=Priority.REQUIRED,
                        question=f"About {category.value}")


class TestTheAllowanceArithmetic(unittest.TestCase):
    """spare calls (left - reserve - the plan) buy extra batches, shared evenly between the needs."""

    def test_an_unlimited_budget_has_no_allowance_to_state(self) -> None:
        self.assertIsNone(batch_allowance(None, 8, 2, CFG))

    def test_no_needs_have_no_allowance(self) -> None:
        self.assertIsNone(batch_allowance(30, 8, 0, CFG))

    def test_exactly_the_plan_and_the_reserve_leaves_the_first_batch_only(self) -> None:
        plan = 2 * rerank_calls(CFG) + judgement_calls(2, CFG)
        self.assertEqual(batch_allowance(8 + plan, 8, 2, CFG), 1)

    def test_a_budget_below_the_plan_still_allows_the_first_batch(self) -> None:
        self.assertEqual(batch_allowance(1, 8, 2, CFG), 1)

    def test_spare_calls_buy_extra_batches_shared_between_the_needs(self) -> None:
        plan = 2 * rerank_calls(CFG) + judgement_calls(2, CFG)
        spare = 4  # two extra batches per need, two needs
        self.assertEqual(batch_allowance(8 + plan + spare, 8, 2, CFG), 3)
        self.assertEqual(batch_allowance(8 + plan + spare + 1, 8, 2, CFG), 3)  # a odd call is lost

    def test_the_work_item_share_is_read_like_the_jev_share(self) -> None:
        self.assertEqual(work_items_available(ShareBudget({"jev": 5, "work_item": 7})), 7)
        self.assertIsNone(work_items_available(object()))


class TestChildrenCarryTheAllowance(ResearchCase):
    """Research hands every retrieval child the batches the budget affords."""

    def children(self, left: int | None, reserve: int) -> list[RetrievalRequestPayload]:
        needs = [need(EvidenceCategory.PRIOR_DECISIONS), need(EvidenceCategory.INTERNAL_PRINCIPLES)]
        payload = ResearchRequestPayload(
            question="Where should run state be stored?", evidence_needs=needs,
            evidence_needs_only=True, jev_reserve=reserve).model_dump(mode="json")
        inv = invocation("research", schema_ids.RESEARCH_REQUEST, payload)
        ctx = self.ctx()
        if left is not None:
            ctx = replace(ctx, budget=ShareBudget({"jev": left, "work_item": 50}))
        result = self.run_research(inv, ctx)
        return [RetrievalRequestPayload.model_validate(r.payload) for r in result.requests]

    def test_a_tight_budget_limits_each_child_to_the_first_batch(self) -> None:
        plan = 2 * rerank_calls(CFG) + judgement_calls(2, CFG)
        kids = self.children(8 + plan, 8)
        self.assertEqual([k.max_rerank_batches for k in kids], [1, 1])

    def test_a_generous_budget_allows_more_batches(self) -> None:
        kids = self.children(60, 8)
        self.assertTrue(all((k.max_rerank_batches or 0) > CFG.retrieval.rerank_max_batches
                            for k in kids))  # the config limit is what binds

    def test_the_reserve_is_what_keeps_a_decision_round_shallow(self) -> None:
        without = self.children(30, 0)[0].max_rerank_batches or 0
        with_reserve = self.children(30, 20)[0].max_rerank_batches or 0
        self.assertGreater(without, with_reserve)

    def test_a_budget_that_cannot_say_leaves_the_children_unlimited(self) -> None:
        self.assertEqual([k.max_rerank_batches for k in self.children(None, 0)], [None, None])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round F tests for the rerank allowance: calls beyond the research
#   plan and the requester's reserve become extra batches per need, carried by every retrieval
#   child, so deeper reranking cannot spend the decision's final assessment. (#KernelV01/F)
# ====================================================================
