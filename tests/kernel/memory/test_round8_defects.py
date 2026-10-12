"""
MODULE: tests.kernel.memory.test_round8_defects
GOAL: One proving test group per defect of the round-8 live decision: (a) a human-added option
    shows the evidence its claims were researched against, (b) the decision report carries its
    trace_refs, (c) report.md has a readable Decision section, (d) limitations are deduplicated and
    retrieval cut notes collapse to one line per need, (e) a criterion assessment cites the
    evidence relevant to it instead of every evidence id, (f) a contract or class an option names
    is fetched by `path::Symbol` as well as by file.
BUSINESS CONTEXT: Round 8 resolved the decision that chose the record format and exposed these six
    defects in its report and ranked packet; each is fixed with a test that fails on the old code.
ARCHITECTURE: (a), (d) and (e) run the real DecisionExecutor with a scripted Jev; (b) and (c) test
    the pure helpers the scheduler calls; (f) runs research planning over a throwaway repository.
"""

from __future__ import annotations

import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from kernel.capabilities.criterion_evidence import relevant_evidence_ids
from kernel.capabilities.research.limitations import (
    SUMMARY_PREFIX,
    collapse_for_decision,
    is_cut_note,
    merge_limitations,
)
from kernel.capabilities.research.planning import resolve_sources
from kernel.capabilities.research.state import Plan
from kernel.capabilities.research.targeting import symbols_named, with_symbol_locators
from kernel.contracts import schema_ids
from kernel.contracts.decision import Decision, Rationale
from kernel.contracts.enums import (
    ApprovalStatus,
    DecisionStatus,
    EvidenceCategory,
    Priority,
    RequestKind,
    ResultStatus,
)
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.payloads import (
    DecisionReportPayload,
    HumanQuestionRequestPayload,
    OptionContext,
)
from kernel.contracts.run import OutputRef, TraceRefs, with_trace_refs
from kernel.intent.decision_text import ReportContext, decision_lines
from tests.kernel.capabilities.support import child, evidence_item, resume
from tests.kernel.capabilities.test_decision_graph import DecisionTestCase
from tests.kernel.capabilities.test_design_ending import EXTRA, DesignCase
from tests.kernel.helpers import as_json, make_context
from tests.kernel.memory.support import CHECKOUT, evidence_item as kernel_evidence

#: Lines as the live round-8 report carried them (the counts differ from round to round).
LIVE_CUTS = [
    "candidate pool capped at 60 (retrieval.max_candidates): 357 of 417 candidate(s) from 10 "
    "source(s) were not offered",
    "40 of 60 candidate(s) were not judged (retrieval.rerank_max_per_need=20, rerank_max_batches=3, "
    "batches allowed here 3); strongest not judged: docs/analysis/trace-review.md#L27-L35 (score 9)",
    "repo.docs: 779 lower-ranked section(s) cut at the source cap of 60 candidates (474 files "
    "scanned, max_candidates=60); 413 matching file(s) had no section offered",
    "repo.analysis: 80 lower-ranked section(s) cut at the source cap of 60 candidates (47 files)",
    "knowledge.components: 50 nodes cut at the source cap of 60 (max_candidates=60)",
    "repo.patterns: 211 item(s) skipped (binary)"]
KEPT = ["need need.existing_patterns: the evidence matched the topic but did not answer the "
        "question (answer judgement 0.45, below 0.7)"]


class TestA_AHumanAddedOptionCitesItsClaimEvidence(DesignCase):
    """The evidence a claim need found is linked to the option it checked."""

    def setUp(self) -> None:
        super().setUp()
        self.params["design"] = {"c1"}
        self.inv, self.ctx_, self.waiting = self.start()

    def ranked_after_the_claim_round(self, linked: bool) -> HumanQuestionRequestPayload:
        added = child(self.ctx_, RequestKind.HUMAN, schema_ids.HUMAN_ANSWER, {
            "added_options": [{"title": "Hybrid", "description": "Both"}]}
        ).model_copy(update={"actor_id": "human:ada"})
        again = self.run_decision(resume(self.inv, self.waiting, [added]), self.ctx_)
        ctx = self.ctx(self.evidence + [EXTRA])
        bundle = {"evidence_ids": [EXTRA.id],
                  "need_evidence": {"need.claim.opt.added.1": [EXTRA.id]} if linked else {}}
        done = self.run_decision(resume(self.inv, again, [child(
            ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, bundle)]), ctx)
        return self.question(done)

    def test_the_ranked_packet_cites_the_evidence_the_claims_were_researched_against(self) -> None:
        # covers: DK-600b-2-i
        question = self.ranked_after_the_claim_round(linked=True)
        choice = next(c for c in question.choices if c.id == "opt.added.1")
        self.assertIn("docs/more.md#L1-L2", choice.consequences)
        self.assertNotIn("no evidence cited", choice.consequences)
        self.assertIn(EXTRA.id, question.evidence_ids)

    def test_without_claim_evidence_the_option_still_says_so(self) -> None:
        choice = next(c for c in self.ranked_after_the_claim_round(linked=False).choices
                      if c.id == "opt.added.1")
        self.assertIn("no evidence cited", choice.consequences)


