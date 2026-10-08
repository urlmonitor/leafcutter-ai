"""
MODULE: kernel.capabilities.retrieval
GOAL: The native read-only repository retrieval capability (registry id `retrieve.repository`).
BUSINESS CONTEXT: Supplies inspectable evidence from allowlisted repository files and the
    knowledge map so decisions rest on real sources (Rev 3 section 10.3).
ARCHITECTURE: executor.py orchestrates; repository.py and knowledge_map.py are the strategies;
    access.py enforces read policy. Bound by the composition root under binding key
    `retrieve.repository` version 1.0.0.
"""

from kernel.capabilities.retrieval.executor import (
    CAPABILITY_ID,
    CAPABILITY_VERSION,
    RepositoryRetrievalExecutor,
)

__all__ = ["CAPABILITY_ID", "CAPABILITY_VERSION", "RepositoryRetrievalExecutor"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Initial export surface. (#KernelBootstrapV0/P5)
# ====================================================================
