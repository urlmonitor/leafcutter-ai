"""MODULE: neo4j_projection
GOAL: Build immutable generations with atomic pointer publication.
BUSINESS CONTEXT: Readers never observe incomplete or overwritten snapshots.
ARCHITECTURE: Writer-only helper; ancestry is verified by the Git sync coordinator.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Separate build transactions from publication CAS. (#TICKET-KM-400b-3)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.contracts import ProjectionSnapshot

import hashlib
import json
import time

from knowledge.adapters.neo4j_backend import scope_key
from knowledge.projection.validation import validate_snapshot
from knowledge.errors import BackendUnavailable


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
    validate_snapshot(snapshot)
    legacy = await db._run(
        "MATCH (r {repository_id:$repo}) WHERE 'KRRepository' IN labels(r) RETURN count(r) AS count",
        {"repo": snapshot.repository_id},
    )
    if legacy[0]["count"]:
        raise ValueError("migrate the legacy graph presentation before publishing")
    key = scope_key(snapshot.repository_id, snapshot.generation_id)
    digest = hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest()
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
            await _validate_counts(db, key, len(snapshot.nodes), len(snapshot.edges))
        except (ValueError, BackendUnavailable) as error:
            await db._run(
                'MATCH (g:KRGeneration {key:$key}) WHERE g.status<>"ready" SET g.status="failed",g.error_code=$code,g.failed_at=$now',
                {"key": key, "code": type(error).__name__, "now": time.time()},
                True,
            )
            raise
        await db._run(
            'MATCH (g:KRGeneration {key:$key}) WHERE g.status<>"ready" SET g.status="validated", g.validated_at=$now',
            {"key": key, "now": time.time()},
            True,
        )
    return await switch_active(
        db, snapshot.repository_id, snapshot.generation_id, expected_generation
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


async def _validate_counts(db: Neo4jBackend, key: str, nodes: int, edges: int) -> None:
    """Reject a staging generation whose persisted record counts differ.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key.
        nodes: Expected number of staged entity records.
        edges: Expected number of staged relationship records.
    """
    rows = await db._run(
        "MATCH (n:KREntity {generation_key:$key}) RETURN count(n) AS count", {"key": key}
    )
    links = await db._run(
        "MATCH (:KREntity {generation_key:$key})-[r:KR_LINK {generation_key:$key}]->(:KREntity {generation_key:$key}) RETURN count(r) AS count",
        {"key": key},
    )
    if rows[0]["count"] != nodes or links[0]["count"] != edges:
        raise ValueError("generation count validation failed")


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

    def transaction(tx: object) -> object:
        """Serialize pointer comparison and publication under one write lock.

        Args:
            tx: Driver-owned transaction provided by the managed callback.

        Returns:
            True when the pointer was published; False when the comparison refused it.
        """
        legacy = db._rows(
            tx,
            "MATCH (r {repository_id:$repo}) WHERE 'KRRepository' IN labels(r) "
            "RETURN count(r) AS count",
            {"repo": repository_id},
        )
        if legacy[0]["count"]:
            raise ValueError("migrate the legacy graph presentation before changing publication")
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
            'MATCH (g:KRGeneration {key:$key}) WHERE g.status IN ["ready","validated"] RETURN g.key AS key',
            {"key": key},
        )
        if not eligible:
            return False
        from knowledge.adapters.neo4j_domain_build import set_current

        if current:
            set_current(db, tx, current, False)
            db._rows(
                tx,
                "MATCH (g:KRGeneration {key:$key}) SET g.retired_at=$now",
                {"key": current, "now": time.time()},
            )
        db._rows(
            tx,
            "MATCH (r:Repository {repository_id:$repo}) SET r.active=$key",
            {"repo": repository_id, "key": key},
        )
        db._rows(
            tx,
            'MATCH (g:KRGeneration {key:$key}) SET g.status="ready",g.ready_at=$now REMOVE g.retired_at',
            {"key": key, "now": time.time()},
        )
        set_current(db, tx, key, True)
        return True

    return await db._transaction(transaction, True)


async def cleanup(
    db: Neo4jBackend,
    repository_id: str,
    generation_id: str,
    retention_seconds: int,
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
    if retention_seconds < 0:
        raise ValueError("retention_seconds must be nonnegative")
    key = scope_key(repository_id, generation_id)
    cutoff = (time.time() if now is None else now) - retention_seconds

    def transaction(tx: object) -> object:
        """Delete only an inactive generation whose retention has elapsed.

        Args:
            tx: Driver-owned transaction provided by the managed callback.

        Returns:
            Names of removed generation indexes, or None when retention prevents deletion.
        """
        rows = db._rows(
            tx,
            "MATCH (r:KRRepository {repository_id:$repo}) SET r.lock=coalesce(r.lock,0)+1 WITH r MATCH (g:KRGeneration {key:$key}) RETURN r.active AS active,coalesce(g.retired_at,g.created_at) AS created,g.vector_indexes AS vector_indexes",
            {"repo": repository_id, "key": key},
        )
        if not rows or rows[0]["active"] == key or rows[0]["created"] > cutoff:
            return None
        db._rows(tx, "MATCH (n:KREntity {generation_key:$key}) DETACH DELETE n", {"key": key})
        db._rows(tx, "MATCH (g:KRGeneration {key:$key}) DELETE g", {"key": key})
        return rows[0]["vector_indexes"] or []

    index = await db._transaction(transaction, True)
    if index is None:
        return False
    for name in index:
        from knowledge.adapters.neo4j_vectors import trusted_name

        await db._run("DROP INDEX " + trusted_name(name) + " IF EXISTS", write=True)
    return True


# - 2026-10-01 [python-coder]: Preserve question evidence and explicit source support through bounded research. (#KM-500/KM-500e-2)
