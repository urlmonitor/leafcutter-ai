"""
MODULE: tests.kernel.grounding.test_round3
GOAL: Tests of the third live round: host findings reaching the research bundle and a readable
    report, supporting host-only needs not pausing a run that has its answer, locators surviving
    redaction while secrets do not, evidence ids on the approval packet, synthesis findings in the
    options packet, line-aware excerpt cuts and trace links on gap rows and drafts.
BUSINESS CONTEXT: A live "Where are tests saved?" run completed with 9 evidence items and "No
    findings were recorded", paused for host work although tests/README.md was already found,
    sent `[REDACTED:entropy].md` locators to the host and left the approval question without
    evidence ids (Rev 3 sections 10.2, 10.3, 11.3 and 13.3).
ARCHITECTURE: Real research executor, decision loading, redactor, retrieval candidate builder,
    gap store and report text; ScriptedJev answers; the kernel resume step comes from the
    capabilities support module.
"""

from __future__ import annotations

import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

from kernel.capabilities.decision.loading import load_working
from kernel.capabilities.decision.requests import options_request
from kernel.capabilities.retrieval.repository import _candidate
from kernel.config import load_kernel_config
from kernel.contracts import (
    ApprovalStatus,
    CapabilityGap,
    FindingKind,
    GapType,
    ProposalStatus,
    Request,
    schema_ids,
)
from kernel.contracts.enums import EvidenceCategory, NeedStatus, ResultStatus
from kernel.contracts.enums import RequestKind as RK
from kernel.contracts.evidence import EvidenceBundlePayload, Finding
from kernel.contracts.payloads import OptionsRequestPayload
from kernel.intent.report_text import output_sections
from kernel.observability.redaction import Redactor
from kernel.observability.tracer import TraceState
from kernel.persistence.base import aggregate_gaps
from kernel.persistence.gap_store import publish_gap, render_gap_draft
from kernel.persistence.memory import MemoryGapStore
from kernel.scheduler.nodes_gaps import build_gap
from tests.kernel.capabilities.support import child, evidence_item, invocation, resume
from tests.kernel.capabilities.test_decision_graph import DECISION, DecisionTestCase
from tests.kernel.capabilities.test_research_graph import ResearchCase, _bundle
from tests.kernel.helpers import narrow

CATS = EvidenceCategory
HOST_NOTE = "host-reported; not verified by the kernel"
NOW = datetime(2026, 10, 1, 4, 23, tzinfo=UTC)


def _finding(claim: str = "Tests live under tests/kernel.") -> Finding:
    return Finding(id="find-aaaaaaaaaaaaaaaa", claim=claim, kind=FindingKind("inference"),
                   producer="host.research", limitations=[HOST_NOTE])


class TestBundleFindings(ResearchCase):
    """Findings a host reported inside an evidence bundle reach the final bundle."""

    def setUp(self) -> None:
        super().setUp()
        self.params["need"] = {"prior_decisions": 0.9}
        self.ctx_ = self.ctx()
        self.inv = self.goal()
        self.waiting = self.run_research(self.inv, self.ctx_)

    def test_child_bundle_findings_are_in_the_final_bundle_labelled_host_reported(self) -> None:
        ev = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        payload = EvidenceBundlePayload(
            evidence_ids=[ev.id], evidence=[ev], findings=[_finding()],
            coverage={"need.prior_decisions": NeedStatus.SATISFIED}).model_dump(mode="json")
        kid = child(self.ctx_, RK.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, payload)
        done = self.run_research(resume(self.inv, self.waiting, [kid, kid]), self.ctx_)
        bundle = self.bundle(done)
        self.assertEqual([f.claim for f in bundle.findings], ["Tests live under tests/kernel."])
        self.assertIn(HOST_NOTE, bundle.findings[0].limitations)
        self.assertEqual(bundle.finding_ids, [bundle.findings[0].id])


class TestReadableReport(unittest.TestCase):
    """Without findings the report still shows the key evidence, not just 'No findings'."""

    def test_evidence_without_findings_shows_key_excerpts_in_readable_form(self) -> None:
        payload = {"evidence": [{"source": {"locator": "tests/README.md#L15-L39"},
                                 "excerpt": "Tests are saved under tests/ and unit_tests/."}]}
        text = "\n".join(output_sections(schema_ids.EVIDENCE_BUNDLE, payload))
        self.assertIn("## Key evidence", text)
        self.assertIn("tests/README.md#L15-L39", text)
        self.assertIn("Tests are saved under tests/ and unit_tests/.", text)
        self.assertNotIn("No findings were recorded", text)


