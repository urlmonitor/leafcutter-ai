"""
MODULE: kernel.service_session
GOAL: One process segment of a run as an async context manager: open the trace segment, the
    checkpointer, the Jev adapter and the compiled graph, hand them out, and close everything in
    the right order.
BUSINESS CONTEXT: A run spans several processes (start, resume, status, cancel). Each one must
    append a segment to the run's single trace, create the Jev client inside the loop that uses
    it, and flush telemetry without ever letting a telemetry problem break the run (Rev 3
    sections 12.2 and 12.4).
ARCHITECTURE: `open_session` yields a `Session`. On exit it closes the Jev adapter, then the
    segment (`close_segment`, which reports ok or degraded), then the checkpointer. The tracer's
    `shutdown` is the environment's job and runs once per process, after the last segment.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from kernel.bootstrap import KernelEnvironment
from kernel.contracts import ALL_MODELS, CorrelationIds
from kernel.contracts.enums import ObservabilityStatus
from kernel.observability.correlation import deterministic_trace_id, run_correlation
from kernel.observability.tracer import TraceState
from kernel.persistence import open_checkpointer
from kernel.providers.base import JevPort
from kernel.scheduler import (
    STATE_MODELS,
    KernelRuntime,
    build_kernel_graph,
    run_config,
)
from kernel.service_errors import ProviderUnavailable

logger = logging.getLogger(__name__)

NEEDS_JEV = frozenset({"start", "resume"})


@dataclass
class Session:
    """The live pieces of one segment.

    Attributes:
        run_id: The run this segment belongs to.
        kind: start, resume, status or cancel.
        trace: This segment's trace identity (its root observation parents new work).
        graph: The compiled kernel graph over the open checkpointer.
        config: LangGraph config (thread id, recursion limit, tracer callbacks).
        runtime: The KernelRuntime for graph invocations.
        observability: Export health, set when the segment closed.
    """

    run_id: str
    kind: str
    trace: TraceState
    graph: Any
    config: dict[str, Any]
    runtime: KernelRuntime
    observability: ObservabilityStatus = ObservabilityStatus.OK

    def runtime_corr(self) -> CorrelationIds:
        """Return run-level correlation ids for events the service records itself."""
        return run_correlation(self.run_id)

    async def values(self) -> dict[str, Any]:
        """Return the checkpointed state values (empty before the first superstep)."""
        snapshot = await self.graph.aget_state(self.config)
        return dict(snapshot.values)


def _open_trace(env: KernelEnvironment, run_id: str, root_task_id: str, kind: str
                ) -> TraceState:
    """Open the tracer segment; a telemetry failure degrades to the deterministic identity."""
    try:
        return env.tracer.open_segment(run_id, root_task_id, kind)
    except (OSError, RuntimeError, ValueError):
        logger.warning("could not open the %s trace segment of %s", kind, run_id, exc_info=True)
        return TraceState(trace_id=deterministic_trace_id(run_id))


def _close_trace(env: KernelEnvironment) -> ObservabilityStatus:
    """Close the segment; a telemetry failure reports degraded instead of raising."""
    try:
        return env.tracer.close_segment()
    except (OSError, RuntimeError, ValueError):
        logger.warning("could not close the trace segment", exc_info=True)
        return ObservabilityStatus.DEGRADED


def _make_jev(env: KernelEnvironment, kind: str) -> JevPort | None:
    """Build the Jev adapter for segments that route work (inside the running loop)."""
    if kind not in NEEDS_JEV:
        return None
    if env.jev_factory is None:
        raise ProviderUnavailable("jev", "no Jev API key is configured")
    return env.jev_factory()


async def _close_jev(jev: JevPort | None) -> None:
    """Close the adapter in the loop that created it; a failure is logged, not raised."""
    closer = getattr(jev, "aclose", None)
    if closer is None:
        return
    try:
        await closer()
    except (OSError, RuntimeError):
        logger.warning("could not close the Jev adapter", exc_info=True)


@asynccontextmanager
async def open_session(env: KernelEnvironment, kind: str, run_id: str,
                       root_task_id: str = "pending") -> AsyncIterator[Session]:
    """Open one segment of a run.

    Args:
        env: The composed environment.
        kind: start, resume, status or cancel (the trace segment kind).
        run_id: The run id (the checkpoint thread id).
        root_task_id: The run's root task id when known.

    Yields:
        Session: Graph, config, runtime and trace for this segment.

    Raises:
        ProviderUnavailable: start or resume without a configured Jev credential.
    """
    jev = _make_jev(env, kind)
    trace = _open_trace(env, run_id, root_task_id, kind)
    session: Session | None = None
    try:
        async with open_checkpointer(env.run_root,
                                     extra_types=[*ALL_MODELS, *STATE_MODELS]) as saver:
            callbacks = env.tracer.langchain_callbacks(run_correlation(run_id, root_task_id))
            runtime = KernelRuntime(
                config=env.config, bindings=env.bindings, jev=jev, tracer=env.tracer,
                run_store=env.run_store, gap_store=env.gap_store, artifacts=env.artifacts,
                secrets=env.secrets, cancel_probe=lambda: env.run_store.is_cancelled(run_id),
                redactor=env.redactor, trace=trace)
            session = Session(
                run_id, kind, trace, build_kernel_graph(saver),
                run_config(run_id, env.config.limits.langgraph_recursion_limit, callbacks),
                runtime)
            yield session
    finally:
        await _close_jev(jev)
        status = _close_trace(env)
        if session is not None:
            session.observability = status


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 10:50 [python-coder]: Status and cancel segments build no Jev adapter (they never
#   route work), so they work without a credential. (#KernelBootstrapV0/P7)
# - 2026-10-01 10:50 [python-coder]: The Jev adapter is closed before the segment so its last
#   generation is exported inside the segment that made the call. (#KernelBootstrapV0/P7)
# ====================================================================
