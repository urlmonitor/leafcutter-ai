"""
MODULE: kernel.capabilities.decision
GOAL: The native decision capability (registry id `decision`).
BUSINESS CONTEXT: Turns a bounded question, options, criteria and evidence into a resolved
    recommendation or a typed request for whatever is missing (Rev 3 sections 9 and 10.1).
ARCHITECTURE: executor.py holds the LangGraph graph; the other modules are its nodes and helpers.
    Bound by the composition root under binding key `decision` version 1.0.0.
"""

from kernel.capabilities.decision.executor import (
    CAPABILITY_ID,
    CAPABILITY_VERSION,
    DecisionExecutor,
)

__all__ = ["CAPABILITY_ID", "CAPABILITY_VERSION", "DecisionExecutor"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Initial export surface. (#KernelBootstrapV0/P5)
# ====================================================================
