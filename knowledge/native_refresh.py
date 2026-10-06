"""Inspect or publish complete native metadata from the currently active source commit.

The default is read-only. Explicit apply creates a private backup, stages a new
generation with field readback verification, then atomically changes the pointer.
"""

from __future__ import annotations

import argparse
import asyncio
from collections import Counter
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

from knowledge.adapters.neo4j_backend import Neo4jBackend, scope_key
from knowledge.adapters.neo4j_domain_migration import inspect, _validate
from knowledge.cli_sync import writer_backend
from knowledge.config import KnowledgeConfig
from knowledge.environment import resolve_database, resolve_neo4j
from knowledge.projection.canonical_loader import load_snapshot


_MANIFEST_QUERY = (
    "MATCH (g:KRGeneration {repository_id:$repo}) RETURN properties(g) AS props ORDER BY g.key"
)
_STAGING_STATES = frozenset({"building", "failed", "validated"})


class _PublishedInspection:
    """Give the unchanged strict inspector only published manifest rows."""

    def __init__(self, db, repository_id):
        self.db = db
        self.repository_id = repository_id
        self.stages = []

    async def _run(self, statement, parameters=None, write=False):
        if write:
            raise ValueError("native refresh inspection cannot write")
        rows = await self.db._run(statement, parameters)
        if statement != _MANIFEST_QUERY:
            return rows
        seen = set()
        published = []
        for row in rows:
            meta = row["props"]
            generation = meta.get("generation_id")
            key = meta.get("key")
            if (
                not isinstance(generation, str)
                or not generation
                or meta.get("repository_id") != self.repository_id
                or key != scope_key(self.repository_id, generation)
                or key in seen
                or meta.get("status") not in _STAGING_STATES | {"ready"}
            ):
                raise ValueError("native refresh generation identity or state mismatch")
            seen.add(key)
            if meta["status"] == "ready":
                published.append(row)
            else:
                self.stages.append(meta)
        return published


async def _inspect_refresh(db, repository_id: str) -> dict:
    """Validate ready evidence unchanged and back up valid inactive partial stages."""
    view = _PublishedInspection(db, repository_id)
    plan = await inspect(view, repository_id)
    stages = []
    for meta in view.stages:
        key = meta["key"]
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
        if (
            not isinstance(meta.get("node_count"), int)
            or not isinstance(meta.get("edge_count"), int)
            or len(nodes) > meta["node_count"]
            or len(edges) > meta["edge_count"]
            or any(row["props"].get("current") is True for row in [*nodes, *edges])
        ):
            raise ValueError("native refresh staging count or current marker mismatch")
        # A partial stage may have fewer records than intended, but each existing
        # record still needs the ordinary identity, provenance and endpoint checks.
        _validate({**meta, "node_count": len(nodes), "edge_count": len(edges)}, nodes, edges)
        stages.append({"metadata": meta, "nodes": nodes, "edges": edges})
    plan["staged_generations"] = stages
    return plan


def _validate_resume(plan: dict, snapshot) -> bool:
    """Resume only an inactive stage whose declared and partial content is exact."""
    key = scope_key(snapshot.repository_id, snapshot.generation_id)
    target = next((g for g in plan["staged_generations"] if g["metadata"]["key"] == key), None)
    if target is None:
        return False
    expected = {
        "repository_id": snapshot.repository_id,
        "generation_id": snapshot.generation_id,
        "source_sha": snapshot.source_sha,
        "mapper_version": snapshot.mapper_version,
        "node_count": len(snapshot.nodes),
        "edge_count": len(snapshot.edges),
        "digest": hashlib.sha256(snapshot.model_dump_json().encode()).hexdigest(),
    }
    if any(target["metadata"].get(field) != value for field, value in expected.items()):
        raise ValueError("native refresh staging plan differs from the exact snapshot")
    nodes = {scope_key(key, node.canonical_id): node.model_dump_json() for node in snapshot.nodes}
    edges = {
        hashlib.sha256(edge.model_dump_json().encode()).hexdigest(): edge.model_dump_json()
        for edge in snapshot.edges
    }
    if any(
        nodes.get(row["props"]["key"]) != row["props"]["payload"] for row in target["nodes"]
    ) or any(edges.get(row["props"]["key"]) != row["props"]["payload"] for row in target["edges"]):
        raise ValueError("native refresh staging records differ from the exact snapshot")
    return True


