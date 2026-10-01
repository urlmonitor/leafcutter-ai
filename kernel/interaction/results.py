"""
MODULE: kernel.interaction.results
GOAL: Turn an accepted submission into the CapabilityResult of the owning work item (human or
    host reported evidence), and build the failed result used when host repairs run out.
BUSINESS CONTEXT: The kernel, not the client, decides what a submission means: a human answer
    becomes human-input evidence attributed to the answering actor, host output becomes
    host-reported (never verified) evidence, and an answer never carries more authority than its
    actor kind (spec sections 7.8 and 11.6).
ARCHITECTURE: Pure functions over contract models. Evidence ids are content addresses, so
    converting the same submission twice yields the same evidence and a re-executed node cannot
    duplicate it.
"""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime
from typing import Any

from kernel.capabilities.host import HostConversion, host_operation
from kernel.contracts import (
    CapabilityInvocation,
    CapabilityResult,
    Evidence,
    EvidenceCategory,
    EvidenceSource,
    HostWorkRequest,
    HumanQuestion,
    InteractionSubmission,
    Provenance,
    ResultStatus,
    SemanticType,
    SourceKind,
    Verification,
    content_hash,
    evidence_id,
)
from kernel.contracts.interaction import Choice

REPAIR_EXHAUSTED_CODE = "host_output_invalid"


def _list_text(label: str, values: list[str] | None) -> str:
    """Return `label: a, b` for a given list, or an empty string when it was not given."""
    return f"{label}: {', '.join(values) if values else 'none'}" if values is not None else ""


def _structured_text(response: dict[str, Any]) -> str:
    """Describe a structured approval answer in one readable evidence line."""
    parts = [_list_text("approved options", response.get("approved_option_ids")),
             _list_text("approved criteria", response.get("approved_criterion_ids"))]
    added = response.get("added_options")
    if added is not None:
        parts.append("added options: " + "; ".join(a["title"] for a in added))
    edits = response.get("edited_criteria")
    if edits is not None:
        parts.append("edited criteria: " + "; ".join(e["question"] for e in edits))
    return ". ".join(p for p in parts if p)


def answer_text(packet: HumanQuestion, response: dict[str, Any]) -> str:
    """Return the evidence text of a human answer (free text, structure summary or label)."""
    if response.get("free_text"):
        return str(response["free_text"])
    structured = _structured_text(response)
    if structured:
        return structured
    chosen: Choice | None = next((c for c in packet.choices if c.id == response.get("choice_id")),
                                 None)
    return f"{chosen.label}" if chosen else f"choice {response.get('choice_id')}"


def evidence_from_submission(packet: HostWorkRequest | HumanQuestion,
                             submission: InteractionSubmission, now: datetime) -> list[Evidence]:
    """Turn the answer and any new evidence of a submission into Evidence items."""
    human = isinstance(packet, HumanQuestion)
    texts = [(f"human:{packet.id}", answer_text(packet, dict(submission.response)))] \
        if human else []
    texts += [(e.locator or f"{submission.actor.kind.value}:{packet.id}#{i}", e.excerpt)
              for i, e in enumerate(submission.new_evidence)]
    out: list[Evidence] = []
    for locator, excerpt in texts:
        digest = content_hash(excerpt)
        out.append(Evidence(
            id=evidence_id(locator, digest), created_at=now, updated_at=now,
            category=EvidenceCategory.TASK_CONTEXT,
            semantic_type=SemanticType.HUMAN_INPUT if human else SemanticType.REPOSITORY_FACT,
            excerpt=excerpt,
            source=EvidenceSource(id="human" if human else "host", locator=locator,
                                  kind=SourceKind.HUMAN if human else SourceKind.HOST_RESEARCH),
            content_hash=digest,
            provenance=Provenance(producer="kernel.interaction", actor=submission.actor.id,
                                  relayed_by=submission.relayed_by),
            verification=Verification.UNVERIFIED if human else Verification.HOST_REPORTED))
    return out


def result_from_submission(packet: HostWorkRequest | HumanQuestion,
                           submission: InteractionSubmission,
                           invocation: CapabilityInvocation | None, now: datetime, *,
                           known_evidence_ids: Collection[str] | None = None) -> CapabilityResult:
    """Return the completed CapabilityResult an accepted submission produces.

    A host submission for a capability with a host operation is converted by that operation
    (proposals stay proposals, evidence is host-reported, ids are kernel-derived); any other
    submission is passed through with the evidence it carried. `known_evidence_ids` lets the
    conversion drop citations of evidence the run does not have.
    """
    evidence = evidence_from_submission(packet, submission, now)
    operation = host_operation(invocation.capability_id) if invocation else None
    if operation is not None and invocation is not None and isinstance(packet, HostWorkRequest):
        return operation.convert(HostConversion(
            packet=packet, submission=submission, invocation=invocation, now=now,
            extra_evidence=tuple(evidence),
            known_evidence_ids=None if known_evidence_ids is None
            else frozenset(known_evidence_ids)))
    return CapabilityResult(
        invocation_id=invocation.id if invocation else packet.id,
        work_item_id=packet.work_item_id, status=ResultStatus.COMPLETED,
        output_schema_id=submission.response_schema_id,
        output_payload=dict(submission.response), evidence=evidence,
        usage=list(submission.usage))


def repair_exhausted_result(packet: HostWorkRequest, invocation: CapabilityInvocation | None,
                            last_code: str) -> CapabilityResult:
    """Return the failed result for a host interaction whose repair attempts ran out."""
    return CapabilityResult(
        invocation_id=invocation.id if invocation else packet.id,
        work_item_id=packet.work_item_id, status=ResultStatus.FAILED,
        error={"code": REPAIR_EXHAUSTED_CODE, "retryable": False,
               "message": f"host output stayed invalid after {len(packet.rejections)} "
                          f"submissions (last: {last_code})"})


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:05 [python-coder]: Host submissions for a capability with a host operation are
#   converted by that operation (kernel.capabilities.host); the pass-through stays for human
#   answers and unknown host capabilities. (#KernelBootstrapV0/P8)
# - 2026-09-30 23:50 [python-coder]: Moved out of nodes_interaction and extended with structured
#   answers; an exhausted repair budget fails the item with retryable=false so the scheduler
#   never retries invalid host output silently. (#KernelBootstrapV0/P6)
# ====================================================================
