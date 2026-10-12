"""
MODULE: kernel.persistence
GOAL: Persistence ports, record models and in-memory implementations.
BUSINESS CONTEXT: The scheduler depends on ports only, so durable file stores (P2) and memory
    doubles are interchangeable.
ARCHITECTURE: Re-exports from base and memory; file-backed stores live in sibling modules
    added by P2.
"""

from kernel.persistence.base import (
    ArtifactRef,
    ArtifactStorePort,
    CancelInfo,
    GapStorePort,
    RunAlreadyExists,
    RunNotFound,
    RunRecord,
    RunStorePort,
    SubmissionRecord,
    aggregate_gaps,
)
from kernel.persistence.artifacts import FileArtifactStore
from kernel.persistence.checkpointer import open_checkpointer
from kernel.persistence.gap_store import FileGapStore
from kernel.persistence.memory import (
    ARTIFACT_NAME_RE,
    InvalidArtifactName,
    MemoryArtifactStore,
    MemoryGapStore,
    MemoryRunStore,
)
from kernel.persistence.run_store import FileRunStore

__all__ = [
    "ARTIFACT_NAME_RE", "ArtifactRef", "ArtifactStorePort", "CancelInfo", "FileArtifactStore",
    "FileGapStore", "FileRunStore", "GapStorePort",
    "InvalidArtifactName", "MemoryArtifactStore", "MemoryGapStore", "MemoryRunStore",
    "RunAlreadyExists", "RunNotFound", "RunRecord", "RunStorePort", "SubmissionRecord",
    "aggregate_gaps", "open_checkpointer",
]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:59 [python-coder]: Re-exported the P2 file stores and open_checkpointer.
#   (#KernelBootstrapV0/INT)
# - 2026-09-30 22:00 [python-coder]: Initial export surface for P2-P9. (#KernelBootstrapV0/P1)
# ====================================================================
