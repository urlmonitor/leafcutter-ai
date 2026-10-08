"""
MODULE: kernel.observability.correlation
GOAL: Correlation ids and deterministic trace identity helpers.
BUSINESS CONTEXT: Every observation must carry the ids needed to find the run, work item,
    invocation and decision it belongs to, and a restarted process must append to the same trace
    (Rev 3 section 12.2).
ARCHITECTURE: The value objects live in kernel.contracts.base (to keep contracts free of the
    observability package) and are re-exported here; this module adds helper constructors.
"""

from __future__ import annotations

import hashlib

from kernel.contracts.base import CorrelationIds, TraceContext
from kernel.contracts.work import CapabilityInvocation

__all__ = ["CorrelationIds", "TraceContext", "correlation_for_invocation",
           "deterministic_trace_id", "run_correlation"]


def deterministic_trace_id(run_id: str) -> str:
    """Return a 32-hex trace id derived from the run id (same algorithm as Langfuse seeds).

    Args:
        run_id: The run id used as the seed.

    Returns:
        str: 32 lowercase hex characters, identical for every process and restart.
    """
    return hashlib.sha256(run_id.encode("utf-8")).digest()[:16].hex()


def run_correlation(run_id: str, root_task_id: str | None = None) -> CorrelationIds:
    """Return run-level correlation ids."""
    return CorrelationIds(run_id=run_id, root_task_id=root_task_id)


def correlation_for_invocation(base: CorrelationIds, invocation: CapabilityInvocation,
                               request_id: str | None = None,
                               parent_work_item_id: str | None = None) -> CorrelationIds:
    """Extend run-level correlation ids with the invocation's identifiers.

    Args:
        base: Run-level correlation ids.
        invocation: The invocation being executed.
        request_id: Id of the request the work item serves.
        parent_work_item_id: Parent work item, if any.

    Returns:
        CorrelationIds: Copy carrying work item, invocation and capability ids.
    """
    return base.with_updates(
        work_item_id=invocation.work_item_id, invocation_id=invocation.id,
        capability_id=invocation.capability_id, request_id=request_id,
        parent_work_item_id=parent_work_item_id)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: deterministic_trace_id mirrors Langfuse create_trace_id
#   (sha256 prefix) without importing the SDK, so offline tests and the tracer agree.
#   (#KernelBootstrapV0/P1)
# ====================================================================
