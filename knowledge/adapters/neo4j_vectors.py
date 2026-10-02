"""MODULE: neo4j_vectors
GOAL: Bind vectors to exact content and one generation-local ANN index.
BUSINESS CONTEXT: Foreign generations must not steal recall or leak into results.
ARCHITECTURE: Optional embedding writes; providers run outside retryable transactions.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Hash scope into trusted index identifiers. (#TICKET-KM-400c-4)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from knowledge.contracts import Entity
    from knowledge.adapters.neo4j_backend import Neo4jBackend

import math
import re

from knowledge.adapters.neo4j_backend import scope_key, entity_from_row
from knowledge.adapters.neo4j_queries import bounded_limit
from knowledge.errors import NotReady, KnowledgeError
from knowledge.adapters.neo4j_vector_build import reserve, build_indexes, index_name


def trusted_name(value: str) -> str:
    """Allow only projector-owned hashed schema identifiers."""
    if not re.fullmatch(r"krv_[a-f0-9]{64}", value):
        raise ValueError("invalid owned vector index identifier")
    return value


def validate_vector(vector: list[float], dimensions: int) -> None:
    """Reject nonfinite, zero-norm or incompatible cosine vectors.

    Args:
        vector: Finite nonzero query vector with the configured dimensions.
        dimensions: Expected number of finite values in every embedding.
    """
    if not isinstance(dimensions, int) or not 1 <= dimensions <= 4096 or len(vector) != dimensions:
        raise ValueError("embedding dimensions mismatch")
    if any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in vector
    ):
        raise ValueError("embedding values must be finite numbers")
    if sum(value * value for value in vector) == 0:
        raise ValueError("cosine embedding requires nonzero norm")


async def put_embeddings(
    db: Neo4jBackend,
    repository_id: str,
    generation_id: str,
    embeddings: dict[str, list[float]],
    model: str,
    dimensions: int,
    content_hashes: dict[str, str],
) -> None:
    """Validate a complete generation vector set before making semantics ready.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        generation_id: Immutable generation identifier within the repository.
        embeddings: Canonical entity IDs mapped to their precomputed vectors.
        model: Embedding model identifier bound to this generation.
        dimensions: Expected number of finite values in every embedding.
        content_hashes: Expected source hashes keyed by canonical entity ID.
    """
    manifest = await db.get_generation(repository_id, generation_id)
    if manifest is None:
        raise NotReady("generation is not ready")
    if not model or set(embeddings) != set(content_hashes):
        raise ValueError("embedding model and exact content hashes required")
    if manifest.embedding_model and manifest.embedding_model != model:
        raise ValueError("immutable generation embedding model mismatch")
    if manifest.embedding_dimensions and manifest.embedding_dimensions != dimensions:
        raise ValueError("immutable generation embedding dimensions mismatch")
    for vector in embeddings.values():
        validate_vector(vector, dimensions)
    key = scope_key(repository_id, generation_id)
    found = await db._run(
        'MATCH (n:KREntity {generation_key:$key}) WHERE n.kind IN ["Decision","Lesson"] RETURN n.canonical_id AS id,n.content_hash AS hash',
        {"key": key},
    )
    if {row["id"]: row["hash"] for row in found} != content_hashes:
        raise ValueError("embedding content hash mismatch or unknown entity")
    if not await reserve(db, key, embeddings, model, dimensions, content_hashes):
        return
    rows = [{"id": identifier, "vector": vector} for identifier, vector in embeddings.items()]
    names = await build_indexes(db, key, rows, model, dimensions)
    ready = bool(embeddings)
    await db._run(
        "MATCH (g:KRGeneration {key:$key}) SET g.semantic_ready=$ready,g.vector_indexes=$names",
        {"key": key, "ready": ready, "names": names},
        True,
    )


async def semantic(
    db: Neo4jBackend,
    repository_id: str,
    generation_id: str,
    vector: list[float],
    kinds: list[str],
    limit: int,
    model: str,
) -> list[tuple[Entity, float]]:
    """Return ANN candidates only from the selected generation and model.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        generation_id: Immutable generation identifier within the repository.
        vector: Finite nonzero query vector with the configured dimensions.
        kinds: Allowed entity kinds for the scoped semantic search.
        limit: Maximum result count after enforcing the adapter bound.
        model: Embedding model identifier bound to this generation.

    Returns:
        Canonical entities paired with descending similarity scores from scoped indexes.
    """
    manifest = await db.get_generation(repository_id, generation_id)
    if manifest is None:
        raise KnowledgeError("stale", "generation no longer available")
    if not manifest.semantic_ready:
        raise NotReady("semantic index is not ready")
    if model != manifest.embedding_model:
        raise ValueError("embedding model mismatch")
    validate_vector(vector, manifest.embedding_dimensions)
    key = scope_key(repository_id, generation_id)
    kind = kinds[0] if len(kinds) == 1 and kinds[0] in {"Decision", "Lesson"} else ""
    name = index_name(key, kind)
    state = await db._run(
        "SHOW INDEXES YIELD name,state WHERE name=$name RETURN state", {"name": name}
    )
    if not state or state[0]["state"] != "ONLINE":
        raise NotReady("semantic index is not online")
    params = {
        "name": trusted_name(name),
        "key": key,
        "vector": vector,
        "limit": bounded_limit(limit),
        "kinds": kinds,
        "model": model,
    }
    rows = await db._run(
        "CALL db.index.vector.queryNodes($name,$limit,$vector) YIELD node,score WHERE node.generation_key=$key AND node.embedding_model=$model AND (size($kinds)=0 OR node.kind IN $kinds) RETURN node.payload AS payload,score ORDER BY score DESC,node.canonical_id LIMIT $limit",
        params,
    )
    return [(entity_from_row(row), row["score"]) for row in rows]
