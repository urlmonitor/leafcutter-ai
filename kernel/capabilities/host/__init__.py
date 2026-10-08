"""
MODULE: kernel.capabilities.host
GOAL: The bounded host operations: one module per `host.*` capability, each compiling its packet
    text and converting the host's schema-valid output into a CapabilityResult.
BUSINESS CONTEXT: Claude Code performs work the kernel cannot (option generation, synthesis,
    research the native sources cannot do, question wording) but never gains authority: output is
    a proposal or a host-reported claim, instruction-like text stays data (Rev 3 sections 10.4,
    11.3, 11.7 and 13.3; ADR-052).
ARCHITECTURE: `spec` holds the value types, `compiler` the deterministic renderer, `base` the
    HostOperation class, `sanitize` the shared conversion rules, four operation modules, a
    lookup `registry`, `telemetry` and the bound `executor`. Nothing here imports the scheduler
    or the interaction package; those import this one.
"""

from kernel.capabilities.host.executor import HostBindingExecuted, HostOperationExecutor
from kernel.capabilities.host.registry import (
    OPERATIONS,
    compiler_for,
    host_operation,
    template_versions,
)
from kernel.capabilities.host.spec import (
    CompiledTask,
    HostConversion,
    TaskInputs,
    bounded,
    parse_compiled_by,
)
from kernel.capabilities.host.telemetry import emit_host_telemetry

__all__ = ["OPERATIONS", "CompiledTask", "HostBindingExecuted", "HostConversion",
           "HostOperationExecutor", "TaskInputs", "bounded", "compiler_for",
           "emit_host_telemetry", "host_operation", "parse_compiled_by", "template_versions"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 11:55 [python-coder]: One module per operation (plus shared spec, compiler and
#   sanitize) keeps every file far below the size cap and lets a fifth host capability be added
#   by one module and one table entry. (#KernelBootstrapV0/P8)
# ====================================================================
