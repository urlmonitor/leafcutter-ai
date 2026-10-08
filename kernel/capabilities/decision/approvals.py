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

from typing import TypeVar

from kernel.capabilities.decision.state import ADDED_OPTION_PREFIX, Working, is_pending
from kernel.contracts.decision import Criterion, Option
from kernel.contracts.enums import ApprovalStatus, ProposalStatus
from kernel.contracts.payloads import HumanAnswerPayload
from kernel.memory.precedent import DECIDE_ANEW, REUSE

_Item = TypeVar("_Item", Option, Criterion)
APPROVE = "approve"
REJECT = "reject"
DEFAULT_APPROVER = "human"
HUMAN_RULING = "human_ruling"


def _approve(item: _Item, actor: str) -> _Item:
    """Return the item marked approved by actor (proposal status stays as generated)."""
    return item.model_copy(update={"approval_status": ApprovalStatus.APPROVED,
                                   "approved_by": actor})


def _decide(item: _Item, approved: set[str], actor: str) -> _Item:
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


def _added_options(work: Working, answer: HumanAnswerPayload, actor: str) -> list[Option]:
    """Build the human-supplied, approved options of an answer (new ids never collide)."""
    taken = {o.id for o in work.options}
    made: list[Option] = []
    for n, added in enumerate(answer.added_options or [], start=1):
        oid = f"{ADDED_OPTION_PREFIX}{n}"
        while oid in taken:
            oid += "+"
        taken.add(oid)
        made.append(Option(id=oid, title=added.title, description=added.description,
                           proposal_status=ProposalStatus.SUPPLIED,
                           approval_status=ApprovalStatus.APPROVED, proposed_by=actor,
                           approved_by=actor))
    return made


def _apply_structured(work: Working, answer: HumanAnswerPayload, actor: str) -> None:
    """Apply a structured answer: a subset approval per kind, edited criteria, added options."""
    if answer.approved_option_ids is not None:
        chosen = set(answer.approved_option_ids)
        work.options = [_decide(o, chosen, actor) for o in work.options]
    work.options = [*work.options, *_added_options(work, answer, actor)]
    if answer.edited_criteria is not None:
        edits = _edited_criteria(work, answer, actor)
        replaced = {c.id for c in edits}
        work.criteria = [_decide(c, set(), actor) for c in work.criteria
                         if c.id not in replaced] + edits
    elif answer.approved_criterion_ids is not None:
        chosen = set(answer.approved_criterion_ids)
        work.criteria = [_decide(c, chosen, actor) for c in work.criteria]


def _stamp(work: Working, actor: str) -> None:
    """Record who approved last and when (the decision record's approved_by and approved_at)."""
    stamp = work.now.isoformat() if work.now else None
    work.cont = work.cont.model_copy(update={"approved_by": actor, "approved_at": stamp})


def _keep_condition(work: Working, answer: HumanAnswerPayload) -> None:
    """Keep the answer's free text verbatim as a condition of the choice that was just applied.

    Call this only on the path where the choice was applied: a condition qualifies a choice, so an
    unusable choice keeps nothing.
    """
    text = (answer.free_text or "").strip()
    if text:
        work.cont = work.cont.model_copy(update={"conditions": [*work.cont.conditions, text]})


def _apply_approval(work: Working, answer: HumanAnswerPayload, actor: str) -> None:
    """Approve all pending proposals, apply a structured answer, or record a free-text fallback.

    Free text with the approve choice is a condition of the approval. Free text alone is kept as
    a human input and a limitation; it is never turned into criteria. An unrecognised choice keeps
    no text.
    """
    if answer.choice_id == APPROVE or answer.is_structured:
        _stamp(work, actor)
    if answer.choice_id == APPROVE:
        work.options = [_approve(o, actor) if is_pending(o) else o for o in work.options]
        work.criteria = [_approve(c, actor) if is_pending(c) else c for c in work.criteria]
        _keep_condition(work, answer)
    elif answer.is_structured:
        _apply_structured(work, answer, actor)
    elif answer.choice_id:
        work.limitations.append(f"unrecognised approval answer {answer.choice_id!r}")
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
        _stamp(work, actor)
        work.cont = work.cont.model_copy(update={
            "decision_approved": True, "approved_revision": work.cont.last_assessment_fp})
    elif answer.choice_id == REJECT:
        work.approval_rejected = True
    else:
        work.limitations.append(f"unrecognised decision approval answer {answer.choice_id!r}")


