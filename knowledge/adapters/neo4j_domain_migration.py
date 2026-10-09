"""MODULE: neo4j_domain_migration
GOAL: Inspect and migrate one owned repository to native domain graph storage.
BUSINESS CONTEXT: KM-400a-3-i preserves source evidence while improving Aura exploration.
ARCHITECTURE: Validate every generation before writes; bounded atomic batches can resume.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .neo4j_backend import Neo4jBackend

import hashlib
import json
import logging
import re

from knowledge.adapters.domain_schema import LABELS, RELATIONSHIPS
from knowledge.adapters.neo4j_backend import scope_key
from knowledge.contracts import Entity, Relation, ProjectionSnapshot
from knowledge.projection.validation import validate_snapshot

LOGGER = logging.getLogger(__name__)

# Only the explicit migration/refresh inspection boundary reads both storage versions.
INSPECTION_MANIFEST_QUERY = (
    "MATCH (g:Snapshot|KRGeneration {repository_id:$repo}) "
    "RETURN properties(g) AS props ORDER BY g.key"
)


class InspectionReader(Protocol):
    """Read interface shared by migration and published-generation inspection."""

    async def _run(
        self, statement: str, parameters: dict | None = None, write: bool = False
    ) -> list[dict]: ...


async def inspect(db: InspectionReader, repository_id: str) -> dict:
    """Read and validate all owned generations; this function never writes.

    Args:
        db: Adapter connected to the explicitly selected database.
        repository_id: Repository whose existing graph will be inspected.

    Returns:
        Serializable migration plan, including original properties for an operator backup.

    Raises:
        ValueError: Unknown, corrupt, duplicate or cross-generation graph data is found.
    """
    repos = await db._run(
        "MATCH (r:Repository|KRRepository {repository_id:$repo}) RETURN properties(r) AS props",
        {"repo": repository_id},
    )
    if len(repos) != 1:
        raise ValueError("expected exactly one owned repository")
    manifests = await db._run(
        INSPECTION_MANIFEST_QUERY,
        {"repo": repository_id},
    )
    groups = []
    keys = set()
    fingerprint = hashlib.sha256()
    for row in manifests:
        meta = row["props"]
        key = scope_key(repository_id, meta["generation_id"])
        if meta["key"] != key or meta["status"] != "ready" or key in keys:
            raise ValueError("generation identity or readiness mismatch")
        keys.add(key)
        nodes = await db._run(
            "MATCH (n {generation_key:$key}) RETURN properties(n) AS props, "
            "labels(n) AS labels ORDER BY n.key",
            {"key": key},
        )
        edges = await db._run(
            "MATCH (a)-[r]->(b) WHERE a.generation_key=$key OR "
            "b.generation_key=$key OR r.generation_key=$key "
            "RETURN properties(r) AS props, type(r) AS type, "
            "a.key AS source, b.key AS target, a.generation_key AS source_scope, "
            "b.generation_key AS target_scope ORDER BY r.key",
            {"key": key},
        )
        snapshot = _validate(meta, nodes, edges)
        for item in nodes:
            fingerprint.update(
                json.dumps([key, item["props"]["key"], item["props"]["payload"]]).encode()
            )
        for item in edges:
            fingerprint.update(
                json.dumps(
                    [
                        key,
                        item["props"]["key"],
                        item["props"]["payload"],
                        item["source"],
                        item["target"],
                    ]
                ).encode()
            )
        groups.append(
            {"metadata": meta, "nodes": nodes, "edges": edges, "snapshot": snapshot.model_dump()}
        )
    if not groups or repos[0]["props"].get("active") not in {g["metadata"]["key"] for g in groups}:
        raise ValueError("active snapshot is missing")
    return {
        "repository_id": repository_id,
        "repository": repos[0]["props"],
        "generations": groups,
        "fingerprint": fingerprint.hexdigest(),
    }


def _validate(meta: dict, nodes: list[dict], edges: list[dict]) -> ProjectionSnapshot:
    """Check persisted identity, endpoints, counts and canonical evidence before writes."""
    key = meta["key"]
    entities = []
    for row in nodes:
        props = row["props"]
        entity = Entity.model_validate_json(props["payload"])
        allowed_labels = {"KREntity", LABELS.get(entity.kind)} | {
            name
            for name in meta.get("vector_indexes", [])
            if re.fullmatch(r"krv_[a-f0-9]{64}", name)
        }
        if (
            props.get("key") != scope_key(key, entity.canonical_id)
            or props.get("canonical_id") != entity.canonical_id
            or props.get("kind") != entity.kind
            or props.get("content_hash") != entity.source.content_hash
            or not ({"KREntity", LABELS.get(entity.kind)} & set(row["labels"]))
            or not set(row["labels"]) <= allowed_labels
        ):
            raise ValueError("node identity or kind mismatch")
        entities.append(entity)
    relations = []
    seen = set()
    for row in edges:
        props = row["props"]
        relation = Relation.model_validate_json(props["payload"])
        if (
            row["source_scope"] != key
            or row["target_scope"] != key
            or props["generation_key"] != key
            or row["source"] != scope_key(key, relation.source_id)
            or row["target"] != scope_key(key, relation.target_id)
            or props["key"] != hashlib.sha256(props["payload"].encode()).hexdigest()
            or props["key"] in seen
            or props["edge_type"] != relation.edge_type
            or row["type"] not in {"KR_LINK", RELATIONSHIPS.get(relation.edge_type)}
        ):
            raise ValueError("relationship identity or scope mismatch")
        seen.add(props["key"])
        relations.append(relation)
    snapshot = ProjectionSnapshot(
        repository_id=meta["repository_id"],
        source_sha=meta["source_sha"],
        generation_id=meta["generation_id"],
        nodes=entities,
        edges=relations,
    )
    validate_snapshot(snapshot)
    if len(nodes) != meta["node_count"] or len(edges) != meta["edge_count"]:
        raise ValueError("persisted generation counts mismatch")
    return snapshot


async def migrate(db: Neo4jBackend, plan: dict) -> dict:
    """Apply a freshly revalidated plan and verify immutable content after migration.

    Args:
        db: Explicitly authorized writer adapter.
        plan: Inspected plan that the operator has backed up before applying.

    Returns:
        Verified content fingerprint and migrated generation/count summary.
    """
    from knowledge.adapters.neo4j_domain_batches import migrate_generation, finish_repository

    fresh = await inspect(db, plan["repository_id"])
    if (
        fresh["fingerprint"] != plan["fingerprint"]
        or fresh["repository"]["active"] != plan["repository"]["active"]
    ):
        raise ValueError("graph changed after migration inspection")
    LOGGER.info("Migrating graph presentation for repository %s", plan["repository_id"])
    await db.setup()
    for group in fresh["generations"]:
        await migrate_generation(db, fresh, group)
        LOGGER.info(
            "Migrated snapshot %s (%s nodes, %s relationships)",
            group["metadata"]["source_sha"][:8],
            len(group["nodes"]),
            len(group["edges"]),
        )
    await finish_repository(db, fresh)
    after = await inspect(db, plan["repository_id"])
    if after["fingerprint"] != plan["fingerprint"]:
        raise ValueError("migration changed canonical evidence")
    for group in after["generations"]:
        current = group["metadata"]["key"] == after["repository"]["active"]
        if (
            group["metadata"].get("storage_version") != 2
            or any(
                "KREntity" in n["labels"] or n["props"].get("current") != current
                for n in group["nodes"]
            )
            or any(
                r["type"] == "KR_LINK" or r["props"].get("current") != current
                for r in group["edges"]
            )
        ):
            raise ValueError("migration presentation verification failed")
    return {
        "repository_id": plan["repository_id"],
        "fingerprint": after["fingerprint"],
        "generations": len(after["generations"]),
        "nodes": sum(len(g["nodes"]) for g in after["generations"]),
        "relationships": sum(len(g["edges"]) for g in after["generations"]),
    }
