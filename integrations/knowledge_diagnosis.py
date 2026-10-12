"""Attributable diagnostics for one actual retrieval attempt.

MODULE: knowledge_diagnosis
GOAL: Separate observed contract violations from unknown underlying causes.
BUSINESS CONTEXT: Execution success does not imply the original question was answered.
ARCHITECTURE: Pure projection of the request and its actual response, with no runtime lookup.
"""
from __future__ import annotations

import json
from knowledge.contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult


def diagnosis(request: KnowledgeRetrievalRequest, result: KnowledgeRetrievalResult, violation: str | None = None) -> dict:
    """Describe only this attempt and never promote an unverified remote trace.

    Args:
        request: Trusted scoped request actually sent.
        result: Response actually received for this attempt.
        violation: Established deterministic boundary rejection, when present.

    Returns:
        Structured caller-visible diagnosis, with unknown cause where evidence is insufficient.
    """
    sources = [item.entity.source for item in result.evidence]
    source = next((item for item in sources if item.repository_id != request.repository_id), None)
    source = source or (sources[0] if sources else None)
    observation = result.observation or {}
    verified = observation.get("state") == "verified" and observation.get("request_id") == request.request_id and observation.get("retrieval_id") == result.retrieval_id
    answer = result.answer
    return {"request_id": request.request_id, "retrieval_id": result.retrieval_id,
        "execution_status": result.status, "answer_status": answer.status if answer else "unassessed",
        "expected": {"repository_id": request.repository_id, "source_sha": request.revision,
            "operation": request.operation, "request_id": request.request_id},
        "observed": {"repository_id": source.repository_id if source else None,
            "source_sha": source.source_sha if source else result.source_sha,
            "operation": result.operation, "request_id": result.request_id,
            "generation_id": result.generation_id},
        "contract": "knowledge retrieval scope binding / original answer requirements",
        "cause": {"status": "established" if violation else "unknown",
            "reason": violation or "The response alone does not establish an underlying failure cause."},
        "trace": {"state": "verified" if verified else ("unverified" if observation.get("state") == "verified" else observation.get("state", "disabled")),
            "trace_id": observation.get("trace_id"),
            "trace_url": observation.get("trace_url") if verified else None},
        "missing_fields": [item.model_dump(mode="json") for item in answer.missing_fields] if answer else [],
        "next_step": {"action": "inspect_matching_attempt",
            "reason": "Inspect the cited request and response scope or missing-field facts before a bounded rerun of the same authorized question."}}


def attach_diagnosis(output, request, result, violation=None):
    """Attach additive diagnostics without changing execution status or evidence.

    Args:
        output: Existing kernel capability result.
        request: Actual trusted request.
        result: Actual neutral response.
        violation: Established contract boundary rejection, if any.

    Returns:
        The same kernel result with serialized matching-attempt diagnostics.
    """
    output.diagnostics["knowledge_diagnosis"] = json.dumps(diagnosis(request, result, violation))
    return output

# DECISION HISTORY
# - 2026-10-01 [python-coder]: Attribute diagnosis only to the observed attempt; verified trace references require matching IDs. (#KM-500/KM-500g-2)
