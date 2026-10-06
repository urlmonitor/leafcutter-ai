"""
MODULE: kernel.capabilities.research.results
GOAL: Build the research capability's results: `waiting` (child retrievals or a synthesis
    request) and the final evidence bundle (completed, or partial when a required need is
    unsatisfied).
BUSINESS CONTEXT: The bundle is the contract with the decision capability: coverage per need,
    attempted and unavailable sources, limitations, contradictions and truncation must all be
    explicit so nothing unknown is presented as complete (Rev 3 sections 10.2 and 10.5).
ARCHITECTURE: Pure functions over the continuation and the collected state.
"""

from __future__ import annotations

from kernel.capabilities.research.state import Collected, Plan, ResearchContinuation
from kernel.contracts import schema_ids
from kernel.contracts.capability import CapabilityResult, Usage
from kernel.contracts.enums import NeedStatus, Priority, RequestKind, ResultStatus
from kernel.contracts.evidence import EvidenceBundlePayload
from kernel.contracts.payloads import SynthesisRequestPayload
from kernel.contracts.work import CapabilityInvocation, RequestProposal

SYNTHESIS_OPERATION = "synthesize_evidence"


def _synthesis_request(question: str, out: Collected) -> RequestProposal:
    """Ask the host to synthesize the collected evidence (explain, never resolve conflicts).

    Args:
        question: Original research question.
        out: Collected evidence, per-need assessments and coverage.

    Returns:
        Existing synthesis request with evidence-only obligations.
    """
    payload = SynthesisRequestPayload(
        operation=SYNTHESIS_OPERATION, question=question, evidence_ids=sorted(out.evidence),
        output_requirements=["answer only from the listed evidence",
                             "report disagreements without choosing between them"])
    return RequestProposal(
        kind=RequestKind.SYNTHESIS, question=question,
        payload_schema=schema_ids.SYNTHESIS_REQUEST, payload=payload.model_dump(mode="json"),
        requested_output_schema=schema_ids.FINDINGS)


def waiting_result(invocation: CapabilityInvocation, cont: ResearchContinuation,
                   requests: list[RequestProposal], usage: list[Usage], *,
                   synthesis: tuple[str, Collected] | None = None) -> CapabilityResult:
    """Build `waiting` for child retrievals, or for a synthesis when `synthesis` is given.

    Args:
        invocation: Current registered capability invocation.
        cont: Persisted research continuation.
        requests: Child requests to dispatch.
        usage: Measured provider usage.

    Returns:
        Waiting result with a durable continuation.

    Keyword-only synthesis: Optional question and collected state for synthesis.
    """
    if synthesis is not None:
        question, out = synthesis
        requests = [_synthesis_request(question, out)]
        cont = cont.model_copy(update={
            "phase": "synthesizing", "synthesized": True, "evidence": list(out.evidence.values()),
            "coverage": dict(out.coverage), "assessments": dict(out.assessments), "contradictions": out.contradictions,
            "limitations": out.limitations, "truncated": out.truncated,
            "attempted": out.attempted, "unavailable": out.unavailable,
            "unanswered": out.unanswered})
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.WAITING, requests=requests, usage=usage,
        continuation_state=cont.model_dump(mode="json"))


def coverage_summary(cont: ResearchContinuation, out: Collected, limitations: list[str]
                     ) -> list[str]:
    """Return the limitations a reader must see even when the run completed.

    A need that is only partly covered (required or not), the answer-aware notes behind it, a need
    the budget did not allow and what a synthesis could not find. The rest of the bundle's limitations (source cut notes and
    the like) stay in the bundle payload; the envelope would drown in them.
    """
    lines = [f"coverage: need {n.id} ({n.category.value}) is "
             f"{out.coverage.get(n.id, NeedStatus.OPEN).value}" for n in cont.needs
             if out.coverage.get(n.id, NeedStatus.OPEN) is not NeedStatus.SATISFIED]
    lines += [t for t in limitations if t.startswith(("need ", "required need "))]
    lines += [f"unresolved: {u}" for u in dict.fromkeys(out.unknowns)]
    return list(dict.fromkeys(lines))


def bundle_result(invocation: CapabilityInvocation, plan: Plan, cont: ResearchContinuation,
                  out: Collected, usage: list[Usage]) -> CapabilityResult:
    """Build the final bundle: partial if a required need is unsatisfied (all_required).

    Args:
        invocation: Current registered capability invocation.
        plan: Original scoped research plan.
        cont: Persisted research continuation.
        out: Collected evidence, per-need assessments and coverage.
        usage: Measured provider usage.

    Returns:
        Final bundle retaining explicit per-need coverage and assessments.
    """
    limitations = list(dict.fromkeys(out.limitations))
    unsatisfied = [n.id for n in cont.needs if n.priority is Priority.REQUIRED
                   and out.coverage.get(n.id) is not NeedStatus.SATISFIED]
    if not cont.needs:
        limitations.append("no evidence needs were identified for the question")
    limitations += [f"required need {i} is {out.coverage.get(i, NeedStatus.OPEN).value}"
                    for i in unsatisfied]
    summary = coverage_summary(cont, out, limitations)
    unavailable = {(u.source_id, u.reason): u for u in [*cont.unavailable, *out.unavailable]}
    bundle = EvidenceBundlePayload(
        evidence_ids=list(out.evidence), finding_ids=[f.id for f in out.findings],
        coverage=dict(out.coverage), assessments=dict(out.assessments), attempted_sources=out.attempted,
        unavailable_sources=list(unavailable.values()), contradictions=out.contradictions,
        limitations=limitations, truncated=out.truncated, evidence=list(out.evidence.values()),
        findings=out.findings, unknowns=list(dict.fromkeys(out.unknowns)),
        need_evidence={n: [i for i in ids if i in out.evidence]
                       for n, ids in out.need_evidence.items() if ids},
        need_limitations={n: notes for n, notes in out.need_notes.items() if notes})
    partial = bool(unsatisfied) and plan.expected_coverage == "all_required"
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.PARTIAL if partial else ResultStatus.COMPLETED,
        output_schema_id=schema_ids.EVIDENCE_BUNDLE,
        output_payload=bundle.model_dump(mode="json"), evidence=list(out.evidence.values()),
        findings=out.findings, usage=usage, limitations=limitations if partial else summary)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The bundle names, per need, the evidence that passed relevance, so
#   the decision can link a human-added option's claim evidence to that option (round 8 defect
#   a). (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: A completed bundle reports partial coverage, the answer-aware
#   notes and the synthesis unknowns in its result limitations (so the envelope shows them); they
#   used to be kept only when a REQUIRED need was unsatisfied, and evidence plans never reach the
#   required threshold. (#KernelV01/E)
# - 2026-10-01 [python-coder]: The bundle carries the synthesis unknowns, and a synthesis request
#   keeps the needs judged unanswered so a resume does not restore their `satisfied` status.
#   (#KernelV01/D)
# - 2026-09-30 23:00 [python-coder]: best_effort coverage completes even with unsatisfied
#   required needs, but the bundle still lists each one in limitations. (#KernelBootstrapV0/P5)
# ====================================================================
