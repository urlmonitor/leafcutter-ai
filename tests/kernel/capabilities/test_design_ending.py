"""
MODULE: tests.kernel.capabilities.test_design_ending
GOAL: Behavioural tests of the design-decision ending through DecisionExecutor: design-judgement
    criteria end in a ranked human question instead of a research loop, a flat pair of
    assessments and the research-round cap do the same, the human's choice resolves the decision
    with the human as approver, and option_context reaches the research request.
BUSINESS CONTEXT: Live run run-5d246775f5e54f11 looped assess, research, synthesis, research for
    18 Jev calls on criteria that are properties of the proposed designs. Retrieval cannot settle
    those; ADR-053 gives the preference to a human, with the kernel ranking as evidence.
ARCHITECTURE: ScriptedJev answers the batch (the `kind.*` question included) from the mutable
    params of script_decision; the kernel's resume step is simulated by the capability support
    helpers. Everything is offline.
"""

from __future__ import annotations

from kernel.config import load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.decision import Criterion, CriterionKind, Option
from kernel.contracts.enums import (
    ApprovalStatus,
    DecisionStatus,
    EvidenceCategory,
    Priority,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.payloads import (
    DecisionReportPayload,
    DecisionRequestPayload,
    HumanQuestionRequestPayload,
    ResearchRequestPayload,
)
from tests.kernel.capabilities.support import child, evidence_item, invocation, resume
from tests.kernel.capabilities.test_decision_graph import DECISION, DecisionTestCase
from tests.kernel.helpers import make_context, narrow

FLAT = {("c1", "A"): 0.55, ("c1", "B"): 0.67, ("c1", "C"): 0.60,
        ("c2", "A"): 0.90, ("c2", "B"): 0.10, ("c2", "C"): 0.50}
EXTRA = evidence_item("docs/more.md#L1-L2", "Another fact.", EvidenceCategory.INTERNAL_PRINCIPLES)


def _payload(options: list[Option] | None = None) -> dict:
    """A decision request: required c1 (a design property), supporting c2, options A, B, C."""
    opts = options if options is not None else [
        Option(id="A", title="One YAML file per decision"),
        Option(id="B", title="One JSON file per component"),
        Option(id="C", title="YAML files plus a generated index")]
    crit = [Criterion(id="c1", question="Are the diffs small and reviewable?"),
            Criterion(id="c2", question="Does it reuse existing conventions?",
                      priority=Priority.SUPPORTING)]
    return DecisionRequestPayload(question="How should decision records be filed?", options=opts,
                                  criteria=crit).model_dump(mode="json")


class DesignCase(DecisionTestCase):
    """Base: the live-loop scores (flat, below every threshold) and a configurable context."""

    decision_config: dict = {}

    def setUp(self) -> None:
        super().setUp()
        self.params.update(sufficient=0.6, satisfies=dict(FLAT), missing="missing_internal_principle")

    def ctx(self, evidence=None):  # noqa: ANN001, ANN201 - mirrors DecisionTestCase.ctx
        base = load_kernel_config()
        config = base.model_copy(update={"decision": base.decision.model_copy(
            update=self.decision_config)})
        return make_context(self.root, jev=self.jev, config=config,
                            evidence=self.evidence if evidence is None else evidence)

    def start(self, **kwargs):
        """Run the first invocation with the design payload."""
        return self.first(payload=_payload(**kwargs))

    def question(self, result) -> HumanQuestionRequestPayload:  # noqa: ANN001
        """Return the human question a waiting result asks (asserting it is one)."""
        self.assertEqual(result.status, ResultStatus.WAITING)
        request = result.requests[0]
        self.assertEqual(request.kind, RequestKind.HUMAN)
        return HumanQuestionRequestPayload.model_validate(request.payload)

    def research_round(self, inv, ctx, waiting, **params):  # noqa: ANN001, ANN201
        """Resume after a research child that brought one new evidence item."""
        self.params.update(params)
        ctx = self.ctx(self.evidence + [EXTRA])
        bundle = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                       {"evidence_ids": [EXTRA.id]})
        return ctx, self.run_decision(resume(inv, waiting, [bundle]), ctx)


