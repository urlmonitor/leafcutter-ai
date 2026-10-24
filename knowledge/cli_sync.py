"""MODULE: cli_sync
GOAL: Expose immutable validation, planning and writer operations independently.
BUSINESS CONTEXT: Merge indexing never starts the kernel or borrows serving secrets.
ARCHITECTURE: CLI composition loads optional adapters only for database commands.

DECISION HISTORY
========================================
- 2026-10-21 12:00 [python-coder]: Fail the sync job before connecting when the database name or writer username is unset, naming each, and report the requested database and its source on a backend rejection. (#KM-400e-8)
- 2026-10-20 23:00 [python-coder]: Extend status with retained generations and capacity usage and add a sweep reclaim command that requires the declared bound. (#KM-400f-4)
- 2026-10-20 18:00 [python-coder]: Run the read-only preflight before setup so a latched store reports the capacity condition, not a raw rejection. (#KM-400f-3/02)
- 2026-10-20 14:00 [python-coder]: Declare the capacity ceiling by four all-or-none flags, refuse a partial declaration before any network access, and report the measured headroom. (#KM-400f-3)
- 2026-10-15 04:00 [python-coder]: Carry the operator-declared retention bound into publication and report the reclamation result. (#KM-400f-2)
- 2026-10-01 12:00 [python-coder]: Separate writer credentials and ancestry verification. (#TICKET-KM-400b-1)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import argparse
    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.adapters.retention.capacity import CapacityCeiling
    from knowledge.config import RetentionBound
    from knowledge.contracts import ProjectionSnapshot

import asyncio
from contextvars import ContextVar
from pathlib import Path
import subprocess

from knowledge.errors import BackendUnavailable

_BOUND_SOURCE = "command line (--retention-max-generations, --retention-min-age-seconds)"
_CAPACITY_FLAGS = (
    "--capacity-max-nodes",
    "--capacity-max-relationships",
    "--capacity-refuse-percent",
    "--capacity-warn-percent",
)
_CAPACITY_SOURCE = "command line (" + ", ".join(_CAPACITY_FLAGS) + ")"
_RECLAIM_NEEDS_BOUND = (
    "reclaim requires the retention bound: declare --retention-max-generations "
    "and --retention-min-age-seconds"
)
_DECLARING = ("sync", "status", "reclaim")  # commands that accept the declared bound and ceiling
_DATABASE_NAMES = ("LEAFCUTTER_NEO4J_DATABASE", "NEO4J_DATABASE")
# Set by run() for the synchronization job: an undeclared database name is then a named failure.
_DATABASE_REQUIRED: ContextVar[bool] = ContextVar("knowledge_database_required", default=False)


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    """Register standalone ingestion and lifecycle commands.

    Args:
        subparsers: Argument-parser collection receiving sync subcommands.
    """
    for name in ("validate", "plan", "sync", "status", "reclaim", "rollback", "cleanup"):
        parser = subparsers.add_parser(name)
        parser.add_argument("--root", required=True)
        parser.add_argument("--repository-id", default="leafcutter")
        parser.add_argument("--revision", default="HEAD")
        from knowledge.projection.canonical_loader import SUPPORTED_SURFACES

        parser.add_argument(
            "--surfaces", nargs="+", choices=sorted(SUPPORTED_SURFACES), default=None
        )
        if name in _DECLARING:
            # Declared by the operator, both together; no built-in bound, no reclamation without one.
            parser.add_argument("--retention-max-generations", type=int, default=None)
            parser.add_argument("--retention-min-age-seconds", type=int, default=None)
            # The backend does not report its ceiling over Bolt: the operator declares all four or none.
            for flag in _CAPACITY_FLAGS:
                parser.add_argument(flag, type=int, default=None)
        if name in ("rollback", "cleanup"):
            parser.add_argument("--generation-id", required=True)
        if name == "cleanup":
            # Declared by the operator; there is no built-in retention value.
            parser.add_argument("--retention-seconds", type=int, default=None)


def database_source(root: str | Path | None = None) -> tuple[str | None, str | None]:
    """Find the declared database name and say where it was read from.

    Args:
        root: Repository directory from which environment-file discovery starts.

    Returns:
        The declared name and a secret-free description of its source, or (None, None) when unset.
    """
    from knowledge.environment import environment_sources

    for index, source in enumerate(environment_sources(root)):
        for name in _DATABASE_NAMES:
            if source.get(name):
                where = "the process environment" if index == 0 else "an environment file"
                return source[name], f"{name} in {where}"
    return None, None


def writer_backend(root: str | Path | None = None) -> Neo4jBackend:
    """Construct the writer from its explicit independent credential lifecycle.

    Publication transactions receive a bounded 30 seconds for staged batches and
    atomic activation. Serving keeps its separate configured default of 3 seconds.

    Args:
        root: Repository directory containing the canonical source data.

    Returns:
        An unopened writer adapter using the separately configured writer credentials.

    Raises:
        ValueError: Naming every unset required setting, before any connection is made.
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
    database = select_value(sources, *_DATABASE_NAMES)
    missing = [name for name, value in zip(names, values) if not value]
    if _DATABASE_REQUIRED.get() and not database:  # the synchronization job never guesses a name
        missing.append(_DATABASE_NAMES[0])
    if missing:
        raise ValueError("writer configuration missing: " + ", ".join(missing))
    return Neo4jBackend(
        str(uri),
        str(username),
        str(password),
        database=database or "neo4j",
        query_timeout=30.0,
    )


