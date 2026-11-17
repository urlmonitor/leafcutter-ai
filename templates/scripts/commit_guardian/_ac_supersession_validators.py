"""
MODULE: scripts/commit_guardian/_ac_supersession_validators.py
GOAL: Hold check_ac_schema.py's two supersession rules: the STRUCTURAL refusals
    for a record that claims to be superseded, and the retired-record lookup
    that lets validate_test_contract skip the forward test-contract rule.
BUSINESS CONTEXT: ACS-900d-4-i/-ii/-iii. A superseded record that names
    existing successors is retired and is no longer asked for a test contract
    (scripts/ac_store/ac_retirement.py owns that predicate). The exemption
    would be a phantom-done route if ``superseded_by: [anything]`` earned it,
    so retirement does not excuse structure: a superseded record must name at
    least one successor, every successor must exist in the WHOLE store, and a
    record cannot supersede itself. Each of those refusals leaves the predicate
    answering "not retired", so the done-proof gate also reports the missing
    covering test in the same run.
ARCHITECTURE: Sibling of check_ac_schema.py (deploys with the directory). The
    structural rules are self-contained: they need no ac_store module, so a
    broken ac_store layout cannot silence them. ``is_retired_record`` reaches
    ``ac_retirement`` through ``_ac_store_locator.ensure_ac_store_on_syspath``
    and looks ``is_retired`` up on the module at call time; when the module is
    missing it answers "not retired" with a stderr WARNING, so the forward rule
    applies (fail closed). ``all_ac_data`` is the AC-id -> record mapping
    check_ac_schema already builds once per run (the shared store index); only
    its keys are read here.

DECISION HISTORY:
  - 2026-10-15 [python-coder/ACS-900d-4]: Created. The existence check uses the
    index's keys (record ids from content), the same id set the retired
    predicate is given, so the two cannot disagree about what exists.
    (#TICKETLESS reason=acs-900d-4-ac-driven-no-ticket-file)
"""
from __future__ import annotations

import sys
from collections.abc import Container, Mapping
from pathlib import Path
from typing import Any

from _ac_store_locator import ensure_ac_store_on_syspath

_SUPERSEDED_STATUSES = frozenset({"superseded_by", "superseded"})


def is_retired_record(data: Mapping[str, Any], all_ac_data: Container[str] | None) -> bool:
    """Return whether *data* is a retired record, judged against the whole store.

    Args:
        data: Parsed AC YAML content.
        all_ac_data: Mapping (or set) of every AC id in the store, or ``None``
            when the store view is unavailable.

    Returns:
        ``True`` only when ``ac_retirement.is_retired`` says so. ``False`` when
        there is no store view or the predicate module cannot be imported
        (fail closed: the forward rule applies).
    """
    if not all_ac_data or data.get("status") not in _SUPERSEDED_STATUSES:
        return False
    ensure_ac_store_on_syspath()
    try:
        import ac_retirement
    except ImportError as exc:
        print(
            f"[check-ac-schema] WARNING: ac_retirement unavailable ({exc}); "
            "the superseded record is not treated as retired.",
            file=sys.stderr,
        )
        return False
    return ac_retirement.is_retired(data, all_ac_data)


def _successors(data: Mapping[str, Any]) -> list[str]:
    """Return the trimmed ``superseded_by`` entries (scalar or list form); blanks kept as ``""``."""
    raw = data.get("superseded_by")
    items: list[Any] = []
    if isinstance(raw, str):
        items = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    return ["" if i is None else str(i).strip() for i in items]


def supersession_errors(
    path: Path, data: Mapping[str, Any], all_ac_data: Container[str] | None
) -> list[str]:
    """Return the structural refusals for a record whose status says it is superseded.

    Applies to status ``superseded_by`` and ``superseded``. A record in any
    other status is not judged here.

    Args:
        path: The AC file (for the message).
        data: Parsed AC YAML content.
        all_ac_data: Every AC id in the whole store (keys are read), or ``None``
            to skip the existence check when no store view is available.

    Returns:
        One message per defect: no successor at all, the record naming itself,
        a blank entry, or a successor that is not in the store. Empty when the
        supersession is structurally sound.
    """
    if data.get("status") not in _SUPERSEDED_STATUSES:
        return []
    record_id = str(data.get("id") or "?").strip()
    entries = _successors(data)
    successors = [s for s in entries if s]
    if not successors:
        return [
            f"{path}: superseded record {record_id} must name at least one successor — "
            "set superseded_by to the existing record(s) that replace it"
        ]
    errors: list[str] = []
    if len(successors) != len(entries):
        errors.append(f"{path}: superseded record {record_id} lists a blank successor in superseded_by")
    if record_id in successors:
        errors.append(
            f"{path}: record {record_id} cannot supersede itself — remove {record_id} from superseded_by"
        )
    for successor in successors:
        if successor != record_id and all_ac_data is not None and successor not in all_ac_data:
            errors.append(
                f"{path}: superseded record {record_id} names successor {successor}, "
                "which does not exist in the AC store"
            )
    return errors