class TestLiveLoopReproduction(DesignCase):
    """The live defect: design criteria and flat scores used to research forever."""

    def test_flat_evidence_answerable_scores_still_ask_research(self) -> None:
        _, _, result = self.start()  # Jev says "not a design property": today's behaviour
        self.assertEqual(result.requests[0].kind, RequestKind.EVIDENCE)
        self.assertEqual(result.decisions[0].status, DecisionStatus.NEEDS_EVIDENCE)

    def test_design_criteria_end_in_a_ranked_human_question(self) -> None:
        self.params["design"] = {"c1"}
        _, _, result = self.start()
        question = self.question(result)
        self.assertEqual([c.id for c in question.choices], ["B", "C", "A"])  # by required mean
        self.assertEqual([c.label[:2] for c in question.choices], ["#1", "#2", "#3"])
        self.assertTrue(question.free_text_allowed and question.structured_allowed)
        first = question.choices[0].consequences
        self.assertIn("Are the diffs small and reviewable? unclear (0.67)", first)
        self.assertIn("Does it reuse existing conventions? likely not met (0.10)", first)
        self.assertIn("Evidence: no evidence cited", first)
        self.assertEqual(result.decisions[0].status, DecisionStatus.NEEDS_HUMAN)
        self.assertEqual(result.continuation_state["phase"], "awaiting_design_choice")
        self.assertEqual(result.continuation_state["design_reason"], "design_judgement")
        self.assertEqual(self.jev.call_count, 1)  # classification rides the one assess batch
        self.assertIn("kind.c1", self.jev.questions_asked("decision.assess"))

    def test_a_cited_option_names_its_evidence_in_words(self) -> None:
        self.params["design"] = {"c1"}
        cited = Option(id="A", title="Use the ADR format", source_refs=[self.evidence[0].id])
        question = self.question(self.start(options=[cited, Option(id="B", title="Other")])[2])
        self.assertIn("docs/adr/1.md#L1-L3", question.choices[1].consequences)  # A ranks second
        self.assertEqual(question.evidence_ids, [self.evidence[0].id])

    def test_the_kind_is_recorded_on_the_criterion_and_asked_once(self) -> None:
        self.params["design"] = {"c1"}
        _, _, result = self.start()
        kinds = {c["id"]: (c["kind"], c["kind_source"])
                 for c in result.continuation_state["criteria"]}
        self.assertEqual(kinds["c1"], (CriterionKind.DESIGN_JUDGEMENT.value, "jev"))
        self.assertEqual(kinds["c2"], (CriterionKind.EVIDENCE_ANSWERABLE.value, "jev"))


class TestHumanChoiceResolves(DesignCase):
    """The human's choice resolves the decision; the kernel ranking is only evidence."""

    def setUp(self) -> None:
        super().setUp()
        self.params["design"] = {"c1"}
        self.inv, self.ctx_, self.waiting = self.start()

    def answer(self, response: dict, actor: str = "human:ada"):  # noqa: ANN201
        out = child(self.ctx_, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, response)
        return self.run_decision(resume(self.inv, self.waiting,
                                        [out.model_copy(update={"actor_id": actor})]), self.ctx_)

    def test_choosing_an_option_resolves_it_with_the_human_as_approver(self) -> None:
        done = self.answer({"choice_id": "C"})  # the kernel ranked C second; the human decides
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        report = DecisionReportPayload.model_validate(done.output_payload)
        self.assertEqual((report.status, report.selected_option_id),
                         (DecisionStatus.RESOLVED, "C"))
        self.assertEqual(report.approval_status, ApprovalStatus.APPROVED)
        decision = done.decisions[0]
        self.assertEqual((decision.status, decision.approval_status, decision.approved_by),
                         (DecisionStatus.RESOLVED, ApprovalStatus.APPROVED, "human:ada"))
        text = narrow(decision.rationale).text
        self.assertIn("1. [B]", text)
        self.assertIn("human:ada chose option [C]", text)
        self.assertIn("kernel rank 2 of 3", text)
        self.assertEqual(self.jev.call_count, 1)  # resolving the human's choice needs no Jev
        self.assertTrue(report.criterion_assessments)

    def test_an_added_option_is_ranked_again(self) -> None:
        again = self.answer({"added_options": [{"title": "Hybrid", "description": "Both"}]})
        question = self.question(again)
        self.assertEqual(len(question.choices), 4)
        self.assertIn("opt.added.1", [c.id for c in question.choices])
        self.assertEqual(self.jev.call_count, 2)

    def test_an_unknown_choice_does_not_resolve(self) -> None:
        self.assertEqual(self.answer({"choice_id": "ZZ"}).status, ResultStatus.PARTIAL)


