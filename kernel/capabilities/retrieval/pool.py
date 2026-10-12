"""
MODULE: kernel.capabilities.retrieval.pool
GOAL: Build the pool of candidates one need considers (explicit locators first, then the best
    candidates by one length-normalised score, with a fair share per source and a cap per file)
    and decide a need's coverage status from the evidence that was kept.
BUSINESS CONTEXT: Live runs lost the evidence that answered the question before Jev ever saw it:
    a fair share per source cut a design section ranked 21st in its source, raw term hits let
    registry JSON and AC yaml fill the single 20-candidate rerank batch while the files that
    answer sat at pool positions 24 to 51, and a need was called satisfied by one weakly related
    item. The pool orders by a BM25-style score over all sources, guarantees every source its best
    candidates, never lets one file take the batch and reports what it cut (Rev 3 section 10.3:
    what was cut is reported).
ARCHITECTURE: Pure functions over Candidate, SearchReport, Evidence and RetrievalConfig. The pool
    is ordered by sending priority, so the rerank step can cut its batch from the front: explicit
    locators, then the first batch (each source's best by score, then the best of the rest, sorted
    by score), then everything else by score. The score only orders; Jev still judges relevance.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import replace

from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.locators import STRATEGY as EXPLICIT_STRATEGY
from kernel.capabilities.retrieval.scoring import CorpusStats, candidate_score
from kernel.config import RetrievalConfig
from kernel.contracts.enums import NeedStatus
from kernel.contracts.evidence import Evidence, UnavailableSource


def _lanes(reports: Sequence[SearchReport], cfg: RetrievalConfig) -> list[list[Candidate]]:
    """Return each source's candidates scored on the shared corpus, best first."""
    stats = CorpusStats()
    for report in reports:
        stats = stats.merged(report.stats)
    lanes = [[replace(c, score=candidate_score(c, stats, r.stats.average_length, cfg))
              for c in r.candidates] for r in reports if r.candidates]
    return [sorted(lane, key=lambda c: (-c.score, c.locator)) for lane in lanes]


