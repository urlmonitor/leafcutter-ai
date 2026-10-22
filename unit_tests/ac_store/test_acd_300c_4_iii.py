"""
MODULE: unit_tests/ac_store/test_acd_300c_4_iii.py
COVERS: ACD-300c-4-iii
GOAL: Red-first specification that the approval step's id-list mode approves a feature record (L1) in
    the batch under its own id, like its children: it is not skipped for having children, never
    expanded to them, and gains exactly one approval entry.
BUSINESS CONTEXT: The step's goal mode promotes only reviewed LEAF children of a goal, so approving the
    batch's top record "as a goal" would leave the L1 itself at reviewed.
ARCHITECTURE: The real CLI as a subprocess on a tmp consumer-style store (_acd_300c_4_fixtures.l1_store).
    The workflow half lives in unit_tests/ac_driven_dev/test_design_stage/test_acd_300c_4_iii.py.
RED STATE: approve_acs.py has no --ids / --priority (argparse exits 2).
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_300c_4_fixtures import amended_by_of, approval_entries, l1_store, report_of, run_ids  # noqa: E402

L1_BATCH = ["ACD-9990a", "ACD-9990a-1", "ACD-9990a-2"]


def test_id_list_mode_approves_an_l1_with_its_children(tmp_path):
    # covers: ACD-300c-4-iii
    # angle: reachability
    """`approve_acs.py --ids ACD-9990a,ACD-9990a-1,ACD-9990a-2 --priority high --json`, where ACD-9990a is
    an L1 covering the two children: all three read readiness approved."""
    store = l1_store(tmp_path)

    run = run_ids(store, L1_BATCH, priority="high")

    assert run.exit_code == 0, run.stderr[-600:]
    assert {rid: store.read(rid)["readiness"] for rid in L1_BATCH} == dict.fromkeys(L1_BATCH, "approved")


def test_l1_is_approved_once_under_its_own_id(tmp_path):
    # covers: ACD-300c-4-iii
    # angle: discrimination
    """Read back: ACD-9990a gained exactly one approval entry, and each child exactly one (not one per
    mention), and the report names the L1 among the approved ids.

    Wrong versions caught: the id-list mode expands an L1 id to its covered_by children (the L1 stays
    reviewed with no entry, each child is touched twice); the mode skips any id whose record has
    covered_by children.
    """
    store = l1_store(tmp_path)
    prior = {rid: len(amended_by_of(store, rid)) for rid in L1_BATCH}

    report = report_of(run_ids(store, L1_BATCH, priority="high"))

    assert sorted(report["approved"]) == sorted(L1_BATCH), report
    for rid in L1_BATCH:
        entries = amended_by_of(store, rid)
        assert len(entries) == prior[rid] + 1 and len(approval_entries(entries)) == 1, (rid, entries)
    assert store.read("ACD-9990a")["covered_by"] == ["ACD-9990a-1", "ACD-9990a-2"]
