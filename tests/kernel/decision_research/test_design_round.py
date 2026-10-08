"""
MODULE: tests.kernel.decision_research.test_design_round
GOAL: Behavioural tests of R1 and R4: a design decision runs ONE bounded targeted research round
    (what its options claim and cite, the gaps a synthesis named) before it ranks, only when the
    options give something to aim at, within the research-round cap and the Jev budget reserve;
    and the decision record carries `design_reason` (R4).
BUSINESS CONTEXT: Round 7 reached the ranked question in 7 calls but on three evidence items: the
    design-judgement exit fired right after the first assessment, so the round that fetches the
    file the user's own option cites (`kernel/contracts/decision.py`) never ran and the option
    showed "no evidence cited"; the record's `design_reason` was null although the state held it.
ARCHITECTURE: DecisionExecutor driven through DesignCase (the rig of test_design_ending, flat
    scores and a design-judgement criterion); `design_round_due` is also checked on a bare
    Working for the cases the executor cannot reach cheaply (the cap, a named gap).
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from kernel.capabilities.decision.ranking import (
    DESIGN_ROUND,
    design_round_due,
    has_targets,
)
from kernel.capabilities.decision.state import DecisionContinuation, Working
from kernel.config import load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import (
    DecisionStatus,
    EvidenceCategory,
    Priority,
    RequestKind,
)
from kernel.contracts.payloads import ResearchRequestPayload
from kernel.scheduler.nodes_execute import ShareBudget
from tests.kernel.capabilities.support import child, resume
from tests.kernel.capabilities.test_design_ending import DesignCase
from tests.kernel.helpers import narrow

CONTRACT = "kernel/contracts/decision.py"
CITING = [Option(id="A", title="Kernel-contract YAML", description=f"Validated by {CONTRACT}"),
          Option(id="B", title="One JSON registry"), Option(id="C", title="YAML plus an index")]


class RoundCase(DesignCase):
    """Design-judgement criterion c1; optionally a Jev budget share."""

    jev_share: int | None = None

    def setUp(self) -> None:
        super().setUp()
        self.params["design"] = {"c1"}

    def ctx(self, evidence=None):  # noqa: ANN001, ANN201
        built = super().ctx(evidence)
        if self.jev_share is None:
            return built
        return replace(built, budget=ShareBudget({"jev": self.jev_share, "work_item": 20}))

    def requested(self, result) -> list[str]:  # noqa: ANN001
        return list(result.continuation_state["requested"])


class TestOneTargetedRoundBeforeRanking(RoundCase):
    """The cited file is looked up, then the options are ranked."""

    def test_a_cited_file_that_is_not_evidence_is_researched_before_ranking(self) -> None:
        _, _, waiting = self.start(options=CITING)
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)
        self.assertEqual(waiting.decisions[0].status, DecisionStatus.NEEDS_EVIDENCE)
        self.assertTrue(self.requested(waiting)[-1].endswith(f":{DESIGN_ROUND}"))
        request = ResearchRequestPayload.model_validate(waiting.requests[0].payload)
        self.assertEqual([n.category for n in request.evidence_needs],
                         [EvidenceCategory.EXISTING_PATTERNS])
        cited = [ref for o in request.option_context for ref in o.cited_refs]
        self.assertIn(CONTRACT, cited)  # research fetches it as an explicit locator

    def test_after_the_round_the_options_are_ranked_and_the_round_is_not_repeated(self) -> None:
        inv, ctx, waiting = self.start(options=CITING)
        _, ranked = self.research_round(inv, ctx, waiting)
        question = self.question(ranked)
        self.assertEqual({c.id for c in question.choices}, {"A", "B", "C"})
        self.assertEqual(ranked.continuation_state["design_reason"], "design_judgement")
        self.assertEqual(sum(k.endswith(f":{DESIGN_ROUND}") for k in self.requested(ranked)), 1)
        self.assertEqual(self.jev.call_count, 2)  # the first assessment and the one after the round

    def test_without_anything_to_aim_at_the_options_are_ranked_at_once(self) -> None:
        _, _, result = self.start()  # no gaps, no human-added option, no cited file
        self.question(result)
        self.assertEqual(self.jev.call_count, 1)
        self.assertFalse(any(k.endswith(f":{DESIGN_ROUND}") for k in self.requested(result)))

    def test_a_cited_file_that_is_already_evidence_is_not_researched_again(self) -> None:
        cited = [Option(id="A", title="Kernel-contract YAML",
                        description="As in docs/adr/1.md, one record per file"),
                 Option(id="B", title="One JSON registry")]
        _, _, result = self.start(options=cited)  # docs/adr/1.md is the decision's evidence
        self.question(result)

    def test_a_budget_that_cannot_fund_the_round_beside_the_reserve_ranks_instead(self) -> None:
        self.jev_share = 3  # one assessment, then too few calls left for a round and the reserve
        _, _, result = self.start(options=CITING)
        self.question(result)
        self.assertEqual(result.continuation_state["design_reason"], "budget_reserve")
        self.assertFalse(any(k.endswith(f":{DESIGN_ROUND}") for k in self.requested(result)))

    def test_a_budget_with_room_runs_the_round(self) -> None:
        self.jev_share = 40
        _, _, waiting = self.start(options=CITING)
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)
        request = ResearchRequestPayload.model_validate(waiting.requests[0].payload)
        self.assertGreater(request.jev_reserve, 0)  # the round is told what it may not spend

    def test_a_human_added_option_has_its_claims_checked_in_that_round(self) -> None:
        inv, ctx, waiting = self.start()
        answered = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {
            "added_options": [{"title": "Hybrid", "description": f"Both, see {CONTRACT}"}]})
        again = self.run_decision(resume(inv, waiting, [answered]), ctx)
        request = ResearchRequestPayload.model_validate(again.requests[0].payload)
        self.assertEqual([o.human_added for o in request.option_context],
                         [False, False, False, True])


def working(*, gaps: list[str] | None = None, options: list[Option] | None = None,
            requested: list[str] | None = None) -> Working:
    """A bare Working over options and one required design criterion."""
    return Working(
        question="How should decision records be filed?",
        cont=DecisionContinuation(gaps=gaps or [], requested=requested or []),
        options=options if options is not None else [Option(id="A", title="One"),
                                                      Option(id="B", title="Two")],
        criteria=[Criterion(id="c1", question="Are diffs small?", priority=Priority.REQUIRED)],
        approval_required=False, constraint_ids=[])


class TestWhenTheRoundIsDue(unittest.TestCase):
    """design_round_due is true once, with something to aim at, below the research-round cap."""

    CFG = load_kernel_config().decision

    def test_a_gap_a_synthesis_named_is_something_to_aim_at(self) -> None:
        work = working(gaps=["kernel/contracts/decision.py is not among the evidence"])
        self.assertTrue(has_targets(work))
        self.assertTrue(design_round_due(work, self.CFG))

    def test_nothing_to_aim_at_is_not_due(self) -> None:
        self.assertFalse(design_round_due(working(), self.CFG))

    def test_a_round_already_asked_is_not_due_again(self) -> None:
        work = working(gaps=["a gap"], requested=[f"research:existing_patterns:abc:{DESIGN_ROUND}"])
        self.assertFalse(design_round_due(work, self.CFG))

    def test_the_research_round_cap_leaves_no_room(self) -> None:
        capped = self.CFG.model_copy(update={"max_research_rounds": 1})
        work = working(gaps=["a gap"], requested=["research:task_context:abc"])
        self.assertTrue(design_round_due(work, self.CFG))
        self.assertFalse(design_round_due(work, capped))


class TestTheRecordCarriesTheDesignReason(RoundCase):
    """R4: Decision.design_reason is set when the options were ranked for a human."""

    def test_the_waiting_record_of_a_ranked_question_names_the_reason(self) -> None:
        _, _, result = self.start()
        self.assertEqual(result.decisions[0].design_reason, "design_judgement")

    def test_a_budget_ranking_records_its_reason(self) -> None:
        self.jev_share = 3
        _, _, result = self.start(options=CITING)
        self.assertEqual(result.decisions[0].design_reason, "budget_reserve")

    def test_a_decision_that_is_not_a_design_one_has_no_reason(self) -> None:
        self.params["design"] = set()
        _, _, result = self.start()  # evidence-answerable: research is asked
        self.assertEqual(result.requests[0].kind, RequestKind.EVIDENCE)
        self.assertIsNone(result.decisions[0].design_reason)

    def test_the_round_waiting_record_has_no_reason_yet(self) -> None:
        _, _, waiting = self.start(options=CITING)
        self.assertIsNone(waiting.decisions[0].design_reason)

    def test_the_resolved_record_keeps_the_reason_after_the_human_chose(self) -> None:
        inv, ctx, waiting = self.start()
        out = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "B"})
        done = self.run_decision(
            resume(inv, waiting, [out.model_copy(update={"actor_id": "human:ada"})]), ctx)
        decision = narrow(done.decisions[0])
        self.assertEqual((decision.status, decision.design_reason),
                         (DecisionStatus.RESOLVED, "design_judgement"))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round F tests for R1 (one targeted research round on the options'
#   claims and cited files before a design decision ranks; only with something to aim at; once;
#   within the cap and the budget reserve) and R4 (Decision.design_reason). (#KernelV01/F)
# ====================================================================
