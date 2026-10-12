"""
MODULE: kernel.observability.tracer
GOAL: The Tracer port plus NoOpTracer and RecordingTracer test doubles.
BUSINESS CONTEXT: Traces are the audit trail of a decision run; the kernel must emit correlated
    observations without depending on Langfuse, so tests can assert names, ids and nesting
    offline (Rev 3 section 12).
ARCHITECTURE: Tracer is a Protocol implemented by LangfuseTracer (P2). Explicit span handles and
    a ContextVar for nesting keep concurrent Send workers correct. RecordingTracer stores every
    call in order.
"""

from __future__ import annotations

import contextvars
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, ContextManager, Protocol, runtime_checkable

from kernel.contracts.base import CorrelationIds, KernelModel
from kernel.contracts.capability import Usage
from kernel.contracts.enums import ObservabilityStatus
from kernel.observability.correlation import deterministic_trace_id


class TraceState(KernelModel):
    """Trace identity persisted in state and run.json."""

    trace_id: str
    root_observation_id: str | None = None
    trace_url: str | None = None


class SpanHandle(Protocol):
    """Handle returned by Tracer.span for late updates."""

    def update(self, *, output: Any = None, metadata: dict[str, Any] | None = None,
               level: str | None = None) -> None:
        """Attach output, metadata or a level to the open span."""


@runtime_checkable
class Tracer(Protocol):
    """Observability port used by the scheduler, capabilities and the Jev adapter."""

    def open_segment(self, run_id: str, root_task_id: str, kind: str) -> TraceState:
        """Open this process's segment of the run trace (kind: start, resume, status, cancel)."""

    def span(self, name: str, kind: str, corr: CorrelationIds, *, input: Any = None,
             metadata: dict[str, Any] | None = None) -> ContextManager[SpanHandle]:
        """Open a span as a context manager."""

    def generation(self, name: str, corr: CorrelationIds, *, model: str, input: Any,
                   output: Any, usage: Usage | None, metadata: dict[str, Any] | None = None
                   ) -> None:
        """Record one model call with its usage."""

    def event(self, name: str, corr: CorrelationIds, *, level: str = "DEFAULT",
              payload: dict[str, Any] | None = None) -> None:
        """Record a point-in-time event."""

    def langchain_callbacks(self, corr: CorrelationIds) -> list:
        """Return LangChain callback handlers for this correlation (empty when unsupported)."""

    def close_segment(self) -> ObservabilityStatus:
        """Flush and close the segment; report ok or degraded."""


class _NullSpan:
    """SpanHandle that ignores updates."""

    def update(self, *, output: Any = None, metadata: dict[str, Any] | None = None,
               level: str | None = None) -> None:
        """Ignore the update."""


class NoOpTracer:
    """Tracer that records nothing (default when observability is off)."""

    def open_segment(self, run_id: str, root_task_id: str, kind: str) -> TraceState:
        """Return the deterministic trace identity without emitting anything."""
        return TraceState(trace_id=deterministic_trace_id(run_id))

    @contextmanager
    def span(self, name: str, kind: str, corr: CorrelationIds, *, input: Any = None,
             metadata: dict[str, Any] | None = None) -> Iterator[SpanHandle]:
        """Yield a handle that ignores updates."""
        yield _NullSpan()

    def generation(self, name: str, corr: CorrelationIds, *, model: str, input: Any,
                   output: Any, usage: Usage | None, metadata: dict[str, Any] | None = None
                   ) -> None:
        """Ignore the generation."""

    def event(self, name: str, corr: CorrelationIds, *, level: str = "DEFAULT",
              payload: dict[str, Any] | None = None) -> None:
        """Ignore the event."""

    def langchain_callbacks(self, corr: CorrelationIds) -> list:
        """Return no callbacks."""
        return []

    def close_segment(self) -> ObservabilityStatus:
        """Report ok (nothing to flush)."""
        return ObservabilityStatus.OK


