"""MODULE: neo4j_inspection
GOAL: Validate native snapshot identity, ownership and immutable evidence.
BUSINESS CONTEXT: KM-400a-3-i preserves source evidence while improving Aura exploration.
ARCHITECTURE: Read-only native storage inspection shared by metadata refresh and recovery.
"""

from __future__ import annotations

from typing import Protocol

import hashlib
import json
import re

from knowledge.adapters.domain_schema import LABELS, RELATIONSHIPS
from knowledge.adapters.neo4j_backend import scope_key
from knowledge.contracts import Entity, Relation, ProjectionSnapshot
from knowledge.projection.validation import validate_snapshot

INSPECTION_MANIFEST_QUERY = (
    "MATCH (g:Snapshot {repository_id:$repo}) RETURN properties(g) AS props ORDER BY g.key"
)


class InspectionReader(Protocol):
    """Read interface shared by published snapshot inspection and recovery."""

    async def _run(
        self, statement: str, parameters: dict | None = None, write: bool = False
    ) -> list[dict]: ...


async def inspect(db: InspectionReader, repository_id: str) -> dict:
    """Read and validate all owned generations; this function never writes.

    Args:
        db: Adapter connected to the explicitly selected database.
        repository_id: Repository whose existing graph will be inspected.

    Returns:
        Serializable native snapshot inventory, including original properties for a private backup.

    Raises:
        ValueError: Unknown, corrupt, duplicate or cross-generation graph data is found.
    """
    repos = await db._run(
        "MATCH (r:Repository {repository_id:$repo}) RETURN properties(r) AS props",
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
        snapshot = validate_records(meta, nodes, edges)
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


def validate_records(meta: dict, nodes: list[dict], edges: list[dict]) -> ProjectionSnapshot:
    """Check persisted identity, endpoints, counts and canonical evidence before writes."""
    key = meta["key"]
    entities = []
    for row in nodes:
        props = row["props"]
        entity = Entity.model_validate_json(props["payload"])
        allowed_labels = {LABELS.get(entity.kind)} | {
            name
            for name in meta.get("vector_indexes", [])
            if re.fullmatch(r"native_vector_[a-f0-9]{64}", name)
        }
        if (
            props.get("key") != scope_key(key, entity.canonical_id)
            or props.get("canonical_id") != entity.canonical_id
            or props.get("kind") != entity.kind
            or props.get("content_hash") != entity.source.content_hash
            or LABELS.get(entity.kind) not in row["labels"]
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
            or row["type"] != RELATIONSHIPS.get(relation.edge_type)
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
