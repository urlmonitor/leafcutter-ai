"""
MODULE: kernel.registry
GOAL: Capability registry adapter, trusted bindings and the deterministic eligibility filter.
BUSINESS CONTEXT: The kernel routes only among registered capabilities from its own registry,
    which starts empty; legacy assets enter only through a recorded admission decision.
ARCHITECTURE: adapter (load + snapshot pinning), bindings (trusted factories), eligibility
    (pure filter). Re-exported here for the scheduler and composition root.
"""

from kernel.contracts.capability import CapabilityDescriptor, RegistrySnapshot
from kernel.registry.adapter import (
    RegistryCompatibilityError,
    RegistryError,
    load_component_ids,
    load_registry,
    verify_pinned,
)
from kernel.registry.bindings import BindingTable, BindingUnavailable
from kernel.registry.eligibility import (
    UNAVAILABLE_CODES,
    EligibilityReport,
    filter_candidates,
)

__all__ = [
    "UNAVAILABLE_CODES", "BindingTable", "BindingUnavailable", "CapabilityDescriptor",
    "EligibilityReport", "RegistryCompatibilityError", "RegistryError", "RegistrySnapshot",
    "filter_candidates", "load_component_ids", "load_registry", "verify_pinned",
]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Initial export surface. (#KernelBootstrapV0/P1)
# ====================================================================
