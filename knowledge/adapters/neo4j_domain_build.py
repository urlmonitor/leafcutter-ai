"""MODULE: neo4j_domain_build
GOAL: Write native domain nodes and relationships for a validated snapshot.
BUSINESS CONTEXT: KM-400a-3-i exposes readable Aura data and declared component filters.
ARCHITECTURE: Existing immutable payloads remain authoritative for retrieval.
"""

from __future__ import annotations

from knowledge.contracts import ProjectionSnapshot
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .neo4j_backend import Neo4jBackend
    from neo4j import ManagedTransaction

import hashlib

from knowledge.adapters.domain_schema import LABELS, RELATIONSHIPS, display_properties, memberships
from knowledge.adapters.neo4j_backend import scope_key


async def build(db: Neo4jBackend, snapshot: ProjectionSnapshot, key: str) -> None:
    """Write bounded batches using only allowlisted physical labels and edge types.

    Args:
        db: Writer adapter.
        snapshot: Validated source snapshot.
        key: Repository and generation scope key.
    """
    components = memberships(snapshot)
    for kind, label in LABELS.items():
        rows = [
            {
                "key": scope_key(key, n.canonical_id),
                "canonical_id": n.canonical_id,
                "kind": n.kind,
                "payload": n.model_dump_json(),
                "content_hash": n.source.content_hash,
                "status": n.properties.get("status"),
                "parent_id": n.properties.get("structural_parent"),
                "decision_type": n.properties.get("decision_type"),
                **display_properties(n, components[n.canonical_id]),
            }
            for n in snapshot.nodes
            if n.kind == kind
        ]
        for start in range(0, len(rows), 250):
            batch = rows[start : start + 250]
            actual = await db._run(
                "UNWIND $rows AS row MERGE (n:"
                + label
                + " {key:row.key}) ON CREATE SET n.current=false SET n += row, n.generation_key=$key RETURN n.key AS key, properties(n) AS props",
                {"rows": batch, "key": key},
                True,
            )
            from knowledge.adapters.native_verification import verify_rows

            verify_rows(batch, actual)
    node_labels = "|".join(LABELS.values())
    for semantic, edge_type in RELATIONSHIPS.items():
        rows = [
            {
                "source": scope_key(key, e.source_id),
                "target": scope_key(key, e.target_id),
                "edge_type": e.edge_type,
                "locator": e.locator,
                "payload": e.model_dump_json(),
                "key": hashlib.sha256(e.model_dump_json().encode()).hexdigest(),
            }
            for e in snapshot.edges
            if e.edge_type == semantic
        ]
        for start in range(0, len(rows), 250):
            await db._run(
                "UNWIND $rows AS row MATCH (a:"
                + node_labels
                + " {key:row.source}), (b:"
                + node_labels
                + " {key:row.target}) "
                "MERGE (a)-[r:" + edge_type + " {key:row.key}]->(b) ON CREATE SET r.current=false "
                "SET r.edge_type=row.edge_type, r.locator=row.locator, r.payload=row.payload, "
                "r.generation_key=$key",
                {"rows": rows[start : start + 250], "key": key},
                True,
            )


def set_current(db: Neo4jBackend, tx: ManagedTransaction, key: str, current: bool) -> None:
    """Update scene filters inside the same transaction as the publication pointer."""
    db._rows(
        tx,
        "MATCH (n:KREntity {generation_key:$key}) SET n.current=$current",
        {"key": key, "current": current},
    )
    db._rows(
        tx,
        "MATCH ()-[r:KR_LINK {generation_key:$key}]->() SET r.current=$current",
        {"key": key, "current": current},
    )
