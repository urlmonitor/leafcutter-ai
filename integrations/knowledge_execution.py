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
    from knowledge.contracts import (
        KnowledgeEvidence,
        KnowledgeRetrievalRequest,
        KnowledgeRetrievalResult,
    )
    from knowledge.ports import KnowledgeRetriever
    from kernel.capabilities.base import ExecutionContext
    from kernel.contracts.capability import CapabilityResult, Usage
    from kernel.contracts.payloads import RetrievalRequestPayload
    from kernel.contracts.work import CapabilityInvocation


import asyncio
from pathlib import Path, PurePosixPath, PureWindowsPath

from pydantic import ValidationError

from integrations.knowledge_capability import map_bounded_evidence
from integrations.knowledge_followups import disclose_selected, response_matches
from integrations.retrieval_decision import assess_retrieval_mode
from kernel.capabilities.decision.jev_support import StopCapability, failed_result
from kernel.capabilities.retrieval.access import ReadPolicy
from kernel.contracts import schema_ids
from kernel.contracts.capability import CapabilityResult
from kernel.contracts.enums import NeedStatus, ResultStatus
from kernel.contracts.evidence import EvidenceBundlePayload, UnavailableSource
from kernel.providers.base import JevInvalidResponse
from knowledge.contracts import KnowledgeRetrievalRequest, KnowledgeRetrievalResult
from knowledge.errors import KnowledgeError


def _authorized(
    ctx: ExecutionContext, request: KnowledgeRetrievalRequest, item: KnowledgeEvidence
) -> bool:
    """Check revision/repository and existing path policy before exposing evidence.

    Args:
        ctx: Trusted execution scope, budgets and telemetry owner.
        request: Validated repository-scoped retrieval request.
        item: Disclosed neutral evidence to map or authorize.

    Returns:
        bool: Validated result of the documented operation.
    """
    source = item.entity.source
    if source.repository_id != request.repository_id:
        return False
    if (
        request.revision != "latest"
        and not request.allow_stale
        and source.source_sha != request.revision
    ):
        return False
    path, win = PurePosixPath(source.path), PureWindowsPath(source.path)
    if path.is_absolute() or win.drive or ".." in (*path.parts, *win.parts):
        return False
    policy = ReadPolicy(
        Path(ctx.scope.repository_root).resolve(),
        tuple(ctx.scope.read_roots),
        tuple(ctx.config.retrieval.deny_globs),
        ctx.config.retrieval.max_file_bytes,
    )
    return policy.relative(policy.root / source.path) is not None and not policy.is_denied(
        source.path
    )


def _scoped_request(
    ctx: ExecutionContext, payload: RetrievalRequestPayload, capabilities: dict[str, Any]
) -> dict[str, Any]:
    """Validate trusted repository/source bindings before routing.

    Args:
        ctx: Existing trusted task scope and configuration.
        payload: Caller retrieval payload.
        capabilities: Available retrieval mechanisms.

    Returns:
        dict[str, Any]: Explicit request fields after scope validation.
    """
    config = ctx.config.knowledge
    root = config.repository_root
    if capabilities.get("status") != "disabled" and (
        not root or Path(root).resolve() != Path(ctx.scope.repository_root).resolve()
    ):
        raise KnowledgeError(
            "scope_mismatch", "knowledge repository binding does not match task scope"
        )
    raw = dict(payload.knowledge or {})
    if raw.get("repository_id", config.repository_id) != config.repository_id:
        raise KnowledgeError("scope_mismatch", "requested knowledge repository is not authorized")
    if ctx.scope.source_ids and not any(
        s.id in ctx.scope.source_ids and s.kind == "graph_query" for s in ctx.config.sources
    ):
        raise KnowledgeError(
            "scope_mismatch", "task source scope does not allow knowledge retrieval"
        )
    return raw


