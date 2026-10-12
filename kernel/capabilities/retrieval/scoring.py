"""
MODULE: kernel.capabilities.retrieval.scoring
GOAL: The ranking signals of the lexical pre-filter: a length-normalised, document-frequency-
    weighted (BM25-style) score of a candidate section, the corpus statistics and term counts it
    needs, the vocabulary a registry speaks, and the word-run overlap of a text with the asking
    goal (a document that reviews a run of that goal).
BUSINESS CONTEXT: Raw term hits ranked huge registry JSON chunks (191 to 263 hits), long ticket
    comments and AC yaml above the short documents that answer the question, so the single 20-
    candidate rerank batch of round E judged noise while `kernel/persistence/run_store.py`, the
    tests READMEs and the design sections sat unjudged at pool positions 24 to 51. A term that
    occurs in most sections says little, and a long section hits a term by size alone. The score
    only ORDERS the pre-filter; it is never a gate and never a relevance judgement (spec section
    17: BM25 is not a mandatory gate; whether a candidate answers the need stays Jev's call).
ARCHITECTURE: Pure functions and one small mutable value (CorpusStats). Each search adds every
    section it scans to its stats (count of sections, characters, sections containing each term);
    merging the stats of all sources of a need gives one corpus, so scores of different sources
    are comparable. A candidate without per-term counts (knowledge-map nodes) is scored by its
    hit count alone, with the same saturation.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from kernel.capabilities.retrieval.chunking import registry_collection

if TYPE_CHECKING:
    from kernel.capabilities.retrieval.candidates import Candidate
    from kernel.config import RetrievalConfig

#: Words per shingle when comparing a text with the goal (long enough that sharing one is not a
#: coincidence of vocabulary).
SHINGLE_WORDS = 5
_WORD = re.compile(r"[a-z0-9]+")


@dataclass
class CorpusStats:
    """What the scanned sections say about how common each term is and how long a section is."""

    sections: int = 0
    chars: int = 0
    doc_freq: Counter[str] = field(default_factory=Counter)

    def add_section(self, length: int, counts: Mapping[str, int]) -> None:
        """Record one scanned section: its length and the terms it contains."""
        self.sections += 1
        self.chars += length
        self.doc_freq.update(term for term, count in counts.items() if count > 0)

    def merged(self, other: CorpusStats) -> CorpusStats:
        """Return the statistics of both corpora taken together."""
        return CorpusStats(self.sections + other.sections, self.chars + other.chars,
                           self.doc_freq + other.doc_freq)

    @property
    def average_length(self) -> float:
        """Return the mean section length in characters (0 for an empty corpus)."""
        return self.chars / self.sections if self.sections else 0.0


def rarity(containing: int, total: int) -> float:
    """Return the BM25 idf of something found in `containing` of `total` items."""
    return math.log(1.0 + (max(total, containing) - containing + 0.5) / (containing + 0.5))


def idf(term: str, stats: CorpusStats) -> float:
    """Return how telling the term is: high when few sections contain it, near 0 when most do."""
    return rarity(stats.doc_freq.get(term, 0), stats.sections)


def saturate(count: float, norm: float, k1: float) -> float:
    """Return the BM25 term-frequency factor: grows with the count but flattens out (k1)."""
    return count * (k1 + 1.0) / (count + k1 * norm)


def bm25(counts: Mapping[str, int], length: int, stats: CorpusStats, k1: float, b: float,
         average: float | None = None) -> float:
    """Return the BM25-style score of one section from its per-term counts and length.

    Args:
        counts: Occurrences of each query term in the section (heading hits already weighted).
        length: The section's length in characters (0 when unknown: no length normalisation).
        stats: The corpus the term rarity (idf) is taken from.
        k1: Term-frequency saturation.
        b: Strength of the length normalisation (0 to 1).
        average: The mean section length the length is compared with (default: the corpus's).
            Sources differ in granularity (a three-line yaml key against a whole design section),
            so a section is measured against its own source's mean.

    Returns:
        float: Higher is a better lexical match; comparable across sources.
    """
    mean = stats.average_length if average is None else average
    norm = 1.0 - b + b * length / mean if mean and length else 1.0
    return sum(idf(term, stats) * saturate(count, norm, k1)
               for term, count in counts.items() if count > 0)


def hits_score(hits: int, k1: float) -> float:
    """Return the score of a candidate known only by its hit count (same saturation, no idf)."""
    return saturate(hits, 1.0, k1)


def candidate_score(c: Candidate, stats: CorpusStats, average: float, cfg: RetrievalConfig
                    ) -> float:
    """Return the candidate's ordering score (higher is a better lexical match).

    BM25-style: a term's weight is its rarity over the corpus (`stats`), the section's length is
    measured against the mean of its OWN source (`average`: a source of three-line fragments and
    one of whole documents are not comparable by length), and every query term that is a distinctive
    word of the file's path adds `path_match_weight` times its rarity (a file named after the topic). A candidate known
    only by its hits (a knowledge-map node) is scored by them alone. A document that reviews a run
    of the asking goal is multiplied by `self_reference_penalty`, so it only reaches the first
    batch on a clearly stronger match.
    """
    if c.term_counts:
        score = bm25(dict(c.term_counts), c.length, stats, cfg.bm25_k1, cfg.bm25_b, average)
    else:
        score = hits_score(c.hits, cfg.bm25_k1)
    score += cfg.path_match_weight * sum(idf(term, stats) for term in c.path_hits)
    return score * cfg.self_reference_penalty if c.reviews_goal else score


#: Weight of a term hit in a section's heading path against one in its body.
HEADING_WEIGHT = 3
_NAME_WORD = re.compile(r"[a-z0-9]+")


def count_terms(body: str, label: str, terms: list[str]) -> dict[str, int]:
    """Return how often each query term occurs: in the body, plus heading hits weighted.

    Terms that do not occur are left out, so a section's counts are what it matched.
    """
    found: dict[str, int] = {}
    for term in terms:
        count = body.count(term) + HEADING_WEIGHT * label.count(term)
        if count:
            found[term] = count
    return found


def stand_in_score(counts: Mapping[str, int], length: int, cfg: RetrievalConfig) -> float:
    """Return a stand-in score to pick a file's best sections before the corpus is known.

    Saturated term counts over a length norm (relative to the excerpt cap), every term weighing
    the same; the real, corpus-aware score is computed once the whole source has been scanned.
    """
    norm = 1.0 - cfg.bm25_b + cfg.bm25_b * length / cfg.max_excerpt_chars
    return sum(saturate(count, norm, cfg.bm25_k1) for count in counts.values())


def registry_vocabulary(rel: str, text: str, terms: Sequence[str]) -> frozenset[str]:
    """Return the query words that are names in a registry's vocabulary (empty if not a registry).

    A registry is a JSON object holding one collection of entries; its vocabulary is the
    collection's name and the field names of its entries, singular or plural (`component` names
    `components`). A goal that speaks it ("filter by component and type") is about that registry.
    """
    if not rel.lower().endswith(".json"):
        return frozenset()
    found = registry_collection(text)
    if found is None:
        return frozenset()
    name, entries = found
    names = {name.lower(), *(k.lower() for e in entries.values() if isinstance(e, dict) for k in e)}
    names |= {w for n in list(names) for w in _NAME_WORD.findall(n)}
    return frozenset(t for t in terms if t in names or f"{t}s" in names or t.rstrip("s") in names)


def _shingles(text: str) -> set[tuple[str, ...]]:
    """Return the overlapping runs of SHINGLE_WORDS words of the text, lowercase."""
    words = _WORD.findall(text.lower())
    return {tuple(words[i:i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)}


def goal_overlap(goal: str, text: str) -> float:
    """Return the share of the goal's word runs that the text repeats verbatim (0 to 1).

    A goal shorter than one shingle has no runs to compare and overlaps nothing.
    """
    wanted = _shingles(goal)
    return len(wanted & _shingles(text)) / len(wanted) if wanted else 0.0


_RUN_ID = re.compile(r"\b(?:run|trace)[-_ ]?(?:id[-_ :]*)?[0-9a-f]{12,}\b", re.IGNORECASE)
#: Cheap substrings a run or trace id cannot be without (checked before the regex is run).
_RUN_HINTS = ("run-", "run_", "run ", "trace-", "trace_", "trace ")


def reviews_run_of_goal(rel: str, text: str, goal: str, quote_ratio: float,
                        path_markers: Sequence[str]) -> bool:
    """True if the document reviews or analyses a kernel run of this same goal.

    Conservative on purpose: a file whose name carries one of `path_markers` (`trace-review`), or
    a document that quotes at least `quote_ratio` of the goal's word runs AND names a run or trace
    id (`run-6081b132e12d4214`). A document that merely quotes the goal, or merely mentions a run,
    is ordinary evidence. A ratio of 0 turns the quote test off.
    """
    name = rel.lower().rsplit("/", 1)[-1]
    if any(marker.lower() in name for marker in path_markers if marker):
        return True
    if quote_ratio <= 0 or not goal:
        return False
    low = text.lower()
    if not any(hint in low for hint in _RUN_HINTS) or not _RUN_ID.search(low):
        return False
    return goal_overlap(goal, text) >= quote_ratio


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: A BM25-style score (idf from the sections the search scanned,
#   length-normalised, saturating term counts) orders the pool instead of raw hits; it is only an
#   ordering of the pre-filter, never a gate (spec section 17). Corpus statistics are merged
#   across the sources of a need so scores compare. goal_overlap moved here from rerank.py (still
#   importable from there). (#KernelV01/F)
# - 2026-10-01 [python-coder]: A review of a kernel run of the same goal is recognised per
#   document (a name marker, or a goal quote plus a run or trace id), not per excerpt: the user's
#   trace review ranked first (0.80) because the section that matched did not quote the goal.
#   (#KernelV01/F)
# ====================================================================