class TestB_TheReportCarriesItsTraceRefs(unittest.TestCase):
    """The decision_report payload used to say `trace_refs: null`."""

    def test_a_decision_report_gets_the_run_trace(self) -> None:
        output = OutputRef(schema_id=schema_ids.DECISION_REPORT,
                           payload={"status": "resolved", "trace_refs": None})
        filled = with_trace_refs(output, TraceRefs(trace_id="a" * 32, trace_url="https://x/t"))
        assert filled is not None
        report = DecisionReportPayload.model_validate({
            **filled.payload, "selected_option_id": "A"})
        self.assertEqual(report.trace_refs.trace_id, "a" * 32)  # type: ignore[union-attr]
        self.assertEqual(report.trace_refs.trace_url, "https://x/t")  # type: ignore[union-attr]

    def test_other_outputs_and_a_missing_output_are_left_alone(self) -> None:
        refs = TraceRefs(trace_id="a" * 32)
        other = OutputRef(schema_id=schema_ids.EVIDENCE_BUNDLE, payload={"evidence_ids": []})
        self.assertEqual(with_trace_refs(other, refs), other)
        self.assertIsNone(with_trace_refs(None, refs))


class TestC_TheReportHasADecisionSection(unittest.TestCase):
    """Choice, approver, rationale, precedent used and key evidence, in words."""

    def context(self) -> tuple[dict, ReportContext]:
        picked = kernel_evidence("docs/a.md#L1-L5", "Use YAML records, one file per decision.")
        precedent = kernel_evidence("docs/decisions/dec-0123456789abcdef.yaml", "Earlier choice.")
        precedent = precedent.model_copy(update={"source": precedent.source.model_copy(update={
            "title": "Precedent dec-0123456789abcdef approved by human:tester on 2026-10-01"})})
        decision = Decision(
            id="dec-ef8ddcb79d668a67", question="How should records be filed?",
            option_ids=["A"], selected_option_id="A", status=DecisionStatus.RESOLVED,
            approval_status=ApprovalStatus.APPROVED, evidence_ids=[picked.id, precedent.id],
            rationale=Rationale(text="The human chose A.", origin="template"),
            approved_by="human:user", approved_at=datetime(2026, 10, 1, 14, 48, tzinfo=UTC),
            precedent_ids=["dec-0123456789abcdef"])
        payload = {"status": "resolved", "recommendation": "One YAML file per decision",
                   "selected_option_id": "A", "approval_status": "approved",
                   "rationale": {"text": "The human chose A.", "origin": "template"},
                   "supporting_evidence_ids": [picked.id]}
        return payload, ReportContext(decisions=[decision], evidence={
            picked.id: picked, precedent.id: precedent})

    def test_the_section_names_the_choice_the_approver_the_rationale_and_the_evidence(self) -> None:
        payload, context = self.context()
        text = "\n".join(decision_lines(payload, context))
        self.assertIn("## Decision", text)
        self.assertIn("Choice: One YAML file per decision (`A`)", text)
        self.assertIn("Approval: approved by human:user on 2026-10-01 14:48 UTC", text)
        self.assertIn("Rationale: The human chose A.", text)
        self.assertIn("- Precedent dec-0123456789abcdef approved by human:tester on 2026-10-01 "
                      "(docs/decisions/dec-0123456789abcdef.yaml)", text)
        self.assertIn("- docs/a.md#L1-L5: Use YAML records, one file per decision.", text)

    def test_an_unresolved_report_says_no_option_was_chosen(self) -> None:
        text = "\n".join(decision_lines({"status": "needs_human", "open_questions": ["Which?"]},
                                        ReportContext()))
        self.assertIn("No option was chosen (status: needs_human)", text)
        self.assertIn("- Which?", text)
        self.assertIn("- None.", text)


