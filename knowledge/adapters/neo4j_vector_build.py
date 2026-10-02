"""MODULE: neo4j_vector_build
GOAL: Reserve immutable vector content and prepare isolated indexes.
BUSINESS CONTEXT: Concurrent jobs cannot change a pinned generation's semantic order.
ARCHITECTURE: Transactional reservation precedes idempotent vector batches.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Freeze vector digest/model before writing. (#TICKET-KM-400c-4)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.adapters.neo4j_backend import Neo4jBackend

import hashlib
import json

from knowledge.adapters.neo4j_backend import scope_key


def index_name(key: str, kind: str = "") -> str:
    """Hash trusted scope and kind into a projector-owned schema identifier."""
    return "krv_" + (scope_key(key, kind) if kind else key)


async def reserve(
    db: Neo4jBackend,
    key: str,
    embeddings: dict[str, list[float]],
    model: str,
    dimensions: int,
    hashes: dict[str, str],
) -> bool:
    """Atomically bind a generation to exactly one semantic content digest.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key.
        embeddings: Canonical entity IDs mapped to their precomputed vectors.
        model: Embedding model identifier bound to this generation.
        dimensions: Expected number of finite values in every embedding.
        hashes: Expected source hashes keyed by canonical entity ID.

    Returns:
        Whether the guarded operation succeeded.
    """
    digest = hashlib.sha256(
        json.dumps([model, dimensions, hashes, embeddings], sort_keys=True).encode()
    ).hexdigest()

    def transaction(tx: object) -> object:
        """Reserve one vector digest while holding the generation write lock.

        Args:
            tx: Driver-owned transaction provided by the managed callback.

        Returns:
            True when vector construction is needed; False for identical ready content.
        """
        rows = db._rows(
            tx,
            'MATCH (g:KRGeneration {key:$key,status:"ready"}) SET g.vector_lock=coalesce(g.vector_lock,0)+1 RETURN g.vector_digest AS digest,g.semantic_ready AS ready',
            {"key": key},
        )
        if not rows:
            raise ValueError("generation no longer available")
        if rows[0]["digest"] and rows[0]["digest"] != digest:
            raise ValueError("immutable generation vector content/model/dimensions conflict")
        if rows[0]["ready"]:
            return False
        db._rows(
            tx,
            "MATCH (g:KRGeneration {key:$key}) SET g.vector_digest=$digest,g.embedding_model=$model,g.embedding_dimensions=$dimensions,g.semantic_ready=false",
            {"key": key, "digest": digest, "model": model, "dimensions": dimensions},
        )
        return True

    return await db._transaction(transaction, True)


async def build_indexes(
    db: Neo4jBackend, key: str, rows: list[dict[str, object]], model: str, dimensions: int
) -> list[str]:
    """Create all-generation and kind-local indexes to avoid ANN postfilter loss.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        key: Trusted hashed repository/generation scope key.
        rows: Prepared parameter rows for the bounded database write.
        model: Embedding model identifier bound to this generation.
        dimensions: Expected number of finite values in every embedding.

    Returns:
        Ordered diagnostic values or generated identifiers.
    """
    names = []
    for kind in ("", "Decision", "Lesson"):
        name = index_name(key, kind)
        names.append(name)
        for start in range(0, len(rows), 250):
            await db._run(
                'UNWIND $rows AS row MATCH (n:KREntity {generation_key:$key,canonical_id:row.id}) WHERE $kind="" OR n.kind=$kind SET n:'
                + name
                + ", n.embedding=row.vector, n.embedding_model=$model",
                {"key": key, "rows": rows[start : start + 250], "model": model, "kind": kind},
                True,
            )
        await db._run(
            "CREATE VECTOR INDEX "
            + name
            + " IF NOT EXISTS FOR (n:"
            + name
            + ") ON (n.embedding) OPTIONS {indexConfig: {`vector.dimensions`: "
            + str(dimensions)
            + ', `vector.similarity_function`: "cosine"}}',
            write=True,
        )
        await db._run("CALL db.awaitIndex($name,30)", {"name": name}, True)
    return names