class TestHostOnlySupportingNeeds(ResearchCase):
    """A supporting need only a host can serve waits until the other evidence proves too thin."""

    def setUp(self) -> None:
        super().setUp()
        self.params["need"] = {"prior_decisions": 0.9, "external_practices": 0.6}
        self.ctx_ = self.ctx()
        self.inv = self.goal()
        self.first = self.run_research(self.inv, self.ctx_)
        ev = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        self.native = child(self.ctx_, RK.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                            _bundle([ev], {"need.prior_decisions": NeedStatus.SATISFIED}))

    def sources_of(self, result) -> list[list[str]]:
        return [list(r.payload["source_ids"]) for r in result.requests]

    def test_the_first_wave_has_only_the_natively_served_need(self) -> None:
        self.assertEqual(self.first.status, ResultStatus.WAITING)
        self.assertEqual(self.sources_of(self.first), [["repo.decisions"]])

    def test_evaluable_native_evidence_skips_the_host_need_with_a_limitation(self) -> None:
        done = self.run_research(resume(self.inv, self.first, [self.native]), self.ctx_)
        self.assertEqual(done.status, ResultStatus.COMPLETED)
        bundle = self.bundle(done)
        self.assertTrue(any("external_practices" in t and "not consulted" in t
                            and "host" in t for t in bundle.limitations), bundle.limitations)
        self.assertNotIn("host.research", bundle.attempted_sources)

    def test_thin_native_evidence_still_asks_the_host(self) -> None:
        self.params["evaluable"] = 0.2
        asked = self.run_research(resume(self.inv, self.first, [self.native]), self.ctx_)
        self.assertEqual(asked.status, ResultStatus.WAITING)
        self.assertEqual(self.sources_of(asked), [["host.research"]])
        host = child(self.ctx_, RK.EVIDENCE, schema_ids.EVIDENCE_BUNDLE,
                     _bundle([evidence_item("https://x.example/p", "Practice.",
                                            CATS.EXTERNAL_PRACTICES)],
                             {"need.external_practices": NeedStatus.PARTIAL}))
        after = self.run_research(resume(self.inv, asked, [self.native, host]), self.ctx_)
        self.assertNotIn(RK.EVIDENCE, [r.kind for r in after.requests])

    def test_a_required_host_only_need_still_pauses_in_the_first_wave(self) -> None:
        self.params["need"] = {"prior_decisions": 0.9, "external_practices": 0.9}
        first = self.run_research(self.goal(), self.ctx())
        self.assertIn(["host.research"], self.sources_of(first))

    def test_authoritative_guidance_has_native_project_sources(self) -> None:
        native = [s for s in load_kernel_config().sources
                  if CATS.AUTHORITATIVE_GUIDANCE in s.categories and s.kind == "repo_text"]
        self.assertTrue(native)


class TestPathsSurviveRedaction(unittest.TestCase):
    """Repo paths are not high-entropy secrets; real secrets are still masked."""

    def setUp(self) -> None:
        self.redactor = Redactor({}, load_kernel_config().data_policy)

    def test_ticket_style_locators_are_kept(self) -> None:
        for path in ("tickets/01_todo/15_TICKET-20260826-ACD-2100c-3.md",
                     "tickets/00_inbox/TICKET-20260930-KernelBootstrapV0.md#L10-L30",
                     "docs/acceptance-criteria/build_pipeline/BP-1100-phantom-done-prevention/"
                     "BP-1100b-4.yaml"):
            with self.subTest(path=path):
                self.assertEqual(self.redactor.mask_text(path), path)
                self.assertEqual(self.redactor.mask({"locator": path})["locator"], path)

    def test_secret_looking_tokens_are_still_masked(self) -> None:
        secret = "".join(["Zk3Qw9Xv", "7Lp2Rt5Y", "b8Nc1Mh4", "Gd6Fs0Ja", "E2uW"])  # built at runtime
        for text in (f"token is {secret} ok", f"secrets/{secret}.md", f"/{secret}"):
            with self.subTest(text=text):
                self.assertNotIn(secret, self.redactor.mask_text(text))


class TestApprovalEvidenceIds(DecisionTestCase):
    """The approval question lists the evidence the proposed options cite."""

    def test_the_approval_payload_carries_the_union_of_cited_evidence(self) -> None:
        from kernel.contracts.decision import Option
        from kernel.contracts.payloads import HumanQuestionRequestPayload, OptionsPayload
        ev = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        self.evidence = [ev]
        ctx = self.ctx()
        inv, _, waiting = self.first(options=False)
        proposed = [Option(id=i, title=i, proposal_status=ProposalStatus("proposed"),
                           approval_status=ApprovalStatus("proposed"), source_refs=[ev.id]) for i in "ab"]
        out = child(ctx, RK.OPTIONS, schema_ids.OPTIONS,
                    OptionsPayload(options=proposed).model_dump(mode="json"))
        asked = self.run_decision(resume(inv, waiting, [out]), ctx)
        body = HumanQuestionRequestPayload.model_validate(asked.requests[0].payload)
        self.assertEqual(body.evidence_ids, [ev.id])


