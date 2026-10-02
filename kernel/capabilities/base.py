"""
MODULE: kernel.capabilities.base
GOAL: The CapabilityExecutor port, the ExecutionContext handed to executors and the budget port.
BUSINESS CONTEXT: Every capability, native or host-backed, runs through one normalised boundary
    (Rev 3 section 5.1) and sees only its validated invocation plus read-only runtime
    dependencies: it cannot call peers or mutate run state.
ARCHITECTURE: ExecutionContext is a frozen dataclass of runtime dependencies that are never
    serialised into graph state. Capabilities propose follow-up work in CapabilityResult; the
    kernel schedules it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Protocol, runtime_checkable

from kernel.config import KernelConfig
from kernel.contracts.base import CorrelationIds
from kernel.contracts.capability import CapabilityDescriptor, CapabilityResult
from kernel.contracts.evidence import Evidence
from kernel.contracts.task import Scope
from kernel.contracts.work import CapabilityInvocation
from kernel.memory.port import ColonyMemory, NullColonyMemory
from kernel.observability.tracer import Tracer
from kernel.persistence.base import ArtifactStorePort
from kernel.providers.base import JevPort

BudgetResource = Literal["jev", "host", "work_item"]


class BudgetExhausted(Exception):
    """A budget reservation was refused because the limit is reached."""

    def __init__(self, resource: str = "") -> None:
        """Build the message from the exhausted resource."""
        super().__init__(f"budget exhausted: {resource}")
        self.resource = resource


@runtime_checkable
class BudgetPort(Protocol):
    """Reserve-before-use budget accounting (a Jev call is counted before it is made)."""

    def reserve(self, resource: BudgetResource) -> bool:
        """Reserve one unit; return False (and reserve nothing) if the limit is reached."""


class UnlimitedBudget:
    """BudgetPort that always grants and counts reservations (tests, single-shot tools)."""

    def __init__(self) -> None:
        """Start all counters at zero."""
        self.reserved: dict[str, int] = {"jev": 0, "host": 0, "work_item": 0}

    def reserve(self, resource: BudgetResource) -> bool:
        """Grant and count the reservation."""
        self.reserved[resource] += 1
        return True

    def available(self, resource: BudgetResource) -> int | None:
        """Report no limit (None): callers must not gate on an unbounded budget."""
        return None


@dataclass(frozen=True)
class ExecutionContext:
    """Runtime dependencies for one capability invocation (never serialised)."""

    run_id: str
    scope: Scope
    config: KernelConfig
    jev: JevPort
    tracer: Tracer
    corr: CorrelationIds
    artifacts: ArtifactStorePort
    budget: BudgetPort
    evidence_lookup: Callable[[Sequence[str]], list[Evidence]]
    clock: Callable[[], datetime]
    cancel_probe: Callable[[], bool]
    descriptor: CapabilityDescriptor | None = None
    constraints: tuple[str, ...] = ()
    #: Approved-decision memory: read precedent, stage a record (never written to the repository).
    memory: ColonyMemory = field(default_factory=NullColonyMemory)

    def evidence(self, ids: Sequence[str]) -> list[Evidence]:
        """Return the evidence items for ids (unknown ids are omitted), in the given order."""
        return self.evidence_lookup(ids)

    def cancelled(self) -> bool:
        """Return True if cancellation was requested."""
        return self.cancel_probe()


@runtime_checkable
class CapabilityExecutor(Protocol):
    """One normalised execution boundary for every capability."""

    async def ainvoke(self, invocation: CapabilityInvocation, ctx: ExecutionContext
                      ) -> CapabilityResult:
        """Execute the invocation and return a result that proposes work, never mutates state."""


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: ExecutionContext carries the ColonyMemory port (null by default), so
#   the decision capability reads precedent and stages records without knowing the backend.
#   (#KernelDecisionStore)
# - 2026-10-01 [python-coder]: A budget may also expose `available(resource)` (units left, None for
#   unbounded); it is an optional capability read through call_costs.jev_available, so the
#   BudgetPort protocol and its test doubles are unchanged. (#KernelV01/E)
# - 2026-09-30 23:59 [python-coder]: `constraints` carries the task's constraint texts (filled by
#   the scheduler) so executors can quote them to Jev without storing them as evidence.
#   (#KernelBootstrapV0/INT)
# - 2026-09-30 22:00 [python-coder]: BudgetPort.reserve returns a bool instead of raising so
#   guards can turn a refusal into a recorded budget_exhausted outcome; BudgetExhausted is
#   provided for callers that prefer to raise. (#KernelBootstrapV0/P1)
# ====================================================================
