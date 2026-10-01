"""
MODULE: kernel.scheduler
GOAL: Public surface of the kernel scheduler: the compiled-graph factory, the runtime context,
    the state types and the guard helpers other phases plug into.
BUSINESS CONTEXT: P2 (checkpointer, run store, tracer), P5 (capability executors), P6
    (interaction), P7 (service and composition root) and P9 (gaps, guards) integrate through
    these names only.
ARCHITECTURE: Importing the package builds nothing: call build_kernel_graph(checkpointer) and
    invoke with `context=KernelRuntime(...)`. STATE_MODELS extends contracts.ALL_MODELS for the
    strict-msgpack checkpoint allowlist.
"""

from __future__ import annotations

from kernel.scheduler.context import KernelRuntime, flush_events
from kernel.scheduler.graph import build_kernel_graph, initial_state, run_config
from kernel.scheduler.guards import GuardTrip, normalize_text, request_dedup_key
from kernel.scheduler.nodes_lifecycle import decide_outcome
from kernel.scheduler.state import STATE_MODELS, Budgets, KernelState, RunOutcome

__all__ = ["STATE_MODELS", "Budgets", "GuardTrip", "KernelRuntime", "KernelState", "RunOutcome",
           "build_kernel_graph", "decide_outcome", "flush_events", "initial_state",
           "normalize_text", "request_dedup_key", "run_config"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:30 [python-coder]: Exports only what other phases need; node functions stay
#   private to the package. (#KernelBootstrapV0/P4)
# ====================================================================
