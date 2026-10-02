"""
MODULE: kernel.capabilities.decision.emit
GOAL: The `emit` node: turn a verdict or a basis follow-up into a CapabilityResult (completed
    report, waiting with a typed child request, partial on no progress, or blocked).
BUSINESS CONTEXT: A needs_* outcome is never collapsed into a guessed answer: it becomes
    `waiting` with a child request, or `partial` with open questions when the evidence revision
    has not changed since the same request was made (Rev 3 sections 8.4 and 10.1).
ARCHITECTURE: followup_for maps a Verdict to a Followup; result builders read and rewrite the
    continuation. The rationale of a resolved decision is template-built (origin template),
    never Jev's hidden reasoning.
"""

from __future__ import annotations

from datetime import datetime

from kernel.capabilities.decision.budget_gate import LIMITATION
from kernel.capabilities.decision.combine import Verdict
from kernel.capabilities.decision.design_ending import choice_rationale, ranking_assessments
from kernel.capabilities.decision.jev_support import blocked_result
from kernel.capabilities.decision.ranking import BUDGET_RESERVE, DESIGN_ROUND
from kernel.capabilities.decision.requests import (
    DEFAULT_MAX_OPTIONS,
    Followup,
    decision_approval_request,
    escalation_request,
    options_request,
    research_request,
    synthesis_request,
)
from kernel.capabilities.decision.state import Working, version_of
from kernel.config import DecisionConfig
from kernel.contracts import schema_ids
from kernel.contracts.base import new_id
from kernel.contracts.capability import CapabilityResult
from kernel.contracts.decision import Criterion, Decision, Option, Rationale
from kernel.contracts.enums import (
    ApprovalStatus,
    DecisionStatus,
    EvidenceCategory,
    MissingKnowledge,
    ProposalStatus,
    ResultStatus,
)
from kernel.contracts.payloads import DecisionReportPayload
from kernel.contracts.work import CapabilityInvocation
from kernel.memory.models import DecisionRecord
from kernel.memory.precedent import reuse_option, reuse_rationale

_HUMAN_TEXT = {
    "tie": "Several options satisfy every required criterion. Which do you prefer?",
    "preference": "Choosing between the options depends on a preference or requirement that "
                  "is not stated. What should apply?",
    "conflict": "The evidence contradicts itself on a point that affects the decision, and "
                "synthesis could not settle it. How should it be resolved?",
    "uncertain": "The evidence is sufficient but the answer stays uncertain after synthesis. "
                 "How should the decision be made?",
    "unidentified_gap": "The decision cannot be made and the missing knowledge is not "
                        "identified. What is missing or which constraint applies?",
    "missing_task_fact": "A fact about the task is missing and no source supplies it. "
                         "Please provide it.",
}


def _research_asked_for(work: Working, category: EvidenceCategory) -> bool:
    """True if a research request naming this category was already emitted."""
    return any(k.startswith("research:") and category.value in k.split(":")[1]
               for k in work.cont.requested)


def _human_followup(work: Working, verdict: Verdict, reason: str) -> Followup:
    """Build a human escalation follow-up (approval of the decision or a ruling)."""
    rev = work.revision()
    if reason == "decision_approval":
        option = next(o for o in work.options if o.id == verdict.candidate_option_id)
        return Followup(
            status=DecisionStatus.NEEDS_HUMAN, key=f"decision_approval:{option.id}:{rev}",
            phase="awaiting_decision_approval", reason=reason, missing=verdict.missing,
            request=decision_approval_request(work, option), candidate_option_id=option.id,
            open_question="The recommendation awaits human approval.")
    tied = [o for o in work.usable_options if o.id in (verdict.tied or [])] \
        or work.usable_options
    return Followup(
        status=DecisionStatus.NEEDS_HUMAN, key=f"human:{reason}:{rev}", phase="awaiting_human",
        reason=reason, missing=verdict.missing or [
            MissingKnowledge.HUMAN_PREFERENCE_OR_AUTHORIZATION],
        request=escalation_request(work, reason, _HUMAN_TEXT.get(reason, _HUMAN_TEXT["preference"]),
                                   tied),
        open_question=_HUMAN_TEXT.get(reason, "A human answer is required."))