@dataclass
class RecordedCall:
    """One call captured by RecordingTracer."""

    index: int
    kind: str
    name: str
    corr: CorrelationIds
    parent: int | None = None
    data: dict[str, Any] = field(default_factory=dict)
    closed: bool = False


class _RecordedSpan:
    """SpanHandle writing into a RecordedCall."""

    def __init__(self, call: RecordedCall) -> None:
        """Bind the handle to its recorded call."""
        self._call = call

    def update(self, *, output: Any = None, metadata: dict[str, Any] | None = None,
               level: str | None = None) -> None:
        """Merge output, metadata and level into the recorded span data."""
        if output is not None:
            self._call.data["output"] = output
        if metadata:
            self._call.data.setdefault("metadata", {}).update(metadata)
        if level is not None:
            self._call.data["level"] = level


_CURRENT: contextvars.ContextVar[int | None] = contextvars.ContextVar("rec_tracer_span",
                                                                     default=None)


class RecordingTracer:
    """Tracer test double storing every call for assertions on names, ids and nesting."""

    def __init__(self, status: ObservabilityStatus = ObservabilityStatus.OK) -> None:
        """Create an empty recorder; status is what close_segment reports."""
        self.calls: list[RecordedCall] = []
        self.status = status
        self.segments: list[tuple[str, str, str]] = []
        self.closed_segments = 0

    def _add(self, kind: str, name: str, corr: CorrelationIds, **data: Any) -> RecordedCall:
        """Append a call parented to the current span."""
        call = RecordedCall(len(self.calls), kind, name, corr, _CURRENT.get(), dict(data))
        self.calls.append(call)
        return call

    def open_segment(self, run_id: str, root_task_id: str, kind: str) -> TraceState:
        """Record the segment and return the deterministic trace identity."""
        self.segments.append((run_id, root_task_id, kind))
        corr = CorrelationIds(run_id=run_id, root_task_id=root_task_id)
        self._add("segment", f"leafcutter.run.{kind}", corr)
        return TraceState(trace_id=deterministic_trace_id(run_id))

    @contextmanager
    def span(self, name: str, kind: str, corr: CorrelationIds, *, input: Any = None,
             metadata: dict[str, Any] | None = None) -> Iterator[SpanHandle]:
        """Record a span; calls made inside it are parented to it."""
        call = self._add("span", name, corr, span_kind=kind, input=input,
                         metadata=dict(metadata or {}))
        token = _CURRENT.set(call.index)
        try:
            yield _RecordedSpan(call)
        finally:
            _CURRENT.reset(token)
            call.closed = True

    def generation(self, name: str, corr: CorrelationIds, *, model: str, input: Any,
                   output: Any, usage: Usage | None, metadata: dict[str, Any] | None = None
                   ) -> None:
        """Record a generation with its model, payloads and usage."""
        self._add("generation", name, corr, model=model, input=input, output=output,
                  usage=usage, metadata=dict(metadata or {}))

    def event(self, name: str, corr: CorrelationIds, *, level: str = "DEFAULT",
              payload: dict[str, Any] | None = None) -> None:
        """Record an event."""
        self._add("event", name, corr, level=level, payload=dict(payload or {}))

    def langchain_callbacks(self, corr: CorrelationIds) -> list:
        """Return no callbacks (the recorder captures explicit calls only)."""
        return []

    def close_segment(self) -> ObservabilityStatus:
        """Count the close and report the configured status."""
        self.closed_segments += 1
        return self.status

    def named(self, name: str, kind: str | None = None) -> list[RecordedCall]:
        """Return recorded calls with this name (and kind, if given)."""
        return [c for c in self.calls if c.name == name and (kind is None or c.kind == kind)]

    def children_of(self, call: RecordedCall) -> list[RecordedCall]:
        """Return calls directly nested under the given span."""
        return [c for c in self.calls if c.parent == call.index]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Nesting uses a ContextVar (per asyncio task) instead of a
#   shared stack because Send workers run concurrently. (#KernelBootstrapV0/P1)
# ====================================================================
