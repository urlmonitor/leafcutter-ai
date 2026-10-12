"""
MODULE: knowledge_followups
GOAL: Selected-entity disclosure follow-ups within one cumulative kernel call budget.
BUSINESS CONTEXT: Keep optional knowledge retrieval bounded and traceable.
ARCHITECTURE: Adapter between neutral knowledge transport and existing kernel contracts.
"""

from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable
    from knowledge.contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult
    from knowledge.ports import KnowledgeRetriever
    from kernel.capabilities.base import ExecutionContext


import time

from knowledge.contracts import KnowledgeRetrievalRequest, RetrievalBudget
from integrations.graph_population import preserve_population


def response_matches(request: KnowledgeRetrievalRequest, result: KnowledgeRetrievalResult) -> bool:
    """Reject a mismatched response before it can seed a follow-up request.

    Args:
        request: Validated repository-scoped retrieval request.
        result: Bounded retrieval response to validate or consume.

    Returns:
        bool: Validated result of the documented operation.
    """
    return (
        result.request_id == request.request_id
        and result.requested_mode == request.mode
        and result.operation in {"", request.operation}
        and (not result.evidence or bool(result.source_sha and result.generation_id))
        and all(
            item.entity.source.repository_id == request.repository_id
            and item.entity.source.source_sha == result.source_sha
            for item in result.evidence
        )
    )


def _budget_exhausted(
    round_index: int,
    initial: KnowledgeRetrievalRequest,
    remaining_bytes: int,
    remaining_tokens: int,
    remaining_candidates: int,
    remaining_ms: int,
) -> bool:
    """Check whether another legal bounded follow-up can be constructed.

    Args:
        round_index: Zero-based completed disclosure round.
        initial: Original cumulative budget request.
        remaining_bytes: Unspent serialized response byte allowance.
        remaining_tokens: Unspent serialized token estimate allowance.
        remaining_candidates: Unspent candidate work allowance.
        remaining_ms: Unspent elapsed-time allowance.

    Returns:
        bool: Whether no additional legal round fits the remaining budget.
    """
    return (
        round_index + 1 >= initial.budget.max_rounds
        or remaining_bytes < 1024
        or remaining_tokens < 256
        or remaining_candidates < 1
        or remaining_ms < 1
    )


async def disclose_selected(
    port: KnowledgeRetriever,
    request: KnowledgeRetrievalRequest,
    ctx: ExecutionContext,
    target_level: int,
    observed_call: Callable[..., Awaitable[KnowledgeRetrievalResult]],
    authorized: Callable[..., bool],
) -> tuple[KnowledgeRetrievalRequest, KnowledgeRetrievalResult, list[str]]:
    """Read discovery then selected source; never paginate an entire graph automatically.

    An explicit request already selects its disclosure. Automatic graph routing begins
    compactly, then reads only the discovered IDs. At most max_rounds calls run, and each
    consumes the original time/byte/token/candidate allowance. Failure and no progress stop.

    Args:
        port: Application-owned neutral retrieval port.
        request: Validated repository-scoped retrieval request.
        ctx: Trusted execution scope, budgets and telemetry owner.
        target_level: Maximum requested progressive disclosure level.
        observed_call: Bounded retrieval callback using existing telemetry.
        authorized: Predicate enforcing trusted source scope.

    Returns:
        tuple[KnowledgeRetrievalRequest, KnowledgeRetrievalResult, list[str]]: Validated result of the documented operation.
    """
    initial = request
    current = request
    started = time.monotonic()
    remaining_bytes = request.budget.max_content_bytes
    remaining_tokens = request.budget.max_estimated_tokens
    remaining_candidates = request.budget.max_candidates
    previous = None
    retrieval_ids = []
    result: KnowledgeRetrievalResult
    population_result: KnowledgeRetrievalResult | None = None
    for round_index in range(request.budget.max_rounds):
        result = await observed_call(port, current, ctx)
        retrieval_ids.append(result.retrieval_id)
        if not response_matches(current, result) or any(
            not authorized(ctx, current, e) for e in result.evidence
        ):
            break
        if population_result is None and "population" in result.stats:
            population_result = result
        fingerprint = tuple(
            (e.entity.canonical_id, e.entity.source.source_sha, e.entity.source.locator, e.content)
            for e in result.evidence
        )
        wire_bytes = len(result.model_dump_json().encode("utf-8"))
        remaining_bytes -= wire_bytes
        remaining_tokens -= max(1, (wire_bytes + 3) // 4)
        remaining_candidates -= max(
            len(result.evidence),
            int(result.stats.get("candidate_work", result.stats.get("candidates", 0))),
        )
        remaining_ms = initial.budget.deadline_ms - int((time.monotonic() - started) * 1000)
        if (
            result.status not in {"ok", "partial"}
            or not result.evidence
            or current.disclosure_level >= target_level
            or fingerprint == previous
            or ctx.cancelled()
        ):
            break
        if _budget_exhausted(
            round_index,
            initial,
            remaining_bytes,
            remaining_tokens,
            remaining_candidates,
            remaining_ms,
        ):
            result.truncated = True
            result.warnings.append("kernel cumulative disclosure budget exhausted")
            break
        previous = fingerprint
        bounds = initial.budget.model_dump()
        bounds.update(
            max_content_bytes=remaining_bytes,
            max_estimated_tokens=remaining_tokens,
            max_candidates=remaining_candidates,
            deadline_ms=remaining_ms,
        )
        # A matched nonempty response establishes an immutable source revision.
        assert result.source_sha is not None
        current = KnowledgeRetrievalRequest(
            request_id=initial.request_id,
            repository_id=initial.repository_id,
            revision=result.source_sha,
            operation="get_entities",
            mode="exact",
            arguments={"entity_ids": [e.entity.canonical_id for e in result.evidence]},
            disclosure_level=target_level,
            budget=RetrievalBudget.model_validate(bounds),
            correlation=initial.correlation,
            answer_requirements=initial.answer_requirements,
            assessment=initial.assessment,
        )
    preserve_population(population_result, result, current)
    return current, result, retrieval_ids


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
# - 2026-10-03 20:00 [python-coder]: Retain authorized population scope and incompleteness across source disclosure. (#TICKETLESS reason=user-approved-DK300-graph-routing)
