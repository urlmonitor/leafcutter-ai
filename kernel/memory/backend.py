"""
MODULE: kernel.memory.backend
GOAL: Select the ColonyMemory backend from configuration (`memory.backend: file | null`).
BUSINESS CONTEXT: The composition root must not know which store serves precedent. A graph
    backend added later registers here and the kernel does not change (ADR-059); `null` keeps the
    kernel exactly as it was before the decision store existed.
ARCHITECTURE: One pure factory over the validated config, the repository root and the run root.
"""

from __future__ import annotations

from pathlib import Path

from kernel.config_memory import MemoryConfig
from kernel.memory.file_store import FileColonyMemory
from kernel.memory.port import ColonyMemory, NullColonyMemory


def build_memory(cfg: MemoryConfig, repo_root: Path, run_root: Path) -> ColonyMemory:
    """Return the configured backend (the file backend reads `cfg.decisions_dir` under the root)."""
    if cfg.backend == "null":
        return NullColonyMemory()
    return FileColonyMemory(repo_root, run_root, cfg.decisions_dir)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Backend choice is data (config), so switching the store off or
#   later to a graph needs no code change in the kernel. (#KernelDecisionStore)
# ====================================================================