def _fair_front(lanes: list[list[Candidate]], cfg: RetrievalConfig) -> list[Candidate]:
    """Return the candidates every source is guaranteed in the first batch.

    Each source's `pool_fair_share` best, round by round (every source's best before any source's
    second), at most half the batch, and only those whose score reaches `pool_fair_min_ratio` of
    the best score of all: a small, curated source cannot be crowded out by a big one, and a source
    with nothing but weak matches does not spend places the strong ones need.
    """
    best = max((lane[0].score for lane in lanes), default=0.0)
    floor = cfg.pool_fair_min_ratio * best
    slots = max(1, cfg.rerank_max_per_need // 2)
    front: list[Candidate] = []
    for rank in range(cfg.pool_fair_share):
        for lane in lanes:
            if rank < len(lane) and lane[rank].score >= floor and len(front) < slots:
                front.append(lane[rank])
    return front


class _Pool:
    """The pool under construction: a size limit, a cap per file and the cap overflow."""

    def __init__(self, cfg: RetrievalConfig, explicit: Sequence[Candidate]) -> None:
        """Start with the explicit candidates (kept regardless, counted against the limit)."""
        self.cfg = cfg
        self.chosen: dict[str, Candidate] = {c.locator: c for c in explicit[:cfg.max_candidates]}
        self.per_file = Counter(c.path for c in self.chosen.values())
        self.overflow: list[Candidate] = []

    def take(self, cand: Candidate, file_cap: int, front: bool = False) -> None:
        """Add the candidate unless the pool is full, it is a duplicate or a cap holds it back.

        A candidate held back by a cap waits in the overflow and fills a place left at the end. For
        the first batch (`front`) a document that reviews a run of the asking goal is held back
        too: it spends a place Jev would judge only to demote it.
        """
        if cand.locator in self.chosen or len(self.chosen) >= self.cfg.max_candidates:
            return
        if self.per_file[cand.path] >= file_cap or (front and cand.reviews_goal):
            self.overflow.append(cand)
            return
        self.chosen[cand.locator] = cand
        self.per_file[cand.path] += 1

    def filled(self, size: int) -> bool:
        """True once the pool holds `size` candidates (or is full)."""
        return len(self.chosen) >= min(size, self.cfg.max_candidates)

    def ordered(self) -> list[Candidate]:
        """Return the explicit candidates, then the others best score first."""
        named = [c for c in self.chosen.values() if c.explicit]
        rest = sorted((c for c in self.chosen.values() if not c.explicit),
                      key=lambda c: (-c.score, c.locator))
        return [*named, *rest]


def merge_pool(reports: Sequence[SearchReport], cfg: RetrievalConfig,
               explicit: Sequence[Candidate] = ()) -> list[Candidate]:
    """Return at most `max_candidates` candidates, in the order they should be sent to rerank.

    Explicit-locator candidates come first (asked for by name, never judged). The first batch of
    `rerank_max_per_need` follows, ordered by score: every source's best candidates (a fair share,
    see _fair_front) completed by the best of all the others, with at most
    `pool_sections_per_file` sections of one file and at most `pool_source_share` of the batch from
    one source (the batch spans documents and sources). The rest of the pool is ordered by score
    with at most `sections_per_file` sections of a file; whatever those caps held back fills the
    places left. Duplicate locators are dropped. The score is length-normalised and weighs rare
    terms (BM25 style, see scoring.py); it orders the pool and decides nothing about relevance.

    Args:
        reports: One search report per source (candidates and corpus statistics).
        cfg: Retrieval bounds (`max_candidates` is the pool, `rerank_max_per_need` the batch).
        explicit: Candidates fetched by explicit locator.

    Returns:
        list[Candidate]: The pool, sending priority first.
    """
    lanes = _lanes(reports, cfg)
    everyone = sorted((c for lane in lanes for c in lane), key=lambda c: (-c.score, c.locator))
    pool = _Pool(cfg, explicit)
    batch = cfg.rerank_max_per_need
    target = len(pool.chosen) + batch
    guaranteed = {c.locator for c in _fair_front(lanes, cfg)}
    for cand in (c for c in everyone if c.locator in guaranteed):
        pool.take(cand, cfg.pool_sections_per_file, front=True)
    for cand in everyone:
        if not pool.filled(target):
            pool.take(cand, cfg.pool_sections_per_file, front=True)
    front = pool.ordered()
    for cand in everyone:
        pool.take(cand, cfg.sections_per_file)
    for cand in everyone + pool.overflow:
        if len(pool.chosen) < cfg.max_candidates:
            pool.chosen.setdefault(cand.locator, cand)
    kept = {c.locator for c in front}
    return front + [c for c in pool.ordered() if c.locator not in kept]


def pool_note(reports: Sequence[SearchReport], explicit: Sequence[Candidate], pool: list[Candidate],
              cfg: RetrievalConfig) -> list[str]:
    """Say what the pool left out (nothing when every candidate fit)."""
    offered = sum(len(r.candidates) for r in reports) + len(explicit)
    if offered <= len(pool):
        return []
    sources = sorted({r.source_id for r in reports if r.candidates})
    return [f"candidate pool capped at {cfg.max_candidates} (retrieval.max_candidates): "
            f"{offered - len(pool)} of {offered} candidate(s) from {len(sources)} source(s) "
            f"were not offered"]


def _explicit(item: Evidence) -> bool:
    """True if the item was fetched by an explicit locator (named by the caller)."""
    return item.provenance.strategy == EXPLICIT_STRATEGY


def above_bar(items: Sequence[Evidence], bar: float) -> list[Evidence]:
    """Return the items on topic: judged at or above `bar`, or named by an explicit locator."""
    return [e for e in items if _explicit(e)
            or (e.provenance.relevance is not None and e.provenance.relevance >= bar)]


def strong(items: Sequence[Evidence], cfg: RetrievalConfig) -> list[Evidence]:
    """Return the items judged at or above the strong bar, or named by an explicit locator."""
    return [e for e in items if _explicit(e) or (
        e.provenance.relevance is not None
        and e.provenance.relevance >= cfg.satisfied_strong_threshold)]


def coverage(evidence: Sequence[Evidence], consulted: int,
             unavailable: Sequence[UnavailableSource], cfg: RetrievalConfig) -> NeedStatus:
    """Return the need status: unavailable, open (searched, nothing), partial or satisfied.

    Satisfied needs `satisfied_min_items` items at or above `coverage_relevance_threshold`, or one
    item at or above `satisfied_strong_threshold`; anything weaker (or never judged) is partial,
    and so is a bundle with an unavailable source.
    """
    if consulted == 0:
        return NeedStatus.UNAVAILABLE
    if not evidence:
        return NeedStatus.OPEN
    if unavailable:
        return NeedStatus.PARTIAL
    enough = len(above_bar(evidence, cfg.coverage_relevance_threshold)) >= cfg.satisfied_min_items
    return NeedStatus.SATISFIED if enough or strong(evidence, cfg) else NeedStatus.PARTIAL


def coverage_note(evidence: Sequence[Evidence], status: NeedStatus, cfg: RetrievalConfig,
                  need_id: str | None = None) -> str | None:
    """Explain why a need with evidence stayed partial because the evidence is too thin.

    The note names the need (`need_id`): a bundle of several needs, or a run log, must say which
    one is thin.
    """
    if not evidence or status is not NeedStatus.PARTIAL:
        return None
    bar = cfg.coverage_relevance_threshold
    head = f"coverage of need {need_id}: " if need_id else "coverage: "
    return (f"{head}{len(above_bar(evidence, bar))} item(s) reached the relevance bar {bar} "
            f"and none the strong bar {cfg.satisfied_strong_threshold}; a need is satisfied by "
            f"{cfg.satisfied_min_items} such items or one strong item, so it stays partial "
            "(the items were kept as context, not as an answer)")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: merge_pool orders by a BM25-style score on the corpus of all
#   sources (not raw hits), guarantees every source `pool_fair_share` candidates whose score
#   reaches `pool_fair_min_ratio` of the best (at most half the first batch; the old guarantee
#   shrank to one place with six sources), holds a file to `pool_sections_per_file` places while
#   the pool has room, and sorts the first batch by score. The thin-coverage note names its need.
#   (#KernelV01/F)
# - 2026-10-01 [python-coder]: The pool guarantees every source its best candidates and fills the
#   rest by term hits across sources, instead of a strict round-robin: with six sources and a cap
#   of 60 the round-robin cut a design section that ranked 21st in its source although it had far
#   more hits than the sections it kept. The cut is reported. (#KernelV01/E)
# - 2026-10-01 [python-coder]: A need is satisfied by `satisfied_min_items` items above the bar or
#   one strong item; a single weakly related item (round 6, need.gap.2) leaves it partial.
#   Explicit-locator evidence counts as on topic (the caller named the place) and is not judged.
#   (#KernelV01/E)
# ====================================================================
