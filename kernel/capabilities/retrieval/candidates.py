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

from kernel.capabilities.retrieval.scoring import CorpusStats
from kernel.contracts.enums import SourceKind


#: Prefix of the note naming a file skipped for its size, and how many such files are named.
OVERSIZED = "not read, too large:"
MAX_OVERSIZED_NAMED = 3


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
    explicit: bool = False
    """True when the caller named this place (an explicit locator); never dropped by ranking."""
    score: float = 0.0
    """Lexical ordering score (BM25-style, see scoring.py); 0 until the pool scores it."""
    length: int = 0
    """Length in characters of the whole section the excerpt was cut from (0 when unknown)."""
    term_counts: tuple[tuple[str, int], ...] = ()
    """Occurrences of each query term in the section (heading hits weighted, path matches added)."""
    path_hits: tuple[str, ...] = ()
    (
        "The query terms that are distinctive words of the file's path (`run_store.py` for "
        "\"store\": a file NAMED after the topic)."
    )
    reviews_goal: bool = False
    """True when the document reviews or analyses a kernel run of the asking goal."""


@dataclass
class SearchReport:
    """What one strategy did for one source."""

    source_id: str
    candidates: list[Candidate] = field(default_factory=list)
    files_scanned: int = 0
    skipped: dict[str, int] = field(default_factory=dict)
    unavailable_reason: str | None = None
    notes: list[str] = field(default_factory=list)
    stats: CorpusStats = field(default_factory=CorpusStats)
    """What the scan saw of the source (sections, lengths, term frequencies) for scoring."""

    def skip(self, reason: str) -> None:
        """Count one skipped file or node under a reason."""
        self.skipped[reason] = self.skipped.get(reason, 0) + 1

    def note_oversized(self, rel: str, limit: int) -> None:
        """Name a file skipped for its size, with the remedy (a count alone hides which one).

        A source that needs a large file raises `max_file_bytes` on the source itself; only the
        first few files are named so a folder of generated data cannot flood the limitations.
        """
        if sum(note.startswith(OVERSIZED) for note in self.notes) < MAX_OVERSIZED_NAMED:
            self.notes.append(f"{OVERSIZED} {rel} (over {limit} bytes: raise `max_file_bytes` on "
                              "this source or in `retrieval`)")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A candidate carries its section length and per-term counts and a
#   report the corpus statistics of its scan, so the pool can score candidates of all sources on
#   one length-normalised, document-frequency-weighted scale; `reviews_goal` marks a document that
#   reviews a run of the asking goal. (#KernelV01/F)
# - 2026-10-01 [python-coder]: `explicit` marks a candidate fetched by locator so reranking keeps
#   it and provenance can say so. (#KernelV01/B)
# - 2026-09-30 23:00 [python-coder]: Skips are counted per reason so the bundle can state how
#   many files were too large, denied or binary instead of silently narrowing the search.
#   (#KernelBootstrapV0/P5)
# ====================================================================
