"""
MODULE: kernel.registry.fallback
GOAL: Find the approved generic host operation that may serve an unsupported request (bounded
    host fallback), or say why none may.
BUSINESS CONTEXT: Fallback is a deliberate, bounded exception (Rev 3 section 14): it needs
    configuration, a bound host_handoff capability that produces the requested output, granted
    permissions, no forbidden side effects, a matching scope and host-operation budget; a denied
    native action is never routed here (the gap node decides that before it asks).
ARCHITECTURE: Pure function over the pinned registry snapshot and plain values (no scheduler
    imports), called by the gap node with its budget arithmetic already done.
"""

from __future__ import annotations

from collections.abc import Collection

from kernel.config import KernelConfig
from kernel.contracts.capability import CapabilityDescriptor, RegistrySnapshot
from kernel.contracts.enums import ExecutionMode, RequestKind
from kernel.contracts.work import RequestBody
from kernel.registry.bindings import BindingTable
from kernel.registry.eligibility import MVP_SIDE_EFFECTS


def find_fallback(snapshot: RegistrySnapshot, bindings: BindingTable, cfg: KernelConfig,
                  permissions: Collection[str], scope_ids: Collection[str],
                  request: RequestBody, host_operations_left: int
                  ) -> tuple[CapabilityDescriptor | None, str]:
    """Return the host operation that may serve an unsupported request, or (None, reason).

    Args:
        snapshot: The run's pinned registry snapshot.
        bindings: The trusted binding table.
        cfg: Kernel configuration (host fallback switches).
        permissions: Permissions granted to the run.
        scope_ids: Scope component ids.
        request: The unsupported request.
        host_operations_left: Host operations the budget still allows.

    Returns:
        tuple: (descriptor, "") for the first usable host operation by id, else (None, reason).
    """
    if not (cfg.host.enabled and cfg.host.fallback_on_no_match):
        return None, "host fallback is disabled"
    if request.kind is RequestKind.HUMAN:
        return None, "human questions are never routed to a host fallback"
    granted, scope = set(permissions), set(scope_ids)
    for d in sorted(snapshot.descriptors, key=lambda x: x.id):
        ops = d.cost_hints.host_operations if d.cost_hints.host_operations is not None else 1
        usable = (d.execution_mode is ExecutionMode.HOST_HANDOFF and d.enabled
                  and d.availability.status != "unavailable"
                  and request.kind in d.request_kinds
                  and request.requested_output_schema in d.produces_schemas
                  and bindings.has(d.binding, d.version)
                  and set(d.permissions_required) <= granted
                  and d.side_effect_class in MVP_SIDE_EFFECTS
                  and (not d.components or bool(set(d.components) & scope)))
        if usable and ops <= host_operations_left:
            return d, ""
    return None, "no approved host operation produces the requested output"


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 22:00 [python-coder]: Moved out of nodes_gaps.py (unchanged logic) to keep that
#   module under the file-size limit; the budget arithmetic stays in the node.
#   (#KernelBootstrapV0/INTENT)
# ====================================================================
