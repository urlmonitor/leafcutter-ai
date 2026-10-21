"""MODULE: cli_generations
GOAL: Show an operator every retained generation and the remaining capacity, and reclaim a whole reclaimable set.
BUSINESS CONTEXT: A store that fills up latches read-only, so the operator must see headroom and reclaimability before that happens.
ARCHITECTURE: Reads verdicts from evaluate_retention, usage from retention.capacity and reclaims through reclaim_superseded; it recomputes no policy and status writes nothing.

DECISION HISTORY
========================================
- 2026-10-20 23:00 [python-coder]: Add the read-only generation listing with capacity usage and the sweep reclamation command. (#KM-400f-4)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from knowledge.adapters.neo4j_backend import scope_key
from knowledge.adapters.retention.capacity import (
    assess,
    measure_usage,
    refuse_if_read_only,
)

if TYPE_CHECKING:
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.adapters.retention.capacity import CapacityCeiling
    from knowledge.config import RetentionBound

UNDETERMINED_NO_BOUND = "undetermined (no retention bound declared)"
UNLISTABLE = "unavailable (backend does not expose generation records)"
_SNAPSHOT_REVISIONS = (
    "MATCH (g:Snapshot {repository_id:$repo}) "
    "RETURN g.generation_id AS generation_id, g.source_sha AS source_sha"
)


def manifest_of(active: object | None) -> dict | None:
    """Serialize the active manifest for the status report.

    Args:
        active: The active manifest (a model, or any object exposing its fields), or None.

    Returns:
        A JSON-compatible mapping, or None when nothing is published.
    """
    if active is None:
        return None
    dump = getattr(active, "model_dump", None)
    return dump(mode="json") if dump else dict(vars(active))


def _repository_statements() -> tuple[str, str]:
    """Build the two read-only statements counting one repository's tagged records.

    Returns:
        The node-count and relationship-count statements, scoped by the ``$keys`` list.
    """
    from knowledge.adapters.domain_schema import EDGE_TYPES, NODE_LABELS

    return (
        "MATCH (n:" + NODE_LABELS + ") WHERE n.generation_key IN $keys RETURN count(n) AS count",
        "MATCH ()-[r:" + EDGE_TYPES + "]->() WHERE r.generation_key IN $keys "
        "RETURN count(r) AS count",
    )


async def _repository_usage(db: Neo4jBackend, keys: list[str]) -> tuple[int, int]:
    """Count the nodes and relationships belonging to this repository's generations.

    Args:
        db: Scoped Neo4j adapter.
        keys: Generation keys of this repository's Snapshot records.

    Returns:
        (nodes, relationships); nodes include one per Snapshot record.
    """
    if not keys:
        return 0, 0
    node_statement, link_statement = _repository_statements()
    nodes = await db._run(node_statement, {"keys": keys})
    links = await db._run(link_statement, {"keys": keys})
    return nodes[0]["count"] + len(keys), links[0]["count"]


def _scope_axis(usage: int, ceiling: int | None, remaining: int | None) -> dict:
    """Shape one axis: measured usage, the ceiling or ``unknown``, and the remaining headroom."""
    return {
        "usage": usage,
        "ceiling": "unknown" if ceiling is None else ceiling,
        "remaining": "unknown" if remaining is None else remaining,
    }


async def capacity_report(
    db: Neo4jBackend, keys: list[str], ceiling: CapacityCeiling | None
) -> dict:
    """Report measured usage for this repository and the whole backend against the ceiling.

    Args:
        db: Scoped Neo4j adapter.
        keys: Generation keys of this repository's Snapshot records.
        ceiling: Declared ceiling, or None (shown as ``unknown``, never omitted).

    Returns:
        ``ceiling_known``, ``verdict``, ``statement``, and per-scope (``repository``, ``backend``)
        per-axis (``nodes``, ``relationships``) usage, ceiling and remaining headroom.
    """
    backend_usage = await measure_usage(db)
    repo_usage = await _repository_usage(db, keys)
    headroom = assess(backend_usage, (0, 0), ceiling)
    limits = (None, None) if ceiling is None else (ceiling.max_nodes, ceiling.max_relationships)
    axes = ("nodes", "relationships")
    return {
        "ceiling_known": headroom["ceiling_known"],
        "verdict": headroom["verdict"],
        "statement": headroom["statement"],
        "backend": {
            axis: _scope_axis(backend_usage[i], limits[i], headroom[axis]["remaining"])
            for i, axis in enumerate(axes)
        },
        "repository": {
            axis: _scope_axis(repo_usage[i], limits[i], None) for i, axis in enumerate(axes)
        },
    }


def _entry(verdict: dict, facts: dict, revisions: dict) -> dict:
    """Join one verdict with its source revision and retirement time.

    Args:
        verdict: A per-generation verdict from ``evaluate_retention``.
        facts: Generation records keyed by generation id (``retired_at``).
        revisions: Source revision keyed by generation id.

    Returns:
        The listed generation: id, source revision, retirement time, reclaimability, reason, age basis.
    """
    gid = verdict["generation_id"]
    return {
        "generation_id": gid,
        "source_sha": revisions.get(gid),
        "retired_at": facts.get(gid, {}).get("retired_at"),
        "reclaimable": verdict["reclaimable"],
        "reason": verdict["reason"],
        "age_basis": verdict["age_basis"],
        "age_seconds": verdict["age_seconds"],
    }


def _undetermined_entry(fact: dict, revision: str | None) -> dict:
    """List one generation when no bound was declared: reclaimability is stated, never guessed."""
    retired = fact.get("retired_at")
    basis = "retired_at" if retired is not None else (
        "created_at" if fact.get("created_at") is not None else "undetermined"
    )
    return {
        "generation_id": fact["generation_id"],
        "source_sha": revision,
        "retired_at": retired,
        "reclaimable": UNDETERMINED_NO_BOUND,
        "reason": UNDETERMINED_NO_BOUND,
        "age_basis": basis,
        "age_seconds": None,
    }


async def _listing(
    db: Neo4jBackend, repository_id: str, bound: RetentionBound | None
) -> tuple[list[dict], dict, list[str]]:
    """List every retained generation with its verdict (or the no-bound statement).

    Args:
        db: Scoped Neo4j adapter.
        repository_id: Trusted repository namespace.
        bound: Declared bound, or None.

    Returns:
        The listed generations, the evaluation's assessment (``{}`` when no bound was declared)
        and the identifier of every generation record (also when it could not be assessed).
    """
    facts = await db.retention_facts(repository_id)
    by_id = {fact["generation_id"]: fact for fact in facts}
    rows = await db._run(_SNAPSHOT_REVISIONS, {"repo": repository_id})
    revisions = {row["generation_id"]: row["source_sha"] for row in rows}
    ids = list(by_id)
    if bound is None:
        ordered = sorted(facts, key=lambda f: (-(f.get("created_at") or 0), f["generation_id"]))
        return [_undetermined_entry(f, revisions.get(f["generation_id"])) for f in ordered], {}, ids
    from knowledge.adapters.neo4j_retention import evaluate_retention

    report = await evaluate_retention(db, repository_id, bound)
    listed = [_entry(v, by_id, revisions) for v in report["generations"]]
    return listed, report["assessment"], ids


async def status_report(
    db: Neo4jBackend,
    repository_id: str,
    bound: RetentionBound | None,
    ceiling: CapacityCeiling | None,
) -> dict:
    """Assemble the read-only retained-generation and capacity part of ``status``.

    Args:
        db: Scoped Neo4j adapter; nothing is written.
        repository_id: Trusted repository namespace.
        bound: Declared bound, or None (reclaimability is then undetermined).
        ceiling: Declared ceiling, or None (shown as unknown).

    Returns:
        ``retention_bound``, ``generations``, ``retained_count``, ``exceeding_bound_count``,
        ``assessment`` and ``capacity``.
    """
    if not hasattr(db, "retention_facts"):
        # A backend that cannot read generation records still gets the revision-lag status (KM-400e-5).
        return {"generations": UNLISTABLE, "retained_count": UNLISTABLE, "capacity": UNLISTABLE}
    generations, assessment, ids = await _listing(db, repository_id, bound)
    keys = [scope_key(repository_id, gid) for gid in ids]
    exceeding = (
        UNDETERMINED_NO_BOUND if bound is None else max(0, len(generations) - bound.generation_limit)
    )
    return {
        "retention_bound": (
            "no retention bound declared" if bound is None else bound.model_dump(mode="json")
        ),
        "generations": generations,
        "retained_count": len(generations),
        "exceeding_bound_count": exceeding,
        "assessment": assessment,
        "capacity": await capacity_report(db, keys, ceiling),
    }


async def reclaim_generations(
    db: Neo4jBackend,
    repository_id: str,
    bound: RetentionBound,
    ceiling: CapacityCeiling | None,
) -> dict:
    """Reclaim every generation the declared bound permits, in one operation.

    Args:
        db: Scoped Neo4j adapter.
        repository_id: Trusted repository namespace; no other repository is touched.
        bound: Declared retention bound (required).
        ceiling: Declared ceiling used to word a read-only refusal, or None.

    Returns:
        The reclamation summary plus ``status``: ``ok`` when assessed (zero reclaimed is ok),
        ``error`` when the retention could not be fully assessed so nothing was reclaimed.
    """
    from knowledge.adapters.retention.reclaim import reclaim_superseded

    await refuse_if_read_only(db, ceiling)
    summary = await reclaim_superseded(db, repository_id, bound)
    assessed = summary["assessment_status"] == "assessed"
    return {"status": "ok" if assessed else "error", **summary}
