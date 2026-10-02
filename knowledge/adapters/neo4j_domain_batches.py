"""MODULE: neo4j_domain_batches
GOAL: Apply bounded graph presentation migrations without altering canonical payloads.
BUSINESS CONTEXT: KM-400a-3-i retains all evidence and historical snapshots.
ARCHITECTURE: Each batch locks the repository, checks its pointer and commits atomically.
"""

from __future__ import annotations

from knowledge.adapters.domain_schema import (
    LABELS,
    RELATIONSHIPS,
    NODE_LABELS,
    display_properties,
    memberships,
)
from knowledge.contracts import ProjectionSnapshot


async def locked(db: object, plan: dict, statement: str, parameters: dict) -> None:
    """Execute migration-only raw Cypher under an expected-publication check.

    Args:
        db: Authorized writer adapter.
        plan: Validated operator migration plan.
        statement: Fixed migration Cypher, bypassing the legacy read-pattern adapter.
        parameters: Bound values from validated graph records.
    """

    def transaction(tx):
        rows = tx.run(
            "MATCH (r:Repository|KRRepository {repository_id:$repo}) "
            "SET r.lock=coalesce(r.lock,0)+1 RETURN r.active AS active",
            {"repo": plan["repository_id"]},
        ).data()
        if len(rows) != 1 or rows[0]["active"] != plan["repository"]["active"]:
            raise ValueError("publication changed during migration")
        tx.run(statement, parameters).consume()

    await db._transaction(transaction, True)


async def migrate_generation(db: object, plan: dict, group: dict) -> None:
    """Relabel nodes in place and atomically replace each legacy edge with its typed copy."""
    snapshot = ProjectionSnapshot.model_validate(group["snapshot"])
    components = memberships(snapshot)
    key = group["metadata"]["key"]
    current = key == plan["repository"]["active"]
    originals = {n["props"]["canonical_id"]: n for n in group["nodes"]}
    for kind, label in LABELS.items():
        rows = [
            {
                "key": originals[n.canonical_id]["props"]["key"],
                "payload": originals[n.canonical_id]["props"]["payload"],
                "display": {
                    **display_properties(n, components[n.canonical_id]),
                    "current": current,
                },
            }
            for n in snapshot.nodes
            if n.kind == kind
        ]
        for offset in range(0, len(rows), 250):
            await locked(
                db,
                plan,
                "UNWIND $rows AS row MATCH (n:" + NODE_LABELS + "|KREntity {key:row.key}) "
                "WHERE n.generation_key=$key AND n.payload=row.payload SET n:"
                + label
                + ", n += row.display REMOVE n:KREntity",
                {"rows": rows[offset : offset + 250], "key": key},
            )
    for semantic, native in RELATIONSHIPS.items():
        rows = [
            {
                "key": r["props"]["key"],
                "payload": r["props"]["payload"],
                "source": r["source"],
                "target": r["target"],
            }
            for r in group["edges"]
            if r["type"] == "KR_LINK" and r["props"]["edge_type"] == semantic
        ]
        for offset in range(0, len(rows), 250):
            await locked(
                db,
                plan,
                "UNWIND $rows AS row MATCH (a:" + NODE_LABELS + "|KREntity {key:row.source})"
                "-[old:KR_LINK {key:row.key}]->(b) WHERE b.key=row.target AND "
                "old.generation_key=$key AND old.payload=row.payload "
                "CREATE (a)-[replacement:" + native + "]->(b) "
                "SET replacement=properties(old), replacement.current=$current DELETE old",
                {"rows": rows[offset : offset + 250], "key": key, "current": current},
            )
    await locked(
        db,
        plan,
        "MATCH (g:Snapshot|KRGeneration {key:$key}) SET g:Snapshot, g.storage_version=2, "
        "g.name=substring(g.source_sha,0,8) REMOVE g:KRGeneration",
        {"key": key},
    )


async def finish_repository(db: object, plan: dict) -> None:
    """Publish readable metadata and remove only unused legacy schema definitions."""
    await locked(
        db,
        plan,
        "MATCH (r:Repository|KRRepository {repository_id:$repo}) SET r:Repository, "
        "r.name=$repo, r.storage_version=2 REMOVE r:KRRepository",
        {"repo": plan["repository_id"]},
    )
    legacy = await db._run(
        "MATCH (n) WHERE any(label IN labels(n) WHERE "
        "label IN ['KREntity','KRGeneration','KRRepository']) RETURN count(n) AS count"
    )
    if legacy[0]["count"] == 0:
        for name in ("kr_repository", "kr_generation", "kr_entity"):
            await db._run("DROP CONSTRAINT " + name + " IF EXISTS", write=True)
        for name in ("kr_entity_scope", "kr_entity_kind"):
            await db._run("DROP INDEX " + name + " IF EXISTS", write=True)