def _apply_escalation(work: Working, answer: HumanAnswerPayload, actor: str) -> None:
    """Record a human ruling on a tie, conflict, preference or unidentified gap.

    A choice of a usable option settles the decision with the human as approver; free text
    that accompanies it is a verbatim condition. An unusable choice records its limitation and
    keeps nothing, the text included.
    """
    cont = work.cont
    updates: dict[str, object] = {}
    text = (answer.free_text or "").strip()
    if answer.choice_id:
        known = {o.id for o in work.usable_options}
        if answer.choice_id not in known:
            work.limitations.append(f"answer {answer.choice_id!r} is not a usable option")
            return
        _stamp(work, actor)
        updates.update(preferred_option_id=answer.choice_id, design_choice_id=answer.choice_id,
                       design_reason=HUMAN_RULING)
        if text:
            updates["conditions"] = [*cont.conditions, text]
        text = ""  # a condition qualifies the choice; it is not a free-standing human input
    if text:
        updates["human_inputs"] = [*cont.human_inputs, text]
    reason = cont.pending_reason
    if reason in {"tie", "preference"}:
        updates["preference_answered"] = True
    if reason == "conflict":
        updates["conflict_resolved"] = True
    work.cont = work.cont.model_copy(update=updates)


def _apply_design_choice(work: Working, answer: HumanAnswerPayload, actor: str) -> None:
    """Record a human's answer to the ranked-options question: a choice, added options or words.

    A choice of a usable option settles the decision (the human is the approver), and free text
    with it is a condition; an unusable choice keeps no text. Added options and free text alone
    change what the kernel ranks, so the decision is assessed and ranked again.
    """
    cont = work.cont
    if answer.added_options:
        work.options = [*work.options, *_added_options(work, answer, actor)]
    text = (answer.free_text or "").strip()
    if answer.choice_id is None:
        if text:
            work.cont = cont.model_copy(update={"human_inputs": [*cont.human_inputs, text]})
        return
    if answer.choice_id not in {o.id for o in work.usable_options}:
        work.limitations.append(f"answer {answer.choice_id!r} is not a usable option")
        return  # an unusable choice keeps nothing: a condition qualifies an applied choice
    _stamp(work, actor)
    work.cont = work.cont.model_copy(update={"design_choice_id": answer.choice_id})
    _keep_condition(work, answer)


def _apply_precedent_choice(work: Working, answer: HumanAnswerPayload, actor: str) -> None:
    """Record the human's answer to the reuse question: reuse the precedent or decide anew.

    Reusing is an approval by this human (the precedent is evidence; it resolves nothing alone).
    """
    if answer.choice_id == REUSE:
        _stamp(work, actor)
        work.cont = work.cont.model_copy(update={"precedent_choice": REUSE})
    elif answer.choice_id == DECIDE_ANEW:
        work.cont = work.cont.model_copy(update={"precedent_choice": DECIDE_ANEW})
    else:
        work.limitations.append(f"unrecognised precedent answer {answer.choice_id!r}")


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
        _apply_escalation(work, answer, who)
    elif phase == "awaiting_design_choice":
        _apply_design_choice(work, answer, who)
    elif phase == "awaiting_precedent":
        _apply_precedent_choice(work, answer, who)
    else:
        work.limitations.append(f"human answer ignored: decision was in phase {phase!r}")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-06 [python-coder]: A condition is kept only when the choice it qualifies is applied: the
#   approve choice now keeps its text in cont.conditions (it was dropped), and an unusable choice
#   keeps nothing at an escalation, a design choice or an approval. The decision approval and
#   precedent questions allow no free text, so the pair is already rejected at submission there.
#   (#KernelChoiceWithCondition)
# - 2026-10-02 [python-coder]: A choice of a usable option at an escalation settles the decision
#   (human approver, design_reason human_ruling); free text with a choice is a verbatim condition.
#   (#KernelChoiceWithCondition)
# - 2026-10-01 [python-coder]: Every human approval stamps who and when (cont.approved_by and
#   approved_at) so a staged record carries the approver and the approval time; the human's reuse
#   or decide-anew answer to a precedent offer is recorded the same way. (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: A human's choice among the kernel-ranked options settles a design
#   decision (approver recorded); added options or free text send it back to be ranked again.
#   (#KernelV01/A)
# - 2026-10-02 [python-coder]: approval helpers are generic over option and criterion so the two lists keep their types (#KernelBootstrapV0/GROUND)
# - 2026-10-02 [python-coder]: A structured approval can add options; they are human-supplied and
#   approved by that human. (#KernelBootstrapV0/GROUND)
# - 2026-10-01 02:00 [python-coder]: A decision approval is stamped with the revision the human
#   was shown (last_assessment_fp), so combine can void it when the basis moves.
#   (#KernelBootstrapV0/FIXA)
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
