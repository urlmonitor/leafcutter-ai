"""
MODULE: kernel.capabilities.decision.approvals
GOAL: Apply a human answer to whatever the decision was waiting on: approval of proposed options
    and criteria, approval of the final recommendation, a tie-break, a conflict ruling or a
    stated preference.
BUSINESS CONTEXT: LLM-proposed options and criteria are proposals until a human approves them
    (ADR-053 section 2, Rev 3 section 10.4). Nothing in this module lets a proposal become usable
    without a human answer, and a human answer is never produced by Jev or by a host.
ARCHITECTURE: Pure functions over Working. The answer arrives as a completed human child
    (human_answer.v1); the continuation's `phase` says which question it answers.
"""

from __future__ import annotations

from kernel.capabilities.decision.state import Working, is_pending
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import ApprovalStatus, ProposalStatus
from kernel.contracts.payloads import HumanAnswerPayload

APPROVE = "approve"
REJECT = "reject"
DEFAULT_APPROVER = "human"


def _approve(item: Option | Criterion, actor: str) -> Option | Criterion:
    """Return the item marked approved by actor (proposal status stays as generated)."""
    return item.model_copy(update={"approval_status": ApprovalStatus.APPROVED,
                                   "approved_by": actor})


def _decide(item: Option | Criterion, approved: set[str], actor: str) -> Option | Criterion:
    """Approve a pending item the human listed, decline one they did not."""
    if not is_pending(item):
        return item
    if item.id in approved:
        return _approve(item, actor)
    return item.model_copy(update={"approval_status": ApprovalStatus.REJECTED})


def _edited_criteria(work: Working, answer: HumanAnswerPayload, actor: str) -> list[Criterion]:
    """Build the human-supplied, approved criteria of an edit (new ids never collide)."""
    explicit = {e.id for e in answer.edited_criteria or [] if e.id}
    taken = {c.id for c in work.criteria if c.id not in explicit}
    made: list[Criterion] = []
    for n, edit in enumerate(answer.edited_criteria or [], start=1):
        cid = edit.id or f"crit.edit.{n}"
        while cid in taken:
            cid += "+"
        taken.add(cid)
        made.append(Criterion(id=cid, question=edit.question, priority=edit.priority,
                              proposal_status=ProposalStatus.SUPPLIED,
                              approval_status=ApprovalStatus.APPROVED, proposed_by=actor,
                              approved_by=actor))
    return made


def _apply_structured(work: Working, answer: HumanAnswerPayload, actor: str) -> None:
    """Apply a structured answer: a subset approval per kind, or edited criteria."""
    if answer.approved_option_ids is not None:
        chosen = set(answer.approved_option_ids)
        work.options = [_decide(o, chosen, actor) for o in work.options]
    if answer.edited_criteria is not None:
        edits = _edited_criteria(work, answer, actor)
        replaced = {c.id for c in edits}
        work.criteria = [_decide(c, set(), actor) for c in work.criteria
                         if c.id not in replaced] + edits
    elif answer.approved_criterion_ids is not None:
        chosen = set(answer.approved_criterion_ids)
        work.criteria = [_decide(c, chosen, actor) for c in work.criteria]


def _apply_approval(work: Working, answer: HumanAnswerPayload, actor: str) -> None:
    """Approve all pending proposals, apply a structured answer, or record a free-text fallback.

    Free text is kept as a human input and a limitation; it is never turned into criteria.
    """
    if answer.choice_id == APPROVE:
        work.options = [_approve(o, actor) if is_pending(o) else o for o in work.options]
        work.criteria = [_approve(c, actor) if is_pending(c) else c for c in work.criteria]
    elif answer.is_structured:
        _apply_structured(work, answer, actor)
    elif answer.free_text:
        work.cont = work.cont.model_copy(update={
            "human_inputs": [*work.cont.human_inputs, answer.free_text.strip()]})
        work.limitations.append("free-text answer recorded; it was not turned into criteria "
                                "and the proposals stay unapproved")
    else:
        work.limitations.append(f"unrecognised approval answer {answer.choice_id!r}")


def _apply_decision_approval(work: Working, answer: HumanAnswerPayload, actor: str) -> None:
    """Record approval or rejection of the final recommendation."""
    if answer.choice_id == APPROVE:
        work.cont = work.cont.model_copy(update={"decision_approved": True,
                                                 "approved_by": actor})
    elif answer.choice_id == REJECT:
        work.approval_rejected = True
    else:
        work.limitations.append(f"unrecognised decision approval answer {answer.choice_id!r}")


def _apply_escalation(work: Working, answer: HumanAnswerPayload) -> None:
    """Record a human ruling on a tie, conflict, preference or unidentified gap."""
    cont = work.cont
    updates: dict[str, object] = {}
    text = (answer.free_text or "").strip()
    if answer.choice_id:
        known = {o.id for o in work.usable_options}
        if answer.choice_id in known:
            updates["preferred_option_id"] = answer.choice_id
            text = text or f"The requester prefers option {answer.choice_id}."
        else:
            work.limitations.append(f"answer {answer.choice_id!r} is not a usable option")
            return
    if text:
        updates["human_inputs"] = [*cont.human_inputs, text]
    reason = cont.pending_reason
    if reason in {"tie", "preference"}:
        updates["preference_answered"] = True
    if reason == "conflict":
        updates["conflict_resolved"] = True
    work.cont = cont.model_copy(update=updates)


def apply_human_answer(work: Working, answer: HumanAnswerPayload, actor: str | None) -> None:
    """Apply one human answer according to the phase the decision is waiting in.

    Args:
        work: The working state (mutated in place).
        answer: The validated human_answer.v1 payload.
        actor: The answering actor id if known; "human" otherwise.
    """
    who = actor or DEFAULT_APPROVER
    phase = work.cont.phase
    if phase == "awaiting_approval":
        _apply_approval(work, answer, who)
    elif phase == "awaiting_decision_approval":
        _apply_decision_approval(work, answer, who)
    elif phase == "awaiting_human":
        _apply_escalation(work, answer)
    else:
        work.limitations.append(f"human answer ignored: decision was in phase {phase!r}")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Editing proposed criteria means the human replaces them
#   with their own (supplied, approved); proposed options are approved by the same answer
#   because the approval question covers both. (#KernelBootstrapV0/P5)
# - 2026-09-30 23:40 [python-coder]: Declined and replaced proposals stay in the list as
#   rejected, never dropped: the options child is handed to every resumed decision and would
#   bring a dropped proposal back as pending. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:30 [python-coder]: The edit is now a structured answer (P6); free text is only
#   recorded, never parsed into criteria, and an unlisted pending proposal of a decided kind is
#   declined (rejected), not left hanging. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:00 [python-coder]: A human ruling on a tie, conflict or preference waives the
#   matching Jev gate afterwards; human authority outranks a classifier probability.
#   (#KernelBootstrapV0/P5)
# ====================================================================
