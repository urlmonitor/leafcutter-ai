"""
MODULE: unit_tests/commit_guardian/test_acs_900d_4_iii_self_supersession.py
GOAL: RED tests for ACS-900d-4-iii -- a record that names itself as its own
    successor is refused ("a record cannot supersede itself") and is NOT treated
    as retired, so done-proof still asks for its covering test.

Self-reference passes a bare "does the successor exist" check by construction (the
record is being staged), so these tests are what separate the self rule from the
existence rule of ACS-900d-4-ii. Both gates are real subprocesses (check_ac_schema.py
and check_done_proof.py, source copies) against a throwaway git repo.

Named wrong versions caught: the predicate checks only that each successor exists
(the record satisfies that itself); the self check fires only for a one-entry list.

DECISION HISTORY
- 2026-10-15 [test-writer/ACS-900d-4-iii]: Initial RED authoring.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _acs_900d_4_fixtures as fx  # noqa: E402

SELF_ID = "RT-100a-3"
CONTROL_ID = "RT-100a-4"
SELF_MESSAGE = "cannot supersede itself"


def _stage(tmp_path: Path, name: str, record: dict) -> Path:
    repo = fx.make_repo(tmp_path / name)
    fx.stage_scenario(repo, [record])
    return repo


def test_self_successor_refused_with_self_supersession_message(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iii
    # angle: criterion
    """superseded_by [X] on record X is refused, and the message names X and says it cannot supersede itself."""
    repo = _stage(tmp_path, "self", fx.retired_record(SELF_ID, successors=[SELF_ID]))
    proc = fx.schema_hook(repo)
    text = fx.out(proc)

    assert proc.returncode != 0, f"self-superseding record passed the schema gate: {text!r}"
    assert fx.lines_naming(proc, SELF_ID, SELF_MESSAGE), (
        f"no refusal line names {SELF_ID} and says {SELF_MESSAGE!r}: {text!r}"
    )


def test_self_successor_not_retired_done_proof_reports_missing_cover(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iii
    # angle: discrimination
    """The done-proof gate, run on the same staged record, still reports the missing covering test.

    Wrong version caught: a predicate that only checks every successor exists would
    count the record as retired (it exists, it is being staged) and skip it.
    """
    repo = _stage(tmp_path, "self_done_proof", fx.retired_record(SELF_ID, successors=[SELF_ID]))
    proc = fx.done_proof(repo)
    refusals = fx.done_proof_refusals(proc)

    assert proc.returncode != 0, f"self-superseding record was treated as retired: {fx.out(proc)!r}"
    assert SELF_ID in refusals, f"done-proof did not name {SELF_ID}: {fx.out(proc)!r}"
    assert f"covers: {SELF_ID}" in refusals[SELF_ID], refusals[SELF_ID]


def test_self_plus_valid_successor_still_refused(tmp_path: Path) -> None:
    # covers: ACS-900d-4-iii
    # angle: boundary
    """superseded_by [X, AR-400c-1] is refused with the same message; a clean [AR-400c-1] twin is not.

    Wrong version caught: the self check only fires when the list has exactly one entry.
    The control record (same shape, successor list without itself) must pass the same
    hook, so the refusal can only come from the self id.
    """
    mixed = fx.retired_record(SELF_ID, successors=[SELF_ID, fx.SUCCESSOR])
    repo = _stage(tmp_path, "mixed", mixed)
    proc = fx.schema_hook(repo)

    assert proc.returncode != 0, f"mixed self+valid successor list passed: {fx.out(proc)!r}"
    assert fx.lines_naming(proc, SELF_ID, SELF_MESSAGE), fx.out(proc)

    control_repo = _stage(tmp_path, "control", fx.retired_record(CONTROL_ID))
    control = fx.schema_hook(control_repo)
    assert control.returncode == 0, f"control retirement (no self id) refused: {fx.out(control)!r}"
    assert not fx.lines_naming(control, SELF_MESSAGE), fx.out(control)