async def _request(
    ctx: ExecutionContext,
    invocation: CapabilityInvocation,
    payload: RetrievalRequestPayload,
    capabilities: dict[str, Any],
) -> tuple[KnowledgeRetrievalRequest, str, list[Usage]]:
    """Bind repository and revision from trusted configuration, never prompt text.

    Args:
        ctx: Trusted execution scope, budgets and telemetry owner.
        invocation: Existing registered capability invocation.
        payload: Existing kernel retrieval payload and content limits.
        capabilities: Available graph and semantic mechanisms.

    Returns:
        tuple[KnowledgeRetrievalRequest, str, list[Usage]]: Validated result of the documented operation.
    """
    config = ctx.config.knowledge
    raw = _scoped_request(ctx, payload, capabilities)
    usage = []
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
    return KnowledgeRetrievalRequest.model_validate(raw), reason, usage


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
        return failed_result(
            invocation, "knowledge_invalid_response", "knowledge response binding mismatch"
        )
    if any(not _authorized(ctx, request, item) for item in result.evidence):
        return failed_result(
            invocation, "knowledge_scope_violation", "knowledge evidence outside authorized scope"
        )
    evidence = map_bounded_evidence(ctx, payload, request, result, invocation)
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
        attempted_sources=sorted(source_ids) or ["knowledge.retrieval"],
        unavailable_sources=[
            UnavailableSource(source_id="knowledge.retrieval", reason=result.status)
        ]
        if unavailable
        else [],
        limitations=limitations,
        truncated=result.truncated,
    )
    diagnostics = {
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
    if result.continuation:
        diagnostics["knowledge_continuation"] = result.continuation
    return CapabilityResult(
        invocation_id=invocation.id,
        work_item_id=invocation.work_item_id,
        status=ResultStatus.PARTIAL
        if unavailable or result.status == "partial" or result.truncated
        else ResultStatus.COMPLETED,
        output_schema_id=schema_ids.EVIDENCE_BUNDLE,
        output_payload=bundle.model_dump(mode="json"),
        evidence=evidence,
        limitations=limitations,
        diagnostics=diagnostics,
        usage=usage,
    )


async def invoke_knowledge(
    port: KnowledgeRetriever,
    invocation: CapabilityInvocation,
    ctx: ExecutionContext,
    payload: RetrievalRequestPayload,
    source_ids: set[str],
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
    try:
        capabilities = await asyncio.wait_for(port.capabilities(), timeout=3)
        request, reason, usage = await _request(ctx, invocation, payload, capabilities)
        original_mode = request.mode
        target = (
            request.disclosure_level
            if payload.knowledge is not None
            else {"locator": 0, "summary": 2, "excerpt": 3}[payload.detail]
        )
        request, result, retrieval_ids = await disclose_selected(
            port, request, ctx, target, _observed_call, _authorized
        )
        output = _kernel_result(
            invocation, ctx, payload, request, result, reason, usage, source_ids
        )
        output.diagnostics["knowledge_requested_mode"] = original_mode
        output.diagnostics["knowledge_rounds"] = len(retrieval_ids)
        output.diagnostics["knowledge_retrieval_refs"] = ",".join(retrieval_ids)
        return output
    except StopCapability as exc:
        return exc.result
    except ValidationError as exc:
        fields = ", ".join(".".join(map(str, e["loc"])) for e in exc.errors())
        return failed_result(
            invocation, "knowledge_invalid_request", f"invalid knowledge fields: {fields}"
        )
    except (KnowledgeError, TimeoutError, JevInvalidResponse) as exc:
        code = getattr(exc, "code", "unavailable")
        if code not in {"unavailable", "unsupported", "stale", "disabled"}:
            return failed_result(invocation, f"knowledge_{code}", str(exc))
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
            diagnostics={"knowledge_status": code},
        )


# DECISION HISTORY
# ================================================================================
# - 2026-10-01 20:00 [python-coder]: Preserve canonical evidence and optional bounded retrieval. (#TICKET-20261001-KM-400e-3)
