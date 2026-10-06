"""
MODULE: knowledge_execution
GOAL: Bounded knowledge execution, scope validation and honest kernel coverage.
BUSINESS CONTEXT: Keep optional knowledge retrieval bounded and traceable.
ARCHITECTURE: Adapter between neutral knowledge transport and existing kernel contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from typing import Any
    from kernel.capabilities.base import CapabilityExecutor, ExecutionContext
    from kernel.contracts import CapabilityInvocation, CapabilityResult, Usage
    from kernel.contracts.payloads import RetrievalRequestPayload
    from knowledge.ports import KnowledgeRetriever
    from knowledge.query_catalog import QueryCatalog

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from knowledge.contracts import (
        KnowledgeRetrievalRequest,
        KnowledgeRetrievalResult,
    )
    from knowledge.ports import KnowledgeRetriever
    from kernel.capabilities.base import ExecutionContext
    from kernel.contracts.capability import CapabilityResult, Usage
    from kernel.contracts.payloads import RetrievalRequestPayload
    from kernel.contracts.work import CapabilityInvocation


import asyncio
from functools import partial

from pydantic import ValidationError

from integrations.knowledge_capability import map_bounded_evidence
from integrations.knowledge_followups import disclose_selected, response_matches
from integrations.knowledge_scope import _authorized, _scoped_request
from integrations.retrieval_decision import assess_retrieval_mode
from integrations.graph_selection import assess_graph_operation
from integrations.graph_selection_result import selection_result
from integrations.graph_population import selected_requirements
from kernel.capabilities.decision.jev_support import StopCapability, failed_result
from kernel.contracts import schema_ids
from kernel.contracts.base import canonical_json
from kernel.contracts.capability import CapabilityResult
from kernel.contracts.enums import NeedStatus, ResultStatus
from kernel.contracts.evidence import EvidenceBundlePayload, UnavailableSource
from kernel.providers.base import JevInvalidResponse
from knowledge.contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult
from knowledge.errors import KnowledgeError
from knowledge.answers import assess_answer
from integrations.knowledge_diagnosis import attach_diagnosis
from integrations.knowledge_assessment import (
    bind_assessment, finalize_assessment, assessment_diagnostics, assessment_limits, assessment_bundle,
)


async def _request(
    ctx: ExecutionContext,
    invocation: CapabilityInvocation,
    payload: RetrievalRequestPayload,
    capabilities: dict[str, Any],
    query_catalog: QueryCatalog | None=None,
) -> tuple[KnowledgeRetrievalRequest, str, list[Usage]]:
    """Bind repository and revision from trusted configuration, never prompt text.

    Args:
        query_catalog: Optional trusted persistent query catalog.
        ctx: Trusted execution scope, budgets and telemetry owner.
        invocation: Existing registered capability invocation.
        payload: Existing kernel retrieval payload and content limits.
        capabilities: Available graph and semantic mechanisms.

    Returns:
        tuple[KnowledgeRetrievalRequest, str, list[Usage]]: Validated result of the documented operation.
    """
    config = ctx.config.knowledge
    raw = _scoped_request(ctx, payload, capabilities)
    usage: list[Usage] = []
    if not raw:
        choice, usage = await assess_retrieval_mode(
            ctx, invocation, known_ids=[], intent=payload.need.question, capabilities=capabilities
        )
        if not choice.retrieve:
            raise KnowledgeError("unsupported", choice.reason)
        raw.update(
            mode=choice.mode,
            operation=choice.operation,
            arguments=choice.arguments,
            disclosure_level=0,
        )
        reason = choice.reason
    else:
        reason = "explicit registered retrieval request"
    revision = ctx.scope.revision.commit if ctx.scope.revision else None
    if revision and raw.get("revision", revision) not in {revision, "latest"}:
        raise KnowledgeError("scope_mismatch", "requested revision differs from task revision")
    raw.update(
        request_id=invocation.id,
        repository_id=config.repository_id,
        revision=revision or raw.get("revision", "latest"),
        correlation={
            "run_id": ctx.run_id,
            "invocation_id": invocation.id,
            "work_item_id": invocation.work_item_id,
        },
    )
    budget = dict(raw.get("budget", {}))
    budget["max_results"] = min(
        budget.get("max_results", 20), payload.limits.top_k or 20, ctx.config.retrieval.top_k
    )
    # Caller character limits are enforced on excerpts; wire bytes are a separate budget.
    budget["deadline_ms"] = min(
        budget.get("deadline_ms", 10000), int(ctx.config.limits.capability_timeout_seconds * 1000)
    )
    raw["budget"] = budget
    if payload.answer_requirements is not None:
        raw["answer_requirements"] = payload.answer_requirements
    raw["assessment"] = bind_assessment(payload.assessment, raw.get("assessment"),
        config.repository_id, raw["revision"])
    return (query_catalog.request(raw) if query_catalog is not None
            else KnowledgeRetrievalRequest.model_validate(raw)), reason, usage


async def _bounded_call(
    port: KnowledgeRetriever, request: KnowledgeRetrievalRequest, ctx: ExecutionContext
) -> KnowledgeRetrievalResult:
    """Cancel underlying work promptly on kernel cancellation or request deadline.

    Args:
        port: Application-owned neutral retrieval port.
        request: Validated repository-scoped retrieval request.
        ctx: Trusted execution scope, budgets and telemetry owner.

    Returns:
        KnowledgeRetrievalResult: Validated result of the documented operation.
    """
    task = asyncio.create_task(port.retrieve(request))
    loop = asyncio.get_running_loop()
    deadline = loop.time() + request.budget.deadline_ms / 1000
    try:
        while not task.done():
            if ctx.cancelled():
                raise KnowledgeError("unavailable", "kernel cancelled knowledge retrieval")
            if loop.time() >= deadline:
                raise KnowledgeError("unavailable", "knowledge retrieval deadline reached")
            await asyncio.wait({task}, timeout=min(0.05, max(0, deadline - loop.time())))
        return task.result()
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def _observed_call(
    port: KnowledgeRetriever, request: KnowledgeRetrievalRequest, ctx: ExecutionContext
) -> KnowledgeRetrievalResult:
    """Use the existing trace owner; telemetry outages do not suppress retrieval.

    Args:
        port: Application-owned neutral retrieval port.
        request: Validated repository-scoped retrieval request.
        ctx: Trusted execution scope, budgets and telemetry owner.

    Returns:
        KnowledgeRetrievalResult: Validated result of the documented operation.
    """
    meta = {
        "repository_id": request.repository_id,
        "request_id": request.request_id,
        "requested_mode": request.mode,
        "operation": request.operation,
        "disclosure_level": request.disclosure_level,
    }
    manager = None
    span = None
    lost = False
    try:
        manager = ctx.tracer.span("knowledge.retrieve", "retriever", ctx.corr, metadata=meta)
        span = manager.__enter__()
    except (OSError, RuntimeError, ValueError):
        lost = True
    try:
        result = await _bounded_call(port, request, ctx)
        if span:
            try:
                span.update(
                    metadata={
                        "retrieval_id": result.retrieval_id,
                        "generation_id": result.generation_id,
                        "source_sha": result.source_sha,
                        "executed_mode": result.executed_mode,
                        "status": result.status,
                        "evidence_count": len(result.evidence),
                    }
                )
            except (OSError, RuntimeError, ValueError):
                lost = True
    finally:
        if span and manager:
            try:
                manager.__exit__(None, None, None)
            except (OSError, RuntimeError, ValueError):
                lost = True
    if lost:
        result.warnings.append("telemetry unavailable")
    return result


def _assess_final_answer(
    request: KnowledgeRetrievalRequest, result: KnowledgeRetrievalResult
) -> bool:
    """Recompute after kernel bounds without upgrading an unresolved provider result.

    Args:
        request: Preserved original answer contract.
        result: Actual final bounded evidence.

    Returns:
        Whether original obligations remain unmet.
    """
    assessed = assess_answer(request, result)
    if assessed is not None:
        if result.answer is None or result.answer.status != "unresolved":
            result.answer = assessed
    return result.answer is not None and result.answer.status != "fulfilled"


def _answer_diagnostics(result: KnowledgeRetrievalResult) -> dict[str, str]:
    """Preserve final answer and continuation facts in the public kernel result.

    Args:
        result: Bounded neutral execution and answer assessment.

    Returns:
        Additive caller-visible diagnostics.
    """
    values = assessment_diagnostics(result)
    if result.answer is not None:
        values["knowledge_answer"] = result.answer.model_dump_json()
    if result.continuation:
        values["knowledge_continuation"] = result.continuation
    return values


def _kernel_result(
    invocation: CapabilityInvocation,
    ctx: ExecutionContext,
    payload: RetrievalRequestPayload,
    request: KnowledgeRetrievalRequest,
    result: KnowledgeRetrievalResult,
    reason: str,
    usage: list[Usage],
    source_ids: set[str],
) -> CapabilityResult:
    """Keep backend status distinct from no-match and never claim unjudged sufficiency.

    Args:
        invocation: Existing registered capability invocation.
        ctx: Trusted execution scope, budgets and telemetry owner.
        payload: Existing kernel retrieval payload and content limits.
        request: Validated repository-scoped retrieval request.
        result: Bounded retrieval response to validate or consume.
        reason: Recorded reason for the selected retrieval mode.
        usage: Existing provider usage records.
        source_ids: Authorized configured source identifiers.

    Returns:
        CapabilityResult: Validated result of the documented operation.
    """
    result = KnowledgeRetrievalResult.model_validate(result.model_dump())
    if not response_matches(request, result):
        return attach_diagnosis(failed_result(
            invocation, "knowledge_invalid_response", "knowledge response binding mismatch", usage=usage
        ), request, result, "knowledge response binding mismatch")
    if any(not _authorized(ctx, request, item, source_ids=source_ids) for item in result.evidence):
        return attach_diagnosis(failed_result(
            invocation, "knowledge_scope_violation", "knowledge evidence outside authorized scope", usage=usage
        ), request, result, "knowledge evidence outside authorized scope")
    evidence = map_bounded_evidence(ctx, payload, request, result, invocation)
    unmet = _assess_final_answer(request, result)
    assessment_unmet = finalize_assessment(request, result)
    unavailable = result.status not in {"ok", "partial"}
    coverage = (
        NeedStatus.UNAVAILABLE
        if unavailable
        else (NeedStatus.PARTIAL if evidence else NeedStatus.OPEN)
    )
    limitations = [
        *result.warnings,
        f"knowledge status: {result.status}",
        f"retrieval choice: {reason}",
    ]
    if unmet and result.answer is not None:
        limitations.extend(result.answer.limitations)
        limitations.append("Original answer requirements remain " + result.answer.status)
    limitations.extend(assessment_limits(result))
    if evidence:
        limitations.append(
            "Retrieved evidence requires the existing research sufficiency assessment."
        )
    if result.continuation:
        limitations.append(
            "More evidence exists; a focused continuation requires remaining task budget."
        )
    bundle = EvidenceBundlePayload(
        request_id=invocation.id,
        evidence=evidence,
        evidence_ids=[e.id for e in evidence],
        coverage={payload.need.id: coverage},
        assessments=assessment_bundle(result, payload.need.id),
        attempted_sources=sorted(source_ids) or ["knowledge.retrieval"],
        unavailable_sources=[
            UnavailableSource(source_id="knowledge.retrieval", reason=result.status)
        ]
        if unavailable
        else [],
        limitations=limitations,
        truncated=result.truncated,
    )
    diagnostics: dict[str, str | int | float | bool] = {
        "knowledge_status": result.status,
        "knowledge_retrieval_id": result.retrieval_id,
        "knowledge_requested_mode": result.requested_mode,
        "knowledge_executed_mode": result.executed_mode,
        "knowledge_operation": result.operation or request.operation,
        "knowledge_reason": reason,
        "knowledge_allowed_fallback": "none",
        "knowledge_disclosure_level": request.disclosure_level,
        "knowledge_budget": request.budget.model_dump_json(),
        "knowledge_generation": result.generation_id or "",
        "knowledge_source_sha": result.source_sha or "",
    }
    diagnostics.update(_answer_diagnostics(result))
    output = CapabilityResult(
        invocation_id=invocation.id,
        work_item_id=invocation.work_item_id,
        status=ResultStatus.PARTIAL
        if any((unavailable, result.status == "partial", result.truncated, unmet, assessment_unmet))
        else ResultStatus.COMPLETED,
        output_schema_id=schema_ids.EVIDENCE_BUNDLE,
        output_payload=bundle.model_dump(mode="json"),
        evidence=evidence,
        limitations=limitations,
        diagnostics=diagnostics,
        usage=usage,
    )
    return attach_diagnosis(output, request, result)


async def invoke_knowledge(
    port: KnowledgeRetriever,
    invocation: CapabilityInvocation,
    ctx: ExecutionContext,
    payload: RetrievalRequestPayload,
    source_ids: set[str],
    *, query_catalog: QueryCatalog | None=None, fallback: CapabilityExecutor | None = None,
) -> CapabilityResult:
    """Validate, execute and map one bounded call through the existing capability boundary.

    Args:
        port: Application-owned neutral retrieval port.
        invocation: Existing registered capability invocation.
        ctx: Trusted execution scope, budgets and telemetry owner.
        payload: Existing kernel retrieval payload and content limits.
        source_ids: Authorized configured source identifiers.

    Returns:
        CapabilityResult: Validated result of the documented operation.
    """
    usage: list[Usage] = []
    selection_diagnostics: dict[str, str] = {}
    try:
        capabilities = await asyncio.wait_for(port.capabilities(), timeout=3)
        selected_payload = payload
        selection_reason = None
        _scoped_request(ctx, payload, capabilities)
        if payload.knowledge is None:
            choice, usage = await assess_graph_operation(ctx, invocation, payload, capabilities)
            if not choice.retrieve:
                return await selection_result(ctx, invocation, payload, choice, usage, fallback)
            selected_payload = payload.model_copy(update={"knowledge": {
                "mode": choice.mode, "operation": choice.operation,
                "arguments": choice.arguments, "disclosure_level": 0},
                "answer_requirements": selected_requirements(payload, choice)})
            selection_reason = choice.reason
            selection_diagnostics = {"knowledge_selection": "selected",
                "knowledge_selected_operation": choice.operation,
                "knowledge_selected_arguments": canonical_json(choice.arguments)}
        request, reason, request_usage = await _request(ctx, invocation, selected_payload, capabilities, query_catalog)
        usage.extend(request_usage)
        reason = selection_reason or reason
        original_mode = request.mode
        target = (
            request.disclosure_level
            if payload.knowledge is not None
            else {"locator": 0, "summary": 2, "excerpt": 3}[payload.detail]
        )
        request, result, retrieval_ids = await disclose_selected(
            port, request, ctx, target, _observed_call, partial(_authorized, source_ids=source_ids)
        )
        output = _kernel_result(
            invocation, ctx, payload, request, result, reason, usage, source_ids
        )
        output.diagnostics["knowledge_requested_mode"] = original_mode
        output.diagnostics["knowledge_rounds"] = len(retrieval_ids)
        output.diagnostics["knowledge_retrieval_refs"] = ",".join(retrieval_ids)
        output.diagnostics.update(selection_diagnostics)
    except StopCapability as exc:
        return exc.result
    except ValidationError as exc:
        fields = ", ".join(".".join(map(str, e["loc"])) for e in exc.errors())
        return failed_result(
            invocation, "knowledge_invalid_request", f"invalid knowledge fields: {fields}", usage=usage
        )
    except (KnowledgeError, TimeoutError, JevInvalidResponse) as exc:
        code = getattr(exc, "code", "unavailable")
        if code not in {"unavailable", "unsupported", "stale", "disabled"}:
            return failed_result(invocation, f"knowledge_{code}", str(exc), usage=usage)
        bundle = EvidenceBundlePayload(
            request_id=invocation.id,
            coverage={payload.need.id: NeedStatus.UNAVAILABLE},
            unavailable_sources=[UnavailableSource(source_id="knowledge.retrieval", reason=code)],
            limitations=[f"knowledge {code}: {exc}"],
        )
        return CapabilityResult(
            invocation_id=invocation.id,
            work_item_id=invocation.work_item_id,
            status=ResultStatus.PARTIAL,
            output_schema_id=schema_ids.EVIDENCE_BUNDLE,
            output_payload=bundle.model_dump(mode="json"),
            limitations=bundle.limitations,
            diagnostics={"knowledge_status": code, **selection_diagnostics},
            usage=usage,
        )
    else:
        return output


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
# - 2026-10-03 20:00 [python-coder]: Select natural-question operations and retain paid usage through binding and execution failures. (#TICKETLESS reason=user-approved-DK300-graph-routing)
