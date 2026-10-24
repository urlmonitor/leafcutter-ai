"""MODULE: neo4j_writes
GOAL: Bound publication write batches by rows and payload bytes, retry time-limit failures, report the slow batch.
BUSINESS CONTEXT: KM-400b-5-iii..vi; one batch of large records must not outrun the writer's time limit.
ARCHITECTURE: Used by neo4j_domain_build for node and relationship batches and by neo4j_projection for activation.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, NoReturn

from knowledge.errors import BackendUnavailable

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from knowledge.adapters.neo4j_backend import Neo4jBackend
    from knowledge.contracts import ProjectionSnapshot

logger = logging.getLogger(__name__)

DEFAULT_ROW_CAP = 250
DEFAULT_PAYLOAD_BUDGET = 2_000_000
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_RETRY_WAIT_SECONDS = 1.0
TIME_LIMIT = "time_limit"


def classify_failure(error: BaseException) -> str:
    """Name the class of a store failure from the driver's code, never from message text.

    Args:
        error: Infrastructure exception raised by the driver or transport.

    Returns:
        ``time_limit``, ``read_only``, ``rule_violation`` or ``unavailable``.
    """
    code = str(getattr(error, "code", "") or "")
    if isinstance(error, TimeoutError) or "TimedOut" in code:
        return TIME_LIMIT
    if "ReadOnly" in code:
        return "read_only"
    if "Constraint" in code:
        return "rule_violation"
    return "unavailable"


def row_bytes(row: dict) -> int:
    """Return the serialized size of one write row in bytes."""
    return len(json.dumps(row, sort_keys=True, default=str).encode("utf-8"))


def partition(rows: list[dict], cap: int, budget: int) -> list[tuple[list[dict], int]]:
    """Split rows, in order, into batches bounded by row count and payload bytes.

    A batch closes at ``cap`` rows or before the row that would take it over ``budget``;
    a row larger than the budget therefore ends up alone.

    Args:
        rows: Rows to write.
        cap: Most rows in one batch.
        budget: Most serialized bytes in one batch holding more than one row.

    Returns:
        Each batch with its serialized size in bytes.
    """
    batches: list[tuple[list[dict], int]] = []
    current: list[dict] = []
    used = 0
    for row in rows:
        size = row_bytes(row)
        if current and (len(current) >= cap or used + size > budget):
            batches.append((current, used))
            current, used = [], 0
        current.append(row)
        used += size
    if current:
        batches.append((current, used))
    return batches


@dataclass
class Plan:
    """The batches of one label or relationship type."""

    label: str
    statement: str
    batches: list[tuple[list[dict], int]]


def _check_retry_settings(settings: dict) -> None:
    """Refuse an attempt cap or retry wait that cannot bound the retries (KM-400b-5-v).

    Args:
        settings: The settings in force.

    Raises:
        ValueError: ``max_attempts`` is not an int >= 1, or ``wait`` is not a finite number >= 0.
    """
    attempts, wait = settings["max_attempts"], settings["wait"]
    if isinstance(attempts, bool) or not isinstance(attempts, int) or attempts < 1:
        _refuse(f"write_max_attempts must be an integer of at least 1, got {attempts!r}")
    if isinstance(wait, bool) or not isinstance(wait, (int, float)) or not math.isfinite(wait) or wait < 0:
        _refuse(f"write_retry_wait_seconds must be a finite number of at least 0, got {wait!r}")


def _refuse(message: str) -> NoReturn:
    """Raise the one refusal type for an unusable write setting."""
    raise ValueError(message)


def begin_writes(db: Neo4jBackend, snapshot: ProjectionSnapshot) -> dict:
    """Declare the settings in force and reset this publication's write report.

    Args:
        db: Writer adapter carrying the optional write settings.
        snapshot: Snapshot whose totals bound the progress report.

    Returns:
        The settings (``row_cap``, ``payload_budget_bytes``, ``max_attempts``, ``wait``).
    """
    settings = {
        "row_cap": getattr(db, "write_row_cap", DEFAULT_ROW_CAP),
        "payload_budget_bytes": getattr(db, "write_payload_budget_bytes", DEFAULT_PAYLOAD_BUDGET),
        "max_attempts": getattr(db, "write_max_attempts", DEFAULT_MAX_ATTEMPTS),
        "wait": getattr(db, "write_retry_wait_seconds", DEFAULT_RETRY_WAIT_SECONDS),
    }
    _check_retry_settings(settings)
    db.publication_writes = {
        "row_cap": settings["row_cap"],
        "payload_budget_bytes": settings["payload_budget_bytes"],
        "oversized_records": [],
        "retried_batches": [],
    }
    db.publication_failure = None
    db.publication_progress = {
        "nodes": {"written": 0, "total": len(snapshot.nodes)},
        "relationships": {"written": 0, "total": len(snapshot.edges)},
    }
    db._write_settings = settings
    return settings


def make_plan(db: Neo4jBackend, phase: str, label: str, statement: str, rows: list[dict]) -> Plan:
    """Partition one label's rows and name every node larger than the payload budget.

    Args:
        db: Writer adapter whose write report is updated.
        phase: ``nodes`` or ``relationships``.
        label: Entity kind (nodes) or upper-case edge type (relationships).
        statement: Write statement for the batches.
        rows: Rows to write.

    Returns:
        The plan holding the bounded batches.
    """
    settings = db._write_settings
    batches = partition(rows, settings["row_cap"], settings["payload_budget_bytes"])
    if phase == "nodes":
        for batch, size in batches:
            if len(batch) == 1 and size > settings["payload_budget_bytes"]:
                record = {"id": batch[0]["canonical_id"], "label": label, "payload_bytes": size}
                db.publication_writes["oversized_records"].append(record)
                logger.warning(
                    "record %s (%s) is %d bytes, larger than the payload budget; written alone",
                    record["id"],
                    label,
                    size,
                )
    return Plan(label, statement, batches)


async def write_batches(
    db: Neo4jBackend,
    phase: str,
    plans: list[Plan],
    key: str,
    verify: Callable[[list[dict], list[dict]], None],
) -> None:
    """Write every planned batch in order, each with bounded retry, verifying its read-back.

    Args:
        db: Writer adapter.
        phase: ``nodes`` or ``relationships``.
        plans: Batches per label, in write order.
        key: Repository and generation scope key.
        verify: Check of a batch's rows against what the store returned.
    """
    total = sum(len(plan.batches) for plan in plans)
    ordinal = 0
    for plan in plans:
        for rows, size in plan.batches:
            ordinal += 1
            descriptor = {
                "phase": phase,
                "label_or_kind": plan.label,
                "ordinal": ordinal,
                "total": total,
                "rows": len(rows),
                "payload_bytes": size,
            }
            params = {"rows": rows, "key": key}
            actual = await with_retry(
                db, phase, descriptor, lambda: db._run(plan.statement, params, True)
            )
            try:
                verify(rows, actual)
            except ValueError as error:
                # a read-back failure is placed: kind, ordinal and the batch's row figures
                error.args = (
                    f"{error}; in {phase} batch {ordinal} of {total} ({plan.label}): "
                    f"expected {len(rows)} rows, found {len(actual)}",
                    *error.args[1:],
                )
                raise
            db.publication_progress[phase]["written"] += len(rows)


async def with_retry(
    db: Neo4jBackend, phase: str, descriptor: dict | None, call: Callable[[], Awaitable]
):
    """Run one write, retrying only time-limit failures, each attempt through a fresh call.

    Args:
        db: Writer adapter.
        phase: ``nodes``, ``relationships`` or ``activation``.
        descriptor: The batch being written; None for activation.
        call: Starts one attempt.

    Returns:
        The call's result.

    Raises:
        BackendUnavailable: The failure, with phase, batch and attempts stated in its message.
    """
    settings = getattr(db, "_write_settings", None) or begin_defaults(db)
    causes: list[str] = []
    while True:
        try:
            result = await call()
        except BackendUnavailable as error:
            cause = getattr(error, "cause_class", "unavailable")
            causes.append(cause)
            if cause == TIME_LIMIT and len(causes) < settings["max_attempts"]:
                logger.warning("write attempt %d hit the time limit; retrying", len(causes))
                if settings["wait"] > 0:
                    await asyncio.sleep(settings["wait"])
                continue
            report_failure(db, error, phase, descriptor, causes)
            raise
        if causes and descriptor is not None:
            db.publication_writes["retried_batches"].append(
                {
                    "batch": descriptor,
                    "attempts": len(causes) + 1,
                    "attempt_causes": causes,
                    "max_attempts": settings["max_attempts"],
                }
            )
        return result


def begin_defaults(db: Neo4jBackend) -> dict:
    """Return the write settings for a path that never began a build (activation of a ready generation)."""
    return {
        "max_attempts": getattr(db, "write_max_attempts", DEFAULT_MAX_ATTEMPTS),
        "wait": getattr(db, "write_retry_wait_seconds", DEFAULT_RETRY_WAIT_SECONDS),
    }


def report_failure(
    db: Neo4jBackend,
    error: BackendUnavailable,
    phase: str,
    descriptor: dict | None,
    causes: list[str],
) -> None:
    """Record the failure on the backend and state it in the propagated message.

    Args:
        db: Writer adapter receiving ``publication_failure``.
        error: The failure being propagated; its message gains the statement of the facts.
        phase: ``nodes``, ``relationships`` or ``activation``.
        descriptor: The batch that failed; None for activation.
        causes: The class of every failed attempt.
    """
    cause = causes[-1]
    progress = getattr(db, "publication_progress", None)
    failure: dict = {"cause": cause}
    limit = getattr(error, "time_limit_seconds", None) or getattr(db, "query_timeout", 0)
    if cause == TIME_LIMIT:
        failure["time_limit_seconds"] = limit
    failure.update(
        phase=phase,
        batch=descriptor if descriptor is not None else "not_applicable",
        attempts=len(causes),
        attempt_causes=list(causes),
        progress=progress,
    )
    db.publication_failure = failure
    text = failure_text(failure)
    logger.error("publication write failed: %s", text)
    error.args = (f"{error}; {text}", *error.args[1:])


def failure_text(failure: dict) -> str:
    """State phase, batch, attempts, limit and progress of a failed write in one sentence.

    Args:
        failure: The ``publication_failure`` report.

    Returns:
        The sentence appended to the failure message.
    """
    batch = failure["batch"]
    if batch == "not_applicable":
        where = "activation failed: no write batch was involved"
    else:
        where = (
            f"writing {batch['phase']} failed: batch {batch['ordinal']} of {batch['total']} "
            f"({batch['label_or_kind']}, {batch['rows']} rows, {batch['payload_bytes']} bytes)"
        )
    attempts = failure["attempts"]
    text = f"{where} after {attempts} attempt{'s' if attempts != 1 else ''}"
    if failure["cause"] == TIME_LIMIT:
        text += f" on the writer's time limit of {failure['time_limit_seconds']:g} seconds"
    progress = failure["progress"]
    if progress:
        nodes, links = progress["nodes"], progress["relationships"]
        text += (
            f"; {nodes['written']} of {nodes['total']} nodes and "
            f"{links['written']} of {links['total']} relationships written"
        )
    return text
