"""MODULE: neo4j_retention
GOAL: Report which retained generations a declared retention bound permits reclaiming.
BUSINESS CONTEXT: Storage is only reclaimed on evidence; the active generation is never at risk.
ARCHITECTURE: Read-only evaluation over generation facts; reclaiming lives elsewhere.

DECISION HISTORY
========================================
- 2026-10-14 23:50 [python-coder]: Name every reclaimability basis per generation and count each basis apart, stating a zero and the overlap; failed publications take no count slot. (#KM-400f-1-iv)
- 2026-10-14 23:30 [python-coder]: Keep retention evaluation in its own module so projection stays under the file-size limit and further retention work lands here. (#KM-400f-1-iii)
- 2026-10-14 23:00 [python-coder]: Protect the active generation by the active pointer alone; with no pointer, report that and reclaim nothing. (#KM-400f-1-iii)
- 2026-10-14 22:00 [python-coder]: State each verdict's age basis (retired_at, created_at or undetermined); an undetermined age is never reclaimable. (#KM-400f-1-ii)
- 2026-10-14 [python-coder]: Assess every generation record regardless of publication outcome and report the assessed count. (#KM-400f-1-i)
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.config import RetentionBound

_INCOMPLETE_ACTIVE = "the active pointer references a generation whose publication did not complete"
_NO_ACTIVE = "no active generation could be identified"
_NO_BOUND = "retention bound is not declared; evaluation refused"
OUTSIDE_COUNT_BOUND = "outside_count_bound"
PUBLICATION_FAILED = "publication_failed"
_BASIS_NOTE = (
    "per-basis counts may overlap: a generation holding both bases is counted under each, "
    "so the counts are not a total; see reclaimable for the total"
)


async def evaluate_retention(
    db: Neo4jBackend,
    repository_id: str,
    bound: RetentionBound,
    now: float | None = None,
) -> dict:
    """Report which retained generations a declared bound permits reclaiming.

    Read-only: it reports a verdict per generation and never reclaims, retires
    or re-points anything. Count rank is by creation time, newest first, and the
    active generation occupies one slot of the count limit.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace isolating all reads.
        bound: Declared retention bound naming a generation count AND a
            minimum retirement age; refused when absent.
        now: Optional clock value for deterministic age checks.

    Returns:
        A report naming the bound, the ``assessed`` count of generation
        records evaluated (whatever their publication outcome), and a
        reclaimability verdict with a reason for every one of them.

    Raises:
        TypeError: When no declared RetentionBound is supplied (nothing is read).
    """
    from knowledge.config import RetentionBound

    if not isinstance(bound, RetentionBound):
        raise TypeError(_NO_BOUND)
    clock = time.time() if now is None else now
    facts = await db.retention_facts(repository_id)
    # A generation with no creation time has no place in the newest-first order; it ranks last.
    ordered = sorted(
        facts,
        key=lambda f: (
            f["created_at"] is None,
            -(f["created_at"] or 0),
            f["generation_id"],
        ),
    )
    active = active_generation_verdict(facts)
    verdicts = [
        {"generation_id": f["generation_id"], **_verdict(f, rank, bound, clock)}
        for f, rank in zip(ordered, _count_ranks(ordered))
    ]
    if not active["identified"]:
        verdicts = [_withhold(v) for v in verdicts]
    return {
        "bound": bound.model_dump(),
        "assessed": len(verdicts),
        "active_generation": active["generation_id"],
        "findings": [active["finding"]] if active["finding"] else [],
        "generations": verdicts,
        "reclaimable": [v["generation_id"] for v in verdicts if v["reclaimable"]],
        "reclaimable_by_basis": _basis_counts(verdicts),
        "reclaimable_by_basis_note": _BASIS_NOTE,
    }


def _count_ranks(ordered: list[dict]) -> list[int]:
    """Rank each generation by how many completed-publication generations are newer.

    A generation that records a failed publication never occupies a count slot, so it
    does not push an older generation outside the bound; its own rank is the number of
    non-failed generations newer than it.

    Args:
        ordered: Generation rows, newest first.

    Returns:
        One rank per row, in the same order.
    """
    ranks = []
    occupied = 0
    for fact in ordered:
        ranks.append(occupied)
        if fact.get("publication_status") != "failed":
            occupied += 1
    return ranks


def _basis_counts(verdicts: list[dict]) -> dict[str, int]:
    """Count reclaimable generations per basis; both keys are always present.

    Args:
        verdicts: Per-generation verdicts carrying ``reclaimable_bases``.

    Returns:
        Mapping of each named basis to its count, 0 stated when none holds it.
    """
    return {
        basis: sum(1 for v in verdicts if basis in v["reclaimable_bases"])
        for basis in (OUTSIDE_COUNT_BOUND, PUBLICATION_FAILED)
    }


def active_generation_verdict(facts: list[dict]) -> dict:
    """Identify the generation the active pointer references, from the pointer alone.

    The result is keyed only on the ``active`` flag of the ``retention_facts`` rows, which is
    true when the repository's active pointer equals the generation's key. Neither publication
    outcome nor creation order is consulted to find or to protect it.

    Args:
        facts: Rows returned by ``retention_facts``.

    Returns:
        Mapping with ``identified`` (bool), ``generation_id`` (str or None),
        ``publication_completed`` (bool, or None when unidentified) and ``finding`` (a
        statement to report, or None when the active generation is complete).
    """
    for fact in facts:
        if fact["active"]:
            completed = fact.get("publication_status") == "ready"
            return {
                "identified": True,
                "generation_id": fact["generation_id"],
                "publication_completed": completed,
                "finding": None if completed else _INCOMPLETE_ACTIVE,
            }
    return {
        "identified": False,
        "generation_id": None,
        "publication_completed": None,
        "finding": _NO_ACTIVE,
    }


def _withhold(verdict: dict) -> dict:
    """Replace one verdict with the refusal to reclaim while no active generation is known.

    Args:
        verdict: A per-generation verdict from ``_verdict``.

    Returns:
        The verdict, not reclaimable, with reason ``active_generation_unidentified``.
    """
    return {
        **verdict,
        "reclaimable": False,
        "reclaimable_bases": [],
        "reason": "active_generation_unidentified",
        "reason_detail": "no generation is reclaimable while the active pointer references none",
    }


async def retention_facts(db: Neo4jBackend, repository_id: str) -> list[dict]:
    """Read generation_id, publication_status, active, created_at, retired_at and pinned_until.

    Every generation record is returned whatever its publication outcome
    (ready, validated, building, failed); none is filtered out.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace isolating all reads.

    Returns:
        One row per generation record; pinned_until is None when no
        continuation is pinned to it. Read-only.
    """
    return await db._run(
        "OPTIONAL MATCH (r:Repository {repository_id:$repo}) "
        "MATCH (g:Snapshot {repository_id:$repo}) "
        "RETURN g.generation_id AS generation_id, g.status AS publication_status, "
        "coalesce(g.key = r.active, false) AS active, "
        "g.created_at AS created_at, g.retired_at AS retired_at, g.pinned_until AS pinned_until",
        {"repo": repository_id},
    )


def _verdict(fact: dict, rank: int, bound: RetentionBound, now: float) -> dict:
    """Decide one generation's reclaimability and the reason, in precedence order.

    Args:
        fact: Generation row with active, created_at, retired_at and pinned_until.
        rank: Zero-based newest-first position among all retained generations.
        bound: Declared RetentionBound.
        now: Clock value for age and pin-expiry checks.

    Returns:
        Mapping with ``reclaimable`` and ``reason``.
    """
    age = _age_basis(fact, now)
    decision = _decide(fact, rank, bound, now, age)
    return {**decision, "reclaimable_bases": _bases(fact, rank, bound, decision), **age}


def _bases(fact: dict, rank: int, bound: RetentionBound, decision: dict) -> list[str]:
    """Name every basis on which a reclaimable generation is reclaimable.

    Args:
        fact: Generation row with publication_status.
        rank: Count rank from ``_count_ranks``.
        bound: Declared RetentionBound.
        decision: Result of ``_decide``.

    Returns:
        Both bases when both hold, never only the first; empty when not reclaimable.
    """
    if not decision["reclaimable"]:
        return []
    bases = []
    if rank >= bound.generation_limit:
        bases.append(OUTSIDE_COUNT_BOUND)
    if fact.get("publication_status") == "failed":
        bases.append(PUBLICATION_FAILED)
    return bases


def _age_basis(fact: dict, now: float) -> dict:
    """State which recorded time a generation's age is measured from.

    Args:
        fact: Generation row with retired_at and created_at (either may be None).
        now: Clock value the age is measured against.

    Returns:
        Mapping with ``age_basis`` (retired_at, created_at or undetermined),
        ``age_seconds`` (None when undetermined) and ``absent_times`` (the
        recorded times that were absent when the age is undetermined).
    """
    if fact.get("retired_at") is not None:
        return {"age_basis": "retired_at", "age_seconds": now - fact["retired_at"], "absent_times": []}
    if fact.get("created_at") is not None:
        return {"age_basis": "created_at", "age_seconds": now - fact["created_at"], "absent_times": []}
    return {"age_basis": "undetermined", "age_seconds": None, "absent_times": ["retired_at", "created_at"]}


def _decide(fact: dict, rank: int, bound: RetentionBound, now: float, age: dict) -> dict:
    """Apply the reclaimability checks in precedence order.

    Args:
        fact: Generation row with active and pinned_until.
        rank: Zero-based newest-first position among all retained generations.
        bound: Declared RetentionBound.
        now: Clock value for pin-expiry checks.
        age: Stated age from ``_age_basis``; an undetermined age never satisfies the minimum.

    Returns:
        Mapping with ``reclaimable`` and ``reason``.
    """
    if fact["active"]:
        return {
            "reclaimable": False,
            "reason": "active_generation",
            "reason_detail": "the generation the active pointer references is never reclaimable",
        }
    if rank < bound.generation_limit and fact.get("publication_status") != "failed":
        return {"reclaimable": False, "reason": "inside_count_bound"}
    if age["age_seconds"] is None:
        return {"reclaimable": False, "reason": "age_undetermined"}
    if age["age_seconds"] < bound.minimum_age_seconds:
        return {"reclaimable": False, "reason": "younger_than_minimum_age"}
    pinned = fact["pinned_until"]
    if pinned is not None and pinned > now:
        return {"reclaimable": False, "reason": "pinned_continuation_unexpired"}
    return {"reclaimable": True, "reason": "reclaimable"}
