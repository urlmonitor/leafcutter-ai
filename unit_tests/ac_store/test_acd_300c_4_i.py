"""
MODULE: unit_tests/ac_store/test_acd_300c_4_i.py
COVERS: ACD-300c-4-i
GOAL: Red-first specification that applying the same final-gate approval a second time changes nothing:
    the approval step's id-list mode is idempotent (no file is rewritten, no second approval entry) and
    reports the already-approved ids in the additive `already_approved` list, exiting with success.
ARCHITECTURE: The real CLI (approve_acs.py --ids ... --priority high --json) twice as a subprocess on a
    tmp consumer-style store (_acd_300c_4_fixtures). The workflow half lives in
    unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_4_i.py.
RED STATE: approve_acs.py has no --ids / --priority (argparse exits 2) and no already_approved key.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300c_4_fixtures import (  # noqa: E402
    BATCH,
    HELD,
    RELEASED,
    UNDECIDED,
    amended_by_of,
    approval_entries,
    batch_store,
    report_of,
    run_ids,
    store_bytes,
)


def test_second_application_rewrites_no_file(tmp_path):
    # covers: ACD-300c-4-i
    # angle: reachability
    """`approve_acs.py --ids ACD-9990a-1,ACD-9990a-2,ACD-9990a-4 --priority high --json` twice: both runs
    exit 0, and after the second run all 4 files are byte-identical to the state after the first.
    Control: the first run really approved the three (so "nothing changed" is not "nothing ran")."""
    store = batch_store(tmp_path)

    first = run_ids(store, RELEASED, priority="high")
    assert first.exit_code == 0, first.stderr[-600:]
    assert [store.read(rid)["readiness"] for rid in RELEASED] == ["approved"] * 3
    after_first = store_bytes(store, BATCH)

    second = run_ids(store, RELEASED, priority="high")

    assert second.exit_code == 0, second.stderr[-600:]
    changed = [rid for rid, raw in store_bytes(store, BATCH).items() if raw != after_first[rid]]
    assert changed == [], f"the second application rewrote: {changed}"


def test_second_application_adds_no_approval_entry(tmp_path):
    # covers: ACD-300c-4-i
    # angle: real_artifact
    """The three approved files read back after the second run: each amended_by list has the same length
    as after the first run, with exactly one approval entry."""
    store = batch_store(tmp_path)
    report_of(run_ids(store, RELEASED, priority="high"))
    lengths = {rid: len(amended_by_of(store, rid)) for rid in RELEASED}

    report_of(run_ids(store, RELEASED, priority="high"))

    for rid in RELEASED:
        entries = amended_by_of(store, rid)
        assert len(entries) == lengths[rid], (rid, entries)
        assert len(approval_entries(entries)) == 1, (rid, entries)


def test_second_application_reports_already_approved(tmp_path):
    # covers: ACD-300c-4-i
    # angle: criterion
    """The second run (all four ids) reports approved [], held [ACD-9990a-3] and already_approved listing
    the three ids, with exit 0 (a repeat is reported, not a failure)."""
    store = batch_store(tmp_path)
    report_of(run_ids(store, BATCH, priority="high"))

    second = run_ids(store, BATCH, priority="high")
    report = report_of(second)

    assert report["approved"] == [], report
    assert report["held"] == [{"id": HELD, "file": store.rel(HELD), "reason": UNDECIDED}], report
    assert sorted(report.get("already_approved", [])) == RELEASED, report