def _fingerprints(plan: dict) -> dict[str, str]:
    result = {}
    for group in plan["generations"]:
        digest = hashlib.sha256()
        for node in group["nodes"]:
            digest.update(json.dumps([node["props"]["key"], node["props"]["payload"]]).encode())
        for edge in group["edges"]:
            digest.update(
                json.dumps(
                    [edge["props"]["key"], edge["props"]["payload"], edge["source"], edge["target"]]
                ).encode()
            )
        result[group["metadata"]["key"]] = digest.hexdigest()
    return result


def _json_value(value):
    if hasattr(value, "to_native"):
        value = value.to_native()
    if hasattr(value, "isoformat"):
        return {"$temporal_type": type(value).__name__, "$value": value.isoformat()}
    raise TypeError("unsupported backup value: " + type(value).__name__)


async def run(args: argparse.Namespace) -> dict:
    config = KnowledgeConfig(repository_root=args.root)
    values = resolve_neo4j(config)
    if urlsplit(values[0]).hostname != args.expected_host:
        raise ValueError("configured host differs from the explicit native refresh target")
    if args.expected_host not in {"127.0.0.1", "localhost"} and not values[0].startswith(
        ("neo4j+s://", "bolt+s://")
    ):
        raise ValueError("verified TLS is required for remote publication")
    db = (
        writer_backend(args.root)
        if args.apply
        else Neo4jBackend(*values, database=resolve_database(config))
    )
    db.query_timeout = 30
    try:
        before = await _inspect_refresh(db, args.repository_id)
        active = next(
            g["metadata"]
            for g in before["generations"]
            if g["metadata"]["key"] == before["repository"]["active"]
        )
        snapshot = await asyncio.to_thread(
            load_snapshot, args.source_root, args.repository_id, active["source_sha"]
        )
        resumed = _validate_resume(before, snapshot)
        summary = {
            "repository_id": args.repository_id,
            "source_sha": snapshot.source_sha,
            "generation_id": snapshot.generation_id,
            "mapper_version": snapshot.mapper_version,
            "counts": dict(sorted(Counter(n.kind for n in snapshot.nodes).items())),
            "node_count": len(snapshot.nodes),
            "relationship_count": len(snapshot.edges),
            "native_metadata_nodes": sum(
                "_native_projection" in n.properties for n in snapshot.nodes
            ),
            "diagnostics": snapshot.diagnostics,
            "published": False,
            "resuming_staged_generation": resumed,
            "inactive_staged_generations": len(before["staged_generations"]),
        }
        if args.apply:
            if not args.backup:
                raise ValueError("a private backup destination is required for apply")
            backup = Path(args.backup).resolve()
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("x", encoding="utf-8") as stream:
                json.dump(before, stream, default=_json_value)
            await db.setup()
            if not await db.publish(snapshot, expected_generation=active["generation_id"]):
                raise ValueError("active generation changed during native metadata staging")
            after = await _inspect_refresh(db, args.repository_id)
            retained = _fingerprints(after)
            if any(retained.get(key) != value for key, value in _fingerprints(before).items()):
                raise ValueError("retained canonical evidence changed during publication")
            current = after["repository"]["active"]
            if current != scope_key(snapshot.repository_id, snapshot.generation_id):
                raise ValueError(
                    "native publication did not activate the intended complete snapshot"
                )
            unchanged_stages = {
                key: value
                for key, value in _fingerprints(
                    {"generations": before["staged_generations"]}
                ).items()
                if key != current
            }
            observed_stages = _fingerprints({"generations": after["staged_generations"]})
            if any(observed_stages.get(key) != value for key, value in unchanged_stages.items()):
                raise ValueError("unrelated inactive staging evidence changed during publication")
            for group in after["generations"]:
                expected = group["metadata"]["key"] == current
                if any(node["props"].get("current") != expected for node in group["nodes"]) or any(
                    edge["props"].get("current") != expected for edge in group["edges"]
                ):
                    raise ValueError("native publication current-scene marker mismatch")
            summary.update(
                published=True,
                backup=str(backup),
                retained_generations_verified=len(before["generations"]),
            )
        return summary
    finally:
        await db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--repository-id", default="leafcutter")
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup")
    parser.add_argument("--report")
    args = parser.parse_args()
    summary = asyncio.run(run(args))
    if args.report:
        Path(args.report).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
