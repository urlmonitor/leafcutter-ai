"""MODULE: neo4j_projection
GOAL: Build immutable generations with atomic pointer publication.
BUSINESS CONTEXT: Readers never observe incomplete or overwritten snapshots.
ARCHITECTURE: Writer-only helper; ancestry is verified by the Git sync coordinator.

DECISION HISTORY
========================================
- 2026-10-20 18:00 [python-coder]: Pass the generation key to the headroom gate so an already-stored generation is not counted twice. (#KM-400f-3/02)
- 2026-10-20 14:00 [python-coder]: Measure headroom and refuse an unfitting snapshot before the first write; classify a read-only rejection of that write. (#KM-400f-3)
- 2026-10-15 04:00 [python-coder]: Reclaim superseded generations after the pointer switch only; a failed or stale publication reports 0 reclaimed. (#KM-400f-2)
- 2026-10-14 23:00 [python-coder]: Protect the active generation by the active pointer alone; with no pointer, report that and reclaim nothing. (#KM-400f-1-iii)
- 2026-10-14 22:00 [python-coder]: State each verdict's age basis (retired_at, created_at or undetermined); an undetermined age is never reclaimable. (#KM-400f-1-ii)
- 2026-10-14 21:00 [python-coder]: Report a refused removal as not/partially removed, naming repository and generation, the refusal and what remains. (#KM-400b-5-ii)
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
    from knowledge.adapters.retention.capacity import CapacityCeiling
    from knowledge.config import RetentionBound
    from knowledge.contracts import ProjectionSnapshot

import hashlib
import json
import logging
import time

from knowledge.adapters.domain_schema import EDGE_TYPES, NODE_LABELS
from knowledge.adapters.neo4j_backend import scope_key
from knowledge.adapters.retention.capacity import enforce_headroom, first_write
from knowledge.adapters.retention.reclaim import nothing_reclaimed
from knowledge.adapters.neo4j_retention import (  # re-exported: retention lives in neo4j_retention
    active_generation_verdict as active_generation_verdict,
    evaluate_retention as evaluate_retention,
    retention_facts as retention_facts,
)
from knowledge.projection.validation import collapse_identical_edges, collapsed_content_digest, validate_snapshot
from knowledge.errors import BackendUnavailable

logger = logging.getLogger(__name__)

# Control records are separate from the generation-scoped native domain nodes.
_CONTROL_SCHEMA_QUERY = (
    "MATCH (n {repository_id:$repo}) WHERE n.generation_key IS NULL "
    "AND NOT (size(labels(n))=1 AND (n:Repository OR n:Snapshot)) "
    "RETURN count(n) AS count"
)


async def publish(
    db: Neo4jBackend,
    snapshot: ProjectionSnapshot,
    expected_generation: str | None,
    retention_bound: RetentionBound | None = None,
    capacity: CapacityCeiling | None = None,
) -> bool:
    """Build or resume a content-addressed generation, then publish with CAS.

    When a retention bound is declared and the pointer switched, the generations the bound
    permits are reclaimed in this same operation; ``db.publication_reclamation`` reports it.
    Before the first write, whole-database usage is measured and a snapshot that does not fit
    the declared ceiling is refused; ``db.publication_capacity`` reports the headroom.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        snapshot: Validated immutable generation and its canonical source records.
        expected_generation: Previously active generation required for compare-and-swap.
        retention_bound: Declared bound; None means no reclamation.
        capacity: Declared ceiling; None means it is unknown (usage is still measured).

    Returns:
        Whether the guarded operation succeeded.
    """
    # A failed or stale publication reclaims nothing, and says so with an explicit zero.
    db.publication_reclamation = nothing_reclaimed()
    db.publication_capacity = None  # no headroom is reported until usage has been measured
    # Records written before KM-400b-2-iii carry this raw pre-collapse digest; it is still accepted.
    legacy_digest = hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest()
    # Counts belong to this publication only; an already-ready generation reports none.
    db.publication_counts = None
    db.publication_writes = None  # set when the build starts: row cap, payload budget, oversized, retried
    db.publication_failure = None  # set by a failed write: cause, phase, batch, attempts, progress
    db.publication_progress = None  # set when the build starts; an activation-only run reports none
    # Nothing is stored until the build starts; a failure before then removes nothing.
    db.publication_removal = {"outcome": "nothing_stored"}
    collapse_identical_edges(snapshot)  # in place, before any node or relationship is written
    # Taken after the collapse and without its diagnostics, so publishing the same snapshot object
    # again (already collapsed in place) names the same content (KM-400b-2-iii).
    digest = collapsed_content_digest(snapshot)
    validate_snapshot(snapshot)
    unsupported = await db._run(_CONTROL_SCHEMA_QUERY, {"repo": snapshot.repository_id})
    if unsupported[0]["count"]:
        raise ValueError("repository control records require native storage")
    key = scope_key(snapshot.repository_id, snapshot.generation_id)
    await enforce_headroom(db, len(snapshot.nodes), len(snapshot.edges), capacity, key)  # before any write
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
    rows = await first_write(
        db,
        'MERGE (g:Snapshot {key:$key}) ON CREATE SET g += $meta, g.status="building", g.semantic_ready=false RETURN g.digest AS digest, g.status AS status',
        {"key": key, "meta": metadata},
    )
    if rows[0]["digest"] not in (digest, legacy_digest):
        raise ValueError("generation identity already belongs to different content")
    if rows[0]["status"] != "ready":
        try:
            await _build(db, snapshot, key)
            # edges were collapsed to distinct identities above, so len() is what the store keys on
            db.publication_counts = await _validate_counts(
                db, key, len(snapshot.nodes), len(snapshot.edges)
            )
        except (ValueError, BackendUnavailable) as error:
            await _record_failed_generation(
                db, key, error, (snapshot.repository_id, snapshot.generation_id)
            )
            raise
        await db._run(
            'MATCH (g:Snapshot {key:$key}) WHERE g.status<>"ready" SET g.status="validated", g.validated_at=$now',
            {"key": key, "now": time.time()},
            True,
        )
    switched = await switch_active(
        db, snapshot.repository_id, snapshot.generation_id, expected_generation
    )
    if switched and retention_bound is not None:
        from knowledge.adapters.retention.reclaim import reclaim_superseded

        db.publication_reclamation = await reclaim_superseded(
            db, snapshot.repository_id, retention_bound
        )
    return switched


async def _record_failed_generation(
    db: Neo4jBackend, key: str, error: ValueError | BackendUnavailable, ids: tuple[str, str]
) -> None:
    """Mark a failed attempt, remove its own generation, and append the outcome to its cause.

    The status write is best effort: its own failure is logged and the removal still runs,
    so the caller always re-raises the original publication failure.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key of the failed attempt.
        error: The original publication failure; its message gains the removal outcome.
        ids: The repository id and generation id the key was derived from.
    """
    try:
        await db._run(
            'MATCH (g:Snapshot {key:$key}) WHERE g.status<>"ready" SET g.status="failed",g.error_code=$code,g.failed_at=$now',
            {"key": key, "code": type(error).__name__, "now": time.time()},
            True,
        )
    except BackendUnavailable as status_error:
        logger.warning("failed generation could not be marked failed: %s", status_error)
    removal = await _remove_own_generation(db, key, ids)
    db.publication_removal = removal
    cause = str(error) or type(error).__name__
    # The refusal wording keeps its own undetermined figures free of any bare 0 (KM-400b-5-ii),
    # so the reclaimed-zero is spelled without a digit there; the integer is in the report.
    reclaimed = "0 generations reclaimed" if removal["outcome"] == "removed" else "no generations reclaimed"
    error.args = (f"{cause}; {_removal_statement(removal)}; {reclaimed}", *error.args[1:])


async def _count_tagged(db: Neo4jBackend, key: str) -> dict | None:
    """Count the nodes and relationships tagged to one generation key.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key.

    Returns:
        ``{"nodes": n, "relationships": m}``, or None when the store refused to count.
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
    except BackendUnavailable as count_error:
        logger.warning("tagged records could not be counted: %s", count_error)
        return None
    return {"nodes": nodes[0]["count"], "relationships": links[0]["count"]}


