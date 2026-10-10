"""
MODULE: tests.kernel.grounding.test_round6_budget
GOAL: Behavioural tests of round E decisions through DecisionExecutor and the Jev call guard: the
    reserved final assessment (research that would eat into it becomes the ranked human question),
    the fallback to the last complete assessment, atomic refusal of an assessment the budget cannot
    fund, usage kept when an assessment aborts, and the criterion-kind question and backstop.
BUSINESS CONTEXT: Round 6 (run-a522094b886048f3) ended `blocked: jev call budget exhausted` three
    quarters through its second assessment and lost the usage of the completed half; Jev called
    six criteria about proposed designs `evidence_answerable` with P between 0.12 and 0.54, so the
    design-judgement ending never fired (V0.1 round E, E1, E3 and E6).
ARCHITECTURE: DesignCase rig (ScriptedJev, DecisionExecutor, simulated resumption) with a
    ShareBudget attached to the context so the decision sees a real Jev budget; the adapter tests
    use the real TypeSafeJevAdapter over a tiny transport. Everything is offline.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from kernel.capabilities.base import ExecutionContext, UnlimitedBudget
from kernel.capabilities.call_costs import (
    FIXED_ASSESSMENT_QUESTIONS,
    assessment_questions,
    assessment_reserve,
    jev_available,
    provider_calls,
    research_round_calls,
)
from kernel.capabilities.decision.assess import KIND_TEMPLATE_VERSION, kind_question
from kernel.capabilities.decision.jev_support import StopCapability, ask_jev, make_batch, noul_question
from kernel.config import load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.decision import Criterion, CriterionKind, Option
from kernel.contracts.enums import (
    ApprovalStatus,
    DecisionStatus,
    ProposalStatus,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.payloads import DecisionReportPayload, DecisionRequestPayload
from kernel.providers.base import JevUnavailable
from kernel.providers.fakes import ScriptedJev, noul_answer
from kernel.providers.jev import TypeSafeJevAdapter
from kernel.providers.jev_budget import bind_call_budget
from kernel.providers.jev_wire import RawResponse
from kernel.scheduler.guards import account_usage
from kernel.scheduler.nodes_execute import ShareBudget
from kernel.scheduler.state import Budgets
from tests.kernel.capabilities.support import child, invocation, resume, script_decision
from tests.kernel.capabilities.test_design_ending import FLAT, DesignCase
from tests.kernel.grounding.test_round6_end_to_end import CRITERIA as ROUND6_CRITERIA
from tests.kernel.helpers import as_type, make_context, narrow

CFG = load_kernel_config()
LIMITED = "limited evidence"


class TestCostModel(unittest.TestCase):
    """The reserve is computed from the question count and the chunk size, never hard-coded."""

    def test_the_round_6_assessment_is_two_calls_and_the_reserve_adds_the_margin(self) -> None:
        # 6 criteria x (1 + 4 options + 1 spare option) + 3 fixed = 39 questions, 20 per call
        self.assertEqual(provider_calls(39, CFG), 2)
        self.assertEqual(assessment_reserve(6, 4, 0, CFG),
                         2 * CFG.decision.reserve_assessments + CFG.decision.reserve_margin_calls)

    def test_a_smaller_chunk_raises_the_reserve(self) -> None:
        jev = CFG.jev.model_copy(update={"max_questions_per_call": 10})
        small = CFG.model_copy(update={"jev": jev})
        self.assertEqual(provider_calls(39, small), 4)
        self.assertGreater(assessment_reserve(6, 4, 0, small), assessment_reserve(6, 4, 0, CFG))

    def test_a_round_costs_one_rerank_call_per_need_and_one_judgement(self) -> None:
        self.assertEqual(research_round_calls(3, CFG), 3 + 1)
        wide = CFG.model_copy(update={"retrieval": CFG.retrieval.model_copy(
            update={"rerank_max_per_need": 60})})
        self.assertEqual(research_round_calls(3, wide), 3 * 3 + 1)  # the old 60-candidate batch

    def test_an_unbounded_or_silent_budget_reports_nothing(self) -> None:
        self.assertIsNone(jev_available(UnlimitedBudget()))
        self.assertIsNone(jev_available(object()))
        self.assertEqual(jev_available(ShareBudget({"jev": 3})), 3)


class BudgetCase(DesignCase):
    """DesignCase whose contexts carry a Jev share of `jev_left` calls (None: unbounded)."""

    jev_left: int | None = None

    def ctx(self, evidence=None):  # noqa: ANN001, ANN201
        base = super().ctx(evidence)
        if self.jev_left is None:
            return base
        return replace(base, budget=ShareBudget({"jev": self.jev_left}))


class TestTheReservedAssessment(BudgetCase):
    """Research that would eat into the reserved final assessment becomes the ranked question."""

    jev_left = 5  # the first assessment (1 call) leaves 4; a round (2) plus the reserve (3) needs 5

    def test_a_round_that_does_not_fit_beside_the_reserve_ends_in_the_ranked_question(self) -> None:
        # covers: DK-600a-4-i
        _, _, result = self.start()
        question = self.question(result)
        self.assertEqual([c.id for c in question.choices], ["B", "C", "A"])
        self.assertIn("Jev call budget", question.question)
        self.assertEqual(result.continuation_state["design_reason"], "budget_reserve")
        self.assertTrue(any(LIMITED in x for x in result.limitations), result.limitations)
        self.assertEqual(self.jev.call_count, 1)  # it never started the research it could not fund

    def test_with_one_more_call_the_round_is_requested_as_before(self) -> None:
        # covers: DK-600a-4-i
        self.jev_left = 6
        _, _, result = self.start()
        self.assertEqual(result.requests[0].kind, RequestKind.EVIDENCE)

    def test_the_research_request_carries_the_reserve_and_plans_exactly_its_needs(self) -> None:
        self.jev_left = 40
        _, _, result = self.start()
        payload = result.requests[0].payload
        self.assertTrue(payload["evidence_needs_only"])
        self.assertEqual(payload["jev_reserve"], assessment_reserve(2, 3, 0, CFG))

    def test_the_humans_choice_resolves_and_the_final_report_says_the_evidence_was_limited(
            self) -> None:
        # covers: DK-600a-4-i
        inv, ctx, waiting = self.start()
        answer = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "C"})
        done = self.run_decision(resume(inv, waiting, [answer.model_copy(
            update={"actor_id": "human:ada"})]), ctx)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        report = DecisionReportPayload.model_validate(done.output_payload)
        self.assertEqual((report.status, report.selected_option_id),
                         (DecisionStatus.RESOLVED, "C"))
        self.assertTrue(any(LIMITED in x for x in report.limitations), report.limitations)
        self.assertEqual(self.jev.call_count, 1)


class TestFallbackToTheLastCompleteAssessment(BudgetCase):
    """An assessment the budget cannot fund is never half scored: rank the last complete one."""

    def research_then(self, left: int, payload: dict | None = None):  # noqa: ANN201
        inv, ctx, waiting = self.start()
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)
        ctx = self.ctx(self.evidence)
        bundle = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, {"evidence_ids": []})
        self.jev_left = left
        again = resume(inv, waiting, [bundle])
        if payload is not None:
            again = invocation("decision", schema_ids.DECISION_REQUEST, payload,
                               work_item_id=inv.work_item_id,
                               continuation=waiting.continuation_state, outcomes=[bundle])
        return self.run_decision(again, self.ctx(self.evidence))

    def test_no_budget_for_a_new_assessment_ranks_the_last_complete_one(self) -> None:
        # covers: DK-600a-4-i
        result = self.research_then(0)
        question = self.question(result)
        self.assertEqual([c.id for c in question.choices], ["B", "C", "A"])
        self.assertEqual(self.jev.call_count, 1)  # nothing new was asked
        self.assertTrue(any(LIMITED in x for x in result.limitations), result.limitations)
        self.assertEqual(result.continuation_state["design_reason"], "budget_reserve")

    def test_a_changed_option_set_is_never_ranked_on_partial_scores(self) -> None:
        from tests.kernel.capabilities.test_design_ending import _payload
        extra = _payload()
        extra["options"] = [*extra["options"], Option(id="D", title="Another").model_dump(
            mode="json")]
        result = self.research_then(0, extra)
        self.assertEqual(result.status, ResultStatus.BLOCKED)
        self.assertEqual(narrow(result.error).code, "budget_exhausted")
        self.assertEqual(self.jev.call_count, 1)

    def test_with_nothing_assessed_and_no_budget_the_run_blocks_plainly(self) -> None:
        self.jev_left = 0
        _, _, result = self.start()
        self.assertEqual(result.status, ResultStatus.BLOCKED)
        self.assertEqual(narrow(result.error).code, "budget_exhausted")
        self.assertEqual(self.jev.call_count, 0)


class TestAnAssessmentIsRefusedWhole(BudgetCase):
    """A two-chunk assessment the budget cannot fund is refused before its first call."""

    jev_left = 1

    def test_the_decision_does_not_start_half_an_assessment(self) -> None:
        criteria = [Criterion(id=f"c{n}", question=f"Is it simple {n}?") for n in range(5)]
        payload = DecisionRequestPayload(
            question="How?", options=[Option(id=o, title=o) for o in "ABCD"],
            criteria=criteria).model_dump(mode="json")
        _, _, result = self.first(payload=payload)  # 5 x 5 + 5 kinds + 3 = 33 questions
        self.assertEqual(result.status, ResultStatus.BLOCKED)
        self.assertIn("needs 2 provider call(s), 1 left", narrow(result.error).message)
        self.assertEqual(self.jev.call_count, 0)


class FakeTransport:
    """A transport answering every noul with 0.5; call number `fail_on` raises JevUnavailable."""

    name, version = "fake", "0"

    def __init__(self, fail_on: int | None = None) -> None:
        self.requests, self.fail_on = 0, fail_on

    async def send(self, state: dict[str, Any], questions: dict[str, dict[str, Any]],
                   *, purpose: str = "") -> RawResponse:
        self.requests += 1
        if self.requests == self.fail_on:
            raise JevUnavailable
        return RawResponse(model="jev-fake", input_tokens=10, output_tokens=1, answers={
            q: {"type": "noul", "noul": 0.5} for q in questions})

    async def aclose(self) -> None:
        """Nothing to close."""


class TestUsageSurvivesAnAbort(unittest.TestCase):
    """Calls completed before an abort are recorded, so usage, cost and budget agree."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)

    def stop(self, transport: FakeTransport, bound_share: int) -> StopCapability:
        adapter = TypeSafeJevAdapter(
            transport, timeout_seconds=5.0, max_questions_per_call=20, max_state_chars=60000,
            max_retries=0, retry_backoff_seconds=0.0, model_name="jev-fake")
        ctx: ExecutionContext = make_context(self.root, jev=ScriptedJev())
        ctx = replace(ctx, jev=adapter)  # the guard's own check is off: the adapter's decides
        batch = make_batch(ctx, "decision.assess", {"x": "y"}, [
            noul_question(f"q{n}", "t", "Is it?") for n in range(25)])  # two provider calls
        inv = invocation("decision", schema_ids.DECISION_REQUEST, {})

        async def run() -> None:
            with bind_call_budget(ShareBudget({"jev": bound_share})):
                await ask_jev(ctx, inv, batch)

        with self.assertRaises(StopCapability) as caught:
            asyncio.run(run())
        return caught.exception

    def test_a_budget_refusal_after_the_first_chunk_keeps_that_chunks_usage(self) -> None:
        transport = FakeTransport()
        result = self.stop(transport, 0).result
        self.assertEqual(result.status, ResultStatus.BLOCKED)
        error = narrow(result.error)
        self.assertEqual((error.code, error.retryable), ("budget_exhausted", False))
        self.assertEqual(transport.requests, 1)
        self.assertEqual(sum(u.calls for u in result.usage), 1)  # round 6 lost this call

    def test_a_provider_failure_after_the_first_chunk_keeps_that_chunks_usage(self) -> None:
        transport = FakeTransport(fail_on=2)
        result = self.stop(transport, 5).result
        self.assertEqual(narrow(result.error).code, "provider_unavailable")
        self.assertEqual(sum(u.calls for u in result.usage), 1)
        self.assertEqual(transport.requests, 2)

    def test_the_kept_usage_reaches_the_rows_and_the_cost(self) -> None:
        result = self.stop(FakeTransport(), 0).result
        folded = account_usage(Budgets(), result.usage, CFG.jev.price_per_input_token_usd)
        (row,) = folded.usage_rows
        self.assertEqual((row.provider, row.calls, row.input_tokens), ("jev", 1, 10))
        self.assertGreater(folded.cost_usd_known, 0)


