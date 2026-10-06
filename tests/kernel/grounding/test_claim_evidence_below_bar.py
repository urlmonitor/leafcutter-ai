"""
MODULE: tests.kernel.grounding.test_claim_evidence_below_bar
GOAL: A claim need (`need.claim.<option id>`) records the evidence its single-need child returned
    even when every item scores below the relevance bar, so the decision can still link that
    evidence to the human-added option; non-claim needs keep the relevance gate.
BUSINESS CONTEXT: Live run run-de1c989117414c1c: the claim children returned 5 and 6 items, all
    below the 0.7 bar, `need_evidence` stayed empty and the report said "no evidence cited" for
    an option research had in fact found evidence about.
ARCHITECTURE: Bundles are built with the real EvidenceBundlePayload and Evidence models and
    absorbed through the research collect node (`_absorb_bundle`); the end-to-end test feeds the
    Collected state through the real `bundle_result` and the decision's `_absorb_bundle`, which
    calls `_link_claim_evidence`, then reads the option's `source_refs`.
"""

from __future__ import annotations

import unittest

from kernel.capabilities.decision.loading import _absorb_bundle as decision_absorb_bundle
from kernel.capabilities.decision.state import DecisionContinuation, Working
from kernel.capabilities.research.collect import _absorb_bundle
from kernel.capabilities.research.results import bundle_result
from kernel.capabilities.research.state import Collected, Plan, ResearchContinuation
from kernel.contracts import schema_ids
from kernel.contracts.decision import Option
from kernel.contracts.enums import EvidenceCategory, NeedStatus, ProposalStatus
from kernel.contracts.evidence import Evidence, EvidenceBundlePayload, EvidenceNeed
from tests.kernel.capabilities.support import evidence_item, invocation

BAR = 0.7
CLAIM_NEED = "need.claim.opt.added.1"
PATTERN_NEED = "need.existing_patterns"


def _scored(locator: str, relevance: float,
            category: EvidenceCategory = EvidenceCategory.PRIOR_DECISIONS) -> Evidence:
    """Return an evidence item whose provenance carries the given relevance."""
    item = evidence_item(locator, f"Excerpt of {locator}.", category)
    prov = item.provenance.model_copy(update={"relevance": relevance})
    return item.model_copy(update={"provenance": prov})


def _bundle(need_id: str, items: list[Evidence]) -> dict:
    """Return a single-need evidence_bundle.v1 payload."""
    return EvidenceBundlePayload(
        evidence_ids=[e.id for e in items], evidence=items,
        coverage={need_id: NeedStatus.PARTIAL},
        attempted_sources=["repo.decisions"]).model_dump(mode="json")


BELOW_BAR = [_scored(f"docs/claim{i}.md#L1-L2", 0.2 + 0.05 * i) for i in range(5)]


class TestClaimEvidenceBelowBar(unittest.TestCase):
    """The claim child's evidence is recorded below the bar; other needs stay gated."""

    def test_claim_need_records_evidence_below_the_bar(self) -> None:
        out = Collected()
        _absorb_bundle(out, _bundle(CLAIM_NEED, BELOW_BAR), BAR)
        self.assertEqual(sorted(out.need_evidence.get(CLAIM_NEED, [])),
                         sorted(e.id for e in BELOW_BAR))

    def test_claim_evidence_retains_its_conditional_assessment(self) -> None:
        # covers: KM-500f-2
        # angle: seam
        payload = _bundle(CLAIM_NEED, BELOW_BAR)
        report = {"status": "unresolved", "limitations": ["Historical proof is unverified."]}
        payload["assessments"] = {CLAIM_NEED: report}
        out = Collected()
        _absorb_bundle(out, payload, BAR)
        self.assertEqual(out.assessments[CLAIM_NEED], report)
        self.assertEqual(sorted(out.need_evidence[CLAIM_NEED]), sorted(e.id for e in BELOW_BAR))
        self.assertEqual(out.coverage[CLAIM_NEED], NeedStatus.PARTIAL)

    def test_non_claim_need_keeps_the_relevance_gate(self) -> None:
        items = [_scored(f"docs/pattern{i}.md#L1-L2", 0.3, EvidenceCategory.EXISTING_PATTERNS)
                 for i in range(3)]
        out = Collected()
        _absorb_bundle(out, _bundle(PATTERN_NEED, items), BAR)
        kept = out.need_evidence.get(PATTERN_NEED, [])
        self.assertEqual([i for i in kept if i in {e.id for e in items}], [])

    def test_collected_claim_evidence_links_to_the_human_added_option(self) -> None:
        out = Collected()
        _absorb_bundle(out, _bundle(CLAIM_NEED, BELOW_BAR), BAR)
        need = EvidenceNeed(id=CLAIM_NEED, category=EvidenceCategory.PRIOR_DECISIONS,
                            question="Is the added option's claim supported?")
        cont = ResearchContinuation(needs=[need])
        plan = Plan(question="Q?", expected_coverage="best_effort", mandated=[need],
                    source_restrictions=[])
        inv = invocation("research", schema_ids.RESEARCH_REQUEST, {})
        result = bundle_result(inv, plan, cont, out, [])
        payload = result.output_payload
        assert payload is not None
        option = Option(id="opt.added.1", title="Hybrid", proposal_status=ProposalStatus.SUPPLIED)
        work = Working(question="Q?", cont=DecisionContinuation(), options=[option], criteria=[],
                       approval_required=False, constraint_ids=[])
        decision_absorb_bundle(work, payload, {})
        linked = work.options[0].source_refs
        self.assertEqual(sorted(linked), sorted(e.id for e in BELOW_BAR))


if __name__ == "__main__":
    unittest.main()