class TestSynthesisReachesOptionsPacket(DecisionTestCase):
    """Accepted findings go into the options request instead of being re-derived."""

    def test_findings_of_a_synthesis_child_are_in_the_options_request(self) -> None:
        ctx = self.ctx()
        payload = {"findings": [{"id": "find-bbbbbbbbbbbbbbbb", "claim": "AC-1 is blocked.",
                                 "kind": "inference", "producer": "host.synthesize"}]}
        out = child(ctx, RK.SYNTHESIS, schema_ids.FINDINGS, payload)
        body = self.first(options=False)[0].input_payload
        inv = invocation(DECISION, schema_ids.DECISION_REQUEST, body, outcomes=[out])
        work = load_working(inv, ctx)
        request = OptionsRequestPayload.model_validate(options_request(work, 5).payload)
        self.assertEqual(request.findings, ["[find-bbbbbbbbbbbbbbbb] AC-1 is blocked."])


class TestLineAwareCuts(unittest.TestCase):
    """An over-long excerpt is cut at a line or sentence end, still marked truncated."""

    def cfg(self, cap: int):
        base = load_kernel_config().retrieval
        return base.model_copy(update={"max_excerpt_chars": cap, "excerpt_context_lines": 20})

    def test_the_cut_falls_on_a_line_boundary(self) -> None:
        lines = [f"line {n:02d} mentions tests here" for n in range(30)]
        cand = _candidate("a.md", "s", lines, ["tests"], self.cfg(100), None)
        self.assertTrue(narrow(cand).truncated)
        self.assertLessEqual(len(narrow(cand).excerpt), 100)
        self.assertTrue(all(line in lines for line in narrow(cand).excerpt.split("\n")))

    def test_a_single_long_line_is_cut_at_a_sentence_end(self) -> None:
        text = "Tests are saved here. " * 20
        cand = _candidate("a.md", "s", [text], ["tests"], self.cfg(100), None)
        self.assertTrue(narrow(cand).truncated)
        self.assertTrue(narrow(cand).excerpt.endswith("."), narrow(cand).excerpt)


class TestGapTraceLinks(unittest.TestCase):
    """Gap rows and drafts name the traces of their example runs."""

    URL = "https://cloud.langfuse.com/project/p/traces/abc"

    def _gap(self, **changes: Any) -> CapabilityGap:
        fields: dict[str, Any] = dict(
            id="gap-0000000000000001", gap_key="k" * 16, gap_type=GapType.HOST_ONLY,
            goal="g", normalized_need="options", request_kind="options",
            input_schema="i.v1", output_schema="o.v1", created_at=NOW, first_seen=NOW,
            last_seen=NOW, example_trace_urls=[self.URL])
        fields.update(changes)
        return CapabilityGap(**fields)

    def test_aggregation_keeps_each_trace_url_once(self) -> None:
        other = "https://cloud.langfuse.com/project/p/traces/def"
        merged = aggregate_gaps([self._gap(), self._gap(id="gap-0000000000000002",
                                                         example_trace_urls=[other, self.URL])])
        self.assertEqual(merged[0].example_trace_urls, [self.URL, other])

    def test_the_draft_lists_the_trace_links(self) -> None:
        store = MemoryGapStore()
        stored = publish_gap(store, self._gap())
        self.assertIn(self.URL, store.drafts[narrow(narrow(narrow(stored).proposal).draft_ref)])
        self.assertIn(self.URL, render_gap_draft(self._gap()))

    def test_a_new_observation_takes_the_runs_trace_url(self) -> None:
        request = Request(id="req-0000000000000001", kind=RK.OPTIONS, goal="g",
                          payload_schema=schema_ids.OPTIONS_REQUEST,
                          payload={"problem": "g"},
                          requested_output_schema=schema_ids.OPTIONS)
        state: Any = {"run_id": "run-0000000000000001",
                 "task": SimpleNamespace(scope=SimpleNamespace(component_ids=[])),
                 "registry": SimpleNamespace(content_hash="h"),
                 "trace": TraceState(trace_id="abc", trace_url=self.URL)}
        item: Any = SimpleNamespace(id="work-0000000000000001", attempts=0)
        gap = build_gap(state, item, request, None, GapType.HOST_ONLY, NOW)
        self.assertEqual(gap.example_trace_urls, [self.URL])


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-02 [python-coder]: Tests for the third live round written first and seen failing.
#   (#KernelBootstrapV0/GROUND)
# ====================================================================
