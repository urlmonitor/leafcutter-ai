"""
MODULE: unit_tests/ac_store/test_tq_500g_4_i.py
GOAL: TQ-500g-4-i -- a run that reports failure overall (exit 1) but shows no
    failing test is inconclusive, never a clean pass.
BUSINESS CONTEXT: R1 is a REAL pytest process whose conftest sets the session
    exit status to 1 while every test line reads PASSED (no hand-typed output).
    R2 (clean) and R3 (plain failure) are the controls. Readers: done_proof's
    _run_pytest_and_parse, done_proof_kind_support's kind-plugin run, the
    verify_done_eligible verdict, and the verify_red_baseline CLI verdict.
"""

from __future__ import annotations

import unit_tests.ac_store._tq500g4_fixtures as fx

_INCONCLUSIVE_REASON = "no failing test could be identified"


def _sentinel():
    done_proof, _ = fx.import_readers()
    return done_proof._PYTEST_RUN_INCOMPLETE_SENTINEL


def _is_inconclusive(readings: dict[str, str]) -> bool:
    return _sentinel() in readings


def _inconclusive_message(readings: dict[str, str]) -> str:
    return readings.get(_sentinel(), "")


def test_exit_one_with_all_parsed_passes_is_inconclusive_at_both_checks(tmp_path):
    # covers: TQ-500g-4-i
    # angle: failure
    # Wrong versions caught: returncode checked only for membership in (0, 1)
    # (R1 parses to all-PASSED and is read as a pass); contradictory run read
    # as all passed (red-baseline lists the tests as green_at_baseline).
    work, test_root, ac_root = fx.build_run(tmp_path, "R1")
    done_read = fx.read_through_done_proof(test_root)
    kind_read = fx.read_through_kind_plugin(test_root)
    for name, reading in (("done_proof", done_read), ("kind_plugin", kind_read)):
        assert _is_inconclusive(reading), f"{name} read R1 as {reading}, not inconclusive"
        assert _INCONCLUSIVE_REASON in _inconclusive_message(reading), reading
    done_proof, _ = fx.import_readers()
    verdict_done = done_proof.verify_done_eligible(
        fx.AC_S1, ac_root=ac_root, test_root=test_root
    )
    assert verdict_done["eligible"] is False, verdict_done
    assert _INCONCLUSIVE_REASON in verdict_done.get("reason", ""), verdict_done
    _rc, verdict = fx.run_red_baseline_cli(work, test_root, [fx.AC_S1, fx.AC_S2])
    assert verdict["red"] == [] and verdict["green_at_baseline"] == [], verdict
    assert fx.bucket_names(verdict, "inconclusive") == {"test_refresh_gate", "test_export_gate"}


def test_ordinary_failing_run_is_not_inconclusive(tmp_path):
    # covers: TQ-500g-4-i
    # angle: discrimination
    # R3: exit 1 with test_refresh_gate FAILED is read per test, not inconclusive.
    # Wrong version caught: every exit-status-1 run reported inconclusive.
    # The second leg (the SUBFAILED run S, also exit 1) must be read FAILED
    # per test too -- a rule that ignores the per-test reading fails it, and it
    # keeps this control from being green on arrival.
    for run in ("R3", "S"):
        work, test_root, _ac_root = fx.build_run(tmp_path / run, run)
        done_read = fx.read_through_done_proof(test_root)
        kind_read = fx.read_through_kind_plugin(test_root)
        assert not _is_inconclusive(done_read) and not _is_inconclusive(kind_read), (
            run, done_read, kind_read)
        assert fx.outcome_by_name(done_read)["test_refresh_gate"] == "FAILED", (run, done_read)
        _rc, verdict = fx.run_red_baseline_cli(work, test_root, fx.ALL_ACS[:2])
        assert fx.bucket_names(verdict, "inconclusive") == set(), (run, verdict)
        assert "test_refresh_gate" in fx.bucket_names(verdict, "red"), (run, verdict)


def test_clean_passing_run_read_as_passed(tmp_path):
    # covers: TQ-500g-4-i
    # angle: criterion
    # R2: exit 0, every test PASSED, read as today. Wrong version caught: a rule
    # that ignores the overall verdict -- paired here with R1, which such a rule
    # would also read as passed (criteria note: R2 alone is green on arrival).
    work, test_root, _ac_root = fx.build_run(tmp_path / "R2", "R2")
    done_read = fx.read_through_done_proof(test_root)
    assert fx.outcome_by_name(done_read) == {
        "test_refresh_gate": "PASSED", "test_export_gate": "PASSED"}, done_read
    _rc, verdict = fx.run_red_baseline_cli(work, test_root, fx.ALL_ACS[:2])
    assert fx.bucket_names(verdict, "green_at_baseline") == {
        "test_refresh_gate", "test_export_gate"}, verdict
    _w1, r1_root, _a1 = fx.build_run(tmp_path / "R1", "R1")
    assert _is_inconclusive(fx.read_through_done_proof(r1_root)), (
        "the contradictory run R1 must not read as the clean R2 does")
