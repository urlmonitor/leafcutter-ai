"""
MODULE: kernel.capabilities.retrieval.pool
GOAL: Build the pool of candidates one need considers (explicit locators first, then the
    strongest candidates of every source) and decide a need's coverage status from the evidence
    that was kept.
BUSINESS CONTEXT: Two live runs lost the evidence that answered the question before Jev ever saw
    it: a fair share per source cut a design section ranked 21st in its source, and a need was
    called satisfied by one weakly related item. The pool keeps the strongest content hits of every
    source, reports what it cut, and a need is satisfied only by enough evidence above the bar
    (Rev 3 section 10.3: what was cut is reported).
ARCHITECTURE: Pure functions over Candidate, SearchReport, Evidence and RetrievalConfig. The pool
    is ordered by sending priority, so the rerank step can cut its batch from the front: explicit
    locators, then each source's best candidates, then the rest by term hits.
"""

from __future__ import annotations

from collections.abc import Sequence

from kernel.capabilities.retrieval.candidates import Candidate, SearchReport
from kernel.capabilities.retrieval.locators import STRATEGY as EXPLICIT_STRATEGY
from kernel.config import RetrievalConfig
from kernel.contracts.enums import NeedStatus
from kernel.contracts.evidence import Evidence, UnavailableSource


def merge_pool(reports: Sequence[SearchReport], cfg: RetrievalConfig,
               explicit: Sequence[Candidate] = ()) -> list[Candidate]:
    """Return at most `max_candidates` candidates, in the order they should be sent to rerank.

    Explicit-locator candidates come first (asked for by name). Then every source is guaranteed
    its best few (an even share of the rerank batch, at least one), so a large source cannot crowd
    a small, curated one out; the remaining places go to the strongest candidates by term hits
    across all sources. Duplicate locators are dropped.

    Args:
        reports: One search report per source.
        cfg: Retrieval bounds (`max_candidates` is the pool, `rerank_max_per_need` the batch).
        explicit: Candidates fetched by explicit locator.

    Returns:
        list[Candidate]: The pool, sending priority first.
    """
    lanes = [list(r.candidates) for r in reports if r.candidates]
    limit = cfg.max_candidates
    chosen: dict[str, Candidate] = {c.locator: c for c in explicit[:limit]}
    floor = max(1, cfg.rerank_max_per_need // (2 * max(1, len(lanes))))
    for rank in range(floor):
        for lane in lanes:
            if rank < len(lane) and len(chosen) < limit:
                chosen.setdefault(lane[rank].locator, lane[rank])
    rest = sorted(((c, lane_no, rank) for lane_no, lane in enumerate(lanes)
                   for rank, c in enumerate(lane) if c.locator not in chosen),
                  key=lambda t: (-t[0].hits, t[1], t[2]))
    for cand, _, _ in rest:
        if len(chosen) < limit:
            chosen.setdefault(cand.locator, cand)
    return list(chosen.values())


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


def coverage_note(evidence: Sequence[Evidence], status: NeedStatus, cfg: RetrievalConfig
                  ) -> str | None:
    """Explain why a need with evidence stayed partial because the evidence is too thin."""
    if not evidence or status is not NeedStatus.PARTIAL:
        return None
    bar = cfg.coverage_relevance_threshold
    return (f"coverage: {len(above_bar(evidence, bar))} item(s) reached the relevance bar {bar} "
            f"and none the strong bar {cfg.satisfied_strong_threshold}; a need is satisfied by "
            f"{cfg.satisfied_min_items} such items or one strong item, so it stays partial "
            "(the items were kept as context, not as an answer)")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The pool guarantees every source its best candidates and fills the
#   rest by term hits across sources, instead of a strict round-robin: with six sources and a cap
#   of 60 the round-robin cut a design section that ranked 21st in its source although it had far
#   more hits than the sections it kept. The cut is reported. (#KernelV01/E)
# - 2026-10-01 [python-coder]: A need is satisfied by `satisfied_min_items` items above the bar or
#   one strong item; a single weakly related item (round 6, need.gap.2) leaves it partial.
#   Explicit-locator evidence counts as on topic (the caller named the place) and is not judged.
#   (#KernelV01/E)
# ====================================================================
