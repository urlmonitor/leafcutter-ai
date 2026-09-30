"""
MODULE: kernel.scheduler.context
GOAL: KernelRuntime (the read-only dependencies injected into every node), the `sequential_node`
    wrapper that adds a tracer span and active-time accounting, and the event flush helper.
BUSINESS CONTEXT: Runtime dependencies must never enter serialised state (spec 5.1), and the
    active-time guard needs every kernel node to account its wall time without each node
    repeating the bookkeeping.
ARCHITECTURE: LangGraph passes KernelRuntime as `runtime.context` (`context_schema`). The wrapper
    is used only by nodes that run alone in their superstep: two parallel nodes writing `budgets`
    in one superstep would collide on its replace reducer.
"""

from __future__ import annotations

import functools
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from langgraph.runtime import Runtime

from kernel.config import KernelConfig
from kernel.contracts import CorrelationIds, canonical_json, utc_now
from kernel.persistence.base import ArtifactStorePort, GapStorePort, RunStorePort
from kernel.providers.base import JevPort
from kernel.registry.bindings import BindingTable
from kernel.scheduler.state import Budgets, KernelState
from kernel.observability.redaction import Redactor
from kernel.observability.tracer import TraceState, Tracer

logger = logging.getLogger(__name__)

NodeFn = Callable[[KernelState, Runtime["KernelRuntime"]], Awaitable[dict[str, Any]]]


@dataclass(frozen=True)
class KernelRuntime:
    """Dependencies of one graph invocation; never serialised into state.

    Attributes:
        config: Validated kernel configuration (limits, routing thresholds).
        bindings: Trusted executor factories.
        jev: The Jev port used by routing.
        tracer: Observability port.
        run_store: Run records and event log.
        gap_store: Capability gap observations.
        artifacts: Run-scoped artifact storage.
        secrets: Loaded credentials (opaque to the scheduler; kept for the composition root).
        clock: Wall clock for timestamps (injectable for tests).
        monotonic: Monotonic seconds for active-time accounting (injectable for tests).
        cancel_probe: Returns True when cancellation was requested.
        max_scheduler_iterations: Explicit iteration guard; None uses
            `limits.max_scheduler_iterations`, then the LangGraph recursion limit (see
            guards.max_iterations_for).
        redactor: Masks secrets in packets before they leave the kernel; None uses a
            pattern-only redactor built from `config.data_policy`.
        trace: The CURRENT process segment's trace identity. New invocations (and so host packets)
            nest under it; None falls back to the `trace` the run was started with.
    """

    config: KernelConfig
    bindings: BindingTable
    jev: JevPort
    tracer: Tracer
    run_store: RunStorePort
    gap_store: GapStorePort
    artifacts: ArtifactStorePort
    secrets: object | None = None
    clock: Callable[[], datetime] = utc_now
    monotonic: Callable[[], float] = time.monotonic
    cancel_probe: Callable[[], bool] = field(default=lambda: False)
    max_scheduler_iterations: int | None = None
    redactor: Redactor | None = None
    trace: TraceState | None = None


def constraint_texts(state: KernelState) -> tuple[str, ...]:
    """Return the task's constraints as short texts (`[severity] kind: value`), in input order."""
    task_input = state.get("task_input")
    if task_input is None:
        return ()
    return tuple(f"[{c.severity.value}] {c.kind}: "
                 f"{c.value if isinstance(c.value, str) else canonical_json(c.value)}"
                 for c in task_input.constraints)


def run_corr(state: KernelState, **updates: str | int | None) -> CorrelationIds:
    """Return run-level correlation ids from state, with optional per-call replacements."""
    base = CorrelationIds(run_id=state.get("run_id"), root_task_id=state.get("root_task_id"),
                          task_id=state.get("root_task_id"))
    return base.with_updates(**updates) if updates else base


def sequential_node(name: str) -> Callable[[NodeFn], NodeFn]:
    """Wrap a node that runs alone in its superstep with a tracer span and time accounting.

    Args:
        name: Node name used for the span (`kernel.<name>`).

    Returns:
        Callable: A decorator; the wrapped node adds the elapsed monotonic seconds to
            `budgets.active_seconds` in its returned update.
    """
    def decorate(fn: NodeFn) -> NodeFn:
        """Return the wrapped node."""
        @functools.wraps(fn)
        async def wrapper(state: KernelState, runtime: Runtime[KernelRuntime]) -> dict[str, Any]:
            """Run the node inside a span and account its wall time."""
            ctx = runtime.context
            started = ctx.monotonic()
            with ctx.tracer.span(f"kernel.{name}", "node", run_corr(state)):
                update = await fn(state, runtime)
            elapsed = max(0.0, ctx.monotonic() - started)
            budgets: Budgets = update.get("budgets", state.get("budgets", Budgets()))
            update["budgets"] = budgets.model_copy(
                update={"active_seconds": budgets.active_seconds + elapsed})
            return update
        return wrapper
    return decorate


def flush_events(run_store: RunStorePort, state: KernelState) -> int:
    """Mirror events not yet persisted to the run store and return the new flushed count.

    Persistence is best effort: a failing store logs a warning and the count stops at the first
    event that could not be written, so a later call retries it.

    Args:
        run_store: Run store receiving the events.
        state: Current state (`events`, `events_flushed`).

    Returns:
        int: Number of leading events now known to be persisted.
    """
    events = state.get("events", [])
    flushed = state.get("events_flushed", 0)
    for event in events[flushed:]:
        try:
            run_store.append_event(event)
        except OSError:
            logger.warning("could not persist event %s of run %s", event.seq, event.run_id,
                           exc_info=True)
            break
        flushed += 1
    return flushed


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 10:00 [python-coder]: `trace` carries the current segment so work created after a
#   resume nests under it, not under the start segment (bug D). (#KernelBootstrapV0/P7)
# - 2026-09-30 23:58 [python-coder]: Optional `redactor` so host packets are masked with the
#   run's real secret values; absent, a pattern-only redactor is used. (#KernelBootstrapV0/P6)
# - 2026-09-30 23:59 [python-coder]: constraint_texts feeds ExecutionContext.constraints from
#   the task input. (#KernelBootstrapV0/INT)
# - 2026-09-30 22:30 [python-coder]: max_scheduler_iterations is an explicit runtime parameter
#   (not a config key) because P1 owns config; the needed `limits.max_scheduler_iterations` key
#   is listed in the P4 report. (#KernelBootstrapV0/P4)
# ====================================================================
