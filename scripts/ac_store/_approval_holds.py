"""
MODULE: _approval_holds
GOAL: Decide whether a reviewed leaf record is held back from approval, and shape the approval
    report the approval step prints.
BUSINESS CONTEXT: ACD-2500b-2 (ADR-071). A requirement that carries test intent but no test design
    must not be approved: approval would release it to a builder with nothing to test against.
    The approval step (approve_acs.py) asks this module and never promotes a held record.
ARCHITECTURE: Pure functions, no I/O. ``APPROVAL_HOLD_CHECKS`` is the tuple of checks (each
    ``record -> reason | None``) that later gates append to; ``approval_hold_reason`` returns the
    first reason found. Every reason must be a member of ``HOLD_REASONS`` (the store's one closed
    vocabulary, _impl_readiness_gate.py), so a check that invents a reason is a defect and raises.
    The test-design check is "design pending, or a needs_test clause no test_spec entry links to
    through the per-entry clause key" (_test_intent). Not deployed: approve_acs.py is not either.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from _impl_readiness_gate import HOLD_REASON_TEST_DESIGN_PENDING, HOLD_REASONS
from _test_intent import design_pending, uncovered_needs_test_clauses


def _test_design_hold(record: dict[str, Any]) -> str | None:
    """Return ``test design pending`` when the intent has no design or an uncovered clause."""
    if design_pending(record) or uncovered_needs_test_clauses(record):
        return HOLD_REASON_TEST_DESIGN_PENDING
    return None


APPROVAL_HOLD_CHECKS: tuple[Callable[[dict[str, Any]], str | None], ...] = (_test_design_hold,)


def approval_hold_reason(record: dict[str, Any]) -> str | None:
    """Return the reason *record* must not be approved, or ``None`` when it may be.

    Raises:
        ValueError: A check returned a reason outside ``HOLD_REASONS``.
    """
    for check in APPROVAL_HOLD_CHECKS:
        reason = check(record)
        if reason is None:
            continue
        if reason not in HOLD_REASONS:
            raise ValueError(f"approval hold reason {reason!r} is not in HOLD_REASONS")
        return reason
    return None


def build_report(approved: list[str], held: list[dict[str, str]]) -> dict[str, Any]:
    """Return the approval report: ``{"approved": [id], "held": [{id, file, reason}]}``."""
    return {"approved": approved, "held": held}
