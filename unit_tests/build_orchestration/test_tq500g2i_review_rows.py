"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_review_rows.py
GOAL: Review-fix tests H-1 and H-3 of TQ-500g-2-i -- which tests answer for a wrong version, and
    which catalogue rows count as "the function the tests call".
BUSINESS CONTEXT: Real runner CLI (subprocess) over the scratch git project of the d1_d2 tests with
    the stand-in PostgreSQL driver; the suite installs the file the runner alters (D2).
"""

from __future__ import annotations

import unit_tests.build_orchestration._tq500g2i_fixtures as fx
import unit_tests.build_orchestration._tq500g2i_review_fixtures as rv


def test_h1_non_holder_gets_no_row_for_a_version_it_does_not_name(tmp_path):
    # covers: TQ-500g-2-i
    # angle: discrimination
    # Catches: 'every database test is judged for every wrong version' -- the test that does not name
    # WV_DROP was not run for it, so no catalogue capture exists and it would read not_run.
    # Control: the same test is caught for the version it does name, and the holder is caught once.
    tests = [(fx.TEST, [fx.WV_DROP]), (rv.SECOND, [fx.WV_OTHER])]
    wrongs = {fx.WV_DROP: fx.WRONG_DROP, fx.WV_OTHER: fx.WRONG_OTHER}
    with fx.Listener() as db:
        proj = rv.build(tmp_path, address=fx.address_for(db.port), tests=tests, wrongs=wrongs)
        proc, verdict = fx.run_runner(proj)
    drop = rv.results_for(verdict, fx.WV_DROP)
    assert [(r["test"].split("::")[-1], r["result"]) for r in drop] == [(fx.TEST, "caught")], f"WV_DROP rows: {drop}"
    other = rv.results_for(verdict, fx.WV_OTHER)
    assert [(r["test"].split("::")[-1], r["result"]) for r in other] == [(rv.SECOND, "caught")], f"WV_OTHER rows: {other}"
    assert not [r for r in verdict["results"] if r["result"] == "not_run"], verdict["results"]
    assert verdict["gate_passed"] is True and proc.returncode == 0, verdict


def _caught_with_extra_rows(tmp_path, extra: list[dict], **kwargs):
    with fx.Listener() as db:
        proj = rv.build(tmp_path, address=fx.address_for(db.port), **kwargs)
        rv.write_rows(proj, extra)
        proc, verdict = fx.run_runner(proj)
    return proj, proc, verdict


def _assert_judged_caught(verdict: dict, proc, what: str) -> None:
    found = fx.rows(verdict, fx.WV_DROP)
    assert [r["result"] for r in found] == ["caught"], f"{what}: {verdict['results']} reason={verdict.get('reason')}"
    assert verdict["gate_passed"] is True and proc.returncode == 0, f"{what}: {verdict}"


def test_h3a_same_name_in_a_schema_off_the_search_path_is_ignored(tmp_path):
    # covers: TQ-500g-2-i
    # angle: discrimination
    # Catches: 'the catalogue read takes every pg_proc row of that name' (two bodies -> "neither", and the
    # put-back of the correct code reads as a mismatch). Control: the visible row is the one the tests call
    # and it holds the wrong version, so a read that picks the visible row judges it "wrong" = caught.
    elsewhere = {"proname": fx.FUNCTION, "prosrc": "SELECT 'a function of the same name in another schema'",
                 "visible": False, "prokind": "f"}
    proj, proc, verdict = _caught_with_extra_rows(tmp_path, [elsewhere])
    _assert_judged_caught(verdict, proc, "invisible same-name row")
    assert any(e.get("ev") == "catalog_read" for e in fx.events(proj)), "the stand-in never answered a catalogue read"


def test_h3b_quoted_mixed_case_name_is_found_with_its_case(tmp_path):
    # covers: TQ-500g-2-i
    # angle: boundary
    # Catches: 'object names folded to lower case before the catalogue lookup' ("MyFn" is stored with its
    # case, so a lookup for "myfn" finds nothing and the run reads "neither"). Control: fn_refresh_due is
    # altered in the same file and found; the wrong version alters the quoted function as well.
    wrongs = {fx.WV_DROP: rv.MYFN_WRONG}
    proj, proc, verdict = _caught_with_extra_rows(tmp_path, [], base_sql=rv.MYFN_BASE, written_sql=rv.MYFN_WRITTEN, wrongs=wrongs)
    _assert_judged_caught(verdict, proc, "quoted mixed-case name")
    installs = [e["name"] for e in fx.events(proj) if e.get("ev") == "install"]
    assert "MyFn" in installs, f"the stand-in never stored the quoted name with its case: {installs}"


def test_h3c_aggregate_or_window_row_of_the_same_name_is_ignored(tmp_path):
    # covers: TQ-500g-2-i
    # angle: discrimination
    # Catches: 'any pg_proc row of the name counts, whatever its kind' (an aggregate "a" or window "w" row
    # is not a function or procedure, and its presence made the read ambiguous). Control: the "f" row is
    # the one the tests call.
    extra = [{"proname": fx.FUNCTION, "prosrc": "SELECT 'an aggregate'", "visible": True, "prokind": kind} for kind in ("a", "w")]
    _proj, proc, verdict = _caught_with_extra_rows(tmp_path, extra)
    _assert_judged_caught(verdict, proc, "aggregate and window rows")