class TestD_LimitationsAreTidy(DecisionTestCase):
    """Retrieval cut notes collapse to one summary line per need; repeats are dropped."""

    def test_cut_notes_are_recognised_and_other_limitations_are_not(self) -> None:
        self.assertTrue(all(is_cut_note(line) for line in LIVE_CUTS))
        self.assertFalse(any(is_cut_note(line) for line in KEPT))

    def test_many_notes_of_one_need_become_one_line(self) -> None:
        lines = collapse_for_decision([*LIVE_CUTS, *KEPT], {"need.existing_patterns": LIVE_CUTS})
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0], KEPT[0])
        summary = lines[1]
        self.assertTrue(summary.startswith(f"{SUMMARY_PREFIX}need.existing_patterns:"))
        for fragment in ("357 of 417 candidates not offered", "40 of 60 candidates not judged",
                         "repo.docs 779", "repo.analysis 80", "knowledge.components 50",
                         "211 unreadable"):
            self.assertIn(fragment, summary)

    def test_each_need_gets_its_own_line_and_an_unclaimed_note_is_unattributed(self) -> None:
        lines = collapse_for_decision(
            LIVE_CUTS[:2] + LIVE_CUTS[2:4],
            {"need.a": LIVE_CUTS[:2], "need.b": [LIVE_CUTS[2]]})
        starts = sorted(line.split(":", 1)[0] for line in lines)
        self.assertEqual(starts, [f"{SUMMARY_PREFIX}need.a", f"{SUMMARY_PREFIX}need.b",
                                  f"{SUMMARY_PREFIX}unattributed"])

    def test_a_later_round_replaces_the_summary_of_the_same_need_and_repeats_vanish(self) -> None:
        first = collapse_for_decision(LIVE_CUTS, {"need.x": LIVE_CUTS})
        newer = collapse_for_decision(LIVE_CUTS[:2], {"need.x": LIVE_CUTS[:2]})
        merged = merge_limitations(merge_limitations(KEPT, first), [*newer, *KEPT, *newer])
        self.assertEqual(len([x for x in merged if x.startswith(SUMMARY_PREFIX)]), 1)
        self.assertEqual(merged.count(KEPT[0]), 1)
        self.assertNotIn("repo.docs 779", " ".join(merged))

    def test_a_decision_that_absorbs_noisy_bundles_reports_a_short_limitation_list(self) -> None:
        self.params.update(sufficient=0.2, missing="missing_internal_principle")
        inv, ctx, waiting = self.first()
        extra = evidence_item("docs/conv.md#L1-L2", "Always use rollback.",
                              EvidenceCategory.INTERNAL_PRINCIPLES)
        ctx = self.ctx(self.evidence + [extra])
        bundle = {"evidence_ids": [extra.id], "limitations": [*LIVE_CUTS, *KEPT, *LIVE_CUTS],
                  "need_limitations": {"need.internal_principles": LIVE_CUTS}}
        out = child(ctx, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, bundle)
        again = self.run_decision(resume(inv, waiting, [out]), ctx)
        self.assertEqual(again.status, ResultStatus.WAITING)
        cuts = [x for x in again.limitations if x.startswith(SUMMARY_PREFIX)]
        self.assertEqual(len(cuts), 1)
        self.assertFalse([x for x in again.limitations if is_cut_note(x) and
                          not x.startswith(SUMMARY_PREFIX)])
        self.assertEqual(again.limitations.count(KEPT[0]), 1)


class TestE_AssessmentsCiteRelevantEvidence(DecisionTestCase):
    """A criterion assessment cites the evidence that bears on it, not all of it."""

    SAFE = evidence_item("docs/db.md#L1-L3", "SQLite is safe for concurrent writers.")
    SIMPLE = evidence_item("docs/ops.md#L1-L3", "Plain files are simple to operate.")
    NOISE = evidence_item("docs/pricing.md#L1-L2", "The pricing page uses a carousel.")

    def setUp(self) -> None:
        super().setUp()
        self.evidence = [self.SAFE, self.SIMPLE, self.NOISE]
        self.params["satisfies"] = {("c1", "A"): 0.95, ("c2", "A"): 0.9}

    def test_each_criterion_cites_its_own_evidence_and_not_everything(self) -> None:
        _, _, result = self.first()
        report = DecisionReportPayload.model_validate(result.output_payload)
        by_criterion: dict[str, set[str]] = {}
        for assessment in report.criterion_assessments:
            by_criterion.setdefault(assessment.criterion_id, set()).update(assessment.evidence_ids)
        self.assertEqual(by_criterion["c1"], {self.SAFE.id})
        self.assertEqual(by_criterion["c2"], {self.SIMPLE.id})
        cited = set().union(*by_criterion.values())
        self.assertNotIn(self.NOISE.id, cited)  # irrelevant evidence is not cited anywhere
        self.assertTrue(all(len(a.evidence_ids) < len(self.evidence)
                            for a in report.criterion_assessments))

    def test_evidence_an_option_cites_comes_first(self) -> None:
        ranked = relevant_evidence_ids(self.evidence, "Is it safe?", limit=3, min_overlap=2,
                                       cited=[self.NOISE.id])
        self.assertEqual(ranked[0], self.NOISE.id)

    def test_the_number_cited_is_bounded_by_configuration(self) -> None:
        many = [evidence_item(f"docs/m{i}.md#L1-L2", "safe concurrent writers everywhere")
                for i in range(8)]
        self.assertEqual(len(relevant_evidence_ids(many, "safe concurrent writers", limit=5,
                                                   min_overlap=2)), 5)

    def test_a_weak_match_still_cites_the_best_item(self) -> None:
        ids = relevant_evidence_ids(self.evidence, "Is it safe?", limit=5, min_overlap=2)
        self.assertEqual(ids, [self.SAFE.id])
        self.assertEqual(relevant_evidence_ids(self.evidence, "zebra quartz", limit=5,
                                               min_overlap=2), [])


