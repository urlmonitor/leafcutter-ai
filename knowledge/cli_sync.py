"""MODULE: cli_sync
GOAL: Expose immutable validation, planning and writer operations independently.
BUSINESS CONTEXT: Merge indexing never starts the kernel or borrows serving secrets.
ARCHITECTURE: CLI composition loads optional adapters only for database commands.

DECISION HISTORY
========================================
- 2026-10-01 12:00 [python-coder]: Separate writer credentials and ancestry verification. (#TICKET-KM-400b-1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.contracts import ProjectionSnapshot

import asyncio
from pathlib import Path
import subprocess


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register standalone ingestion and lifecycle commands.

    Args:
        subparsers: Argument-parser collection receiving sync subcommands.
    """
    for name in ("validate", "plan", "sync", "status", "rollback", "cleanup"):
        parser = subparsers.add_parser(name)
        parser.add_argument("--root", required=True)
        parser.add_argument("--repository-id", default="leafcutter")
        parser.add_argument("--revision", default="HEAD")
        from knowledge.projection.canonical_loader import SUPPORTED_SURFACES

        parser.add_argument(
            "--surfaces", nargs="+", choices=sorted(SUPPORTED_SURFACES), default=None
        )
        if name in ("rollback", "cleanup"):
            parser.add_argument("--generation-id", required=True)


def writer_backend(root: str | Path | None = None) -> Neo4jBackend:
    """Construct the writer from its explicit independent credential lifecycle.

    Args:
        root: Repository directory containing the canonical source data.

    Returns:
        An unopened writer adapter using the separately configured writer credentials.
    """
    from knowledge.adapters.neo4j_backend import Neo4jBackend

    names = (
        "LEAFCUTTER_NEO4J_URI",
        "LEAFCUTTER_NEO4J_WRITER_USERNAME",
        "LEAFCUTTER_NEO4J_WRITER_PASSWORD",
    )
    from knowledge.environment import environment_sources, select_value

    sources = environment_sources(root)
    values = [select_value(sources, names[0], "NEO4J_URI")]
    values.extend(select_value(sources, name) for name in names[1:])
    uri, username, password = values
    if not uri or not username or not password:
        missing = [name for name, value in zip(names, values) if not value]
        raise ValueError("writer configuration missing: " + ", ".join(missing))
    return Neo4jBackend(
        uri,
        username,
        password,
        database=select_value(sources, "LEAFCUTTER_NEO4J_DATABASE", "NEO4J_DATABASE") or "neo4j",
    )


async def sync(
    root: str | Path,
    repository_id: str,
    revision: str,
    backend: Neo4jBackend,
    surfaces: list[str] | None = None,
) -> dict:
    """Validate source ancestry before CAS so a delayed merge cannot regress state.

    Args:
        root: Repository directory containing the canonical source data.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        revision: Git revision resolved once to an immutable commit.
        backend: Writer adapter used for staged publication.
        surfaces: Optional explicit surface selection; defaults to the approved set.

    Returns:
        Publication outcome, selected source SHA, generation identity and validation plan.
    """
    from knowledge.projection.canonical_loader import load_snapshot

    snapshot = await asyncio.to_thread(load_snapshot, root, repository_id, revision, surfaces)
    active = await backend.active(repository_id)
    scope = [value for value in snapshot.diagnostics if value.startswith("projection_scope:")]
    old_scope = (
        [value for value in active.diagnostics if value.startswith("projection_scope:")]
        if active
        else scope
    )
    if scope != old_scope:
        raise ValueError(
            "projection scope changed; use a separate repository scope or explicit reconciliation"
        )
    if active and active.source_sha != snapshot.source_sha:
        result = await asyncio.to_thread(
            subprocess.run,
            [
                "git",
                "-C",
                str(root),
                "merge-base",
                "--is-ancestor",
                active.source_sha,
                snapshot.source_sha,
            ],
            capture_output=True,
            timeout=15,
        )
        if result.returncode != 0:
            raise ValueError(
                "source revision is older or non-descendant; explicit reconciliation is required"
            )
    published = await backend.publish(
        snapshot, expected_generation=active.generation_id if active else None
    )
    return {"status": "ok" if published else "stale", "published": published, **_plan(snapshot)}


def _plan(snapshot: ProjectionSnapshot) -> dict:
    """Summarize a validated generation without loading it into a database.

    Args:
        snapshot: Validated immutable generation and its canonical source records.

    Returns:
        Generation identity, counts and diagnostics suitable for CLI serialization.
    """
    return {
        "repository_id": snapshot.repository_id,
        "source_sha": snapshot.source_sha,
        "generation_id": snapshot.generation_id,
        "mapper_version": snapshot.mapper_version,
        "node_count": len(snapshot.nodes),
        "edge_count": len(snapshot.edges),
        "diagnostics": snapshot.diagnostics,
        "semantic_ready": False,
    }


async def run(args: argparse.Namespace) -> dict:
    """Run one standalone command and always release its owned driver.

    Args:
        args: Parsed command-line arguments for the chosen operation.

    Returns:
        The selected command result, including readiness, publication or cleanup status.
    """
    if args.command in ("validate", "plan"):
        from knowledge.projection.canonical_loader import load_snapshot

        snapshot = await asyncio.to_thread(
            load_snapshot, args.root, args.repository_id, args.revision, args.surfaces
        )
        return {"status": "ok", "published": False, **_plan(snapshot)}
    backend = writer_backend(args.root)
    try:
        if args.command == "sync":
            await backend.setup()
            return await sync(args.root, args.repository_id, args.revision, backend, args.surfaces)
        active = await backend.active(args.repository_id)
        if args.command == "status":
            from knowledge.adapters.git_source import resolve_revision

            requested = await asyncio.to_thread(resolve_revision, Path(args.root), args.revision)
            published = active.source_sha if active else None
            return {
                "status": "ok" if published == requested else "stale",
                "requested_sha": requested,
                "published_sha": published,
                "lagging": published != requested,
                "manifest": active.model_dump(mode="json") if active else None,
            }
        if args.command == "rollback":
            changed = await backend.rollback(
                args.repository_id, args.generation_id, active.generation_id if active else None
            )
        else:
            changed = await backend.cleanup(args.repository_id, args.generation_id)
        return {"status": "ok" if changed else "stale", "changed": changed}
    finally:
        await backend.close()