async def sync(
    root: str | Path,
    repository_id: str,
    revision: str,
    backend: Neo4jBackend,
    surfaces: list[str] | None = None,
    retention_bound: RetentionBound | None = None,
    capacity: CapacityCeiling | None = None,
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
        capacity: Declared ceiling; None leaves the ceiling unknown (usage is still measured).

    Returns:
        Publication outcome, selected source SHA, generation identity, validation plan,
        ``reclamation`` (reclaimed and retained counts with a reason per retained generation)
        and ``capacity`` (the measured headroom report).
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
    extra: dict[str, Any] = {} if retention_bound is None else {"retention_bound": retention_bound}
    if capacity is not None:
        extra["capacity"] = capacity
    published = await backend.publish(
        snapshot, expected_generation=active.generation_id if active else None, **extra
    )
    counts = getattr(backend, "publication_counts", None)
    return {
        "status": "ok" if published else "stale",
        "published": published,
        "counts": counts,
        "reclamation": getattr(backend, "publication_reclamation", None),
        "capacity": getattr(backend, "publication_capacity", None),
        "writes": getattr(backend, "publication_writes", None),
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
    if args.command not in _DECLARING:
        return None
    if count is None and age is None:
        if args.command == "reclaim":
            raise ValueError(_RECLAIM_NEEDS_BOUND)
        return None
    from knowledge.config import KnowledgeConfig, resolve_retention_bound

    config = KnowledgeConfig(retention_max_generations=count, retention_min_age_seconds=age)
    return resolve_retention_bound(config, source=_BOUND_SOURCE)


def _declared_capacity(args: argparse.Namespace) -> CapacityCeiling | None:
    """Resolve the capacity ceiling the operator declared for ``sync``, if any.

    Args:
        args: Parsed command-line arguments for the chosen operation.

    Returns:
        The declared ceiling, or None when none of the four settings was given (unknown ceiling).

    Raises:
        ValueError: When only some of the four settings were declared, or one is out of range.
    """
    if args.command not in _DECLARING:
        return None
    from knowledge.adapters.retention.capacity import resolve_capacity

    values = [getattr(args, flag[2:].replace("-", "_"), None) for flag in _CAPACITY_FLAGS]
    return resolve_capacity(*values, source=_CAPACITY_SOURCE)


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
    capacity = _declared_capacity(args)  # likewise refused before any network access
    required = _DATABASE_REQUIRED.set(args.command == "sync")
    try:
        backend = writer_backend(args.root)
    finally:
        _DATABASE_REQUIRED.reset(required)
    try:
        return await _dispatch(args, backend, bound, capacity)
    except BackendUnavailable as exc:
        name, source = database_source(args.root)
        detail = f"{exc} [database requested: {name}; read from {source}]"
        failure = BackendUnavailable(detail)
        failure.details = failure_details(backend, exc)
        raise failure from exc
    finally:
        await backend.close()


def failure_details(backend: Neo4jBackend, error: BackendUnavailable) -> dict:
    """Collect the discrete failure fields a failed publication carries (KM-400b-5-vi).

    Args:
        backend: Writer adapter holding the last publication's reports.
        error: The failure being re-raised; its cause class and time limit are kept.

    Returns:
        ``cause_class``, ``time_limit_seconds`` (time limit only), and from the write report
        ``phase``, ``batch``, ``attempts``, ``attempt_causes``, ``progress`` and ``writes``;
        a field the failure does not have is left out rather than reported as 0.
    """
    details: dict = {}
    cause = getattr(error, "cause_class", None)
    if cause is not None:
        details["cause_class"] = cause
    if getattr(error, "time_limit_seconds", None) is not None:
        details["time_limit_seconds"] = error.time_limit_seconds
    report = getattr(backend, "publication_failure", None) or {}
    for field in ("time_limit_seconds", "phase", "batch", "attempts", "attempt_causes", "progress"):
        if field in report and field not in details:
            details[field] = report[field]
    writes = getattr(backend, "publication_writes", None)
    if writes is not None:
        details["writes"] = writes
    return details


async def _dispatch(
    args: argparse.Namespace,
    backend: Neo4jBackend,
    bound: RetentionBound | None,
    capacity: CapacityCeiling | None,
) -> dict:
    """Run the chosen command against an already-constructed writer.

    Args:
        args: Parsed command-line arguments for the chosen operation.
        backend: Writer adapter (owned and closed by the caller).
        bound: Declared retention bound, if any.
        capacity: Declared capacity ceiling, if any.

    Returns:
        The selected command result.
    """
    if args.command == "sync":
        from knowledge.adapters.retention.capacity import prepare_writable

        await prepare_writable(backend, capacity)  # read-only preflight, then setup
        return await sync(
            args.root, args.repository_id, args.revision, backend, args.surfaces, bound, capacity
        )
    if args.command == "reclaim":
        from knowledge.cli_generations import reclaim_generations

        if bound is None:  # already refused by _declared_bound; restated for the type checker
            raise ValueError(_RECLAIM_NEEDS_BOUND)

        return await reclaim_generations(backend, args.repository_id, bound, capacity)
    active = await backend.active(args.repository_id)
    if args.command == "status":
        from knowledge.adapters.git_source import resolve_revision
        from knowledge.cli_generations import manifest_of, status_report

        requested = await asyncio.to_thread(resolve_revision, Path(args.root), args.revision)
        published = active.source_sha if active else None
        return {
            "status": "ok" if published == requested else "stale",
            "requested_sha": requested,
            "published_sha": published,
            "lagging": published != requested,
            "manifest": manifest_of(active),
            **await status_report(backend, args.repository_id, bound, capacity),
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

# - 2026-10-09 16:20 [python-coder]: Give standalone publication its bounded writer timeout without changing serving latency or atomicity. (#KM-400/TICKET-20261001-KM-400e-5)
