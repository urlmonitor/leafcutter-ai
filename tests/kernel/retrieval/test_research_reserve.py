"""
MODULE: tests.kernel.retrieval.test_research_reserve
GOAL: Prove that research never spends the Jev calls its requester keeps for itself: the plan is
    trimmed to the needs the remaining budget affords beside the reserve (targeted extras go first,
    each named in a limitation), and the round's judgement is skipped, with a limitation, when it
    would eat into the reserve.
BUSINESS CONTEXT: Round 6 fanned out into 8 needs after approval and left nothing for the second
    decision assessment; the decision reserves that assessment (jev_reserve) and research must
    respect it even if the decision's own estimate was off (V0.1 round E, E1).
ARCHITECTURE: ResearchExecutor with mandated needs (no planning call) and a ShareBudget on the
    context, like the production worker's share; the requests it emits are read back as
    retrieval children.
"""

from __future__ import annotations

from dataclasses import replace

from kernel.capabilities.call_costs import judgement_calls, rerank_calls
from kernel.config import load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, NeedStatus, RequestKind, ResultStatus
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import OptionContext, ResearchRequestPayload
from kernel.scheduler.nodes_execute import ShareBudget
from tests.kernel.capabilities.support import child, evidence_item, invocation, resume
from tests.kernel.capabilities.test_research_graph import QUESTION, ResearchCase, _bundle

CFG = load_kernel_config()
PER_NEED = rerank_calls(CFG)
CATS = EvidenceCategory
NEEDS = [EvidenceNeed(id=f"need.{c.value}", category=c, question=f"{c.value}: {QUESTION}")
         for c in (CATS.PRIOR_DECISIONS, CATS.EXISTING_PATTERNS, CATS.INTERNAL_PRINCIPLES)]
ADDED = OptionContext(option_id="opt.added.1", title="Added option", human_added=True)


class ReserveCase(ResearchCase):
    """Research on mandated needs with a Jev share of `left` calls and `reserve` kept back."""

    def setUp(self) -> None:
        super().setUp()
        self.base = self.ctx()  # one artifact store, so children written here are read back

    def ctx_with(self, left: int):  # noqa: ANN201
        return replace(self.base, budget=ShareBudget({"jev": left}))

    def request(self, reserve: int, **fields):  # noqa: ANN003, ANN201
        payload = ResearchRequestPayload(question=QUESTION, evidence_needs=NEEDS,
                                         evidence_needs_only=True, jev_reserve=reserve, **fields)
        return invocation("research", schema_ids.RESEARCH_REQUEST, payload.model_dump(mode="json"))


class TestThePlanIsTrimmed(ReserveCase):
    """Each need is one retrieval child; the round ends with one judgement."""

    def children(self, left: int, reserve: int, **fields):  # noqa: ANN003, ANN201
        waiting = self.run_research(self.request(reserve, **fields), self.ctx_with(left))
        return waiting, [r.payload["need"]["id"] for r in waiting.requests]

    def test_with_room_for_everything_all_needs_run(self) -> None:
        room = 3 * PER_NEED + judgement_calls(3, CFG)
        waiting, ids = self.children(left=room + 4, reserve=4)
        self.assertEqual(len(ids), 3)
        self.assertEqual(waiting.status, ResultStatus.WAITING)

    def test_one_call_short_drops_the_last_need_and_says_so(self) -> None:
        room = 3 * PER_NEED + judgement_calls(3, CFG)
        waiting, ids = self.children(left=room + 4 - 1, reserve=4)
        self.assertEqual(ids, ["need.prior_decisions", "need.existing_patterns"])
        state = waiting.continuation_state
        text = " ".join(state["limitations"])
        self.assertIn("need need.internal_principles not researched", text)
        self.assertIn("4 kept in reserve", text)

    def test_the_targeted_extras_are_the_first_to_go(self) -> None:
        gaps = ["kernel/contracts/decision.py is not among the evidence"]
        room = 5 * PER_NEED + judgement_calls(5, CFG)  # three planned needs, one claim, one gap
        _, ids = self.children(left=room + 2, reserve=2, gaps=gaps, option_context=[ADDED])
        self.assertEqual(len(ids), 5)
        _, trimmed = self.children(left=room + 1, reserve=2, gaps=gaps, option_context=[ADDED])
        self.assertNotIn("need.gap.1", trimmed)
        self.assertIn("need.prior_decisions", trimmed)

    def test_with_nothing_to_spare_no_child_is_requested(self) -> None:
        waiting = self.run_research(self.request(10), self.ctx_with(10))
        self.assertEqual(waiting.requests, [])
        self.assertEqual(waiting.status, ResultStatus.COMPLETED)  # nothing to wait for ...
        self.assertIn("need need.prior_decisions not researched", " ".join(waiting.limitations))

    def test_an_unbounded_budget_changes_nothing(self) -> None:
        waiting = self.run_research(self.request(99), self.base)
        self.assertEqual(len(waiting.requests), 3)


class TestTheJudgementLeavesTheReserve(ReserveCase):
    """The round's judgement is skipped, not run into the reserve."""

    def finish(self, left_at_judgement: int, reserve: int):  # noqa: ANN201
        inv = self.request(reserve)
        ctx = self.ctx_with(100)
        waiting = self.run_research(inv, ctx)
        item = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        kids = [child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                      _bundle([item], {n.id: NeedStatus.SATISFIED for n in NEEDS}))]
        return self.run_research(resume(inv, waiting, kids), self.ctx_with(left_at_judgement))

    def test_a_judgement_that_would_eat_the_reserve_is_skipped_with_a_limitation(self) -> None:
        done = self.finish(left_at_judgement=reserve_plus(3, 0), reserve=reserve_plus(3, 0))
        self.assertEqual(self.jev.call_count, 0)  # nothing was asked
        self.assertIn("evidence not judged", " ".join(self.bundle(done).limitations))

    def test_with_room_beside_the_reserve_it_runs(self) -> None:
        done = self.finish(left_at_judgement=reserve_plus(3, 5), reserve=5)
        self.assertEqual(self.jev.call_count, 1)
        self.assertNotIn("evidence not judged", " ".join(self.bundle(done).limitations))


def reserve_plus(needs: int, reserve: int) -> int:
    """Return the share that leaves exactly `reserve` after one judgement of `needs` needs."""
    return judgement_calls(needs, CFG) + reserve


if __name__ == "__main__":
    import unittest
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round E (E1): research trims its plan and skips its judgement
#   rather than spend into the requester's reserve. (#KernelV01/E)
# ====================================================================
