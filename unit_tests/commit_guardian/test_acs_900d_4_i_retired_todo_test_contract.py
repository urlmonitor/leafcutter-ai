"""
MODULE: unit_tests/commit_guardian/test_acs_900d_4_i_retired_todo_test_contract.py
GOAL: RED tests for ACS-900d-4-i -- a record retired at work_status todo is not
    asked for a test contract, while an active twin still is.

Every test runs the REAL check_ac_schema.py (source copy under
templates/scripts/commit_guardian/) as a subprocess in a throwaway git repo with
the records staged. The successor (AR-400c-1) sits in the base commit, NOT in the
staged set, so the hook must resolve it from the whole store.

Named wrong versions caught: validate_test_contract skips every todo record;
validate_test_contract skips any record that merely has a superseded_by key; the
contradiction check (test_spec together with test_required false) being waived
for retired records.

DECISION HISTORY
- 2026-10-15 [test-writer/ACS-900d-4-i]: Initial RED authoring.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _acs_900d_4_fixtures as fx  # noqa: E402

RETIRED_ID = "RT-100a-1-i"
ACTIVE_ID = "RT-100a-2-i"


def _run_schema(tmp_path: Path, name: str, record: dict):
    """Stage *record* over a base store holding the successor; run the schema hook."""
    repo = fx.make_repo(tmp_path / name)
    staged = fx.stage_scenario(repo, [record])
    return staged[0], fx.schema_hook(repo)


def _retired_todo(ac_id: str = RETIRED_ID, **overrides) -> dict:
    return fx.retired_record(ac_id, level="L3", work_status="todo", **overrides)


def test_retired_todo_approved_code_ac_not_asked_for_test_contract(tmp_path: Path) -> None:
    # covers: ACS-900d-4-i
    # angle: criterion
    """A staged retired L3 record (todo, approved, code, no test_spec) is not refused.

    Fails today because validate_test_contract ignores status superseded_by.
    """
    _, proc = _run_schema(tmp_path, "retired", _retired_todo())
    text = fx.out(proc)

    assert fx.TEST_CONTRACT_REFUSAL not in text, f"retired record asked for a test contract: {text!r}"
    assert proc.returncode == 0, f"schema gate refused the retired record (exit {proc.returncode}): {text!r}"


def test_retired_record_readiness_and_change_target_untouched(tmp_path: Path) -> None:
    # covers: ACS-900d-4-i
    # angle: criterion
    """The record passes as authored: readiness approved, change_target code, bytes unchanged."""
    record = _retired_todo()
    path, proc = _run_schema(tmp_path, "untouched", record)
    after = path.read_bytes()

    assert proc.returncode == 0, f"retired record only passes by being edited or refused: {fx.out(proc)!r}"
    reread = yaml.safe_load(after)
    assert reread["readiness"] == "approved" and reread["change_target"] == "code", reread
    assert "test_spec" not in reread and "test_required" not in reread, reread
    expected = yaml.safe_dump(record, sort_keys=False, allow_unicode=True).encode("utf-8")
    assert after == expected, "the hook rewrote the staged record"


def test_active_twin_refused_for_missing_test_contract(tmp_path: Path) -> None:
    # covers: ACS-900d-4-i
    # angle: discrimination
    """The same record with status active and superseded_by null is still refused.

    Wrong versions caught: skipping every todo record; skipping any record that has
    a superseded_by key (the twin carries the key, set to null).
    """
    twin = fx.active_twin(_retired_todo(ACTIVE_ID))
    assert twin["superseded_by"] is None and "superseded_by" in twin
    path, proc = _run_schema(tmp_path, "twin", twin)
    text = fx.out(proc)

    assert proc.returncode != 0, f"active twin was not refused: {text!r}"
    assert fx.TEST_CONTRACT_REFUSAL in text, f"refusal reason missing: {text!r}"
    assert fx.lines_naming(proc, ACTIVE_ID, fx.TEST_CONTRACT_REFUSAL), f"refusal does not name {ACTIVE_ID}: {text!r}"


def test_retired_record_with_contradictory_test_contract_still_refused(tmp_path: Path) -> None:
    # covers: ACS-900d-4-i
    # angle: boundary
    """A retired record with BOTH a non-empty test_spec and test_required false is refused.

    Control row: the same retired record with only a test_spec passes, so the refusal
    below comes from the contradiction and nothing else.
    """
    _, control = _run_schema(
        tmp_path, "contract_only", fx.with_test_contract(_retired_todo())
    )
    assert control.returncode == 0, f"retired record with a valid contract refused: {fx.out(control)!r}"

    contradictory = fx.with_test_contract(_retired_todo(), required_false=True)
    _, proc = _run_schema(tmp_path, "contradiction", contradictory)
    text = fx.out(proc)

    assert proc.returncode != 0, f"contradictory retired record passed: {text!r}"
    assert "test_spec lists" in text and "test_required is false" in text, text
    assert fx.TEST_CONTRACT_REFUSAL not in text, "the contradiction must not be reported as a missing contract"