def followup_for(work: Working, verdict: Verdict, reserve: int = 0) -> Followup:
    """Map a needs_* verdict to the child request that can reduce the uncertainty.

    `reserve` is the Jev calls the decision keeps for its own final assessment; a research
    request carries it so research plans no more than the rest of the budget affords.
    """
    rev = work.revision()
    status = verdict.status
    if status is DecisionStatus.NEEDS_EVIDENCE:
        cats = verdict.categories
        if (EvidenceCategory.TASK_CONTEXT in cats
                and _research_asked_for(work, EvidenceCategory.TASK_CONTEXT)):
            return _human_followup(work, verdict, "missing_task_fact")
        key = "research:" + ",".join(sorted(c.value for c in cats)) + f":{rev}"
        key += f":{DESIGN_ROUND}" if verdict.reason == DESIGN_ROUND else ""
        names = ", ".join(c.value for c in cats)
        return Followup(status=status, key=key, phase="awaiting_evidence",
                        reason=verdict.reason, missing=verdict.missing,
                        request=research_request(work, cats, reserve),
                        open_question=f"Missing evidence: {names}.")
    if status is DecisionStatus.NEEDS_SYNTHESIS:
        return Followup(status=status, key=f"synthesis:{rev}", phase="awaiting_synthesis",
                        reason=verdict.reason, missing=verdict.missing,
                        request=synthesis_request(work, f"reason: {verdict.reason}"),
                        open_question="Evidence conflicts or the answer stays uncertain.")
    if status is DecisionStatus.NEEDS_OPTIONS:
        return Followup(status=status, key=f"options:more:{rev}", phase="awaiting_options",
                        reason=verdict.reason, missing=verdict.missing,
                        request=options_request(work, DEFAULT_MAX_OPTIONS),
                        open_question="No known option satisfies the required criteria.")
    return _human_followup(work, verdict, verdict.reason)


def _continuation_state(work: Working, followup: Followup) -> dict:
    """Return the JSON continuation that resumes the decision after the follow-up."""
    cont = work.cont.model_copy(update={
        "phase": followup.phase, "pending_reason": followup.reason,
        "requested": [*work.cont.requested, followup.key],
        "pending_subjects": work.pending_ids, "candidate_option_id": followup.candidate_option_id,
        "options": work.options, "criteria": work.criteria, "last_assessment_fp": work.revision(),
        "options_version": _ver(work.options), "criteria_version": _ver(work.criteria)})
    return cont.model_dump(mode="json")


def _ver(items: list) -> str:
    """Return the approval-aware version fingerprint of options or criteria."""
    return version_of(items)


def _approved_at(work: Working) -> datetime | None:
    """Return when the human last approved something in this decision (None if no one did)."""
    stamp = work.cont.approved_at
    return datetime.fromisoformat(stamp) if stamp else None


def _decision_record(work: Working, status: DecisionStatus, missing: list[MissingKnowledge],
                     selected: str | None = None, rationale: Rationale | None = None,
                     approval: ApprovalStatus = ApprovalStatus.NOT_REQUIRED,
                     approved_by: str | None = None, approved_at: datetime | None = None
                     ) -> Decision:
    """Build the Decision record carried in the result."""
    return Decision(
        approved_at=approved_at,
        precedent_ids=[n.id for n in work.cont.precedents if n.action != "not_applicable"],
        id=work.decision_id or new_id("dec"), question=work.question, status=status,
        selected_option_id=selected, design_reason=work.cont.design_reason or None,
        option_ids=[o.id for o in work.usable_options],
        criterion_ids=[c.id for c in work.usable_criteria], evidence_ids=work.evidence_ids,
        missing=missing, rationale=rationale, approval_status=approval, approved_by=approved_by,
        versions={"options": _ver(work.options), "criteria": _ver(work.criteria),
                  "templates": "decision.assess@1"})