class TestF_NamedSymbolsAreFetchedBySymbol(unittest.TestCase):
    """`Decision contract` plus a cited kernel/contracts/decision.py means `...decision.py::Decision`."""

    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        (self.root / "kernel" / "contracts").mkdir(parents=True)
        (self.root / "kernel" / "contracts" / "decision.py").write_text(
            "class Decision:\n    status: str\n\n\ndef helper():\n    return 1\n", encoding="utf-8")
        (self.root / "docs").mkdir()
        (self.root / "docs" / "note.md").write_text("# Decision\ntext\n", encoding="utf-8")

    def test_names_are_read_from_prose_and_backticks(self) -> None:
        self.assertEqual(symbols_named(["the Decision contract and `Option`, a Foo class"]),
                         ["Decision", "Option", "Foo"])
        self.assertEqual(symbols_named(["no names here at all"]), [])

    def test_the_symbol_locator_follows_the_file_that_defines_it(self) -> None:
        found = with_symbol_locators(self.root, ["kernel/contracts/decision.py"],
                                     ["Reuse the Decision contract fields"])
        self.assertEqual(found, ["kernel/contracts/decision.py",
                                 "kernel/contracts/decision.py::Decision"])

    def test_no_symbol_is_added_for_a_name_the_file_does_not_define(self) -> None:
        found = with_symbol_locators(self.root, ["kernel/contracts/decision.py"],
                                     ["the Criterion class"])
        self.assertEqual(found, ["kernel/contracts/decision.py"])

    def test_only_python_files_without_an_anchor_get_a_symbol(self) -> None:
        found = with_symbol_locators(self.root, ["docs/note.md", "kernel/contracts/decision.py#L1-L2"],
                                     ["the Decision contract"])
        self.assertEqual(found, ["docs/note.md", "kernel/contracts/decision.py#L1-L2"])

    def test_research_planning_asks_the_retrieval_child_for_the_symbol(self) -> None:
        plan = Plan(
            question="How should records be filed?", expected_coverage="best_effort", mandated=[],
            source_restrictions=[], options=[OptionContext(
                option_id="opt.a", title="Kernel contract YAML",
                description="Fields mirror the Decision contract in kernel/contracts/decision.py",
                cited_refs=["kernel/contracts/decision.py"])])
        need = EvidenceNeed(id="need.existing_patterns", category=EvidenceCategory.EXISTING_PATTERNS,
                            question="How is it done?", priority=Priority.REQUIRED)
        ctx = make_context(self.root)
        resolution = resolve_sources(ctx, [need], plan)
        locators = [loc for r in resolution.requests
                    for loc in as_json(r.payload)["explicit_locators"]]
        self.assertIn("kernel/contracts/decision.py", locators)
        self.assertIn("kernel/contracts/decision.py::Decision", locators)

    def test_the_real_contract_file_holds_the_class_a_symbol_locator_would_fetch(self) -> None:
        found = with_symbol_locators(CHECKOUT, ["kernel/contracts/decision.py"],
                                     ["Decision contract"])
        self.assertIn("kernel/contracts/decision.py::Decision", found)


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Each round-8 defect (a-f) has a test group that fails on the code
#   before the fix: the packet text, the report payload, the Decision section, the limitation
#   count, the evidence cited per criterion and the symbol locator. (#KernelDecisionStore)
# ====================================================================
