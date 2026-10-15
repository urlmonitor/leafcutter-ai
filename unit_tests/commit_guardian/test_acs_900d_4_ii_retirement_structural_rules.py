"""
MODULE: unit_tests/commit_guardian/test_acs_900d_4_ii_retirement_structural_rules.py
GOAL: RED tests for ACS-900d-4-ii -- retirement does not exempt a record from the
    STRUCTURAL rules: successor existence (against the WHOLE store), a non-empty
    successor list, the parent covered_by link, and the work_status shape.

This is the anti-gaming guard: without it, "superseded_by: [anything]" would silently
dodge done-proof. Every scenario runs the real hooks (check_ac_schema.py,
check_done_proof.py, check_ac_parent_covered_by.py from templates/scripts/commit_guardian/,
and scripts/ac_store/validate_ac_schema.py) as subprocesses against a throwaway git repo.

Named wrong version caught: the predicate counts any non-empty superseded_by as retired
without checking that the successor exists.

Not covered here (no named test in the AC's test_spec): reconciling the 'superseded'
status spelling in _ac_schema_validators.VALID_STATUSES and validate_ac_schema._STATUS_VALUES
(it_requirements); it is exercised at the predicate level in the ac_store unit test.

DECISION HISTORY
- 2026-10-15 [test-writer/ACS-900d-4-ii]: Initial RED authoring.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _acs_900d_4_fixtures as fx  # noqa: E402

RECORD_ID = "RT-100a-1"
TWIN_ID = "RT-100a-2"
PARENT_ID = "RT-100a"
AT_LEAST_ONE = "must name at least one successor"


def _stage(tmp_path: Path, name: str, record: dict, base_extra: list[dict] = ()) -> Path:
    repo = fx.make_repo(tmp_path / name)
    fx.stage_scenario(repo, [record], base_extra=list(base_extra))
    return repo


def test_missing_successor_refused_naming_record_and_successor(tmp_path: Path) -> None:
    # covers: ACS-900d-4-ii
    # angle: criterion
    """superseded_by [ZZ-999] with ZZ-999 absent from the store is refused, naming both ids."""
    repo = _stage(tmp_path, "missing", fx.retired_record(RECORD_ID, successors=[fx.MISSING_SUCCESSOR]))
    proc = fx.schema_hook(repo)

    assert proc.returncode != 0, f"record naming a nonexistent successor passed: {fx.out(proc)!r}"
    assert fx.lines_naming(proc, RECORD_ID, fx.MISSING_SUCCESSOR), (
        f"no refusal line names both {RECORD_ID} and {fx.MISSING_SUCCESSOR}: {fx.out(proc)!r}"
    )


def test_missing_successor_record_not_retired_done_proof_reports_missing_cover(tmp_path: Path) -> None:
    # covers: ACS-900d-4-ii
    # angle: discrimination
    """In the same staged set, done-proof still reports the missing covering test.

    Wrong version caught: the predicate counts any non-empty superseded_by as retired
    without checking the successor exists (done-proof would then skip the record).
    """
    repo = _stage(tmp_path, "missing_dp", fx.retired_record(RECORD_ID, successors=[fx.MISSING_SUCCESSOR]))
    proc = fx.done_proof(repo)
    refusals = fx.done_proof_refusals(proc)

    assert proc.returncode != 0, f"record with a nonexistent successor was treated as retired: {fx.out(proc)!r}"
    assert RECORD_ID in refusals and f"covers: {RECORD_ID}" in refusals[RECORD_ID], fx.out(proc)


def test_empty_successor_list_refused(tmp_path: Path) -> None:
    # covers: ACS-900d-4-ii
    # angle: boundary
    """status superseded_by with superseded_by [] is refused: a superseded record must name a successor."""
    repo = _stage(tmp_path, "empty", fx.retired_record(RECORD_ID, successors=[]))
    proc = fx.schema_hook(repo)

    assert proc.returncode != 0, f"empty successor list passed: {fx.out(proc)!r}"
    assert fx.lines_naming(proc, RECORD_ID, AT_LEAST_ONE), (
        f"no refusal line names {RECORD_ID} and says {AT_LEAST_ONE!r}: {fx.out(proc)!r}"
    )


def test_null_successor_refused(tmp_path: Path) -> None:
    # covers: ACS-900d-4-ii
    # angle: boundary
    """status superseded_by with superseded_by null gets the same at-least-one-successor refusal."""
    record = fx.ac_record(RECORD_ID, status="superseded_by", superseded_by=None)
    repo = _stage(tmp_path, "null", record)
    proc = fx.schema_hook(repo)

    assert proc.returncode != 0, f"null successor passed: {fx.out(proc)!r}"
    assert fx.lines_naming(proc, RECORD_ID, AT_LEAST_ONE), (
        f"no refusal line names {RECORD_ID} and says {AT_LEAST_ONE!r}: {fx.out(proc)!r}"
    )


def test_successor_resolved_against_whole_store_not_staged_set(tmp_path: Path) -> None:
    # covers: ACS-900d-4-ii
    # angle: boundary
    """A successor in the committed store (not staged) resolves; a twin naming ZZ-999 does not.

    The control run proves the existence check is live in this very fixture: without it
    the clean pass below would be indistinguishable from a hook that checks nothing.
    """
    repo = _stage(tmp_path, "resolves", fx.retired_record(RECORD_ID))
    proc = fx.schema_hook(repo)
    assert proc.returncode == 0, f"existing, unstaged successor was not resolved: {fx.out(proc)!r}"
    assert not fx.lines_naming(proc, fx.SUCCESSOR), fx.out(proc)

    control_repo = _stage(
        tmp_path, "control", fx.retired_record(RECORD_ID, successors=[fx.MISSING_SUCCESSOR])
    )
    control = fx.schema_hook(control_repo)
    assert control.returncode != 0 and fx.lines_naming(control, RECORD_ID, fx.MISSING_SUCCESSOR), (
        f"control: a nonexistent successor must be refused in the same fixture: {fx.out(control)!r}"
    )


def _parent_with(covered_by: list[str]) -> dict:
    return fx.ac_record(PARENT_ID, level="L1", work_status="todo", covered_by=covered_by)


def _parent_message(proc, child_id: str) -> str:
    lines = [ln.strip() for ln in fx.out(proc).splitlines() if f"does not include '{child_id}'" in ln]
    return lines[0].replace(child_id, "<CHILD>") if lines else ""


def test_retired_child_missing_from_parent_covered_by_refused(tmp_path: Path) -> None:
    # covers: ACS-900d-4-ii
    # angle: criterion
    """A correctly retired child absent from its parent's covered_by gets the active-child refusal.

    Control rows: the same shape with an ACTIVE child is refused with the identical message,
    and the retired child passes once the parent names it (so the hook saw the files).
    """
    retired = fx.retired_record(RECORD_ID, depends_on=[PARENT_ID])
    twin = fx.ac_record(TWIN_ID, depends_on=[PARENT_ID])

    retired_proc = fx.parent_hook(_stage(tmp_path, "retired", retired, [_parent_with([])]))
    active_proc = fx.parent_hook(_stage(tmp_path, "active", twin, [_parent_with([])]))
    linked_proc = fx.parent_hook(_stage(tmp_path, "linked", retired, [_parent_with([RECORD_ID])]))

    assert active_proc.returncode != 0 and _parent_message(active_proc, TWIN_ID), fx.out(active_proc)
    assert retired_proc.returncode != 0, f"retired child with an unlinked parent passed: {fx.out(retired_proc)!r}"
    assert _parent_message(retired_proc, RECORD_ID) == _parent_message(active_proc, TWIN_ID), (
        "retired child must get exactly the active child's message"
    )
    assert linked_proc.returncode == 0, f"linked retired child refused: {fx.out(linked_proc)!r}"


def test_retired_record_invalid_work_status_refused(tmp_path: Path) -> None:
    # covers: ACS-900d-4-ii
    # angle: criterion
    """A retired record with work_status 'finished' is refused for shape by BOTH shape gates.

    Control: the same retired record with a valid work_status passes validate_ac_schema.py,
    so its refusal below is the bad value and not the record's retirement.
    """
    repo = fx.make_repo(tmp_path / "shape")
    bad = fx.stage_scenario(repo, [fx.retired_record(RECORD_ID, work_status="finished")])[0]
    hook = fx.schema_hook(repo)
    ci_check = fx.validate_schema(repo, bad)

    assert hook.returncode != 0 and "'finished'" in fx.out(hook), f"check_ac_schema passed it: {fx.out(hook)!r}"
    assert ci_check.returncode != 0 and "'finished'" in fx.out(ci_check), (
        f"validate_ac_schema passed it: {fx.out(ci_check)!r}"
    )

    good_repo = fx.make_repo(tmp_path / "shape_ok")
    good = fx.stage_scenario(good_repo, [fx.retired_record(RECORD_ID)])[0]
    control = fx.validate_schema(good_repo, good)
    assert control.returncode == 0, f"control retired record failed validate_ac_schema: {fx.out(control)!r}"
