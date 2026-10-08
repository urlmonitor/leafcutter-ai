"""
MODULE: kernel.capabilities.host.executor
GOAL: The CapabilityExecutor bound to every host_handoff descriptor: it prepares the packet text
    and converts the host's result, and refuses to run anything in-process.
BUSINESS CONTEXT: Rev 3 section 11: host work is done by the client, never by the kernel. The
    binding exists so eligibility finds an approved, versioned implementation; the scheduler
    opens an interaction instead of calling it, and the operation it carries does the compile
    and conversion that keep host output within a host authority.
ARCHITECTURE: A thin wrapper over a HostOperation (generic when the capability has no module).
    `ainvoke` raises `HostBindingExecuted`: reaching it means a host binding was run as if it
    were native, which the scheduler must never do.
"""

from __future__ import annotations

from kernel.capabilities.host.base import HostOperation
from kernel.capabilities.host.registry import compiler_for
from kernel.capabilities.host.spec import CompiledTask, HostConversion, Mask, TaskInputs
from kernel.contracts import CapabilityInvocation, CapabilityResult


class HostBindingExecuted(RuntimeError):
    """A host_handoff binding was executed in-process, which the scheduler must never do."""

    def __init__(self) -> None:
        """Build the fixed message."""
        super().__init__("a host_handoff binding must never execute in-process")


class HostOperationExecutor:
    """Executor for one host capability: prepares packets and converts results, never runs."""

    def __init__(self, capability_id: str = "") -> None:
        """Bind the operation of the capability (the generic one for an unknown id)."""
        self.capability_id = capability_id
        self.operation: HostOperation = compiler_for(capability_id)

    def prepare(self, inputs: TaskInputs, mask: Mask | None = None) -> CompiledTask:
        """Return the compiled task text of a packet."""
        return self.operation.compile(inputs, mask)

    def convert(self, ctx: HostConversion) -> CapabilityResult:
        """Return the CapabilityResult of an accepted host submission."""
        return self.operation.convert(ctx)

    async def ainvoke(self, invocation: CapabilityInvocation, ctx: object) -> CapabilityResult:
        """Never called: host items open an interaction and wait for the client."""
        raise HostBindingExecuted


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:50 [python-coder]: `ainvoke` still raises: P8 gives the binding real packet and
#   conversion behaviour, but the kernel executing host work itself would break the trust model,
#   so the scheduler keeps routing host items to an interaction. (#KernelBootstrapV0/P8)
# ====================================================================