def waiting_result(invocation: CapabilityInvocation, work: Working, followup: Followup
                   ) -> CapabilityResult:
    """Build `waiting` carrying the typed child request and the continuation."""
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.WAITING, requests=[followup.request], evidence=work.new_evidence,
        continuation_state=_continuation_state(work, followup), usage=work.usage,
        decisions=[_decision_record(work, followup.status, followup.missing)],
        limitations=work.limitations)


def stalled_result(invocation: CapabilityInvocation, work: Working, followup: Followup
                   ) -> CapabilityResult:
    """No progress: the same request was already made. Options block; others end `partial`."""
    if followup.status is DecisionStatus.NEEDS_OPTIONS:
        return blocked_result(invocation, "options_unavailable",
                              "the options request returned nothing usable", usage=work.usage)
    note = f"no progress: {followup.open_question} (request already made at this revision)"
    report = DecisionReportPayload(
        status=followup.status, open_questions=[followup.open_question],
        limitations=[*work.limitations, note])
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.PARTIAL, output_schema_id=schema_ids.DECISION_REPORT,
        output_payload=report.model_dump(mode="json"), usage=work.usage,
        decisions=[_decision_record(work, followup.status, followup.missing)],
        evidence=work.new_evidence, limitations=[*work.limitations, note])


def resolved_result(invocation: CapabilityInvocation, work: Working, verdict: Verdict
                    ) -> CapabilityResult:
    """Build the completed decision report for a resolved verdict."""
    option = next(o for o in work.options if o.id == verdict.selected_option_id)
    required = [c.id for c in work.usable_criteria if c.priority.value == "required"]
    text = (f"Option [{option.id}] {option.title} satisfies the required criteria "
            f"{required} according to evidence {work.evidence_ids}.")
    rationale = Rationale(text=text, origin="template")
    used: list[Option | Criterion] = [*work.usable_options, *work.usable_criteria]
    approved = (work.cont.decision_approved or any(
        i.proposal_status is ProposalStatus.PROPOSED for i in used))
    approval = ApprovalStatus.APPROVED if approved else ApprovalStatus.NOT_REQUIRED
    report = DecisionReportPayload(
        status=DecisionStatus.RESOLVED, recommendation=option.title,
        selected_option_id=option.id, criterion_assessments=verdict.assessments,
        supporting_evidence_ids=work.evidence_ids, approval_status=approval,
        limitations=work.limitations, rationale=rationale)
    approver = work.cont.approved_by if approved else None
    decision = _decision_record(work, DecisionStatus.RESOLVED, [], option.id, rationale, approval,
                                approved_by=approver,
                                approved_at=_approved_at(work) if approved else None)
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.COMPLETED, output_schema_id=schema_ids.DECISION_REPORT,
        output_payload=report.model_dump(mode="json"), decisions=[decision], usage=work.usage,
        evidence=work.new_evidence, limitations=work.limitations)


def design_resolved_result(invocation: CapabilityInvocation, work: Working, cfg: DecisionConfig
                           ) -> CapabilityResult:
    """Resolve a design decision with the option the human chose (approved by that human).

    The kernel ranking the human saw is recorded in the rationale and the assessments; it is
    evidence for the choice, never the authority for it.
    """
    option = next(o for o in work.options if o.id == work.cont.design_choice_id)
    rationale = Rationale(text=choice_rationale(work), origin="template")
    note = ("design decision: the options were ranked by the kernel and a human chose "
            f"[{option.id}]")
    limited = [LIMITATION] if work.cont.design_reason == BUDGET_RESERVE else []
    report = DecisionReportPayload(
        status=DecisionStatus.RESOLVED, recommendation=option.title,
        selected_option_id=option.id, criterion_assessments=ranking_assessments(work, cfg),
        supporting_evidence_ids=work.evidence_ids, approval_status=ApprovalStatus.APPROVED,
        limitations=[*work.limitations, *limited, note], rationale=rationale)
    decision = _decision_record(work, DecisionStatus.RESOLVED, [], option.id, rationale,
                                ApprovalStatus.APPROVED, approved_by=work.cont.approved_by,
                                approved_at=_approved_at(work))
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.COMPLETED, output_schema_id=schema_ids.DECISION_REPORT,
        output_payload=report.model_dump(mode="json"), decisions=[decision], usage=work.usage,
        evidence=work.new_evidence, limitations=[*work.limitations, *limited, note])


