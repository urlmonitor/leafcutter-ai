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
from kernel.persistence.memory import (
    ARTIFACT_NAME_RE,
    InvalidArtifactName,
    MemoryArtifactStore,
    MemoryGapStore,
    MemoryRunStore,
)

__all__ = [
    "ARTIFACT_NAME_RE", "ArtifactRef", "ArtifactStorePort", "CancelInfo", "GapStorePort",
    "InvalidArtifactName", "MemoryArtifactStore", "MemoryGapStore", "MemoryRunStore",
    "RunAlreadyExists", "RunNotFound", "RunRecord", "RunStorePort", "SubmissionRecord",
    "aggregate_gaps",
]

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 22:00 [python-coder]: Initial export surface for P2-P9. (#KernelBootstrapV0/P1)
# ====================================================================
