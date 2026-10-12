"""
MODULE: scripts/ac_store/_impl_readiness_gate.py
GOAL: Flag an AC NOT implementation-ready when it lacks file targets or a test
    contract (or carries another hold reason), and decide whether the flag
    holds the AC back from dispatch to a coder.
BUSINESS CONTEXT: ACD-1600c-1 / ACD-1600c-1-i. An AC released to a builder
    without declared files or a test contract forces the coder to guess its
    file scope. This gate checks enrichment COMPLETENESS, complementary to the
    approval-readiness gate (ACD-1200b) that checks readiness status. ADR-026
    rules 3-4: advisory first -- a record reading as schema_version < 2 is
    REPORTED with its reason but not held back unless enforce is on.
ARCHITECTURE: Pure functions. ``HOLD_REASONS`` is the store's single
    hold-reason list (mirrored in docs/reference/ac-readiness-and-assignment-gates.md); ACD-2500b-2
    extends it in place and every gate that emits a hold reason reads it, so
    this module never keeps a gate-local list. File targets are read ONLY
    through ``declared_files.get_declared_files`` (ACD-1600c-4) -- never
    parsed here and never derived from it_requirements, doc_links or
    reference_file_path. A reason carried on the record in ``hold_reason``
    (set by another gate) is reported under its own name, unchanged.
    Re-exported by scan_ac_store.py, which owns the CLI wiring; deployed flat
    beside it (AC_STORE_DEPLOY_MAP).

DECISION HISTORY:
  - 2026-10-12 [python-coder/ACD-1600c-1]: Created, outside scan_ac_store.py
    (already over the file-size ratchet). The record-level field that carries
    another gate's reason is named ``hold_reason`` (ACD-2500b-2 defines only
    the approval-report key ``reason``, no record field). ACD-2500b-2's
    ``held`` approval report is a separate shape and is not produced here.
"""

from __future__ import annotations

from typing import Any

from declared_files import NoDeclaredFiles, get_declared_files

HOLD_REASON_MISSING_FILE_TARGETS = "missing file targets"
HOLD_REASON_MISSING_TEST_CONTRACT = "missing test contract"

HOLD_REASONS: tuple[str, ...] = (
    HOLD_REASON_MISSING_FILE_TARGETS,
    HOLD_REASON_MISSING_TEST_CONTRACT,
    "test design pending",
    "reference file pending",
    "file finding undecided",
)

_HELD_SCHEMA_VERSION = 2

__all__ = [
    "HOLD_REASONS", "HOLD_REASON_MISSING_FILE_TARGETS", "HOLD_REASON_MISSING_TEST_CONTRACT",
    "implementation_readiness_reasons", "is_held_back", "partition_by_readiness",
]


def _has_test_contract(ac: dict[str, Any]) -> bool:
    """Return True when *ac* has a non-empty test_spec or ``test_required: false``."""
    spec = ac.get("test_spec")
    if isinstance(spec, list) and spec:
        return True
    return ac.get("test_required") is False


def implementation_readiness_reasons(ac: dict[str, Any]) -> list[str]:
    """List why *ac* is NOT implementation-ready (empty when it is ready).

    Order: ``missing file targets``, ``missing test contract``, then the
    record's own ``hold_reason`` value (when set), reported unchanged and
    never folded into one of the two owned reasons.

    Args:
        ac: Parsed AC record.

    Returns:
        Reasons, each a value of ``HOLD_REASONS`` (or the record's own value).
    """
    reasons: list[str] = []
    if isinstance(get_declared_files(ac), NoDeclaredFiles):
        reasons.append(HOLD_REASON_MISSING_FILE_TARGETS)
    if not _has_test_contract(ac):
        reasons.append(HOLD_REASON_MISSING_TEST_CONTRACT)
    other = ac.get("hold_reason")
    if isinstance(other, str) and other and other not in reasons:
        reasons.append(other)
    return reasons


def _schema_version(ac: dict[str, Any]) -> int:
    """Return the record's schema_version as int; absent or invalid reads as 1."""
    try:
        return int(ac.get("schema_version", 1))
    except (TypeError, ValueError):
        return 1


def is_held_back(ac: dict[str, Any], *, enforce: bool = False) -> bool:
    """Return True when *ac* is flagged AND the flag holds it back from dispatch.

    Held iff reasons are non-empty and (enforce is on OR schema_version >= 2).
    A schema_version < 2 record is reported but dispatchable in advisory mode.
    """
    if not implementation_readiness_reasons(ac):
        return False
    return enforce or _schema_version(ac) >= _HELD_SCHEMA_VERSION


def partition_by_readiness(
    ready: list[dict[str, Any]], *, enforce: bool = False
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split *ready* into the dispatch set and the not-implementation-ready report.

    Args:
        ready: Dependency-ready AC records, already sorted.
        enforce: ADR-026 enforce flag (default off = advisory).

    Returns:
        ``(dispatchable, report)``; ``dispatchable`` keeps input order and
        omits held-back ACs; ``report`` lists every flagged AC (held or not)
        as ``{"ac_id", "reasons", "held_back"}``.
    """
    dispatchable: list[dict[str, Any]] = []
    report: list[dict[str, Any]] = []
    for ac in ready:
        reasons = implementation_readiness_reasons(ac)
        held = bool(reasons) and is_held_back(ac, enforce=enforce)
        if reasons:
            report.append({"ac_id": ac.get("id", ""), "reasons": reasons, "held_back": held})
        if not held:
            dispatchable.append(ac)
    return dispatchable, report
