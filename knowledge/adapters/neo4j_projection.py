"""MODULE: neo4j_projection
GOAL: Build immutable generations with atomic pointer publication.
BUSINESS CONTEXT: Readers never observe incomplete or overwritten snapshots.
ARCHITECTURE: Writer-only helper; ancestry is verified by the Git sync coordinator.

DECISION HISTORY
========================================
- 2026-10-14 19:00 [python-coder]: Guard the failed-status write so removal always runs and the original error is re-raised with a never-empty cause. (#KM-400b-5-i/02)
- 2026-10-14 18:00 [python-coder]: Remove a failed publication's own generation by key and report it with the original cause. (#KM-400b-5-i)
- 2026-10-14 15:00 [python-coder]: Count check names each mismatched kind with expected and kept figures and publishes them. (#KM-400b-2-ii)
- 2026-10-14 14:00 [python-coder]: Collapse identical relationships in publish, before the first write. (#KM-400b-2-i/01)
- 2026-10-01 12:00 [python-coder]: Separate build transactions from publication CAS. (#TICKET-KM-400b-3)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from neo4j import ManagedTransaction
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.config import RetentionBound
    from knowledge.contracts import ProjectionSnapshot

import hashlib
import json
import logging
import time

from knowledge.adapters.domain_schema import EDGE_TYPES, NODE_LABELS
from knowledge.adapters.neo4j_backend import scope_key
from knowledge.projection.validation import collapse_identical_edges, validate_snapshot
from knowledge.errors import BackendUnavailable

logger = logging.getLogger(__name__)

# Control records are separate from the generation-scoped native domain nodes.
_CONTROL_SCHEMA_QUERY = (
    "MATCH (n {repository_id:$repo}) WHERE n.generation_key IS NULL "
    "AND NOT (size(labels(n))=1 AND (n:Repository OR n:Snapshot)) "
    "RETURN count(n) AS count"
)


async def publish(
    db: Neo4jBackend, snapshot: ProjectionSnapshot, expected_generation: str | None
) -> bool:
    """Build or resume a content-addressed generation, then publish with CAS.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        snapshot: Validated immutable generation and its canonical source records.
        expected_generation: Previously active generation required for compare-and-swap.

    Returns:
        Whether the guarded operation succeeded.
    """
    # The digest names the loaded source content, so it is taken before the collapse: a
    # generation record left by an earlier attempt on the same revision keeps its identity.
    digest = hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest()
    # Counts belong to this publication only; an already-ready generation reports none.
    db.publication_counts = None
    # Nothing is stored until the build starts; a failure before then removes nothing.
    db.publication_removal = {"outcome": "nothing_stored"}
    collapse_identical_edges(snapshot)  # in place, before any node or relationship is written
    validate_snapshot(snapshot)
    unsupported = await db._run(_CONTROL_SCHEMA_QUERY, {"repo": snapshot.repository_id})
    if unsupported[0]["count"]:
        raise ValueError("repository control records require native storage")
    key = scope_key(snapshot.repository_id, snapshot.generation_id)
    kinds = snapshot.supported_kinds or sorted({n.kind for n in snapshot.nodes})
    metadata = {
        "key": key,
        "repository_id": snapshot.repository_id,
        "generation_id": snapshot.generation_id,
        "source_sha": snapshot.source_sha,
        "mapper_version": snapshot.mapper_version,
        "projection_schema_version": "1",
        "supported_kinds": kinds,
        "supported_fields": json.dumps(snapshot.supported_fields),
        "supported_relationships": snapshot.supported_relationships,
        "diagnostics": json.dumps(snapshot.diagnostics),
        "node_count": len(snapshot.nodes),
        "edge_count": len(snapshot.edges),
        "digest": digest,
        "created_at": time.time(),
        "name": snapshot.source_sha[:8],
        "storage_version": 2,
    }
    rows = await db._run(
        'MERGE (g:Snapshot {key:$key}) ON CREATE SET g += $meta, g.status="building", g.semantic_ready=false RETURN g.digest AS digest, g.status AS status',
        {"key": key, "meta": metadata},
        True,
    )
    if rows[0]["digest"] != digest:
        raise ValueError("generation identity already belongs to different content")
    if rows[0]["status"] != "ready":
        try:
            await _build(db, snapshot, key)
            # edges were collapsed to distinct identities above, so len() is what the store keys on
            db.publication_counts = await _validate_counts(
                db, key, len(snapshot.nodes), len(snapshot.edges)
            )
        except (ValueError, BackendUnavailable) as error:
            await _record_failed_generation(db, key, error)
            raise
        await db._run(
            'MATCH (g:Snapshot {key:$key}) WHERE g.status<>"ready" SET g.status="validated", g.validated_at=$now',
            {"key": key, "now": time.time()},
            True,
        )
    return await switch_active(
        db, snapshot.repository_id, snapshot.generation_id, expected_generation
    )


async def _record_failed_generation(
    db: Neo4jBackend, key: str, error: ValueError | BackendUnavailable
) -> None:
    """Mark a failed attempt, remove its own generation, and append the outcome to its cause.

    The status write is best effort: its own failure is logged and the removal still runs,
    so the caller always re-raises the original publication failure.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key of the failed attempt.
        error: The original publication failure; its message gains the removal outcome.
    """
    try:
        await db._run(
            'MATCH (g:Snapshot {key:$key}) WHERE g.status<>"ready" SET g.status="failed",g.error_code=$code,g.failed_at=$now',
            {"key": key, "code": type(error).__name__, "now": time.time()},
            True,
        )
    except BackendUnavailable as status_error:
        logger.warning("failed generation could not be marked failed: %s", status_error)
    removal = await _remove_own_generation(db, key)
    db.publication_removal = removal
    cause = str(error) or type(error).__name__
    error.args = (f"{cause}; {_removal_statement(removal)}", *error.args[1:])


async def _remove_own_generation(db: Neo4jBackend, key: str) -> dict:
    """Remove the nodes and relationships tagged to one failed attempt's own generation key.

    Matching is by the attempt's generation key only, never by failed status, so no other
    generation or repository is touched. A failure of the removal itself never replaces
    the publication failure being reported.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key of the failed attempt.

    Returns:
        ``removed`` with node and relationship figures taken before deleting, or
        ``not_removed`` with the removal failure reason.
    """
    params = {"key": key}
    try:
        nodes = await db._run(
            "MATCH (n:" + NODE_LABELS + " {generation_key:$key}) RETURN count(n) AS count", params
        )
        links = await db._run(
            "MATCH ()-[r:" + EDGE_TYPES + " {generation_key:$key}]->() RETURN count(r) AS count",
            params,
        )
        await db._run(
            "MATCH ()-[r:" + EDGE_TYPES + " {generation_key:$key}]->() DELETE r", params, True
        )
        await db._run(
            "MATCH (n:" + NODE_LABELS + " {generation_key:$key}) DETACH DELETE n", params, True
        )
    except BackendUnavailable as removal_error:
        logger.warning("failed generation could not be removed: %s", removal_error)
        return {"outcome": "not_removed", "reason": str(removal_error)}
    return {"outcome": "removed", "nodes": nodes[0]["count"], "relationships": links[0]["count"]}


def _removal_statement(removal: dict) -> str:
    """State the removal outcome of a failed generation for the failure message.

    Args:
        removal: Outcome returned by ``_remove_own_generation``.

    Returns:
        A sentence fragment appended after the original failure cause.
    """
    if removal["outcome"] != "removed":
        return "failed generation not removed: " + removal["reason"]
    return (
        f"failed generation removed: {removal['nodes']} entity records, "
        f"{removal['relationships']} relationships"
    )


async def _build(db: Neo4jBackend, snapshot: ProjectionSnapshot, key: str) -> None:
    """Write idempotent node and relationship batches into a staging generation.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        snapshot: Validated immutable generation and its canonical source records.
        key: Trusted hashed repository/generation scope key.
    """
    from knowledge.adapters.neo4j_domain_build import build

    await build(db, snapshot, key)


async def _validate_counts(db: Neo4jBackend, key: str, nodes: int, edges: int) -> dict:
    """Reject a staging generation whose persisted record counts differ.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key.
        nodes: Expected number of staged entity records.
        edges: Expected number of distinct staged relationship identities.

    Returns:
        Expected and kept figures for nodes and for relationships.

    Raises:
        ValueError: Naming each mismatched kind with its expected and kept figure.
    """
    rows = await db._run(
        "MATCH (n:" + NODE_LABELS + " {generation_key:$key}) RETURN count(n) AS count", {"key": key}
    )
    links = await db._run(
        "MATCH (:"
        + NODE_LABELS
        + " {generation_key:$key})-[r:"
        + EDGE_TYPES
        + " {generation_key:$key}]->(:"
        + NODE_LABELS
        + " {generation_key:$key}) RETURN count(r) AS count",
        {"key": key},
    )
    counts = {
        "nodes": {"expected": nodes, "kept": rows[0]["count"]},
        "relationships": {"expected": edges, "kept": links[0]["count"]},
    }
    wrong = [
        f"{kind} expected {c['expected']} kept {c['kept']}"
        for kind, c in counts.items()
        if c["expected"] != c["kept"]
    ]
    if wrong:
        raise ValueError("generation count validation failed: " + "; ".join(wrong))
    return counts


async def switch_active(
    db: Neo4jBackend, repository_id: str, generation_id: str, expected_generation: str | None
) -> bool:
    """Acquire a repository write lock before testing and changing the pointer.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        generation_id: Immutable generation identifier within the repository.
        expected_generation: Previously active generation required for compare-and-swap.

    Returns:
        Whether the guarded operation succeeded.
    """
    key = scope_key(repository_id, generation_id)
    expected = scope_key(repository_id, expected_generation) if expected_generation else None

    def transaction(tx: ManagedTransaction) -> bool:
        """Serialize pointer comparison and publication under one write lock.

        Args:
            tx: Driver-owned transaction provided by the managed callback.

        Returns:
            True when the pointer was published; False when the comparison refused it.
        """
        unsupported = db._rows(tx, _CONTROL_SCHEMA_QUERY, {"repo": repository_id})
        if unsupported[0]["count"]:
            raise ValueError("repository control records require native storage")
        rows = db._rows(
            tx,
            "MERGE (r:Repository {repository_id:$repo}) SET r.lock=coalesce(r.lock,0)+1, r.name=$repo RETURN r.active AS active",
            {"repo": repository_id},
        )
        current = rows[0]["active"]
        if current == key:
            return True
        if current != expected:
            return False
        eligible = db._rows(
            tx,
            'MATCH (g:Snapshot {key:$key}) WHERE g.status IN ["ready","validated"] RETURN g.key AS key',
            {"key": key},
        )
        if not eligible:
            return False
        from knowledge.adapters.neo4j_domain_build import set_current

        if current:
            set_current(db, tx, current, False)
            db._rows(
                tx,
                "MATCH (g:Snapshot {key:$key}) SET g.retired_at=$now",
                {"key": current, "now": time.time()},
            )
        db._rows(
            tx,
            "MATCH (r:Repository {repository_id:$repo}) SET r.active=$key",
            {"repo": repository_id, "key": key},
        )
        db._rows(
            tx,
            'MATCH (g:Snapshot {key:$key}) SET g.status="ready",g.ready_at=$now REMOVE g.retired_at',
            {"key": key, "now": time.time()},
        )
        set_current(db, tx, key, True)
        return True

    return await db._transaction(transaction, True)


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
    ordered = sorted(facts, key=lambda f: (-f["created_at"], f["generation_id"]))
    verdicts = [
        {"generation_id": f["generation_id"], **_verdict(f, rank, bound, clock)}
        for rank, f in enumerate(ordered)
    ]
    return {
        "bound": bound.model_dump(),
        "assessed": len(verdicts),
        "generations": verdicts,
        "reclaimable": [v["generation_id"] for v in verdicts if v["reclaimable"]],
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


_NO_BOUND = "retention bound is not declared; evaluation refused"
_NO_RETENTION = (
    "retention bound is unset: retention_seconds must be declared by the caller; "
    "no built-in value is used"
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
    if fact["active"]:
        return {"reclaimable": False, "reason": "active_generation"}
    if rank < bound.generation_limit:
        return {"reclaimable": False, "reason": "inside_count_bound"}
    retired = fact["retired_at"] if fact["retired_at"] is not None else fact["created_at"]
    if now - retired < bound.minimum_age_seconds:
        return {"reclaimable": False, "reason": "younger_than_minimum_age"}
    pinned = fact["pinned_until"]
    if pinned is not None and pinned > now:
        return {"reclaimable": False, "reason": "pinned_continuation_unexpired"}
    return {"reclaimable": True, "reason": "reclaimable"}


async def cleanup(
    db: Neo4jBackend,
    repository_id: str,
    generation_id: str,
    retention_seconds: int | None,
    now: float | None,
) -> bool:
    """Guard active publication and retention before deleting one owned generation.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        generation_id: Immutable generation identifier within the repository.
        retention_seconds: Minimum elapsed retirement time before removal is permitted.
        now: Optional clock value for deterministic retention checks.

    Returns:
        Whether the guarded operation succeeded.
    """
    if retention_seconds is None:
        raise ValueError(_NO_RETENTION)
    if retention_seconds < 0:
        raise ValueError("retention_seconds must be nonnegative")
    key = scope_key(repository_id, generation_id)
    cutoff = (time.time() if now is None else now) - retention_seconds

    def transaction(tx: ManagedTransaction) -> list[str] | None:
        """Delete only an inactive generation whose retention has elapsed.

        Args:
            tx: Driver-owned transaction provided by the managed callback.

        Returns:
            Names of removed generation indexes, or None when retention prevents deletion.
        """
        rows = db._rows(
            tx,
            "MATCH (r:Repository {repository_id:$repo}) SET r.lock=coalesce(r.lock,0)+1 WITH r MATCH (g:Snapshot {key:$key}) RETURN r.active AS active,coalesce(g.retired_at,g.created_at) AS created,g.vector_indexes AS vector_indexes",
            {"repo": repository_id, "key": key},
        )
        if not rows or rows[0]["active"] == key or rows[0]["created"] > cutoff:
            return None
        db._rows(
            tx, "MATCH (n:" + NODE_LABELS + " {generation_key:$key}) DETACH DELETE n", {"key": key}
        )
        db._rows(tx, "MATCH (g:Snapshot {key:$key}) DELETE g", {"key": key})
        return rows[0]["vector_indexes"] or []

    index = await db._transaction(transaction, True)
    if index is None:
        return False
    for name in index:
        from knowledge.adapters.neo4j_vectors import trusted_name

        await db._run("DROP INDEX " + trusted_name(name) + " IF EXISTS", write=True)
    return True


# - 2026-10-14 [python-coder]: Assess every generation record regardless of publication outcome and report the assessed count. (#KM-400f-1-i)
# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
