"""
MODULE: unit_tests/ac_store/test_tq_500g_4.py
GOAL: TQ-500g-4 -- a test that failed in any of its cases (incl. unittest
    subTest sub-cases) is read as failed by EVERY check that reads a test run.
BUSINESS CONTEXT: pytest 9 prints "<nodeid> PASSED" for a test whose only
    failures are inside self.subTest() and reports them on SUBFAILED lines the
    shared outcome reader drops (KI-TQ-20260928-subtest-failures-read-as-passed).
    Every run here is a REAL child pytest over a real fixture module (S1/S2/S3,
    see _tq500g4_fixtures.py), read through the REAL production readers.
    Own tests use separate functions, NOT self.subTest (that is the bug).
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.ac_store._tq500g4_fixtures as fx


def _readings(tmp_path: Path):
    """Run the S fixture once per reader; return the three per-check readings."""
    work, test_root, ac_root = fx.build_run(tmp_path, "S")
    done_map = fx.outcome_by_name(fx.read_through_done_proof(test_root))
    kind_map = fx.outcome_by_name(fx.read_through_kind_plugin(test_root))
    rc, verdict = fx.run_red_baseline_cli(work, test_root, fx.ALL_ACS)
    return work, test_root, ac_root, done_map, kind_map, rc, verdict


def _baseline_map(verdict: dict) -> dict[str, str]:
    entries = []
    for bucket in ("red", "green_at_baseline", "inconclusive"):
        entries += verdict.get(bucket, [])
    return {e["nodeid"].rsplit("::", 1)[-1]: e["outcome"] for e in entries}


def test_subfailed_test_read_identically_by_done_proof_and_red_baseline(tmp_path):
    # covers: TQ-500g-4
    # angle: seam
    # Wrong versions caught: (a) parser ignores SUBFAILED lines -> S1 PASSED in
    # every map; (b) only the done-proof path reads SUBFAILED while red-baseline
    # keeps a private parser -> the maps differ / S1 lands in green_at_baseline.
    _w, test_root, ac_root, done_map, kind_map, _rc, verdict = _readings(tmp_path)
    expected = {
        "test_refresh_gate": "FAILED",
        "test_export_gate": "PASSED",
        "test_window_gate": "FAILED",
    }
    base_map = _baseline_map(verdict)
    assert done_map == expected, f"done_proof reading: {done_map}"
    assert kind_map == done_map, f"kind-plugin reading differs: {kind_map}"
    assert base_map == done_map, f"red-baseline reading differs: {base_map}"
    done_proof, _ = fx.import_readers()
    reason = done_proof.verify_done_eligible(
        fx.AC_S1, ac_root=ac_root, test_root=test_root
    ).get("reason", "")
    assert fx.SUBCASE in reason, f"done-proof reason must name the sub-case: {reason!r}"
    s1_entry = [e for e in verdict["red"] if e["ac_id"] == fx.AC_S1]
    assert s1_entry and fx.SUBCASE in repr(s1_entry[0]), (
        f"red-baseline verdict entry must name the sub-case: {verdict['red']}"
    )


def test_done_proof_refuses_requirement_covered_only_by_subfailed_test(tmp_path):
    # covers: TQ-500g-4
    # angle: reachability
    # Real entry point: the mark_ac_done.py CLI (--test-root) which calls
    # verify_done_eligible; the refusal must be consumed as exit 3.
    # Wrong version caught: SUBFAILED downgrade applied in the red-baseline
    # path only -> the CLI still says "would mark done" and exits 0.
    work, test_root, ac_root, *_ = _readings(tmp_path)
    proc = fx.run_mark_done_cli(work, ac_root, test_root, fx.AC_S1)
    assert proc.returncode == 3, (
        f"AC covered only by the SUBFAILED test must be refused; rc={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    assert fx.AC_S1 in proc.stderr and fx.SUBCASE in proc.stderr, proc.stderr


def test_test_with_only_passing_subcases_stays_passed(tmp_path):
    # covers: TQ-500g-4
    # angle: discrimination
    # Control (S2). Wrong versions caught: any test with sub-cases read as
    # FAILED; SUBPASSED lines read as failures. The S1==FAILED leg keeps the
    # control honest: a reader that changes nothing would pass S2 alone.
    work, test_root, ac_root, done_map, kind_map, _rc, verdict = _readings(tmp_path)
    assert done_map["test_refresh_gate"] == "FAILED", "S1 must still read FAILED"
    assert done_map["test_export_gate"] == "PASSED", done_map
    assert kind_map["test_export_gate"] == "PASSED", kind_map
    green = {e["ac_id"] for e in verdict["green_at_baseline"]}
    assert fx.AC_S2 in green and fx.AC_S1 not in green, verdict
    proc = fx.run_mark_done_cli(work, ac_root, test_root, fx.AC_S2)
    assert proc.returncode == 0, f"S2-only AC must stay eligible: {proc.stderr!r}"
