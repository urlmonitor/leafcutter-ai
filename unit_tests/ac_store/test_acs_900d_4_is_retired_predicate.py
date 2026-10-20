"""
MODULE: unit_tests/ac_store/test_acs_900d_4_is_retired_predicate.py
GOAL: RED unit tests for the ONE shared "is this record retired" predicate,
    ``is_retired(record, store_ids) -> bool`` in scripts/ac_store/ac_retirement.py
    (ACS-900d-4).

A record is retired when, and only when: status is 'superseded_by' or 'superseded';
AND superseded_by (a string or a list) is non-empty; AND every successor id is in the
whole-store id set; AND no successor equals the record's own id. 'deprecated' is never
retired; req_status is not an input. The predicate is pure: the caller supplies the
record and the id set.

The module is loaded from its file path in this process (no sys.path edit, no package
that could shadow scripts/ac_store), so a missing file fails as an ImportError naming it.

DECISION HISTORY
- 2026-10-15 [test-writer/ACS-900d-4]: Initial RED authoring.
"""
from __future__ import annotations

import importlib.util
import itertools
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "ac_store" / "ac_retirement.py"
STORE = {"AR-400c-1", "AR-400c-2", "RT-1"}


def _load_is_retired():
    if not MODULE_PATH.is_file():
        msg = f"scripts/ac_store/ac_retirement.py does not exist ({MODULE_PATH})"
        raise ImportError(msg)
    spec = importlib.util.spec_from_file_location("acs_900d_4_ac_retirement_under_test", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.is_retired


def _record(status: str, superseded_by, **extra) -> dict:
    return {"id": "RT-1", "status": status, "superseded_by": superseded_by, **extra}


def test_is_retired_accepts_both_status_spellings_and_successor_forms() -> None:
    # covers: ACS-900d-4
    # angle: boundary
    """True for both superseded spellings x string/list successors when all exist; False for active/deprecated.

    req_status is ignored: the same retired record stays retired under any req_status, and an
    active record never becomes retired because its req_status says superseded.
    """
    is_retired = _load_is_retired()
    forms = ("AR-400c-1", ["AR-400c-1"], ["AR-400c-1", "AR-400c-2"])

    for status, successors in itertools.product(("superseded_by", "superseded"), forms):
        assert is_retired(_record(status, successors), STORE) is True, (status, successors)
    for req_status in ("draft", "active", "superseded"):
        record = _record("superseded_by", ["AR-400c-1"], req_status=req_status)
        assert is_retired(record, STORE) is True, f"req_status {req_status!r} changed the verdict"
    for status in ("active", "deprecated"):
        assert is_retired(_record(status, ["AR-400c-1"]), STORE) is False, status
    assert is_retired(_record("active", ["AR-400c-1"], req_status="superseded"), STORE) is False


def test_is_retired_is_false_for_structurally_invalid_supersession() -> None:
    # covers: ACS-900d-4
    # covers: ACS-900d-4-ii
    # covers: ACS-900d-4-iii
    # angle: discrimination
    """Empty/null successors, a successor missing from the store, and self-supersession are NOT retired.

    Wrong versions caught: 'any non-empty superseded_by is retired' (missing successor);
    'every successor exists' as the only test (the record itself exists, so a self id passes).
    Control: the same record with a valid, existing successor is retired.
    """
    is_retired = _load_is_retired()

    assert is_retired(_record("superseded_by", ["AR-400c-1"]), STORE) is True
    for bad in ([], None, "", ["ZZ-999"], ["AR-400c-1", "ZZ-999"], ["RT-1"], ["RT-1", "AR-400c-1"], "RT-1"):
        assert is_retired(_record("superseded_by", bad), STORE) is False, bad
    assert is_retired(_record("superseded_by", ["AR-400c-1"]), set()) is False
    assert is_retired({"id": "RT-1", "status": "superseded_by"}, STORE) is False
