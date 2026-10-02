"""
MODULE: tests.kernel.capabilities.test_decision_graph
GOAL: Behavioural tests of the native decision capability through its CapabilityExecutor entry
    point: the resolved-gate, the needs_* routing, the criteria-proposal and human-approval path,
    conflict escalation, no-progress and provider failure.
BUSINESS CONTEXT: The decision capability must never coerce a weak probability into a decision
    and must never use LLM-proposed options or criteria without a human approval (ADR-053).
ARCHITECTURE: ScriptedJev answers from a mutable params dict; the kernel's resume step is
    simulated by tests.kernel.capabilities.support (continuation plus child outputs via the
    artifact store). Everything is offline.
"""

from __future__ import annotations

import asyncio
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision import DecisionExecutor
from kernel.contracts import schema_ids
from kernel.contracts.enums import (
    ApprovalStatus,
    DecisionStatus,
    EvidenceCategory,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.payloads import (
    DecisionReportPayload,
    HumanQuestionRequestPayload,
)
from kernel.contracts.task import RevisionInfo
from kernel.providers.base import JevUnavailable
from kernel.providers.fakes import ScriptedJev
from tests.kernel.capabilities.support import (
    child,
    evidence_item,
    invocation,
    resume,
    script_decision,
)
from tests.kernel.capabilities.support import (
    decision_payload as _payload,
)
from tests.kernel.helpers import as_json, make_context, narrow

DECISION = "decision"


class DecisionTestCase(unittest.TestCase):
    """Base: a temp repository root, a scripted Jev and helpers to run the executor."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.jev = ScriptedJev()
        self.params = script_decision(self.jev)
        self.evidence = [evidence_item("docs/adr/1.md#L1-L3", "Decision: use sqlite for state.")]

    def ctx(self, evidence=None) -> ExecutionContext:
        return make_context(self.root, jev=self.jev,
                            evidence=self.evidence if evidence is None else evidence)

    def run_decision(self, inv, ctx):
        return asyncio.run(DecisionExecutor().ainvoke(inv, ctx))

    def first(self, payload: dict | None = None, **extra):
        ctx = self.ctx()
        body = dict(payload) if payload is not None else _payload(**extra)
        body["evidence_ids"] = body.get("evidence_ids") or [e.id for e in self.evidence]
        inv = invocation(DECISION, schema_ids.DECISION_REQUEST, body)
        return inv, ctx, self.run_decision(inv, ctx)


class TestResolvedGate(DecisionTestCase):
    """The resolved-gate opens only when every condition holds."""

    def test_resolved_when_all_conditions_hold(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}
        _, _, result = self.first()
        self.assertEqual(result.status, ResultStatus.COMPLETED)
        report = DecisionReportPayload.model_validate(result.output_payload)
        self.assertEqual(report.status, DecisionStatus.RESOLVED)
        self.assertEqual(report.selected_option_id, "A")
        self.assertEqual(narrow(report.rationale).origin, "template")
        self.assertEqual(result.decisions[0].selected_option_id, "A")
        raw = [a for a in report.criterion_assessments if a.option_id == "A"]
        self.assertTrue(all(narrow(a.provider_answer).probabilities for a in raw))

    def test_one_jev_call_per_assessment_with_atomic_questions(self) -> None:
        # covers: DK-100a-4
        self.params["satisfies"] = {("c1", "A"): 0.95}
        self.first()
        asked = self.jev.questions_asked("decision.assess")
        self.assertEqual(self.jev.call_count, 1)
        for qid in ("sufficient.c1", "satisfies.c1.A", "satisfies.c2.B", "missing",
                    "preference", "conflict"):
            self.assertIn(qid, asked)

    def test_weak_probability_is_not_coerced_into_a_decision(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.6}
        _, _, result = self.first()
        self.assertNotEqual(result.status, ResultStatus.COMPLETED)
        self.assertEqual(result.requests[0].kind, RequestKind.SYNTHESIS)
        self.assertEqual(result.decisions[0].status, DecisionStatus.NEEDS_SYNTHESIS)
        self.assertIsNone(result.decisions[0].selected_option_id)

    def test_no_option_passes_asks_for_more_options(self) -> None:
        _, _, result = self.first()
        self.assertEqual(result.requests[0].kind, RequestKind.OPTIONS)
        self.assertEqual(result.decisions[0].status, DecisionStatus.NEEDS_OPTIONS)

    def test_two_passing_options_need_a_human_tie_break(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c1", "B"): 0.95}
        _, _, result = self.first()
        request = result.requests[0]
        self.assertEqual(request.kind, RequestKind.HUMAN)
        question = HumanQuestionRequestPayload.model_validate(request.payload)
        self.assertEqual({c.id for c in question.choices}, {"A", "B"})

    def test_preference_needs_a_human(self) -> None:
        self.params.update(satisfies={("c1", "A"): 0.95}, preference=0.9)
        _, _, result = self.first()
        self.assertEqual(result.requests[0].kind, RequestKind.HUMAN)
        self.assertEqual(result.decisions[0].status, DecisionStatus.NEEDS_HUMAN)

    def test_required_approval_waits_then_resolves_after_approval(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95}
        inv, ctx, waiting = self.first(approval_required=True)
        self.assertEqual(waiting.requests[0].kind, RequestKind.HUMAN)
        answer = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER,
                       {"choice_id": "approve"})
        done = self.run_decision(resume(inv, waiting, [answer]), ctx)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        report = DecisionReportPayload.model_validate(done.output_payload)
        self.assertEqual(report.approval_status, ApprovalStatus.APPROVED)

    def test_rejected_approval_blocks(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95}
        inv, ctx, waiting = self.first(approval_required=True)
        answer = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {"choice_id": "reject"})
        done = self.run_decision(resume(inv, waiting, [answer]), ctx)
        self.assertEqual(done.status, ResultStatus.BLOCKED)
        self.assertEqual(done.error.code, "approval_rejected")

    def test_report_has_no_single_confidence_field(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95}
        _, _, result = self.first()
        self.assertNotIn("confidence", result.output_payload)
        self.assertNotIn("confidence", DecisionReportPayload.model_fields)


class TestNeedsEvidence(DecisionTestCase):
    """Insufficient evidence becomes a research request built from the missing taxonomy."""

    def test_insufficient_evidence_requests_research_with_categories(self) -> None:
        self.params.update(sufficient=0.2, missing="missing_internal_principle")
        _, _, result = self.first()
        request = result.requests[0]
        self.assertEqual(request.kind, RequestKind.EVIDENCE)
        self.assertEqual(request.payload_schema, schema_ids.RESEARCH_REQUEST)
        self.assertEqual([n.category for n in request.evidence_needs],
                         [EvidenceCategory.INTERNAL_PRINCIPLES])
        self.assertEqual(result.continuation_state["phase"], "awaiting_evidence")

    def test_existing_implementation_is_a_pattern_not_proof(self) -> None:
        pattern = evidence_item("kernel/x.py#L1-L5", "def use_sqlite(): ...",
                                EvidenceCategory.EXISTING_PATTERNS)
        self.evidence = [pattern]
        self.params["satisfies"] = {("c1", "A"): 0.99}
        _, _, result = self.first()
        self.assertEqual(result.status, ResultStatus.WAITING)
        cats = [n.category for n in result.requests[0].evidence_needs]
        self.assertIn(EvidenceCategory.PRIOR_DECISIONS, cats)
        batch = self.jev.batches[0]
        self.assertEqual(as_json(batch.state)["evidence"][pattern.id]["role"], "pattern_only")

    def test_same_request_at_same_revision_is_partial_no_progress(self) -> None:
        self.params.update(sufficient=0.2, missing="missing_internal_principle")
        inv, ctx, waiting = self.first()
        empty = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, {})
        again = self.run_decision(resume(inv, waiting, [empty]), ctx)
        self.assertEqual(again.status, ResultStatus.PARTIAL)
        report = DecisionReportPayload.model_validate(again.output_payload)
        self.assertEqual(report.status, DecisionStatus.NEEDS_EVIDENCE)
        self.assertTrue(report.open_questions)

    def test_new_evidence_allows_a_fresh_request(self) -> None:
        self.params.update(sufficient=0.2, missing="missing_internal_principle")
        inv, ctx, waiting = self.first()
        extra = evidence_item("docs/conv.md#L1-L2", "Always use rollback.",
                              EvidenceCategory.INTERNAL_PRINCIPLES)
        ctx = self.ctx(self.evidence + [extra])
        bundle = {"evidence_ids": [extra.id]}
        out = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, bundle)
        again = self.run_decision(resume(inv, waiting, [out]), ctx)
        self.assertEqual(again.status, ResultStatus.WAITING)

    def test_decision_basis_from_another_revision_is_a_limitation(self) -> None:
        self.params["satisfies"] = {("c1", "A"): 0.95}
        base = self.ctx()
        scope = base.scope.model_copy(update={"revision": RevisionInfo(commit="zzz9999999")})
        ctx = replace(base, scope=scope)
        inv = invocation(DECISION, schema_ids.DECISION_REQUEST,
                         _payload(evidence_ids=[e.id for e in self.evidence]))
        result = self.run_decision(inv, ctx)
        report = DecisionReportPayload.model_validate(result.output_payload)
        self.assertEqual(report.status, DecisionStatus.RESOLVED)
        self.assertTrue(any("was read at abc1234567" in x for x in report.limitations))


class TestConflict(DecisionTestCase):
    """Conflicting evidence escalates; it is never averaged into a decision."""

    def test_conflict_escalates(self) -> None:
        self.params.update(satisfies={("c1", "A"): 0.95}, conflict=0.9)
        inv, ctx, waiting = self.first()
        self.assertEqual(waiting.requests[0].kind, RequestKind.SYNTHESIS)
        findings = child(ctx, RequestKind.SYNTHESIS, schema_ids.FINDINGS,
                         {"disagreements": ["ADR 1 and ADR 2 disagree"]})
        asked = self.run_decision(resume(inv, waiting, [findings]), ctx)
        self.assertEqual(asked.status, ResultStatus.WAITING)
        self.assertEqual(asked.requests[0].kind, RequestKind.HUMAN)
        self.assertEqual(asked.decisions[0].status, DecisionStatus.NEEDS_HUMAN)
        self.assertNotEqual(asked.status, ResultStatus.COMPLETED)

    def test_human_ruling_on_conflict_lets_the_decision_resolve(self) -> None:
        self.params.update(satisfies={("c1", "A"): 0.95}, conflict=0.9)
        inv, ctx, waiting = self.first()
        findings = child(ctx, RequestKind.SYNTHESIS, schema_ids.FINDINGS, {})
        asked = self.run_decision(resume(inv, waiting, [findings]), ctx)
        ruling = child(ctx, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER,
                       {"free_text": "ADR 2 supersedes ADR 1."})
        done = self.run_decision(resume(inv, asked, [ruling]), ctx)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertIn("ADR 2 supersedes ADR 1.", as_json(self.jev.batches[-1].state)["constraints"])


class TestProviderFailure(DecisionTestCase):
    """Provider problems are explicit outcomes, never fabricated decisions."""

    def test_jev_unavailable_fails_with_provider_code(self) -> None:
        self.jev.fail_next(JevUnavailable("down"))
        _, _, result = self.first()
        self.assertEqual(result.status, ResultStatus.FAILED)
        self.assertEqual(result.error.code, "provider_unavailable")
        self.assertTrue(result.error.retryable)
        self.assertEqual(result.decisions, [])

    def test_exhausted_budget_blocks_before_calling_jev(self) -> None:
        ctx = self.ctx()
        object.__setattr__(ctx, "budget", _NoBudget())
        inv = invocation(DECISION, schema_ids.DECISION_REQUEST, _payload())
        result = self.run_decision(inv, ctx)
        self.assertEqual(result.status, ResultStatus.BLOCKED)
        self.assertEqual(result.error.code, "budget_exhausted")
        self.assertEqual(self.jev.call_count, 0)


class _NoBudget:
    """Budget that refuses every reservation."""

    def reserve(self, resource: str) -> bool:
        return False


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:55 [python-coder]: The criteria edit is a structured answer now; free text is a
#   recorded fallback, and answers of an earlier wait are ignored. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:00 [python-coder]: A basis read at another revision is a limitation, not a
#   block: the decision still resolves but the report states the mismatch. (#KernelBootstrapV0/P5)
# ====================================================================