async def _delete_tagged(db: Neo4jBackend, key: str) -> dict[str, str]:
    """Attempt both deletes of one generation's records, whatever the first one's outcome.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key.

    Returns:
        The refusal text per kind (``relationships`` / ``nodes``) whose delete was refused.
    """
    params = {"key": key}
    statements = {
        "relationships": "MATCH ()-[r:" + EDGE_TYPES + " {generation_key:$key}]->() DELETE r",
        "nodes": "MATCH (n:" + NODE_LABELS + " {generation_key:$key}) DETACH DELETE n",
    }
    refused: dict[str, str] = {}
    for kind, statement in statements.items():
        try:
            await db._run(statement, params, True)
        except BackendUnavailable as removal_error:
            logger.warning("failed generation %s could not be removed: %s", kind, removal_error)
            refused[kind] = str(removal_error)
    return refused


async def _remove_own_generation(db: Neo4jBackend, key: str, ids: tuple[str, str]) -> dict:
    """Remove the nodes and relationships tagged to one failed attempt's own generation key.

    Matching is by the attempt's generation key only, never by failed status, so no other
    generation or repository is touched. A failure of the removal itself never replaces
    the publication failure being reported.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key of the failed attempt.
        ids: The repository id and generation id the key was derived from.

    Returns:
        ``removed`` with figures taken before deleting; ``partially_removed`` or
        ``not_removed`` naming repository, generation, refusal and what remains
        (``undetermined`` when it could not be counted, never 0).
    """
    before = await _count_tagged(db, key)
    refused = await _delete_tagged(db, key)
    if not refused:
        figures = before or {"nodes": "undetermined", "relationships": "undetermined"}
        return {"outcome": "removed", **figures}
    remaining = await _count_tagged(db, key)
    outcome: dict[str, object] = {
        "outcome": "partially_removed" if len(refused) < 2 else "not_removed",
        "repository_id": ids[0],
        "generation_id": ids[1],
        "refusal": "; ".join(dict.fromkeys(refused.values())),
        "remaining": remaining or "undetermined",
    }
    if len(refused) < 2:
        outcome["remaining_kinds"] = list(refused)
    return outcome


def _removal_statement(removal: dict) -> str:
    """State the removal outcome of a failed generation for the failure message.

    Args:
        removal: Outcome returned by ``_remove_own_generation``.

    Returns:
        A sentence fragment appended after the original failure cause.
    """
    if removal["outcome"] == "removed":
        return (
            f"failed generation removed: {removal['nodes']} entity records, "
            f"{removal['relationships']} relationships"
        )
    if removal["outcome"] == "partially_removed":
        head = "failed generation partially removed"
        head += f" ({' and '.join(removal['remaining_kinds'])} remain)"
    else:
        head = "failed generation not removed"
    left = removal["remaining"]
    if left == "undetermined":
        amount = "remaining amount undetermined"
    else:
        amount = f"{left['nodes']} entity records, {left['relationships']} relationships remain"
    return (
        f"{head}: repository {removal['repository_id']} generation {removal['generation_id']}; "
        f"refused: {removal['refusal']}; {amount}"
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

    from knowledge.adapters.neo4j_writes import with_retry

    return await with_retry(db, "activation", None, lambda: db._transaction(transaction, True))


_NO_RETENTION = (
    "retention bound is unset: retention_seconds must be declared by the caller; "
    "no built-in value is used"
)


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
