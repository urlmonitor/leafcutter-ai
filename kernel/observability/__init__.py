"""
MODULE: kernel.observability
GOAL: Observability ports and in-memory doubles: Tracer, NoOpTracer, RecordingTracer and
    correlation helpers.
BUSINESS CONTEXT: The kernel and capabilities depend on the Tracer port only; Langfuse is one
    implementation (P2), so runs stay testable and degrade gracefully when export fails.
ARCHITECTURE: Re-exports from tracer and correlation; nothing here imports Langfuse.
"""

from kernel.observability.correlation import (
    CorrelationIds,
    TraceContext,
    correlation_for_invocation,
    deterministic_trace_id,
    run_correlation,
)
from kernel.observability.tracer import (
    NoOpTracer,
    RecordedCall,
    RecordingTracer,
    SpanHandle,
    TraceState,
    Tracer,
)

__all__ = [
    "CorrelationIds", "NoOpTracer", "RecordedCall", "RecordingTracer", "SpanHandle",
    "TraceContext", "TraceState", "Tracer", "correlation_for_invocation",
    "deterministic_trace_id", "run_correlation",
]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Package init re-exports only the port and doubles; P2 adds
#   langfuse_tracer/redaction/spool as separate modules. (#KernelBootstrapV0/P1)
# ====================================================================
