"""MODULE: neo4j_retention_assessment
GOAL: Describe how much of a retention evaluation the backend allowed, naming every refusal.
BUSINESS CONTEXT: An evaluation that could not read the store must never read as a store with nothing to reclaim.
ARCHITECTURE: Pure report-shaping helpers used by neo4j_retention; no I/O, no backend access.

DECISION HISTORY
========================================
- 2026-10-15 02:00 [python-coder]: Report refusals as an assessment outcome (assessed, partial, could_not_assess) with undetermined figures and a read-only consequence, never as an empty result. (#KM-400f-1-vi)
"""

from __future__ import annotations

UNDETERMINED = "undetermined"
RECORDS_PART = "generation_records"
COUNTS_PART = "entity_node_counts"
_READ_ONLY_MARKERS = ("read-only", "readonly", "read only")
_READ_ONLY_DETAIL = (
    "the backend has latched read-only and refuses changes; reclaiming space is blocked "
    "while it holds, and this is not an absence of generations"
)


def refusal(part: str, exc: Exception) -> dict:
    """Record one refused request, keeping the backend's own text.

    Args:
        part: Which part of the assessment the refused request served.
        exc: The refusal the backend raised.

    Returns:
        Mapping with ``part`` and ``message``.
    """
    return {"part": part, "message": str(exc)}


def assessment(refusals: list[dict]) -> dict:
    """State which part of the assessment succeeded and which could not be completed.

    Args:
        refusals: Every refusal received, in order.

    Returns:
        Mapping with ``status``, ``refusals``, ``succeeded`` and ``could_not_complete``.
    """
    refused = [r["part"] for r in refusals]
    parts = (RECORDS_PART, COUNTS_PART)
    if RECORDS_PART in refused:
        status = "could_not_assess"
        succeeded: list[str] = []
        failed = [RECORDS_PART]
    else:
        succeeded = [p for p in parts if p not in refused]
        failed = [p for p in parts if p in refused]
        status = "partial" if failed else "assessed"
    return {"status": status, "refusals": refusals, "succeeded": succeeded, "could_not_complete": failed}


def read_only_condition(refusals: list[dict]) -> dict | None:
    """Report a read-only latch, with its consequence, when any refusal names one.

    Args:
        refusals: Every refusal received.

    Returns:
        ``{"latched", "reclaim_blocked", "detail"}``, or None when no refusal is a read-only latch.
    """
    for item in refusals:
        if any(marker in item["message"].lower() for marker in _READ_ONLY_MARKERS):
            return {"latched": True, "reclaim_blocked": True, "detail": _READ_ONLY_DETAIL}
    return None


def could_not_assess_report(bound_dump: dict, refusals: list[dict]) -> dict:
    """Build the report for an evaluation that could not read the generation records.

    Args:
        bound_dump: The declared bound, as a mapping.
        refusals: Every refusal received.

    Returns:
        A report whose figures are ``"undetermined"``, never 0 or an empty reclaimable set.
    """
    return {
        "unaccounted_nodes": UNDETERMINED,
        "unaccounted_generation_keys": UNDETERMINED,
        "bound": bound_dump,
        "assessed": UNDETERMINED,
        "active_generation": UNDETERMINED,
        "findings": ["the generation population could not be assessed; no verdict was made"],
        "generations": [],
        "reclaimable": UNDETERMINED,
        "reclaimable_by_basis": UNDETERMINED,
        "assessment": assessment(refusals),
        **_read_only_field(refusals),
    }


def _read_only_field(refusals: list[dict]) -> dict:
    """Return the ``read_only`` entry when a latch is reported, else nothing.

    Args:
        refusals: Every refusal received.

    Returns:
        ``{"read_only": ...}`` or an empty mapping.
    """
    condition = read_only_condition(refusals)
    return {"read_only": condition} if condition else {}


def with_assessment(report: dict, refusals: list[dict]) -> dict:
    """Attach the assessment (and any read-only condition) to a report.

    Args:
        report: A report built from the generation records.
        refusals: Every refusal received.

    Returns:
        The report with ``assessment`` and, when latched, ``read_only``.
    """
    return {**report, "assessment": assessment(refusals), **_read_only_field(refusals)}
