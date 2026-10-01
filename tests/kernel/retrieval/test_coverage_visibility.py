"""
MODULE: tests.kernel.retrieval.test_coverage_visibility
GOAL: Prove that partial coverage and synthesis unknowns are visible when an evidence run
    completes: in the result's limitations (so the envelope shows them) and in the report's
    Coverage and Unknowns sections, and that key evidence is ordered by judged relevance.
BUSINESS CONTEXT: A regression pass ended `completed` with every need partial (answer judgements
    0.37, 0.54, 0.41), an empty envelope `limitations` and no limitations, coverage or unknowns
    section in report.md: result limitations were kept only when a REQUIRED need was unsatisfied,
    and evidence plans never reach the required threshold. An unrelated table also ranked first.
ARCHITECTURE: The research graph runs through ResearchExecutor with scripted Jev (the planning
    batch marks the need supporting, a child bundle reports it partial); report text is built by
    the pure `output_sections` function.
"""

from __future__ import annotations

from kernel.capabilities.research.results import coverage_summary
from kernel.capabilities.research.state import Collected, ResearchContinuation
from kernel.contracts import schema_ids
from kernel.contracts.enums import EvidenceCategory, NeedStatus, Priority, RequestKind, ResultStatus
from kernel.contracts.evidence import EvidenceNeed
from kernel.intent.report_text import output_sections
from tests.kernel.capabilities.support import child, evidence_item, resume
from tests.kernel.capabilities.test_research_graph import ResearchCase, _bundle

NOISE = "repo.docs: 1059 lower-ranked section(s) cut at the source cap of 60 candidates"
UNKNOWN = "no file-type filter vocabulary was found"


class TestACompletedRunShowsPartialCoverage(ResearchCase):
    """Goal 5 of the regression pass: completed, every need partial, nothing said."""

    def setUp(self) -> None:
        super().setUp()
        self.params["need"] = {"prior_decisions": 0.6}  # supporting: below the required bar
        self.params["evaluable"] = 0.3
        self.ctx_, self.inv = self.ctx(), self.goal()
        self.waiting = self.run_research(self.inv, self.ctx_)

    def finish(self):  # noqa: ANN201
        item = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        kids = [child(self.ctx_, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, _bundle(
            [item], {"need.prior_decisions": NeedStatus.PARTIAL}, limitations=[NOISE]))]
        asked = self.run_research(resume(self.inv, self.waiting, kids), self.ctx_)
        findings = child(self.ctx_, RequestKind.SYNTHESIS, schema_ids.FINDINGS,
                         {"findings": [], "unknowns": [UNKNOWN]})
        return self.run_research(resume(self.inv, asked, [findings]), self.ctx_)

    def test_the_run_completes_and_its_result_limitations_name_what_is_partial(self) -> None:
        done = self.finish()
        self.assertEqual(done.status, ResultStatus.COMPLETED)  # no required need: not `partial`
        self.assertIn("coverage: need need.prior_decisions (prior_decisions) is partial",
                      done.limitations)
        self.assertIn(f"unresolved: {UNKNOWN}", done.limitations)

    def test_source_cut_notes_stay_in_the_bundle_not_in_the_envelope_limitations(self) -> None:
        done = self.finish()
        self.assertFalse([x for x in done.limitations if NOISE in x])
        self.assertIn(NOISE, self.bundle(done).limitations)  # nothing is lost

    def test_a_fully_satisfied_run_adds_no_coverage_limitations(self) -> None:
        self.params["evaluable"] = 0.95
        item = evidence_item("docs/a.md#L1-L2", "Use sqlite.")
        kids = [child(self.ctx_, RequestKind.EVIDENCE, schema_ids.EVIDENCE_BUNDLE, _bundle(
            [item], {"need.prior_decisions": NeedStatus.SATISFIED}))]
        done = self.run_research(resume(self.inv, self.waiting, kids), self.ctx_)
        self.assertEqual(done.limitations, [])


class TestCoverageSummary(ResearchCase):
    """The summary keeps coverage, answer-aware notes and unknowns, and drops the noise."""

    def test_answer_notes_dropped_needs_and_unknowns_are_kept_and_source_cut_notes_are_not(
            self) -> None:
        need = EvidenceNeed(id="need.x", category=EvidenceCategory.TASK_CONTEXT,
                            priority=Priority.SUPPORTING, question="q")
        cont = ResearchContinuation(needs=[need])
        out = Collected(coverage={"need.x": NeedStatus.PARTIAL}, unknowns=[UNKNOWN, UNKNOWN])
        lines = coverage_summary(cont, out, [
            "need need.x: the evidence matched the topic but did not answer the question "
            "(answer judgement 0.37, below 0.7)",
            "need need.y not researched: 3 Jev call(s) are left", NOISE])
        self.assertEqual(lines, [  # a need the budget dropped is as visible as a partial one
            "coverage: need need.x (task_context) is partial",
            "need need.x: the evidence matched the topic but did not answer the question "
            "(answer judgement 0.37, below 0.7)",
            "need need.y not researched: 3 Jev call(s) are left",
            f"unresolved: {UNKNOWN}"])


class TestTheReportSections(ResearchCase):
    """The report has Coverage and Unknowns sections and shows the most relevant evidence first."""

    PAYLOAD = {
        "coverage": {"need.prior_decisions": "partial", "need.task_context": "satisfied"},
        "unknowns": [UNKNOWN],
        "evidence": [
            {"source": {"locator": "docs/testing/README.md#L1-L9 (§Directory Placement)"},
             "excerpt": "An adopter template table.", "provenance": {"relevance": 0.71}},
            {"source": {"locator": "tests/README.md#L15-L39"}, "excerpt": "Tests are saved here.",
             "provenance": {"relevance": 0.93}},
            {"source": {"locator": "config/x.json#L1-L2"}, "excerpt": "Unjudged.",
             "provenance": {"relevance": None}}]}

    def text(self) -> str:
        return "\n".join(output_sections(schema_ids.EVIDENCE_BUNDLE, self.PAYLOAD))

    def test_coverage_and_unknowns_have_their_own_sections(self) -> None:
        text = self.text()
        self.assertIn("## Coverage", text)
        self.assertIn("- need.prior_decisions: partial", text)
        self.assertIn("## Unknowns", text)
        self.assertIn(f"- {UNKNOWN}", text)

    def test_key_evidence_is_ordered_by_judged_relevance_unjudged_last(self) -> None:
        text = self.text()
        first = text.index("tests/README.md#L15-L39")
        second = text.index("docs/testing/README.md#L1-L9")
        third = text.index("config/x.json#L1-L2")
        self.assertLess(first, second)
        self.assertLess(second, third)

    def test_a_bundle_without_coverage_or_unknowns_adds_no_empty_sections(self) -> None:
        text = "\n".join(output_sections(schema_ids.EVIDENCE_BUNDLE, {"evidence": []}))
        self.assertNotIn("## Coverage", text)
        self.assertNotIn("## Unknowns", text)


if __name__ == "__main__":
    import unittest
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Round E (D3, D7): partial coverage and unknowns reach the envelope
#   limitations and the report of a completed evidence run, and key evidence is shown best
#   relevance first. (#KernelV01/E)
# ====================================================================
