"""
MODULE: kernel.capabilities.retrieval.rerank
GOAL: Rerank retrieval candidates with one Jev batch of relevance nouls and keep the top ones.
BUSINESS CONTEXT: Term hits find candidates; whether a candidate actually answers the need is a
    bounded semantic judgement, which is what Jev is for (design part 4). Excerpt text is only
    ever quoted state, never part of an instruction.
ARCHITECTURE: Candidates get short ids (c1..cn) so question ids stay stable and readable. When
    the data policy forbids sending excerpts to Jev the ranking falls back to term hits and the
    bundle says so.
"""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import JsonValue

from kernel.capabilities.base import ExecutionContext
from kernel.capabilities.decision.jev_support import (
    ask_jev,
    excerpt_limit,
    make_batch,
    noul_question,
)
from kernel.capabilities.retrieval.candidates import Candidate
from kernel.contracts.capability import Usage
from kernel.contracts.evidence import EvidenceNeed
from kernel.contracts.work import CapabilityInvocation

PURPOSE = "retrieval.rerank"


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


async def rerank(ctx: ExecutionContext, invocation: CapabilityInvocation, need: EvidenceNeed,
                 candidates: list[Candidate], top_k: int) -> RerankOutcome:
    """Keep candidates with relevance >= relevance_threshold, at most top_k, best first.

    Candidates fetched by an explicit locator are always kept (first, with the relevance Jev gave
    them) and count against top_k, so naming a place can never lose to a lexical neighbour.

    Args:
        ctx: Execution context (config, Jev, budget).
        invocation: The running invocation.
        need: The evidence need the candidates should answer.
        candidates: Strategy output in rank order.
        top_k: Maximum number of candidates to keep.

    Returns:
        RerankOutcome: Kept candidates with relevance and rank.

    Raises:
        StopCapability: Jev was unavailable or over budget (propagated from ask_jev).
    """
    if not candidates:
        return RerankOutcome([], [], [])
    if not ctx.config.data_policy.send_repo_excerpts_to_jev:
        return _fallback(candidates, top_k, "data policy forbids sending excerpts to Jev")
    cap = excerpt_limit(ctx, len(candidates))
    ids = {f"c{i}": c for i, c in enumerate(candidates, start=1)}
    state: dict[str, JsonValue] = {
        "need": {"category": need.category.value, "question": need.question},
        "candidates": {cid: {"locator": c.locator, "title": c.title, "excerpt": c.excerpt[:cap]}
                       for cid, c in ids.items()}}
    questions = [noul_question(
        f"relevant.{cid}", "retrieval.relevant",
        f"Is `candidates.{cid}` relevant to answering `need`?") for cid in ids]
    result = await ask_jev(ctx, invocation, make_batch(ctx, PURPOSE, state, questions))
    threshold = ctx.config.retrieval.relevance_threshold
    scored = [(result.noul(f"relevant.{cid}").probability, i, c)
              for i, (cid, c) in enumerate(ids.items())]
    explicit = [t for t in scored if t[2].explicit]
    relevant = sorted((t for t in scored if not t[2].explicit and t[0] >= threshold),
                      key=lambda t: (-t[0], t[1]))
    slots = max(top_k - len(explicit), 0)
    chosen = explicit + relevant[:slots]
    kept = [Ranked(c, p, rank) for rank, (p, _, c) in enumerate(chosen)]
    return RerankOutcome(kept, [result.usage], [], len(scored) - len(explicit) - len(relevant))


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 [python-coder]: Explicit-locator candidates are kept regardless of relevance and
#   come first; they are still judged so coverage reflects how relevant they were. (#KernelV01/B)
# - 2026-09-30 23:00 [python-coder]: A failed Jev call fails the retrieval (it is not degraded
#   to unranked evidence) because a provider outage must stay visible; only an explicit data
#   policy switch skips the judgement, with a limitation. (#KernelBootstrapV0/P5)
# ====================================================================
