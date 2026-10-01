"""
MODULE: kernel.scheduler.nodes_execute
GOAL: The `execute` Send worker: resolve the trusted executor for an invocation, run it under
    the capability timeout and return exactly one CapabilityResult, never raising.
BUSINESS CONTEXT: Workers run in parallel, so they must not touch shared state: they receive a
    read-only packet, write only `results[invocation_id]`, and turn every failure (timeout,
    exception, missing binding) into a failed result the kernel can retry or surface.
ARCHITECTURE: The packet carries the invocation, its descriptor, an evidence snapshot, the scope
    and an even share of the Jev and work-item budgets, so concurrent workers can never overspend
    (design part 3, guards). Elapsed time and reserved Jev calls travel back in `diagnostics`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from langgraph.runtime import Runtime

from kernel.capabilities.base import BudgetResource, ExecutionContext
from kernel.contracts import (
    CapabilityInvocation,
    CapabilityResult,
    ErrorInfo,
    Evidence,
    ResultStatus,
)
from kernel.observability.correlation import correlation_for_invocation
from kernel.observability.redaction import Redactor
from kernel.providers.base import JevUnavailable
from kernel.registry.bindings import BindingUnavailable
from kernel.scheduler.context import KernelRuntime

logger = logging.getLogger(__name__)

ELAPSED_KEY = "kernel.elapsed_s"
JEV_RESERVED_KEY = "kernel.jev_reserved"
_MAX_MESSAGE = 300


class ShareBudget:
    """BudgetPort holding one worker's even share of the remaining budget."""

    def __init__(self, shares: dict[str, int]) -> None:
        """Start with the Jev and work-item shares given by the route node."""
        self._left = {"jev": shares.get("jev", 0), "work_item": shares.get("work_item", 0),
                      "host": 0}
        self.reserved = {"jev": 0, "work_item": 0, "host": 0}

    def reserve(self, resource: BudgetResource) -> bool:
        """Reserve one unit if the share allows it; refuse (and reserve nothing) otherwise."""
        if self._left[resource] <= 0:
            return False
        self._left[resource] -= 1
        self.reserved[resource] += 1
        return True


def failed_result(invocation: CapabilityInvocation, code: str, message: str, *,
                  retryable: bool = False) -> CapabilityResult:
    """Build the failed result that represents an execution problem."""
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.FAILED,
        error=ErrorInfo(code=code, message=message[:_MAX_MESSAGE], retryable=retryable))


def _context(packet: dict[str, Any], ctx: KernelRuntime, budget: ShareBudget
             ) -> ExecutionContext:
    """Build the ExecutionContext of one worker from its packet."""
    invocation: CapabilityInvocation = packet["invocation"]
    known: dict[str, Evidence] = packet["evidence"]
    corr = correlation_for_invocation(invocation.trace.correlation, invocation)

    def lookup(ids: Any) -> list[Evidence]:
        """Return known evidence for ids in order, skipping unknown ids."""
        return [known[i] for i in ids if i in known]

    return ExecutionContext(
        run_id=corr.run_id or "", scope=packet["scope"], config=ctx.config, jev=ctx.jev,
        tracer=ctx.tracer, corr=corr, artifacts=ctx.artifacts, budget=budget,
        evidence_lookup=lookup, clock=ctx.clock, cancel_probe=ctx.cancel_probe,
        descriptor=packet["descriptor"], constraints=tuple(packet.get("constraints", ())))


def cancelled_result(invocation: CapabilityInvocation) -> CapabilityResult:
    """Build the blocked result of an invocation that was not started because the run is cancelled."""
    return CapabilityResult(
        invocation_id=invocation.id, work_item_id=invocation.work_item_id,
        status=ResultStatus.BLOCKED,
        error=ErrorInfo(code="cancelled", message="run cancelled before the capability started"),
        limitations=["cancelled: the capability was not started"])


def _mask(ctx: KernelRuntime, text: str) -> str:
    """Mask secrets in exception text before it becomes a client-visible error message."""
    redactor = ctx.redactor or Redactor({}, ctx.config.data_policy)
    return redactor.mask_text(text)


async def _run_executor(packet: dict[str, Any], ctx: KernelRuntime, budget: ShareBudget
                        ) -> CapabilityResult:
    """Resolve and run the executor; every failure becomes a failed result."""
    invocation: CapabilityInvocation = packet["invocation"]
    descriptor = packet["descriptor"]
    if descriptor is None:
        return failed_result(invocation, "binding_unavailable", "capability not in snapshot")
    try:
        executor = ctx.bindings.resolve(descriptor.binding, invocation.capability_version)
    except BindingUnavailable as exc:
        return failed_result(invocation, "binding_unavailable", _mask(ctx, str(exc)))
    timeout = ctx.config.limits.capability_timeout_seconds
    exec_ctx = _context(packet, ctx, budget)
    try:
        return await asyncio.wait_for(executor.ainvoke(invocation, exec_ctx), timeout=timeout)
    except TimeoutError:
        logger.warning("capability %s timed out after %ss", invocation.capability_id, timeout)
        return failed_result(invocation, "timeout", f"no result within {timeout}s",
                             retryable=True)
    except JevUnavailable as exc:
        logger.warning("capability %s: jev unavailable", invocation.capability_id)
        return failed_result(invocation, "provider_unavailable", _mask(ctx, exc.reason))
    except Exception as exc:  # noqa: BLE001  (a capability must never crash the graph)
        logger.exception("capability %s raised", invocation.capability_id)
        return failed_result(invocation, "executor_exception",
                             _mask(ctx, f"{type(exc).__name__}: {exc}"))


async def execute(packet: dict, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
    """Send worker: run one invocation and return `{results: {invocation_id: result}}`."""
    ctx = runtime.context
    invocation: CapabilityInvocation = packet["invocation"]
    if ctx.cancel_probe():
        # Safe point: before each invocation (first attempts and retries both come through here).
        return {"results": {invocation.id: cancelled_result(invocation)}}
    budget = ShareBudget(packet.get("shares", {}))
    started = ctx.monotonic()
    with ctx.tracer.span(f"capability.{invocation.capability_id}", "capability",
                         invocation.trace.correlation):
        result = await _run_executor(packet, ctx, budget)
    diagnostics = {**result.diagnostics, ELAPSED_KEY: max(0.0, ctx.monotonic() - started),
                   JEV_RESERVED_KEY: budget.reserved["jev"]}
    return {"results": {invocation.id: result.model_copy(update={"diagnostics": diagnostics})}}


__all__ = ["ELAPSED_KEY", "JEV_RESERVED_KEY", "ShareBudget", "cancelled_result", "execute", "failed_result"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 16:30 [python-coder]: Exception text is masked here, where it becomes an
#   ErrorInfo, because that message reaches the stdout envelope, run.json and events, which the
#   Langfuse mask never covers. (#KernelBootstrapV0/FIXC)
# - 2026-10-01 17:00 [python-coder]: A worker consults `cancel_probe` before it starts; a
#   cancelled run gets a blocked `cancelled` result instead of a capability call. Retries are
#   re-dispatched through this worker, so the same check covers "between retries".
#   (#KernelBootstrapV0/INT2)
# - 2026-09-30 22:30 [python-coder]: Workers get an even share of the remaining Jev budget
#   instead of a shared counter: no mutable state crosses workers, the split is deterministic,
#   and the sum of shares can never exceed the limit. (#KernelBootstrapV0/P4)
# ====================================================================
