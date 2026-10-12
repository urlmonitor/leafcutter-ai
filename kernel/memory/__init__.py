"""
MODULE: kernel.memory
GOAL: The decision store: the `ColonyMemory` port, its null and file backends, the decision record
    model, builder, validation, generated index, publication and the `decisions` CLI.
BUSINESS CONTEXT: Approved decisions are filed as reviewable YAML records in the repository and
    later runs reuse them as precedent (ADR-059). The kernel talks only to the port, so a graph
    backend can replace the file store later without kernel changes; the kernel never writes into
    the repository during a run (ADR-060).
ARCHITECTURE: A leaf package: it imports kernel contracts and persistence helpers, never
    capabilities or the scheduler, so `kernel.capabilities.base` can hold a `ColonyMemory` on its
    ExecutionContext without an import cycle. Modules that depend on the decision capability's
    internals (`precedent`, `staging`) are not imported here for the same reason.
"""

from __future__ import annotations

from kernel.memory.models import DecisionRecord
from kernel.memory.port import (
    ColonyMemory,
    DecisionHit,
    DecisionQuery,
    NullColonyMemory,
    StagedRecord,
)

__all__ = ["ColonyMemory", "DecisionHit", "DecisionQuery", "DecisionRecord", "NullColonyMemory",
           "StagedRecord"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: New package for the decision store (files in docs/decisions behind
#   a port) because kernel/capabilities/decision and tests/kernel/grounding are at the folder
#   density limit. (#KernelDecisionStore)
# ====================================================================
