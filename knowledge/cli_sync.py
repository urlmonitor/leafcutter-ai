"""MODULE: cli_sync
GOAL: Expose immutable validation, planning and writer operations independently.
BUSINESS CONTEXT: Merge indexing never starts the kernel or borrows serving secrets.
ARCHITECTURE: CLI composition loads optional adapters only for database commands.

DECISION HISTORY
========================================
- 2026-10-15 04:00 [python-coder]: Carry the operator-declared retention bound into publication and report the reclamation result. (#KM-400f-2)
- 2026-10-01 12:00 [python-coder]: Separate writer credentials and ancestry verification. (#TICKET-KM-400b-1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import argparse
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.config import RetentionBound
    from knowledge.contracts import ProjectionSnapshot

import asyncio
from pathlib import Path
import subprocess

_BOUND_SOURCE = "command line (--retention-max-generations, --retention-min-age-seconds)"


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
        if name == "sync":
            # Declared by the operator, both together; no built-in bound, no reclamation without one.
            parser.add_argument("--retention-max-generations", type=int, default=None)
            parser.add_argument("--retention-min-age-seconds", type=int, default=None)
        if name in ("rollback", "cleanup"):
            parser.add_argument("--generation-id", required=True)
        if name == "cleanup":
            # Declared by the operator; there is no built-in retention value.
            parser.add_argument("--retention-seconds", type=int, default=None)


def writer_backend(root: str | Path | None = None) -> Neo4jBackend:
    """Construct the writer from its explicit independent credential lifecycle.

    Publication transactions receive a bounded 30 seconds for staged batches and
    atomic activation. Serving keeps its separate configured default of 3 seconds.

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
        query_timeout=30.0,
    )


async def sync(
    root: str | Path,
    repository_id: str,
    revision: str,
    backend: Neo4jBackend,
    surfaces: list[str] | None = None,
    retention_bound: RetentionBound | None = None,
) -> dict:
    """Validate source ancestry before CAS so a delayed merge cannot regress state.

    Args:
        root: Repository directory containing the canonical source data.
        repository_id: Trusted repository namespace that isolates all reads and writes.
        revision: Git revision resolved once to an immutable commit.
        backend: Writer adapter used for staged publication.
        surfaces: Optional explicit surface selection; defaults to the approved set.
        retention_bound: Declared bound; when given, a successful publication reclaims
            the generations it permits.

    Returns:
        Publication outcome, selected source SHA, generation identity, validation plan and
        ``reclamation`` (reclaimed and retained counts with a reason per retained generation).
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
    # Only a declared bound travels with the publication; without one nothing is reclaimed.
    extra = {} if retention_bound is None else {"retention_bound": retention_bound}
    published = await backend.publish(
        snapshot, expected_generation=active.generation_id if active else None, **extra
    )
    counts = getattr(backend, "publication_counts", None)
    return {
        "status": "ok" if published else "stale",
        "published": published,
        "counts": counts,
        "reclamation": getattr(backend, "publication_reclamation", None),
        **_plan(snapshot),
    }


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


def _declared_bound(args: argparse.Namespace) -> RetentionBound | None:
    """Resolve the retention bound the operator declared for ``sync``, if any.

    Args:
        args: Parsed command-line arguments for the chosen operation.

    Returns:
        The declared bound, or None when neither setting was given (no reclamation).

    Raises:
        ValueError: When only one of the two settings was declared, or one is out of range.
    """
    count = getattr(args, "retention_max_generations", None)
    age = getattr(args, "retention_min_age_seconds", None)
    if args.command != "sync" or (count is None and age is None):
        return None
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    config = KnowledgeConfig(retention_max_generations=count, retention_min_age_seconds=age)
    return resolve_retention_bound(config, source=_BOUND_SOURCE)


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
    bound = _declared_bound(args)  # refuses an incomplete declaration before any network access
    backend = writer_backend(args.root)
    try:
        if args.command == "sync":
            await backend.setup()
            return await sync(
                args.root, args.repository_id, args.revision, backend, args.surfaces, bound
            )
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
            changed = await backend.cleanup(
                args.repository_id, args.generation_id, args.retention_seconds
            )
        return {"status": "ok" if changed else "stale", "changed": changed}
    finally:
        await backend.close()

# - 2026-10-09 16:20 [python-coder]: Give standalone publication its bounded writer timeout without changing serving latency or atomicity. (#KM-400/TICKET-20261001-KM-400e-5)
