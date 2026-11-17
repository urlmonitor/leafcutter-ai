"""
MODULE: _ac_test_rationale_validators
GOAL: Hold the commit-time rules about the stated reason of a test-free requirement record
    (BO-2500a-8-i reason required, BO-2500a-8-v no copied reason) and the one entry point
    check_ac_schema calls for the whole test-contract gate.
BUSINESS CONTEXT: The done gate refuses a ``test_required: false`` record with no reason at
    mark time (BO-2500a-1-ii); these rules move that refusal to authoring time and stop one
    reason being copied across records. Only records in the change are refused; stored
    records that predate the rules are refused the first time they are themselves changed.
ARCHITECTURE: Sibling of _ac_schema_validators.py (the _ac_side_effect_validators.py
    precedent; the build copies every .py in templates/scripts/commit_guardian/). The
    reason-present test is NOT defined here: it is imported from
    scripts/ac_store/_done_proof_phase_helpers.py through _ac_store_locator, the same
    function the done gate uses. A failed import refuses the record (fail closed).
    The store view is the shared index check_ac_schema already builds (no second walk).

DOC_LINKS:
  - docs/reference/test-free-declarations.md

DECISION HISTORY:
  - 2026-10-25 [python-coder/BO-2500a-8-i, BO-2500a-8-v]: Created. Punctuation is REPLACED
    by a space, not deleted: deleting turns 'Docs-only' into 'docsonly' and a retyped copy
    would slip through.
"""

from __future__ import annotations

import re
import sys
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from _ac_schema_validators import validate_test_contract
from _ac_store_locator import ensure_ac_store_on_syspath

_PREFIX = "[check-ac-schema]"
_WHITESPACE_RE = re.compile(r"\s+")
_MAP_CACHE: dict[str, Any] = {"index": None, "map": None}


def _warn(message: str) -> None:
    """Print one WARNING line to stderr (hook diagnostics)."""
    print(f"{_PREFIX} WARNING: {message}", file=sys.stderr)


def _load_reason_predicate() -> Any:
    """Return the shared ``is_reason_present`` function, or None when it cannot be imported."""
    ensure_ac_store_on_syspath()
    try:
        from _done_proof_phase_helpers import is_reason_present
    except ImportError as exc:
        _warn(f"shared reason-present rule unavailable ({exc}); a test-free record is refused.")
        return None
    return is_reason_present


def normalise_reason(text: str) -> str:
    """Normalise a reason for comparison (BO-2500a-8-v).

    Case-folds, replaces every punctuation character (Unicode category P*) with a
    space, collapses whitespace runs to one space and trims both ends.

    Args:
        text: The raw test_rationale text.

    Returns:
        The normalised text.
    """
    spaced = "".join(" " if unicodedata.category(ch).startswith("P") else ch for ch in text.casefold())
    return _WHITESPACE_RE.sub(" ", spaced).strip()


def _duplicate_map(all_ac_data: Mapping[str, Mapping[str, Any]], present: Any) -> dict[str, list[str]]:
    """Map normalised reason -> sorted ids over every test-free record carrying a reason (cached per index)."""
    if _MAP_CACHE["index"] is all_ac_data:
        return _MAP_CACHE["map"]
    groups: dict[str, list[str]] = {}
    for ac_id, rec in all_ac_data.items():
        if rec.get("test_required") is False and present(rec.get("test_rationale")):
            groups.setdefault(normalise_reason(rec["test_rationale"]), []).append(str(ac_id))
    result = {key: sorted(ids) for key, ids in groups.items()}
    _MAP_CACHE.update(index=all_ac_data, map=result)
    return result


def reason_rule_errors(
    path: Path, data: Mapping[str, Any], all_ac_data: Mapping[str, Mapping[str, Any]] | None
) -> list[str]:
    """Refuse a ``test_required: false`` record with no reason or a copied reason.

    Args:
        path: The record's file (for messages).
        data: The parsed staged record.
        all_ac_data: The store index; ``None`` or empty means it could not be read.

    Returns:
        Refusal messages; empty for records with ``test_required`` true or absent.
    """
    if data.get("test_required") is not False:
        return []
    ac_id = str(data.get("id", path.stem))
    present = _load_reason_predicate()
    if present is None:
        return [
            f"{path}: record {ac_id} test_rationale could not be checked - the done-gate helper "
            f"(_done_proof_phase_helpers.is_reason_present) could not be loaded, so the test-free "
            f"declaration is refused"
        ]
    if not present(data.get("test_rationale")):
        return [
            f"{path}: record {ac_id} sets test_required: false but its test_rationale is "
            f"missing or blank - a test-free declaration needs a stated reason"
        ]
    if not all_ac_data:
        _warn("store index unreadable; cannot confirm the reason is unique.")
        return [
            f"{path}: record {ac_id} test_rationale: uniqueness could not be confirmed "
            f"(the store index could not be read), so the test-free declaration is refused"
        ]
    others = [i for i in _duplicate_map(all_ac_data, present).get(normalise_reason(data["test_rationale"]), [])
              if i != ac_id]
    if not others:
        return []
    return [
        f"{path}: record {ac_id} test_rationale is identical to the test_rationale of "
        f"{', '.join(others)} once normalised - a test-free declaration needs its own stated reason"
    ]


def contract_and_reason_errors(
    path: Path,
    data: dict[str, Any],
    all_ac_data: Mapping[str, Mapping[str, Any]] | None,
    *,
    retired: bool = False,
) -> list[str]:
    """Run the whole test-contract gate: the older contract rules plus the reason rules.

    Args:
        path: The record's file.
        data: The parsed staged record.
        all_ac_data: The store index (None when unavailable).
        retired: Whether the record is retired (exempt from the contract requirement only).

    Returns:
        All refusal messages for the record's test declaration.
    """
    return [
        *validate_test_contract(path, data, retired=retired),
        *reason_rule_errors(path, data, all_ac_data),
    ]