class TestNoProgressAndCap(DesignCase):
    """Evidence-answerable criteria stop researching when research is not converging."""

    def test_flat_scores_after_new_evidence_end_in_a_ranked_question(self) -> None:
        inv, ctx, waiting = self.start()
        self.assertEqual(waiting.requests[0].kind, RequestKind.EVIDENCE)
        _, second = self.research_round(inv, ctx, waiting)  # scores identical
        question = self.question(second)
        self.assertEqual(question.choices[0].id, "B")
        self.assertEqual(second.continuation_state["design_reason"], "no_progress")

    def test_scores_that_moved_more_than_epsilon_keep_researching(self) -> None:
        inv, ctx, waiting = self.start()
        _, second = self.research_round(inv, ctx, waiting, sufficient=0.75)
        self.assertEqual(second.requests[0].kind, RequestKind.EVIDENCE)

    def test_the_research_round_cap_ends_in_a_ranked_question(self) -> None:
        self.decision_config = {"max_research_rounds": 1}
        inv, ctx, waiting = self.start()
        _, second = self.research_round(inv, ctx, waiting, sufficient=0.4)  # moving, but capped
        self.question(second)
        self.assertEqual(second.continuation_state["design_reason"], "research_cap")

    def test_the_epsilon_is_configuration(self) -> None:
        self.decision_config = {"progress_epsilon": 0.2, "max_research_rounds": 5}
        inv, ctx, waiting = self.start()
        _, second = self.research_round(inv, ctx, waiting, sufficient=0.75)  # within 0.2
        self.assertEqual(second.continuation_state["design_reason"], "no_progress")


class TestEvidenceAnswerableUnchanged(DesignCase):
    """Without a design judgement, loop or cap the decision behaves as before."""

    def test_a_decision_that_passes_the_gate_resolves(self) -> None:
        self.params.update(sufficient=0.95, satisfies={("c1", "A"): 0.95, ("c2", "A"): 0.9})
        _, _, result = self.start()
        self.assertEqual(result.status, ResultStatus.COMPLETED)
        report = DecisionReportPayload.model_validate(result.output_payload)
        self.assertEqual(report.selected_option_id, "A")
        self.assertEqual(result.decisions[0].approved_by, None)

    def test_the_kind_question_is_not_asked_again_after_classification(self) -> None:
        inv, ctx, waiting = self.start()
        self.research_round(inv, ctx, waiting, sufficient=0.4)
        second = [q for q in self.jev.batches[1].questions if q.id.startswith("kind.")]
        self.assertEqual(second, [])


class TestOptionContext(DesignCase):
    """A research request made after options exist carries option_context."""

    def test_research_after_options_carries_titles_descriptions_and_cited_refs(self) -> None:
        evidence_id = self.evidence[0].id
        options = [Option(id="A", title="Contract fields",
                          description="Add fields in kernel/contracts/decision.py to "
                                      "`DecisionContinuation` and call parse_record().",
                          source_refs=[evidence_id]),
                   Option(id="B", title="Plain files")]
        _, _, result = self.start(options=options)
        payload = ResearchRequestPayload.model_validate(result.requests[0].payload)
        by_id = {c.option_id: c for c in payload.option_context}
        self.assertEqual(set(by_id), {"A", "B"})
        self.assertEqual(by_id["A"].title, "Contract fields")
        refs = by_id["A"].cited_refs
        for expected in (evidence_id, "kernel/contracts/decision.py", "DecisionContinuation",
                         "parse_record"):
            self.assertIn(expected, refs)
        self.assertEqual((by_id["B"].description, by_id["B"].cited_refs), (None, []))

    def test_grounding_research_has_no_option_context(self) -> None:
        inv = invocation(DECISION, schema_ids.DECISION_REQUEST, _payload(options=[]) | {
            "evidence_ids": []})
        result = self.run_decision(inv, self.ctx(evidence=[]))
        self.assertEqual(result.requests[0].kind, RequestKind.EVIDENCE)
        payload = ResearchRequestPayload.model_validate(result.requests[0].payload)
        self.assertEqual(payload.option_context, [])


if __name__ == "__main__":
    import unittest
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Reproduces the live loop offline (design criteria, flat scores) and
#   proves each stop trigger, the human's choice and option_context. (#KernelV01/A)
# ====================================================================