class KindCase(DesignCase):
    """Round 6 criteria on proposed options; Jev's kind probability is set per criterion."""

    def setUp(self) -> None:
        super().setUp()
        self.kind_p: dict[str, float] = {}
        self.jev = ScriptedJev()
        self.jev.script("decision.assess", "kind.*", lambda q, b: noul_answer(
            self.kind_p.get(q.id.removeprefix("kind."), 0.05)))
        self.params = script_decision(self.jev)
        self.params.update(sufficient=0.6, satisfies=dict(FLAT) | {
            (c, o): 0.5 for c, _ in ROUND6_CRITERIA for o in "ABC"})
        self.proposed = True

    def payload(self, texts: dict[str, str] | None = None) -> dict[str, Any]:
        """Return the decision request: three options (proposals unless told otherwise)."""
        shown = texts or dict(ROUND6_CRITERIA)
        approved: dict[str, Any] = {"proposal_status": ProposalStatus.PROPOSED,
                                    "approval_status": ApprovalStatus.APPROVED,
                                    "approved_by": "human:ada",
                                    "proposed_by": "host:fake"} if self.proposed else {}
        options = [Option(id=i, title=f"Option {i}", **approved) for i in "ABC"]
        criteria = [Criterion(id=i, question=q) for i, q in shown.items()]
        return DecisionRequestPayload(question="How should records be filed?", options=options,
                                      criteria=criteria).model_dump(mode="json")

    def kinds(self, texts: dict[str, str] | None = None) -> dict[str, tuple[str, str | None]]:
        """Run one assessment and return each criterion's (kind, kind_source)."""
        _, _, result = self.first(payload=self.payload(texts))
        state = result.continuation_state
        return {c["id"]: (c["kind"], c["kind_source"]) for c in state["criteria"]}


