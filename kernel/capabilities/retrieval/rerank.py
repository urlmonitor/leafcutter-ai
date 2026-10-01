"""
MODULE: kernel.capabilities.retrieval.rerank
GOAL: Rerank retrieval candidates with one Jev batch of relevance nouls and keep the top ones.
BUSINESS CONTEXT: Term hits find candidates; whether a candidate actually answers the need is a
    bounded semantic judgement, which is what Jev is for (design part 4). Excerpt text is only
    ever quoted state, never part of an instruction. Round E judged one batch and stopped as soon
    as one candidate passed, so deeper and stronger candidates were never judged; a need now goes
    on, within the budget and the requester's reserve, until it has enough relevant evidence.
ARCHITECTURE: Candidates get short ids (c1..cn) so question ids stay stable and readable. Batches
    follow the pool order; the loop stops when the need has enough on-topic items, when what is
    left scores clearly below what was judged, at `rerank_max_batches` or when the budget says no.
    When the data policy forbids sending excerpts to Jev the ranking falls back to term hits and
    the bundle says so.
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass

from pydantic import JsonValue

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import (
    StopCapability,
    ask_jev,
    excerpt_limit,
    make_batch,
    noul_question,
)
from kernel.capabilities.retrieval.candidates import Candidate
from kernel.capabilities.retrieval.scoring import goal_overlap
from kernel.config import RetrievalConfig
from kernel.contracts.capability import Usage
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.work import CapabilityInvocation

PURPOSE = "retrieval.rerank"
__all__ = ["PURPOSE", "Ranked", "RerankOutcome", "goal_overlap", "rerank"]


@dataclass(frozen=True)
class Ranked:
    """A kept candidate with its relevance (None when Jev was not asked)."""

    candidate: Candidate
    relevance: float | None
    rank: int


@dataclass(frozen=True)
class RerankOutcome:
    """Kept candidates plus usage and limitations from the rerank step."""

    kept: list[Ranked]
    usage: list[Usage]
    limitations: list[str]
    dropped_irrelevant: int = 0


def _fallback(candidates: list[Candidate], top_k: int, why: str) -> RerankOutcome:
    """Rank by term hits only (no Jev), keeping the order the strategies produced."""
    chosen = _with_explicit_first(candidates)[:max(top_k, _explicit_count(candidates))]
    kept = [Ranked(c, None, i) for i, c in enumerate(chosen)]
    return RerankOutcome(kept, [], [f"relevance not judged: {why}"])


def _explicit_count(candidates: list[Candidate]) -> int:
    """Return how many candidates were fetched by an explicit locator."""
    return sum(1 for c in candidates if c.explicit)


def _with_explicit_first(candidates: list[Candidate]) -> list[Candidate]:
    """Return the candidates with the explicit ones first (each group keeps its order)."""
    return [c for c in candidates if c.explicit] + [c for c in candidates if not c.explicit]


def _demoted(c: Candidate, goal: str | None, cited: Collection[str], ratio: float) -> bool:
    """True if the candidate reviews the asking run and was not explicitly cited.

    A document that quotes the whole request is a review or analysis OF the run asking, not
    evidence for it (a live run ranked the trace review of its own previous run first because it
    quotes the goal). Two tests: the excerpt repeats the goal near-verbatim, or the search
    flagged the whole document as a review of a kernel run of this goal (`reviews_goal`: a run or
    trace id beside the goal's quote, or a `trace-review` file name), which the matching section
    need not quote. A ratio of 0 turns both off; a cited path is never demoted.
    """
    if not goal or ratio <= 0 or c.path in cited:
        return False
    return c.reviews_goal or goal_overlap(goal, c.excerpt) >= ratio


async def _judge(ctx: ExecutionContext, invocation: CapabilityInvocation, need: EvidenceNeed,
                 batch: list[Candidate], goal: str | None, cited: Collection[str],
                 prior_usage: list[Usage]) -> tuple[list[tuple[float, int, Candidate]], Usage, int]:
    """Judge one batch of candidates with one Jev call; return (scored, usage, demoted count).

    A candidate that repeats the goal near-verbatim (and is not cited) has its relevance
    multiplied by `retrieval.self_reference_penalty`.

    Raises:
        StopCapability: Jev was unavailable or over budget (propagated from ask_jev).
    """
    cfg = ctx.config.retrieval
    cap = excerpt_limit(ctx, len(batch))
    ids = {f"c{i}": c for i, c in enumerate(batch, start=1)}
    state: dict[str, JsonValue] = {
        "need": {"category": need.category.value, "question": need.question},
        "candidates": {cid: {"locator": c.locator, "title": c.title, "excerpt": c.excerpt[:cap]}
                       for cid, c in ids.items()}}
    questions = [noul_question(
        f"relevant.{cid}", "retrieval.relevant",
        f"Is `candidates.{cid}` relevant to answering `need`?") for cid in ids]
    result = await ask_jev(ctx, invocation, make_batch(ctx, PURPOSE, state, questions),
                           prior_usage=prior_usage)
    scored, demoted = [], 0
    for i, (cid, c) in enumerate(ids.items()):
        p = result.noul(f"relevant.{cid}").probability
        if _demoted(c, goal, cited, cfg.self_reference_ratio):
            p, demoted = p * cfg.self_reference_penalty, demoted + 1
        scored.append((p, i, c))
    return scored, result.usage, demoted


def _enough(scored: list[tuple[float, int, Candidate]], named: int, cfg: RetrievalConfig) -> bool:
    """True if the judged candidates already give the need enough on-topic evidence.

    The need would count as satisfied (`satisfied_min_items` items at the coverage bar or one
    strong item; a named place counts as on topic) AND at least `rerank_min_items` items passed
    the keep bar, so a need is not left with one or two items when a deeper look is affordable.
    """
    ratings = [p for p, _, _ in scored]
    kept = sum(p >= cfg.relevance_threshold for p in ratings) + named
    on_topic = sum(p >= cfg.coverage_relevance_threshold for p in ratings) + named
    strong = any(p >= cfg.satisfied_strong_threshold for p in ratings)
    return (on_topic >= cfg.satisfied_min_items or strong) and kept >= cfg.rerank_min_items


def _deeper_is_weaker(left: list[Candidate], scored: list[tuple[float, int, Candidate]],
                      cfg: RetrievalConfig) -> bool:
    """True if nothing is left, or the best unjudged candidate scores clearly below the judged ones.

    The score is the pool's lexical one (a deeper batch of weak matches is not worth a call).
    """
    if not left:
        return True
    judged = max((c.score for _, _, c in scored), default=0.0)
    return max(c.score for c in left) < cfg.rerank_stop_ratio * judged


async def rerank(ctx: ExecutionContext, invocation: CapabilityInvocation, need: EvidenceNeed,
                 candidates: list[Candidate], top_k: int, *, goal: str | None = None,
                 cited: Collection[str] = (), max_batches: int | None = None) -> RerankOutcome:
    """Keep candidates with relevance >= relevance_threshold, at most top_k, best first.

    Candidates fetched by an explicit locator are kept regardless (first) and count against
    top_k, so naming a place can never lose to a lexical neighbour; they are not sent to Jev, which
    saves their share of the batch. The other candidates (the pool, in sending priority order) are
    judged `retrieval.rerank_max_per_need` at a time, one Jev call per batch. The first batch is
    always judged; a further one (up to `retrieval.rerank_max_batches`, and `max_batches` when the
    requester's budget allows fewer) only while the need lacks evidence: it stops once the judged
    candidates give the need enough on-topic items (see `_enough`), or what is left scores clearly
    below what was judged (`retrieval.rerank_stop_ratio`). A later batch the budget cannot fund
    ends the search with what was found, and says so.

    Args:
        ctx: Execution context (config, Jev, budget).
        invocation: The running invocation.
        need: The evidence need the candidates should answer.
        candidates: The pool in sending priority order (explicit locators among them).
        top_k: Maximum number of candidates to keep.
        goal: The request's goal; a candidate that reviews it is demoted.
        cited: Paths the request named explicitly (never demoted).
        max_batches: Most batches the requester's budget affords (None: the configured limit).

    Returns:
        RerankOutcome: Kept candidates with relevance and rank.

    Raises:
        StopCapability: Jev was unavailable or over budget for the first batch.
    """
    if not candidates:
        return RerankOutcome([], [], [])
    if not ctx.config.data_policy.send_repo_excerpts_to_jev:
        return _fallback(candidates, top_k, "data policy forbids sending excerpts to Jev")
    cfg = ctx.config.retrieval
    named = [c for c in candidates if c.explicit]
    searched = [c for c in candidates if not c.explicit]
    size = cfg.rerank_max_per_need
    allowed = cfg.rerank_max_batches if max_batches is None else max(1, min(
        cfg.rerank_max_batches, max_batches))
    batches = [searched[i:i + size] for i in range(0, len(searched), size)][:allowed]
    scored: list[tuple[float, int, Candidate]] = []
    usage: list[Usage] = []
    notes: list[str] = []
    demoted = judged = 0
    for number, batch in enumerate(batches):
        try:
            part, used, count = await _judge(ctx, invocation, need, batch, goal, cited, usage)
        except StopCapability as stop:
            if number == 0:
                raise
            usage = list(stop.result.usage)  # finished batches plus any call the stop completed
            notes.append(f"rerank stopped after {number} of {len(batches)} batch(es): the Jev "
                         "budget cannot fund the next one")
            break
        scored += [(p, number * size + i, c) for p, i, c in part]
        usage, demoted, judged = [*usage, used], demoted + count, judged + len(batch)
        if _enough(scored, len(named), cfg) or _deeper_is_weaker(searched[judged:], scored, cfg):
            break
    notes += _unjudged_note(searched[judged:], len(searched), cfg, allowed)
    if demoted:
        notes.append(f"{demoted} candidate(s) quote the request near-verbatim or review a kernel "
                     "run of it (a review or analysis of the run asking) and were demoted")
    relevant = sorted((t for t in scored if t[0] >= cfg.relevance_threshold),
                      key=lambda t: (-t[0], t[1]))
    slots = max(top_k - len(named), 0)
    chosen = [(None, 0, c) for c in named] + relevant[:slots]
    kept = [Ranked(c, p, rank) for rank, (p, _, c) in enumerate(chosen)]
    return RerankOutcome(kept, usage, notes, len(scored) - len(relevant))


def _unjudged_note(left: list[Candidate], total: int, cfg: RetrievalConfig, allowed: int
                   ) -> list[str]:
    """Say how many candidates were not judged and which of them scored best (same score)."""
    if not left:
        return []
    best = max(left, key=lambda c: c.score)
    return [f"{len(left)} of {total} candidate(s) were not judged "
            f"(retrieval.rerank_max_per_need={cfg.rerank_max_per_need}, rerank_max_batches="
            f"{cfg.rerank_max_batches}, batches allowed here {allowed}); strongest not judged: "
            f"{best.locator} (score {best.score:.1f}, {best.hits} hit(s))"]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: The loop no longer stops at the first batch with one relevant
#   candidate: it goes on (to `rerank_max_batches`, or `max_batches` from the requester's budget)
#   until the need has enough on-topic items and `rerank_min_items` kept ones, or what is left
#   scores below `rerank_stop_ratio` of what was judged. "Strongest not judged" is the pool's
#   score, not raw hits. A document flagged as a review of a run of this goal is demoted whether
#   or not the matching section quotes the goal. (#KernelV01/F)
# - 2026-10-01 [python-coder]: A need judges further batches (up to retrieval.rerank_max_batches)
#   only while nothing relevant was found: with one batch of 20 the live pause goal found no
#   evidence at all (it had found some among the 60), so the cap would have blocked a decision
#   the old pool could ground. A later batch the budget cannot fund keeps the earlier results.
#   (#KernelV01/E)
# - 2026-10-01 [python-coder]: One Jev batch of at most retrieval.rerank_max_per_need candidates
#   per need (round 6 sent 60 in three calls per need and spent 33 of 40 calls on reranks);
#   explicit-locator hits are no longer judged (they are kept regardless); a candidate that
#   repeats the goal near-verbatim is demoted unless cited (conservative: word-run overlap above
#   retrieval.self_reference_ratio, relevance times retrieval.self_reference_penalty).
#   (#KernelV01/E)
# - 2026-10-01 [python-coder]: Explicit-locator candidates are kept regardless of relevance and
#   come first; they were also judged so coverage reflected how relevant they were; round E
#   stopped judging them. (#KernelV01/B)
# - 2026-09-30 23:00 [python-coder]: A failed Jev call fails the retrieval (it is not degraded
#   to unranked evidence) because a provider outage must stay visible; only an explicit data
#   policy switch skips the judgement, with a limitation. (#KernelBootstrapV0/P5)
# ====================================================================
