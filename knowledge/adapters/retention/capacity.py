"""MODULE: retention.capacity
GOAL: Measure capacity headroom before a publication writes, and refuse one that does not fit.
BUSINESS CONTEXT: A full hosted store latches read-only and then blocks the very writes that would reclaim space.
ARCHITECTURE: Reads whole-database usage through db._run, compares usage plus snapshot with the operator-declared ceiling per axis, and raises before the first write; db.publication_capacity carries the report.

DECISION HISTORY
========================================
- 2026-10-20 18:00 [python-coder]: Preflight a read-only store before setup's schema writes, classify a read-only setup rejection, and count an already-stored generation as adding 0. (#KM-400f-3/02)
- 2026-10-20 14:00 [python-coder]: Measure whole-database usage before the first write, refuse above the declared threshold on either axis, report an undeclared ceiling as unknown, and classify a read-only latch as a capacity condition. (#KM-400f-3)
- 2026-10-20 12:00 [main-loop]: Contract stub declaring CapacityCeiling only, so the red-baseline tests reach the publication path instead of failing on import. (#KM-400f-3)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from knowledge.contracts import Model
from knowledge.errors import BackendUnavailable

if TYPE_CHECKING:
    from knowledge.adapters.neo4j_backend import Neo4jBackend

logger = logging.getLogger(__name__)

_NODE_COUNT = "MATCH (n) RETURN count(n) AS count"
_RELATIONSHIP_COUNT = "MATCH ()-[r]->() RETURN count(r) AS count"
_GENERATION_STATUS = "MATCH (g:Snapshot {key:$key}) RETURN g.status AS status"
_SHOW_ACCESS ="SHOW DATABASE $name YIELD access"
_READ_ONLY_MARKERS = ("read-only", "readonly", "read only", "no write operations")
_FLAGS = (
    "--capacity-max-nodes",
    "--capacity-max-relationships",
    "--capacity-refuse-percent",
    "--capacity-warn-percent",
)


class CapacityCeiling(Model):
    """Operator-declared capacity ceiling with refuse and warning thresholds, in percent of the ceiling."""

    max_nodes: int
    max_relationships: int
    refuse_percent: int
    warn_percent: int
    source: str


_RANGE_REFUSALS = {
    "size": "capacity ceiling must be at least 1 node and 1 relationship",
    "percent": "capacity percentages must satisfy 1 <= warn <= refuse <= 100",
}


def _refused_declaration(kind: str, missing: list[str], source: str) -> ValueError:
    """Build the refusal of a partial (``missing``) or out-of-range (``size`` / ``percent``) declaration."""
    if kind == "partial":
        return ValueError(
            "capacity ceiling is partially declared: " + ", ".join(missing) + " not declared "
            f"(source: {source}); declare all four capacity settings or none"
        )
    return ValueError(_RANGE_REFUSALS[kind])


def resolve_capacity(
    max_nodes: int | None,
    max_relationships: int | None,
    refuse_percent: int | None,
    warn_percent: int | None,
    *,
    source: str,
) -> CapacityCeiling | None:
    """Resolve the declared ceiling, refusing a partial or out-of-range declaration.

    Args:
        max_nodes: Declared node ceiling, or None.
        max_relationships: Declared relationship ceiling, or None.
        refuse_percent: Percent of the ceiling above which publication is refused, or None.
        warn_percent: Percent of the ceiling above which publication warns, or None.
        source: Inspectable name of where the declaration was read from.

    Returns:
        The ceiling, or None when nothing was declared (the ceiling is then unknown).

    Raises:
        ValueError: When only some of the four settings were declared, or one is out of range.
    """
    values = (max_nodes, max_relationships, refuse_percent, warn_percent)
    if all(value is None for value in values):
        return None
    missing = [flag for flag, value in zip(_FLAGS, values) if value is None]
    if missing:
        raise _refused_declaration("partial", missing, source)
    ceiling = CapacityCeiling(
        max_nodes=max_nodes or 0,
        max_relationships=max_relationships or 0,
        refuse_percent=refuse_percent or 0,
        warn_percent=warn_percent or 0,
        source=source,
    )
    if min(ceiling.max_nodes, ceiling.max_relationships) < 1:
        raise _refused_declaration("size", missing, source)
    if not 1 <= ceiling.warn_percent <= ceiling.refuse_percent <= 100:
        raise _refused_declaration("percent", missing, source)
    return ceiling


def _over(total: int, maximum: int, percent: int) -> bool:
    """Say whether a total is strictly greater than a percentage of the ceiling."""
    return total * 100 > percent * maximum


def _axis(usage: int, size: int, maximum: int | None, refuse: int) -> dict:
    """Report the four figures of one axis; shortfall and remaining are None when the ceiling is unknown."""
    figures: dict = {"usage": usage, "ceiling": maximum, "snapshot": size}
    if maximum is None:
        return {**figures, "shortfall": None, "remaining": None}
    gap = (usage + size) * 100 - refuse * maximum  # hundredths of a record, so no rounding hides a miss
    return {**figures, "shortfall": max(0, -(-gap // 100)), "remaining": max(0, -gap // 100)}


def _verdict(totals: list[tuple[int, int]], ceiling: CapacityCeiling | None) -> str:
    """Classify the publication from (total, ceiling) per axis against the declared thresholds."""
    if ceiling is None:
        return "unknown"
    if any(_over(t, m, ceiling.refuse_percent) for t, m in totals):
        return "refused"
    if any(_over(t, m, ceiling.warn_percent) for t, m in totals):
        return "warning"
    return "within_headroom"


def _line(axis: str, figures: dict, tail: str) -> str:
    """Name usage, ceiling and snapshot size of one axis, then its shortfall or remaining headroom."""
    ceiling = "undetermined" if figures["ceiling"] is None else f"{figures['ceiling']:,}"
    return (
        f"{axis}: measured usage {figures['usage']:,}, ceiling {ceiling}, "
        f"snapshot {figures['snapshot']:,}{tail}"
    )


def _statement(verdict: str, nodes: dict, links: dict) -> str:
    """State the headroom result in words, with the measured figures for both axes."""
    if verdict == "unknown":
        return (
            "capacity headroom unknown: the ceiling could not be determined, so no headroom check "
            f"was satisfied; usage measured from the backend: {nodes['usage']:,} nodes, "
            f"{links['usage']:,} relationships"
        )
    return f"capacity headroom {verdict.replace('_', ' ')} (usage measured from the backend)"


def _warnings(verdict: str, nodes: dict, links: dict) -> list[str]:
    """Name usage, ceiling, snapshot and remaining headroom for each axis when the warning level is crossed."""
    if verdict != "warning":
        return []
    return [
        "capacity headroom warning, usage measured from the backend; "
        + _line(axis, figures, f", remaining headroom {figures['remaining']:,}")
        for axis, figures in (("nodes", nodes), ("relationships", links))
    ]


def assess(
    usage: tuple[int, int], snapshot: tuple[int, int], ceiling: CapacityCeiling | None
) -> dict:
    """Compare measured usage plus the prepared snapshot with the declared ceiling, per axis.

    Args:
        usage: Measured whole-database (nodes, relationships).
        snapshot: Prepared snapshot size (nodes, distinct relationships).
        ceiling: Declared ceiling, or None when it could not be determined.

    Returns:
        The headroom report: verdict, basis, ceiling_known, satisfied, warnings, statement and
        the per-axis ``nodes`` / ``relationships`` figures.
    """
    limits = (None, None) if ceiling is None else (ceiling.max_nodes, ceiling.max_relationships)
    refuse = 100 if ceiling is None else ceiling.refuse_percent
    nodes = _axis(usage[0], snapshot[0], limits[0], refuse)
    links = _axis(usage[1], snapshot[1], limits[1], refuse)
    totals = [(usage[i] + snapshot[i], m) for i, m in enumerate(limits) if m is not None]
    verdict = _verdict(totals, ceiling)
    return {
        "verdict": verdict,
        "basis": "measured",
        "ceiling_known": ceiling is not None,
        "satisfied": verdict in ("within_headroom", "warning"),
        "warnings": _warnings(verdict, nodes, links),
        "statement": _statement(verdict, nodes, links),
        "nodes": nodes,
        "relationships": links,
    }


def refusal_message(report: dict) -> str:
    """Word the refusal: four figures per axis, that usage was measured, and the zero reclaimed.

    Args:
        report: A ``refused`` headroom report.

    Returns:
        The refusal text raised before any write.
    """
    parts = [
        _line(axis, report[axis], f", shortfall {report[axis]['shortfall']:,}")
        for axis in ("nodes", "relationships")
    ]
    return (
        "publication refused before any write: capacity headroom is insufficient "
        "(usage figures were measured from the backend, not estimated); "
        + "; ".join(parts)
        + "; 0 generations reclaimed"
    )


def read_only_message(report: dict, cause: str | None = None) -> str:
    """Word the read-only refusal: the latched condition and the measured usage.

    Args:
        report: The headroom report of the publication.
        cause: The backend's own rejection text, when the condition was classified from a write.

    Returns:
        The refusal text naming ``read-only`` and the measured usage.
    """
    nodes, links = report["nodes"]["usage"], report["relationships"]["usage"]
    detail = f" ({cause})" if cause else ""
    return (
        "backend is read-only, a capacity condition: the store accepts no writes, so this is not a "
        f"result about knowledge{detail}; usage measured from the backend: {nodes:,} nodes, "
        f"{links:,} relationships; 0 generations reclaimed"
    )


async def database_access(db: Neo4jBackend) -> str | None:
    """Read the database's access mode from the system database, where the principal may.

    Args:
        db: Scoped Neo4j adapter; ``SHOW DATABASE`` runs against the ``system`` database.

    Returns:
        ``read-write`` / ``read-only``, or None when the query is refused or returns nothing.
    """
    name = getattr(db, "database", "neo4j")
    try:
        rows = await db._run(_SHOW_ACCESS, {"name": name}, database="system")
    except BackendUnavailable as error:
        logger.warning("database access mode could not be read; a read-only latch will be classified from a write rejection: %s", error)
        return None
    return str(rows[0]["access"]) if rows else None


async def _measure(db: Neo4jBackend) -> tuple[int, int]:
    """Read whole-database (nodes, relationships); reads still work on a read-only database."""
    nodes = await db._run(_NODE_COUNT, {})
    links = await db._run(_RELATIONSHIP_COUNT, {})
    return nodes[0]["count"], links[0]["count"]


def _read_only_report(usage: tuple[int, int], ceiling: CapacityCeiling | None) -> dict:
    """Headroom report of a latched store: the usual figures, the verdict ``read_only``, never satisfied."""
    return {**assess(usage, (0, 0), ceiling), "verdict": "read_only", "satisfied": False}


async def refuse_if_read_only(db: Neo4jBackend, ceiling: CapacityCeiling | None = None) -> None:
    """Read-only preflight: refuse a latched store before any write, including setup's schema writes.

    Args:
        db: Scoped Neo4j adapter.
        ceiling: Declared ceiling, or None (reported as unknown).

    Raises:
        BackendUnavailable: The store reports ``read-only``; names the condition and measured usage.
    """
    if await database_access(db) != "read-only":
        return
    db.publication_capacity = report = _read_only_report(await _measure(db), ceiling)
    raise BackendUnavailable(read_only_message(report))


async def prepare_writable(db: Neo4jBackend, ceiling: CapacityCeiling | None = None) -> None:
    """Preflight, then run ``db.setup()``, classifying a read-only rejection of its schema writes.

    Args:
        db: Scoped Neo4j adapter.
        ceiling: Declared ceiling, or None.

    Raises:
        BackendUnavailable: A read-only condition (named, with measured usage, original chained), or
            any other setup failure unchanged.
    """
    await refuse_if_read_only(db, ceiling)
    try:
        await db.setup()
    except BackendUnavailable as error:
        if not any(m in str(error).lower() for m in _READ_ONLY_MARKERS):
            raise
        logger.warning("setup was rejected as read-only: %s", error)
        db.publication_capacity = report = _read_only_report(await _measure(db), ceiling)
        raise BackendUnavailable(read_only_message(report, str(error))) from error


async def _already_stored(db: Neo4jBackend, generation_key: str | None) -> bool:
    """Say whether this generation's records are already inside the measured usage.

    A ``validated`` or ``ready`` record is complete, so a rerun or a resume after a failed pointer
    switch adds nothing. ``building`` (partially written) or absent counts in full: conservative.
    """
    if generation_key is None:
        return False
    rows = await db._run(_GENERATION_STATUS, {"key": generation_key})
    return bool(rows) and rows[0]["status"] in ("validated", "ready")


async def enforce_headroom(
    db: Neo4jBackend,
    snapshot_nodes: int,
    snapshot_edges: int,
    ceiling: CapacityCeiling | None,
    generation_key: str | None = None,
) -> None:
    """Measure usage and refuse before the first write when the snapshot does not fit.

    Sets ``db.publication_capacity`` to the headroom report. An unknown ceiling is reported, not refused.
    A generation already stored complete (``validated`` / ``ready``) adds 0 on both axes, and the report
    says ``snapshot_already_stored``; a partial (``building``) or absent one counts in full.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        snapshot_nodes: Entity records the prepared snapshot will write.
        snapshot_edges: Distinct relationships the prepared snapshot will write.
        ceiling: Declared ceiling, or None.
        generation_key: Scoped key of this generation's record; None skips the existing-record read.

    Raises:
        BackendUnavailable: The backend reports ``read-only``.
        ValueError: Usage plus snapshot exceeds the refuse threshold on either axis.
    """
    usage = await _measure(db)
    stored = await _already_stored(db, generation_key)
    added = (0, 0) if stored else (snapshot_nodes, snapshot_edges)
    report = {**assess(usage, added, ceiling), "snapshot_already_stored": stored}
    if stored:
        report["statement"] += "; snapshot already stored, so it adds 0 to the measured usage"
    db.publication_capacity = report
    if await database_access(db) == "read-only":
        db.publication_capacity = report = {**report, "verdict": "read_only", "satisfied": False}
        raise BackendUnavailable(read_only_message(report))
    if report["verdict"] == "refused":
        raise ValueError(refusal_message(report))
    for warning in report["warnings"]:
        logger.warning(warning)


async def first_write(db: Neo4jBackend, statement: str, params: dict) -> list[dict]:
    """Run the first write of a publication, classifying a read-only rejection as a capacity condition.

    Args:
        db: Scoped Neo4j adapter owning the driver and transaction policy.
        statement: The write statement.
        params: Its bound parameters.

    Returns:
        The statement's rows.

    Raises:
        BackendUnavailable: The rejection, naming ``read-only`` and the measured usage when the
            backend rejected the write because it is read-only.
    """
    try:
        return await db._run(statement, params, True)
    except BackendUnavailable as error:
        report = getattr(db, "publication_capacity", None)
        if report is None or not any(m in str(error).lower() for m in _READ_ONLY_MARKERS):
            raise
        db.publication_capacity = report = {**report, "verdict": "read_only", "satisfied": False}
        raise BackendUnavailable(read_only_message(report, str(error))) from error