def precedent_resolved_result(invocation: CapabilityInvocation, work: Working,
                              record: DecisionRecord, evidence_id: str) -> CapabilityResult:
    """Resolve the decision with an earlier decision's choice the human agreed to reuse.

    The approver is the CURRENT human (who confirmed the reuse); the rationale cites the
    precedent. The precedent is evidence for the choice, never its authority: this result exists
    only because a human answered `reuse`.
    """
    actor = work.cont.approved_by or "human"
    option = reuse_option(record, actor, [evidence_id])
    work.options, work.criteria = [option], []
    rationale = Rationale(text=reuse_rationale(record, actor), origin="template")
    note = f"reused the human-approved precedent {record.id} after {actor} confirmed it applies"
    report = DecisionReportPayload(
        status=DecisionStatus.RESOLVED, recommendation=option.title, selected_option_id=option.id,
        supporting_evidence_ids=[evidence_id], approval_status=ApprovalStatus.APPROVED,
        limitations=[*work.limitations, note], rationale=rationale)
    decision = _decision_record(work, DecisionStatus.RESOLVED, [], option.id, rationale,
                                ApprovalStatus.APPROVED, approved_by=actor,
                                approved_at=_approved_at(work))
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.COMPLETED, output_schema_id=schema_ids.DECISION_REPORT,
        output_payload=report.model_dump(mode="json"), decisions=[decision], usage=work.usage,
        evidence=work.new_evidence, limitations=[*work.limitations, note])


def emit_followup(invocation: CapabilityInvocation, work: Working, followup: Followup
                  ) -> CapabilityResult:
    """Emit `waiting` for a fresh follow-up, or the stalled outcome if it was already made."""
    if followup.key in work.cont.requested:
        return stalled_result(invocation, work, followup)
    return waiting_result(invocation, work, followup)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A human-approved resolution records approved_by and approved_at and
#   the precedents used; a reuse resolves with the precedent's choice approved by the current
#   human, and results hand the kernel the evidence the decision created (precedent items).
#   (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: The decision record carries `design_reason` (from the
#   continuation) so a reader of the record, not only of the state, sees why the options were
#   ranked for a human; the design round's research request key ends in `:design_round` so it
#   is asked once. (#KernelV01/F)
# - 2026-10-01 [python-coder]: A research follow-up carries the decision's reserved Jev calls, and
#   a design decision settled after a budget hand-over records the limited-evidence limitation in
#   its final report. (#KernelV01/E)
# - 2026-10-01 [python-coder]: design_resolved_result completes a design decision with the human's
#   choice: approval approved, approved_by the human, rationale recording ranking and choice.
#   (#KernelV01/A)
# - 2026-10-02 [python-coder]: mypy: the used items are typed as options or criteria (#KernelBootstrapV0/GROUND)
# - 2026-10-01 23:00 [python-coder]: The decision record uses the stable decision id, so the
#   scheduler merges every status of one decision into a single record. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 02:00 [python-coder]: The decision-approval request key carries the revision so a
#   voided approval can be asked again instead of stalling. (#KernelBootstrapV0/FIXA)
# - 2026-09-30 23:00 [python-coder]: Approval status of a resolved report is approved when the
#   decision was approved or a used option or criterion started as a proposal (approved by a
#   human before use); proposed-only items can never reach this point. (#KernelBootstrapV0/P5)
# ====================================================================
