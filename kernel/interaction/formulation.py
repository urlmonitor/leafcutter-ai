"""
MODULE: kernel.interaction.formulation
GOAL: Pure helpers for the optional `host.formulate_question` step in front of a human question:
    build the wording request, find its answered child and apply the converted wording.
BUSINESS CONTEXT: Rev 3 section 11.6: the host may word a question, but the pending interaction
    is always created by Leafcutter and only a human can answer it. The step is off by default
    (`host.formulate_questions`); when it fails or is refused the original question is asked.
ARCHITECTURE: No scheduler imports. The route node passes its Draft (duck-typed: `items`,
    `requests`, `results`, `request_of`). The wording request is an ordinary `capability` request
    whose payload is the human question, so it is routed, budgeted and traced like any host
    operation; the converted human_question_request.v1 replaces the human request's payload.
"""

from __future__ import annotations

from typing import Any

from kernel.contracts import Priority, RequestKind, RequestProposal, ResultStatus, schema_ids
from kernel.contracts.payloads import HumanQuestionRequestPayload

FORMULATE_CAPABILITY = "host.formulate_question"
FORMULATE_OPERATION = "formulate_question"


def formulation_proposal(request: Any) -> RequestProposal:
    """Return the SUPPORTING request to word `request`, a human question, through the host.

    Supporting, because wording is optional help: a failed wording must never block the item it
    words or discard the human's answer.
    """
    if request.payload_schema == schema_ids.HUMAN_QUESTION_REQUEST:
        body = HumanQuestionRequestPayload.model_validate(request.payload)
    else:
        body = HumanQuestionRequestPayload(question=request.question or request.goal or "?",
                                           free_text_allowed=True)
    return RequestProposal(
        kind=RequestKind.CAPABILITY, goal=f"Word the question: {body.question}"[:300],
        payload_schema=schema_ids.HUMAN_QUESTION_REQUEST, payload=body.model_dump(mode="json"),
        requested_output_schema=schema_ids.HUMAN_QUESTION_REQUEST,
        operation=FORMULATE_OPERATION, priority=Priority.SUPPORTING)


def formulation_child(draft: Any, item: Any) -> Any | None:
    """Return the work item that was asked to word `item`'s question, if any."""
    for ref in item.child_ids:
        child = draft.items.get(ref)
        request = draft.request_of(child) if child is not None else None
        if request is not None and request.operation == FORMULATE_OPERATION:
            return child
    return None


def apply_wording(draft: Any, item: Any, child: Any) -> bool:
    """Replace the human request's payload with the host's converted wording, if it completed.

    Returns:
        bool: True when the wording was applied; False leaves the original question in place.
    """
    result = draft.results.get(child.result_ref) if child.result_ref else None
    if (result is None or result.status is not ResultStatus.COMPLETED
            or not result.output_payload):
        return False
    body = HumanQuestionRequestPayload.model_validate(result.output_payload)
    request = draft.request_of(item)
    draft.add_request(request.model_copy(update={
        "payload_schema": schema_ids.HUMAN_QUESTION_REQUEST,
        "payload": body.model_dump(mode="json"), "question": body.question}))
    return True


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: The wording request is SUPPORTING (it defaulted to REQUIRED),
#   so an exhausted formulation repair no longer makes `integrate` block the human item with
#   required_child_failed after a valid human answer. (#KernelBootstrapV0/FIXB)
# - 2026-10-01 18:00 [python-coder]: Wording is applied by replacing the human request's payload
#   rather than carrying a second request to the interaction node, so packet building, redaction
#   and the answer protocol stay exactly as for an unworded question. (#KernelBootstrapV0/INT2)
# ====================================================================
