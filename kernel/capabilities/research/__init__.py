"""
MODULE: kernel.capabilities.research
GOAL: The native research capability (registry id `research`).
BUSINESS CONTEXT: Turns a question into an evidence bundle by planning generic evidence needs,
    fanning out retrieval children and collecting coverage, limitations and contradictions
    (Rev 3 sections 10.2 and 10.5).
ARCHITECTURE: executor.py holds the LangGraph graph; planning, collect and results are its
    nodes' logic. Bound by the composition root under binding key `research` version 1.0.0.
"""

from kernel.capabilities.research.executor import (
    CAPABILITY_ID,
    CAPABILITY_VERSION,
    ResearchExecutor,
)

__all__ = ["CAPABILITY_ID", "CAPABILITY_VERSION", "ResearchExecutor"]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Initial export surface. (#KernelBootstrapV0/P5)
# ====================================================================
