"""
MODULE: _rc_backlinks
GOAL: Rule family "parent-to-child back-links": every child record id appears in its
    parent's `covered_by`; a missing back-link is appended, a missing parent is reported.
BUSINESS CONTEXT: ACD-2500a-2-i. The business analyst adds a child and forgets to list
    it in the parent. There is exactly one correct repair, so the check makes it; a child
    whose parent record does not exist is a decision for a person, never a record the
    check invents.
ARCHITECTURE: Pure `evaluate_record(ctx, record)`. The parent id comes from
    `ac_parent_id.derive_parent_id`; the parent is looked up ONLY in the checked folder
    (`ctx.sibling`). A present parent that lacks the child yields a `fixed` finding that
    lands on the PARENT (its file and id) with `repair=("covered_by", ("append", child))`;
    the subject is the child id so several missing children of one parent stay distinct
    findings. An absent parent yields `needs a decision` on the child. Deployed flat.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-2-i]: Created (ticket 10).
"""

from __future__ import annotations

from typing import Any

from _rc_report import DISPOSITION_DECISION, DISPOSITION_FIXED, FAMILY_BACKLINKS, Finding
from ac_parent_id import derive_parent_id

NAME = FAMILY_BACKLINKS


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """Check `record`'s back-link in its parent; repair it when the parent is present."""
    child_id = str(record["id"])
    parent_id = derive_parent_id(child_id)
    if parent_id is None:
        return []
    parent = ctx.sibling(parent_id)
    if parent is None:
        message = (
            f"{child_id} has derived parent {parent_id}, but no record {parent_id} exists in the "
            "checked folder; the check does not create records"
        )
        return [Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject="parent")]
    covered = parent.get("covered_by")
    if covered is None:
        covered = []
    if not isinstance(covered, list):
        message = f"covered_by of {parent_id} is not a list, so the back-link to {child_id} cannot be appended"
        return [Finding.for_record(parent, NAME, DISPOSITION_DECISION, message, subject=child_id)]
    if child_id in covered:
        return []
    message = f"appended {child_id} to covered_by of {parent_id} ({parent.file})"
    return [
        Finding.for_record(
            parent, NAME, DISPOSITION_FIXED, message,
            subject=child_id, repair=("covered_by", ("append", child_id)),
        )
    ]
