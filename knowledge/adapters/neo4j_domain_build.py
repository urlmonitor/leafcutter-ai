"""MODULE: neo4j_domain_build
GOAL: Write native domain nodes and relationships for a validated snapshot.
BUSINESS CONTEXT: KM-400a-3-i exposes readable Aura data and declared component filters.
ARCHITECTURE: Existing immutable payloads remain authoritative for retrieval.

DECISION HISTORY
========================================
- 2026-10-24 12:00 [python-coder]: Bound batches by rows and payload bytes and verify writes by content fingerprint. (#KM-400b-5-iii, #KM-400b-5-iv)
"""

from __future__ import annotations

from knowledge.contracts import ProjectionSnapshot
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .neo4j_backend import Neo4jBackend
    from neo4j import ManagedTransaction

import hashlib

from knowledge.adapters.domain_schema import (
    LABELS,
    RELATIONSHIPS,
    EDGE_TYPES,
    NODE_LABELS,
    display_properties,
    memberships,
)
from knowledge.adapters.native_verification import fingerprint, verify_rows
from knowledge.adapters.neo4j_backend import scope_key
from knowledge.adapters.neo4j_writes import Plan, begin_writes, make_plan, write_batches


def _node_plans(db: Neo4jBackend, snapshot: ProjectionSnapshot, key: str) -> list[Plan]:
    """Plan the bounded node batches of every kind, in registry order."""
    components = memberships(snapshot)
    plans = []
    for kind, label in LABELS.items():
        rows = [
            {
                "key": scope_key(key, n.canonical_id),
                "canonical_id": n.canonical_id,
                "kind": n.kind,
                "payload": (payload := n.model_dump_json()),
                "fingerprint": fingerprint(payload),
                "content_hash": n.source.content_hash,
                "status": n.properties.get("status"),
                "parent_id": n.properties.get("structural_parent"),
                "decision_type": n.properties.get("decision_type"),
                **display_properties(n, components[n.canonical_id]),
            }
            for n in snapshot.nodes
            if n.kind == kind
        ]
        statement = (
            "UNWIND $rows AS row MERGE (n:"
            + label
            + " {key:row.key}) ON CREATE SET n.current=false SET n += row, "
            "n.content_fingerprint=row.fingerprint, n.generation_key=$key REMOVE n.fingerprint "
            "RETURN n.key AS key, n.content_fingerprint AS fingerprint"
        )
        plans.append(make_plan(db, "nodes", kind, statement, rows))
    return plans


def _edge_plans(db: Neo4jBackend, snapshot: ProjectionSnapshot, key: str) -> list[Plan]:
    """Plan the bounded relationship batches of every allowlisted edge type."""
    plans = []
    for semantic, edge_type in RELATIONSHIPS.items():
        rows = [
            {
                "source": scope_key(key, e.source_id),
                "target": scope_key(key, e.target_id),
                "edge_type": e.edge_type,
                "locator": e.locator,
                "payload": (payload := e.model_dump_json()),
                "fingerprint": fingerprint(payload),
                "key": hashlib.sha256(payload.encode()).hexdigest(),
            }
            for e in snapshot.edges
            if e.edge_type == semantic
        ]
        statement = (
            "UNWIND $rows AS row MATCH (a:"
            + NODE_LABELS
            + " {key:row.source}), (b:"
            + NODE_LABELS
            + " {key:row.target}) "
            "MERGE (a)-[r:" + edge_type + " {key:row.key}]->(b) ON CREATE SET r.current=false "
            "SET r.edge_type=row.edge_type, r.locator=row.locator, r.payload=row.payload, "
            "r.content_fingerprint=row.fingerprint, r.generation_key=$key "
            "RETURN r.key AS key, r.content_fingerprint AS fingerprint"
        )
        plans.append(make_plan(db, "relationships", edge_type, statement, rows))
    return plans


def _verify_relationships(rows: list[dict], actual: list[dict]) -> None:
    """Verify a relationship batch's read-back; an empty read-back is left to the count check.

    A relationship whose endpoints are absent is never matched, so a batch that returns
    nothing is caught by the generation count check, which names the kind and both figures.
    """
    if actual:
        verify_rows(rows, actual)


async def build(db: Neo4jBackend, snapshot: ProjectionSnapshot, key: str) -> None:
    """Write bounded batches using only allowlisted physical labels and edge types.

    Args:
        db: Writer adapter.
        snapshot: Validated source snapshot.
        key: Repository and generation scope key.
    """
    begin_writes(db, snapshot)
    await write_batches(db, "nodes", _node_plans(db, snapshot, key), key, verify_rows)
    await write_batches(
        db, "relationships", _edge_plans(db, snapshot, key), key, _verify_relationships
    )


def set_current(db: Neo4jBackend, tx: ManagedTransaction, key: str, current: bool) -> None:
    """Update scene filters inside the same transaction as the publication pointer."""
    db._rows(
        tx,
        "MATCH (n:" + NODE_LABELS + " {generation_key:$key}) SET n.current=$current",
        {"key": key, "current": current},
    )
    db._rows(
        tx,
        "MATCH ()-[r:" + EDGE_TYPES + " {generation_key:$key}]->() SET r.current=$current",
        {"key": key, "current": current},
    )