DESIGN = CriterionKind.DESIGN_JUDGEMENT.value
FACT = CriterionKind.EVIDENCE_ANSWERABLE.value


class TestTheKindQuestion(unittest.TestCase):
    """The question is literal, atomic and states both readings with a boundary example each."""

    def test_the_question_is_a_true_or_false_judgement_with_both_readings_named(self) -> None:
        spec = kind_question("crit.reviewable_diffs")
        text = str(spec.instructions)
        self.assertEqual((spec.id, spec.kind, spec.template_version),
                         ("kind.crit.reviewable_diffs", "noul", KIND_TEMPLATE_VERSION))
        self.assertIn("`criteria.crit.reviewable_diffs`", text)
        self.assertIn("property that each proposed option", text)
        self.assertIn("not about a fact that `evidence` or the repository already states today",
                      text)
        self.assertIn("True or false?", text)
        criteria = as_type(spec.criteria, dict)
        self.assertEqual(set(criteria), {"true", "false"})
        self.assertIn("reviewable", criteria["true"])
        self.assertIn("already uses", criteria["false"])
        self.assertIn("recorded decision", criteria["false"])


class TestTheKindBackstop(KindCase):
    """With proposed options, a criterion worded as a question about them is a design judgement."""

    def test_the_six_round_6_criteria_classify_as_design_judgements_at_the_live_probabilities(
            self) -> None:
        self.kind_p = dict(zip((c for c, _ in ROUND6_CRITERIA),
                               (0.54, 0.31, 0.40, 0.33, 0.45, 0.35), strict=True))
        self.assertEqual(set(self.kinds().values()), {(DESIGN, "rule")})

    def test_a_confident_evidence_answerable_reading_is_respected(self) -> None:
        texts = dict(ROUND6_CRITERIA) | {"c.fact": "Does the repository already contain a YAML "
                                                    "parser?"}
        self.kind_p = {"c.fact": 0.12, "crit.reviewable_diffs": 0.12}
        kinds = self.kinds(texts)
        self.assertEqual(kinds["c.fact"], (FACT, "jev"))  # P 0.12 is below 1 - 0.7
        self.assertEqual(kinds["crit.reviewable_diffs"], (FACT, "jev"))

    def test_jevs_own_design_reading_is_not_overridden(self) -> None:
        self.kind_p = {"crit.reviewable_diffs": 0.9}
        self.assertEqual(self.kinds()["crit.reviewable_diffs"], (DESIGN, "jev"))

    def test_the_rule_only_applies_to_proposed_options(self) -> None:
        self.proposed = False  # options a caller supplied may be existing artifacts
        self.kind_p = {c: 0.45 for c, _ in ROUND6_CRITERIA}
        self.assertEqual({v[0] for v in self.kinds().values()}, {FACT})

    def test_a_criterion_not_worded_as_a_question_is_left_to_jev(self) -> None:
        self.kind_p = {"c.noun": 0.45}
        self.assertEqual(self.kinds({"c.noun": "Reviewable diffs in one file"})["c.noun"],
                         (FACT, "jev"))

    def test_a_design_decision_whose_option_clearly_passes_is_resolved_not_ranked(self) -> None:
        """The live ADR-settled goal: scores 0.98 and 0.96 must resolve, whatever the kind."""
        self.kind_p = {c: 0.9 for c, _ in ROUND6_CRITERIA}
        self.params["satisfies"] = {(c, "A"): 0.97 for c, _ in ROUND6_CRITERIA}
        self.params["sufficient"] = 0.9
        _, _, result = self.first(payload=self.payload())
        self.assertEqual(result.status, ResultStatus.COMPLETED)
        report = DecisionReportPayload.model_validate(result.output_payload)
        self.assertEqual(report.selected_option_id, "A")

    def test_flat_scores_on_design_criteria_still_end_in_the_ranking(self) -> None:
        self.kind_p = {c: 0.9 for c, _ in ROUND6_CRITERIA}
        self.params["satisfies"] = {(c, "A"): 0.79 for c, _ in ROUND6_CRITERIA}  # just short
        _, _, result = self.first(payload=self.payload())
        self.assertEqual(result.continuation_state["design_reason"], "design_judgement")

    def test_nothing_is_classified_before_the_decision_has_evidence(self) -> None:
        """A decision an ADR settles was ranked for a human live: classify only against evidence."""
        self.kind_p = {c: 0.9 for c, _ in ROUND6_CRITERIA}
        inv = invocation("decision", schema_ids.DECISION_REQUEST, self.payload())
        waiting = self.run_decision(inv, self.ctx(evidence=[]))
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)  # research comes first
        sources = {c["kind_source"] for c in waiting.continuation_state["criteria"]}
        self.assertEqual(sources, {None})  # still unclassified: asked again with evidence in state
        kind_questions = [q.id for q in self.jev.batches[0].questions if q.id.startswith("kind.")]
        self.assertEqual(len(kind_questions), len(ROUND6_CRITERIA))

    def test_the_escape_bar_follows_the_configured_threshold(self) -> None:
        self.decision_config = {"design_judgement_threshold": 0.9}  # escape below 0.1
        self.kind_p = {"crit.reviewable_diffs": 0.12}
        self.assertEqual(self.kinds()["crit.reviewable_diffs"], (DESIGN, "rule"))


class TestTheCostModelMatchesTheRealBatch(KindCase):
    """The reserve is only as good as its question count: it must be the batch the code sends."""

    def test_the_assessment_question_count_is_what_the_batch_carries(self) -> None:
        # covers: DK-600a-4
        self.kinds()  # one assessment: 6 criteria, 3 options, 6 criteria still unclassified
        (batch,) = [b for b in self.jev.batches if b.purpose == "decision.assess"]
        self.assertEqual(len(batch.questions), assessment_questions(6, 3, 6))
        self.assertEqual(len(batch.questions), 6 * (1 + 3) + 6 + FIXED_ASSESSMENT_QUESTIONS)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round E decision tests: the reserved assessment and its ranked
#   hand-over, the all-or-nothing fallback, atomic refusal, usage kept on abort, and the literal
#   kind question with its deterministic backstop. (#KernelV01/E)
# ====================================================================
