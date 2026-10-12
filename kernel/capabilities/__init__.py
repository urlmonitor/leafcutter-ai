"""
MODULE: kernel.capabilities
GOAL: Capability execution port and context.
BUSINESS CONTEXT: Native graphs, retrieval and host handoffs all implement CapabilityExecutor so
    the kernel treats them uniformly.
ARCHITECTURE: Re-exports from base; concrete capabilities live in subpackages added by P5 and P8.
"""

from kernel.capabilities.base import (
    BudgetExhausted,
    BudgetPort,
    BudgetResource,
    CapabilityExecutor,
    ExecutionContext,
    UnlimitedBudget,
)

__all__ = ["BudgetExhausted", "BudgetPort", "BudgetResource", "CapabilityExecutor",
           "ExecutionContext", "UnlimitedBudget"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Initial export surface. (#KernelBootstrapV0/P1)
# ====================================================================
