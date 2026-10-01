"""MODULE: answers
GOAL: Assess the actual bounded response against the unchanged question contract.
BUSINESS CONTEXT: An ok query may still leave required facts or a full count unresolved.
ARCHITECTURE: Pure neutral consumer; application callers may recompute after truncation.
"""

from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING
from .answer_models import AnswerAssessment, MissingField, PopulationCompleteness
from .answer_fields import field_value

if TYPE_CHECKING:
    from .contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult


def assess_answer(
    request: KnowledgeRetrievalRequest, result: KnowledgeRetrievalResult
) -> AnswerAssessment | None:
    """Recompute evidence sufficiency after the caller has applied its final bounds.

    Args:
        request: Original validated requirements and authorized repository scope.
        result: Actual disclosed response, including any later truncation.

    Returns:
        A separate question assessment, or None for a legacy request without requirements.
    """
    need = request.answer_requirements
    if need is None:
        return None
    items = {item.entity.canonical_id: item for item in result.evidence}
    limitations = _limitations(request, result, items)
    missing = _missing_fields(need.required_fields, items)
    counts = dict(Counter(_work_status(item) for item in items.values()))
    relevant_status = "work_status" in need.required_fields
    if not relevant_status:
        counts = {}
    if not items and need.required_fields and need.scope.population == "returned_entities":
        limitations.append("no evidence for the requested facts")
    complete = not limitations
    hard_failure = _hard_failure(need, result, limitations)
    fulfilled = not missing and not hard_failure and not (need.require_complete and limitations)
    state = "fulfilled" if fulfilled else ("partial" if items else "unresolved")
    return AnswerAssessment(
        status=state,
        original_question=need.original_question,
        required_fields=need.required_fields,
        scope=need.scope,
        missing_fields=missing,
        completeness=PopulationCompleteness(
            complete=complete,
            known_count=len(items),
            exact_total=len(items) if complete else None,
            limitations=list(limitations),
        ),
        work_status_counts=counts
        if relevant_status and complete and "unknown" not in counts
        else None,
        known_work_status_counts=counts,
        limitations=limitations,
    )


def _hard_failure(need: object, result: object, limitations: list[str]) -> bool:
    """Treat absent execution, scope and exact-clause evidence as non-waivable gaps.

    Args:
        need: Original required fields and question scope.
        result: Actual bounded retrieval response.
        limitations: Already established execution and scope limitations.

    Returns:
        Whether missing evidence prevents fulfillment regardless of best-effort mode.
    """
    return (
        (result.truncated and "criteria" in need.required_fields)
        or result.status not in {"ok", "partial"}
        or any(
            value in limitations
            for value in (
                "no evidence for the requested facts",
                "source generation is not established",
                "requested source revision is not established",
                "requested population scope is not established",
                "requested identities are missing from returned evidence",
            )
        )
    )


def _work_status(item: object) -> str:
    """Keep absent or malformed implementation status in the unknown bucket."""
    value = field_value(item, "work_status")
    return value if isinstance(value, str) and value else "unknown"


def _missing_fields(fields: list[str], items: dict) -> list[MissingField]:
    """Find missing facts using only actual values and disclosed availability.

    Args:
        fields: Required canonical field names.
        items: Actual evidence indexed by canonical identity.

    Returns:
        Missing field identities with their attributable reasons.
    """
    missing = []
    for identifier, item in items.items():
        for name in fields:
            reason = item.field_availability.get(name, "unknown")
            if field_value(item, name) is not None and reason in {"present", "unknown"}:
                continue
            if reason == "present":
                reason = "unknown"
            missing.append(MissingField(canonical_id=identifier, field=name, reason=reason))
    return missing


def _limitations(
    request: KnowledgeRetrievalRequest, result: KnowledgeRetrievalResult, items: dict
) -> list[str]:
    """Require actual completeness and population identity before exact totals.

    Args:
        request: Original request and question contract.
        result: Actual bounded response.
        items: Unique actual evidence identities.

    Returns:
        Distinct limitations preventing an exact complete answer.
    """
    limits = []
    if result.status != "ok":
        limits.append("execution is " + result.status)
    if result.truncated or result.continuation:
        limits.append("enumeration or disclosure is incomplete")
    if request.continuation:
        limits.append("continuation page is not an aggregate population")
    if not result.source_sha or not result.generation_id:
        limits.append("source generation is not established")
    if request.revision != "latest" and result.source_sha != request.revision:
        limits.append("requested source revision is not established")
    if request.mode in {"semantic", "hybrid", "precedent"}:
        limits.append("bounded relevance retrieval does not establish a complete population")
    scope = request.answer_requirements.scope
    if scope.population != "returned_entities":
        actual = result.stats.get("population", {})
        if not _scope_matches(scope, actual):
            limits.append("requested population scope is not established")
        if not actual.get("complete", False):
            limits.append("complete population enumeration is not established")
    if request.operation == "get_entities":
        if set(request.arguments["entity_ids"]) - set(items):
            limits.append("requested identities are missing from returned evidence")
    return list(dict.fromkeys(limits))


def _scope_matches(scope: object, actual: dict) -> bool:
    """Require actual population identity and inclusion to match the question scope."""
    return all(
        actual.get(name) == getattr(scope, name)
        for name in ("population", "root_id", "levels", "inclusion")
    )


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 18:55 [python-coder]: Keep requested facts separate from execution success and preserve canonical field meaning. (#KM-500/KM-500e-2)
