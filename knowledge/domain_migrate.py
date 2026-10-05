"""MODULE: domain_migrate
GOAL: Inspect, back up and explicitly apply the Aura domain graph presentation migration.
BUSINESS CONTEXT: KM-400a-3-i makes the approved migration reviewable and repeatable.
ARCHITECTURE: Read-only by default; writes require --apply, a backup and writer credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlsplit

from knowledge.adapters.neo4j_backend import Neo4jBackend
from knowledge.adapters.neo4j_domain_migration import inspect, migrate
from knowledge.cli_sync import writer_backend
from knowledge.config import KnowledgeConfig
from knowledge.environment import resolve_neo4j, resolve_database


async def run(args: argparse.Namespace) -> dict:
    """Inspect one explicit host, optionally saving a full backup and migrating it."""
    config = KnowledgeConfig(repository_root=args.root)
    values = resolve_neo4j(config)
    if urlsplit(values[0]).hostname != args.expected_host:
        raise ValueError("configured host does not match the explicit migration target")
    if args.expected_host not in {"127.0.0.1", "localhost"} and not values[0].startswith(
        ("neo4j+s://", "bolt+s://")
    ):
        raise ValueError("verified TLS is required for remote migration")
    db = (
        writer_backend(args.root)
        if args.apply
        else Neo4jBackend(*values, database=resolve_database(config))
    )
    db.query_timeout = 30
    try:
        plan = await inspect(db, args.repository_id)
        summary = {
            "repository_id": args.repository_id,
            "fingerprint": plan["fingerprint"],
            "active": plan["repository"]["active"],
            "generations": [
                {
                    "source_sha": g["metadata"]["source_sha"],
                    "nodes": len(g["nodes"]),
                    "relationships": len(g["edges"]),
                }
                for g in plan["generations"]
            ],
        }
        if args.apply:
            if not args.backup:
                raise ValueError("--backup is required for migration")
            backup = Path(args.backup).resolve()
            backup.parent.mkdir(parents=True, exist_ok=True)
            with backup.open("x", encoding="utf-8") as stream:
                json.dump(plan, stream)
            summary["migration"] = await migrate(db, plan)
            summary["backup"] = str(backup)
        return summary
    finally:
        await db.close()


def main() -> None:
    """Run the explicit operator command; never print credentials or graph payloads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--repository-id", required=True)
    parser.add_argument("--expected-host", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(run(args)), indent=2))


if __name__ == "__main__":
    main()
