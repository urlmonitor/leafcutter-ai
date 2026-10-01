"""
MODULE: tests.kernel.capabilities.test_research_graph
GOAL: Behavioural tests of the native research capability through its CapabilityExecutor entry
    point: need planning, source resolution, parallel children, collection with coverage and
    contradictions, conditional synthesis, stop conditions and an end-to-end run against the real
    retrieval executor.
BUSINESS CONTEXT: Research must gather inspectable evidence without looping to raise confidence,
    keep conflicting sources visible and report unavailable sources explicitly (Rev 3 sections
    10.2 and 10.5).
ARCHITECTURE: ScriptedJev answers from a mutable params dict; the kernel's fan-out and resume are
    simulated with tests.kernel.capabilities.support. The end-to-end test feeds the children's
    payloads to RepositoryRetrievalExecutor over a temp repository.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from typing import Any

from kernel.capabilities.research import ResearchExecutor
from kernel.capabilities.research.planning import retrieval_operation
from kernel.capabilities.retrieval import RepositoryRetrievalExecutor
from kernel.capabilities.retrieval.knowledge_map import clear_caches
from kernel.config import load_kernel_config
from kernel.contracts import schema_ids
from kernel.contracts.enums import (
    EvidenceCategory,
    NeedStatus,
    Priority,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.evidence import EvidenceBundlePayload, EvidenceNeed
from kernel.contracts.payloads import (
    GoalRequestPayload,
    ResearchRequestPayload,
    RetrievalRequestPayload,
    SynthesisRequestPayload,
)
from kernel.providers.base import JevUnavailable
from kernel.providers.fakes import ScriptedJev, noul_answer
from tests.kernel.capabilities.support import (
    child,
    evidence_item,
    invocation,
    no_git,
    resume,
    script_research,
)
from tests.kernel.helpers import as_type, bundle_of, make_context

QUESTION = "Where should run state be stored with sqlite?"
CATS = EvidenceCategory


def _bundle(ev_items: list, coverage: dict, **extra: Any) -> dict:
    """Return an evidence_bundle.v1 payload with the given evidence and coverage."""
    return EvidenceBundlePayload(
        evidence_ids=[e.id for e in ev_items], evidence=ev_items, coverage=coverage,
        attempted_sources=["repo.decisions"], **extra).model_dump(mode="json")


class ResearchCase(unittest.TestCase):
    """Base: temp repository layout, scripted Jev and run helpers."""

    def setUp(self) -> None:
        clear_caches()
        no_git(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve() / "repo"
        for rel in ("docs/architecture/adrs", "docs/conventions", "kernel"):
            (self.root / rel).mkdir(parents=True)
        (self.root / "CLAUDE.md").write_text("Rules: always roll back sqlite tests.\n",
                                             encoding="utf-8")
        (self.root / "docs/architecture/adrs/ADR-001.md").write_text(
            "Decision: use sqlite for run state.\n", encoding="utf-8")
        self.jev = ScriptedJev()
        self.params = script_research(self.jev, {"need": {"prior_decisions": 0.9,
                                                  "internal_principles": 0.9}})

    def ctx(self, config=None):
        return make_context(self.root, jev=self.jev, config=config)

    def goal(self, question: str = QUESTION):
        return invocation("research", schema_ids.GOAL_REQUEST,
                          GoalRequestPayload(goal=question).model_dump())

    def run_research(self, inv, ctx):
        return asyncio.run(ResearchExecutor().ainvoke(inv, ctx))

    def bundle(self, result) -> EvidenceBundlePayload:
        return as_type(bundle_of(result),
                       EvidenceBundlePayload)


class TestPlanning(ResearchCase):
    """plan_needs and resolve_sources."""

    def test_jev_selects_needs_and_thresholds_set_priority(self) -> None:
        self.params["need"]["internal_principles"] = 0.6
        result = self.run_research(self.goal(), self.ctx())
        self.assertEqual(result.status, ResultStatus.WAITING)
        needs = {n.category: n.priority for r in result.requests for n in r.evidence_needs}
        self.assertEqual(needs, {CATS.PRIOR_DECISIONS: Priority.REQUIRED,
                                 CATS.INTERNAL_PRINCIPLES: Priority.SUPPORTING})

    def test_one_batch_asks_every_generic_category_with_config_descriptions(self) -> None:
        self.run_research(self.goal(), self.ctx())
        self.assertEqual(self.jev.call_count, 1)
        batch = self.jev.batches[0]
        self.assertEqual(sorted(self.jev.questions_asked()),
                         sorted(f"need.{c.value}" for c in CATS))
        described = load_kernel_config().research.category_descriptions
        self.assertEqual(batch.state["categories"],
                         {c.value: described[c] for c in CATS})

    def test_caller_mandated_needs_are_kept_and_not_asked_again(self) -> None:
        mandated = EvidenceNeed(id="need.existing_patterns", category=CATS.EXISTING_PATTERNS,
                                question="How do existing modules store state?")
        payload = ResearchRequestPayload(question=QUESTION,
                                         evidence_needs=[mandated]).model_dump(mode="json")
        inv = invocation("research", schema_ids.RESEARCH_REQUEST, payload)
        result = self.run_research(inv, self.ctx())
        asked = self.jev.questions_asked()
        self.assertNotIn("need.existing_patterns", asked)
        ids = [n.id for r in result.requests for n in r.evidence_needs]
        self.assertIn("need.existing_patterns", ids)

    def test_independent_needs_become_independent_children(self) -> None:
        result = self.run_research(self.goal(), self.ctx())
        self.assertEqual(len(result.requests), 2)
        for request in result.requests:
            self.assertEqual(request.kind, RequestKind.EVIDENCE)
            self.assertEqual(request.payload_schema, schema_ids.RETRIEVAL_REQUEST)
            self.assertEqual(request.depends_on, [])
            payload = RetrievalRequestPayload.model_validate(request.payload)
            self.assertIn("repo.decisions" if payload.need.category is CATS.PRIOR_DECISIONS
                          else "repo.principles", payload.source_ids)

    def test_need_without_native_source_becomes_host_research_child(self) -> None:
        self.params["need"] = {"external_practices": 0.9}
        cfg = load_kernel_config()
        result = self.run_research(self.goal(), self.ctx(cfg))
        request = result.requests[0]
        payload = RetrievalRequestPayload.model_validate(request.payload)
        self.assertEqual(payload.source_ids, ["host.research"])
        self.assertEqual(retrieval_operation(request.payload, cfg.sources), "bounded_research")

    def test_native_child_operation_is_retrieve(self) -> None:
        result = self.run_research(self.goal(), self.ctx())
        ops = {retrieval_operation(r.payload, load_kernel_config().sources)
               for r in result.requests}
        self.assertEqual(ops, {"retrieve"})

    def test_host_disabled_makes_the_need_unavailable_and_ends_without_children(self) -> None:
        self.params["need"] = {"external_practices": 0.9}
        base = load_kernel_config()
        cfg = base.model_copy(update={"host": base.host.model_copy(update={"enabled": False})})
        result = self.run_research(self.goal(), self.ctx(cfg))
        bundle = self.bundle(result)
        self.assertEqual(result.status, ResultStatus.PARTIAL)
        self.assertEqual(bundle.coverage["need.external_practices"], NeedStatus.UNAVAILABLE)
        reasons = [u.reason for u in bundle.unavailable_sources]
        self.assertIn("host research is disabled", reasons)

    def test_scope_source_ids_and_restrictions_narrow_sources(self) -> None:
        self.params["need"] = {"prior_decisions": 0.9}
        payload = ResearchRequestPayload(
            question=QUESTION, source_restrictions=["repo.decisions"]).model_dump(mode="json")
        inv = invocation("research", schema_ids.RESEARCH_REQUEST, payload)
        result = self.run_research(inv, self.ctx())
        ids = RetrievalRequestPayload.model_validate(result.requests[0].payload).source_ids
        self.assertEqual(ids, ["repo.decisions"])

    def test_unreadable_native_sources_are_reported_unavailable(self) -> None:
        self.params["need"] = {"existing_patterns": 0.9}
        shutil.rmtree(self.root / "kernel")
        shutil.rmtree(self.root / "docs" / "architecture")
        result = self.run_research(self.goal(), self.ctx())
        self.assertEqual(result.status, ResultStatus.PARTIAL)
        bundle = self.bundle(result)
        names = [u.source_id for u in bundle.unavailable_sources]
        self.assertIn("repo.patterns", names)
        self.assertIn("all native sources are unavailable",
                      [u.reason for u in bundle.unavailable_sources])


class TestCollect(ResearchCase):
    """collect and evaluate."""

    def plan(self):
        ctx = self.ctx()
        inv = self.goal()
        return inv, ctx, self.run_research(inv, ctx)

    def children(self, ctx, waiting, ev_a, ev_b, cov_b=NeedStatus.SATISFIED):
        a = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                  _bundle([ev_a], {"need.prior_decisions": NeedStatus.SATISFIED}))
        b = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                  _bundle([ev_b], {"need.internal_principles": cov_b}))
        return [a, b]

    def test_merges_child_bundles_into_coverage_per_need(self) -> None:
        inv, ctx, waiting = self.plan()
        ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        ev_b = evidence_item("CLAUDE.md#L1-L1", "Roll back.", CATS.INTERNAL_PRINCIPLES)
        done = self.run_research(resume(inv, waiting, self.children(ctx, waiting, ev_a, ev_b)),
                                 ctx)
        bundle = self.bundle(done)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(bundle.coverage, {"need.prior_decisions": NeedStatus.SATISFIED,
                                           "need.internal_principles": NeedStatus.SATISFIED})
        self.assertEqual(sorted(bundle.evidence_ids), sorted([ev_a.id, ev_b.id]))
        self.assertEqual({e.id for e in done.evidence}, {ev_a.id, ev_b.id})

    def test_conflict_recorded(self) -> None:
        inv, ctx, waiting = self.plan()
        ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        ev_b = evidence_item("docs/b.md#L1-L2", "Do not use sqlite.")
        self.params["conflict"] = 0.9
        done = self.run_research(resume(inv, waiting, self.children(ctx, waiting, ev_a, ev_b)),
                                 ctx)
        bundle = self.bundle(done)
        self.assertEqual(len(bundle.contradictions), 1)
        self.assertIn("not localised", bundle.contradictions[0].note)
        self.assertEqual(sorted(bundle.evidence_ids), sorted([ev_a.id, ev_b.id]))
        self.assertEqual(done.status, ResultStatus.COMPLETED)

    def test_no_conflict_below_threshold_records_nothing(self) -> None:
        inv, ctx, waiting = self.plan()
        ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        ev_b = evidence_item("docs/b.md#L1-L2", "Sqlite is fine.")
        self.params["conflict"] = 0.2
        done = self.run_research(resume(inv, waiting, self.children(ctx, waiting, ev_a, ev_b)),
                                 ctx)
        self.assertEqual(self.bundle(done).contradictions, [])

    def test_unsatisfied_required_need_makes_the_bundle_partial(self) -> None:
        inv, ctx, waiting = self.plan()
        ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        ev_b = evidence_item("CLAUDE.md#L1-L1", "Roll back.", CATS.INTERNAL_PRINCIPLES)
        kids = self.children(ctx, waiting, ev_a, ev_b, cov_b=NeedStatus.OPEN)
        done = self.run_research(resume(inv, waiting, kids), ctx)
        self.assertEqual(done.status, ResultStatus.PARTIAL)
        self.assertTrue(any("need.internal_principles" in x for x in done.limitations))

    def test_best_effort_coverage_completes_but_still_lists_the_gap(self) -> None:
        payload = ResearchRequestPayload(question=QUESTION, expected_coverage="best_effort"
                                         ).model_dump(mode="json")
        inv = invocation("research", schema_ids.RESEARCH_REQUEST, payload)
        ctx = self.ctx()
        waiting = self.run_research(inv, ctx)
        ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        ev_b = evidence_item("CLAUDE.md#L1-L1", "Roll back.", CATS.INTERNAL_PRINCIPLES)
        kids = self.children(ctx, waiting, ev_a, ev_b, cov_b=NeedStatus.OPEN)
        done = self.run_research(resume(inv, waiting, kids), ctx)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertTrue(any("need.internal_principles" in x for x in self.bundle(done).limitations))

    def test_failed_child_is_a_limitation_never_an_empty_result(self) -> None:
        inv, ctx, waiting = self.plan()
        ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        ok = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                   _bundle([ev_a], {"need.prior_decisions": NeedStatus.SATISFIED}))
        bad = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, None,
                    ResultStatus.FAILED)
        done = self.run_research(resume(inv, waiting, [ok, bad]), ctx)
        bundle = self.bundle(done)
        self.assertEqual(done.status, ResultStatus.PARTIAL)
        self.assertEqual(bundle.coverage["need.internal_principles"], NeedStatus.UNAVAILABLE)
        self.assertTrue(any("failed" in x for x in bundle.limitations))

    def test_unavailable_sources_and_truncation_propagate(self) -> None:
        inv, ctx, waiting = self.plan()
        ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        ev_b = evidence_item("CLAUDE.md#L1-L1", "Roll back.", CATS.INTERNAL_PRINCIPLES)
        kids = self.children(ctx, waiting, ev_a, ev_b)
        extra = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, _bundle(
            [], {"need.prior_decisions": NeedStatus.PARTIAL}, truncated=True, limitations=["cut"],
            unavailable_sources=[{"source_id": "knowledge.decisions", "reason": "timed out"}]))
        done = self.run_research(resume(inv, waiting, [*kids, extra]), ctx)
        bundle = self.bundle(done)
        self.assertTrue(bundle.truncated)
        self.assertIn("timed out", [u.reason for u in bundle.unavailable_sources])
        self.assertIn("cut", bundle.limitations)


class TestSynthesisAndStop(ResearchCase):
    """Synthesis only when raw evidence cannot answer; no re-planning; guards."""

    def setUp(self) -> None:
        super().setUp()
        self.ctx_ = self.ctx()
        self.inv = self.goal()
        self.waiting = self.run_research(self.inv, self.ctx_)
        self.ev_a = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        self.ev_b = evidence_item("CLAUDE.md#L1-L1", "Roll back.", CATS.INTERNAL_PRINCIPLES)
        self.kids = [
            child(self.ctx_, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                  _bundle([self.ev_a], {"need.prior_decisions": NeedStatus.SATISFIED})),
            child(self.ctx_, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                  _bundle([self.ev_b], {"need.internal_principles": NeedStatus.SATISFIED}))]

    def test_synthesis_is_requested_only_when_evidence_is_not_directly_evaluable(self) -> None:
        self.params["evaluable"] = 0.3
        asked = self.run_research(resume(self.inv, self.waiting, self.kids), self.ctx_)
        self.assertEqual(asked.status, ResultStatus.WAITING)
        request = asked.requests[0]
        self.assertEqual(request.kind, RequestKind.SYNTHESIS)
        body = SynthesisRequestPayload.model_validate(request.payload)
        self.assertEqual(sorted(body.evidence_ids), sorted([self.ev_a.id, self.ev_b.id]))
        self.assertEqual(asked.continuation_state["phase"], "synthesizing")

    def test_evaluable_evidence_needs_no_synthesis(self) -> None:
        done = self.run_research(resume(self.inv, self.waiting, self.kids), self.ctx_)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(done.requests, [])

    def test_synthesis_resume_finishes_without_replanning_or_more_jev_calls(self) -> None:
        self.params["evaluable"] = 0.3
        asked = self.run_research(resume(self.inv, self.waiting, self.kids), self.ctx_)
        calls = self.jev.call_count
        findings = child(self.ctx_, RequestKind.SYNTHESIS, schema_ids.FINDINGS, {
            "findings": [], "disagreements": ["A and B weigh consistency differently"]})
        done = self.run_research(resume(self.inv, asked, [findings]), self.ctx_)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertEqual(self.jev.call_count, calls)
        bundle = self.bundle(done)
        self.assertEqual(sorted(bundle.evidence_ids), sorted([self.ev_a.id, self.ev_b.id]))
        self.assertTrue(any("disagreement" in x for x in bundle.limitations))

    def test_allow_synthesis_off_never_requests_synthesis(self) -> None:
        self.params["evaluable"] = 0.1
        base = load_kernel_config()
        cfg = base.model_copy(update={"research": base.research.model_copy(
            update={"allow_synthesis": False})})
        ctx = replace(self.ctx_, config=cfg)
        done = self.run_research(resume(self.inv, self.waiting, self.kids), ctx)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        self.assertNotIn("evaluable", self.jev.questions_asked("research.assess"))

    def test_resume_asks_no_planning_questions(self) -> None:
        self.run_research(resume(self.inv, self.waiting, self.kids), self.ctx_)
        self.assertEqual(self.jev.questions_asked("research.plan_needs").count("need.task_context"),
                         1)
        self.assertEqual(len(self.jev.questions_asked("research.plan_needs")), len(list(CATS)))

    def test_jev_unavailable_fails_with_provider_code(self) -> None:
        self.jev.fail_next(JevUnavailable("down"))
        result = self.run_research(self.goal(), self.ctx())
        self.assertEqual(result.status, ResultStatus.FAILED)
        self.assertEqual(result.error.code, "provider_unavailable")


class TestEndToEnd(ResearchCase):
    """Research children executed by the real retrieval executor over a temp repository."""

    def test_research_with_real_retrieval_children(self) -> None:
        self.jev.script("retrieval.rerank", "relevant.*", noul_answer(0.9))
        ctx = self.ctx()
        inv = self.goal()
        waiting = self.run_research(inv, ctx)
        outcomes = []
        for request in waiting.requests:
            sub = invocation("retrieve.repository", request.payload_schema, request.payload)
            got = asyncio.run(RepositoryRetrievalExecutor().ainvoke(sub, ctx))
            outcomes.append(child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                                  got.output_payload, got.status))
        done = self.run_research(resume(inv, waiting, outcomes), ctx)
        bundle = self.bundle(done)
        locators = sorted(e.source.locator.split("#")[0] for e in done.evidence)
        self.assertEqual(locators, ["CLAUDE.md", "docs/architecture/adrs/ADR-001.md"])
        self.assertEqual(set(bundle.coverage.values()), {NeedStatus.SATISFIED})
        self.assertIn("knowledge.decisions", [u.source_id for u in bundle.unavailable_sources])
        self.assertTrue(all(e.content_hash and e.source.locator for e in done.evidence))


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The research Jev script moved to support.script_research, which
#   now also answers `answers.*`. (#KernelV01/D)
# - 2026-10-02 [python-coder]: the host-only examples use external_practices: authoritative_guidance now has native project sources.
#   (#KernelBootstrapV0/GROUND)
# - 2026-09-30 23:00 [python-coder]: The end-to-end test expects the knowledge-map sources to be
#   listed as unavailable (the temp repository has no scripts/) while the needs are still
#   satisfied by the reachable sources. (#KernelBootstrapV0/P5)
# ====================================================================
