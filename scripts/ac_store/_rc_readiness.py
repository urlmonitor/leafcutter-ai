"""
MODULE: _rc_readiness
GOAL: Rule family "readiness never raised to approved by an authoring agent": a record
    that ends an authoring stage `approved` but was not `approved` at stage start is
    restored to its before-stage value.
BUSINESS CONTEXT: ACD-2500a-2-iv / ACD-400c. A requirement joins the buildable queue only
    once a person has approved it. The user-run approval step is exempt by STAGE IDENTITY
    (`--stage approval`), never by inspecting readiness values.
ARCHITECTURE: Pure `evaluate_record`. The before-state is `ctx.before_state(record)` ->
    (existed, readiness), supplied by the workflow (snapshot or git ref), never by the
    stage agent. A record absent from the before-state is restored to the authoring
    default `draft` and reported with its before-state stated as absent. The repair is
    `repair=("readiness", ("set", value))`.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-2-iv]: Created (ticket 13).
"""

from __future__ import annotations

from typing import Any

from _rc_report import DISPOSITION_FIXED, FAMILY_READINESS, Finding

NAME = FAMILY_READINESS
_APPROVED = "approved"
_DEFAULT = "draft"
_APPROVAL_STAGE = "approval"


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """Restore an agent-raised `approved`; the approval stage and unchanged records pass."""
    if ctx.stage == _APPROVAL_STAGE or record.get("readiness") != _APPROVED:
        return []
    existed, before = ctx.before_state(record)
    if before == _APPROVED:
        return []
    if existed and before is not None:
        restored, state = before, f"before-state {before!r}"
    elif existed:
        restored, state = _DEFAULT, "before-state had no readiness"
    else:
        restored, state = _DEFAULT, "before-state absent: record created during the stage"
    message = f"readiness was raised to {_APPROVED!r} by an authoring agent; restored to {restored!r} ({state})"
    return [
        Finding.for_record(
            record, NAME, DISPOSITION_FIXED, message,
            subject="readiness", repair=("readiness", ("set", restored)),
        )
    ]
