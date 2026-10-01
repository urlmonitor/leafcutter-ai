"""
MODULE: kernel.capabilities.retrieval.candidates
GOAL: The Candidate and SearchReport value objects shared by the retrieval strategies.
BUSINESS CONTEXT: Both strategies (repository text and knowledge map) must report what they found
    and what they could not read in one shape, so a failed or partial search stays visible in the
    bundle instead of looking like an empty result (Rev 3 section 10.3).
ARCHITECTURE: Frozen dataclasses with no behaviour; built by repository.py and knowledge_map.py,
    consumed by rerank.py and evidence_build.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from kernel.contracts.enums import SourceKind


@dataclass(frozen=True)
class Candidate:
    """One excerpt found by a strategy, before reranking."""

    source_id: str
    kind: SourceKind
    strategy: str
    path: str
    title: str
    locator: str
    excerpt: str
    hits: int
    terms: tuple[str, ...]
    truncated: bool = False
    modified_at: datetime | None = None


@dataclass
class SearchReport:
    """What one strategy did for one source."""

    source_id: str
    candidates: list[Candidate] = field(default_factory=list)
    files_scanned: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    unavailable_reason: str | None = None
    notes: list[str] = field(default_factory=list)

    def skip(self, reason: str) -> None:
        """Count one skipped file or node under a reason."""
        self.skipped[reason] = self.skipped.get(reason, 0) + 1


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: Skips are counted per reason so the bundle can state how
#   many files were too large, denied or binary instead of silently narrowing the search.
#   (#KernelBootstrapV0/P5)
# ====================================================================
