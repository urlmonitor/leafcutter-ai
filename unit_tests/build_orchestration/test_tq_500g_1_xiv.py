"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_xiv.py
GOAL: RED tests for TQ-500g-1-xiv: a test held to a wrong version that changes no line the test runs is
    reported ``not_executed`` (unfinished), never as a survivor; run-or-not-run is judged per test, an
    untraceable file keeps its run-decided verdict, and a line run at import counts for every test.
BUSINESS CONTEXT: Every test drives the real runner CLI (subprocess, real pytest) on a real git sandbox, real
    tests and a real AC store (see _tq500g1xiv_fixtures.py). Today the runner has no reachability check, so a
    test that never ran the changed line is reported ``survived``: each test fails on an assertion about the
    verdict JSON, never on an import (except the pure-function test, which needs the not-yet-written
    ``_wvr_effect`` module).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1xiv_fixtures as f
import unit_tests.build_orchestration._tq500g2i_fixtures as dbfx

NAIVE = {f.WV_NAIVE: f.CHAIN_LINE}


def _unfinished(verdict: dict, test: str, wv: str) -> list[dict]:
    return [u for u in verdict["unfinished"] if str(u["test"]).endswith("::" + test) and u["wrong_version"] == wv]


def test_unreached_test_reads_not_executed_never_survivor(tmp_path):
    # covers: TQ-500g-1-xiv
    # angle: discrimination
    # Catches: 'a test that never ran the changed line counted as a survivor' (T2 would read survived);
    # 'reachability judged per name, so T1 reaching it covers T2' (T2 would read survived or caught);
    # 'a line run by another test counted for T2' (the same). Control: T1 ran the line and is decided by its run.
    sb = f.build(tmp_path, f.spec_t1_t2(), NAIVE)
    proc, verdict = f.run(sb)
    assert f.results_of(verdict, f.T1, f.WV_NAIVE) == ["caught"], verdict["results"]
    t2 = f.rows(verdict, f.T2, f.WV_NAIVE)
    assert [r["result"] for r in t2] == ["not_executed"], f"T2 rows: {t2}"
    assert t2[0]["detail"] == f.NOT_EXECUTED and t2[0]["blocking"] is True, t2[0]
    assert f.T2 not in f.survivor_tests(verdict) and verdict["survivors"] == [], verdict["survivors"]
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished", (verdict["reason"], verdict["unfinished"])
    entries = _unfinished(verdict, f.T2, f.WV_NAIVE)
    assert [u["result"] for u in entries] == ["not_executed"], verdict["unfinished"]
    assert proc.returncode == 1
    assert (sb.work / f.MOD).read_bytes() == sb.written[f.MOD], "the code was not put back byte for byte"


def test_not_executed_row_is_told_apart_from_a_weak_test(tmp_path):
    # covers: TQ-500g-1-xiv
    # angle: criterion
    # Catches: 'not_executed folded into survived in the report'. T3 runs the changed line and still passes
    # (weak); T2 never ran it. Same verdict, two different result words and details.
    spec = [*f.spec_t1_t2(), f.entry(f.T3, f.WV_NAIVE)]
    sb = f.build(tmp_path, spec, NAIVE)
    _proc, verdict = f.run(sb)
    t2, t3 = f.rows(verdict, f.T2, f.WV_NAIVE), f.rows(verdict, f.T3, f.WV_NAIVE)
    assert [r["result"] for r in t3] == ["survived"], f"T3 rows: {t3}"
    assert [r["result"] for r in t2] == ["not_executed"], f"T2 rows: {t2}"
    assert t2[0]["result"] != t3[0]["result"] and t2[0]["detail"] != t3[0]["detail"], (t2, t3)
    assert t2[0]["detail"] == f.NOT_EXECUTED
    assert f.survivor_tests(verdict) == [f.T3], verdict["survivors"]
    assert verdict["reason"] == "survivor", "a survivor still outranks an unfinished row"
    assert _unfinished(verdict, f.T2, f.WV_NAIVE) and not _unfinished(verdict, f.T3, f.WV_NAIVE), verdict["unfinished"]


def test_untraceable_sql_alteration_keeps_its_run_verdict(tmp_path):
    # covers: TQ-500g-1-xiv
    # angle: boundary
    # Catches: 'an untraceable file treated as not executed'. TS2 never reads the SQL file yet must keep its
    # run-decided row (survived), with the could-not-be-traced note; TS1 reads it and is caught.
    spec = [f.entry(f.TS1, f.WV_SQL), f.entry(f.TS2, f.WV_SQL)]
    sb = f.build(tmp_path, spec, {f.WV_SQL: f.SQL_LINE})
    _proc, verdict = f.run(sb)
    assert [r for r in verdict["results"] if r["result"] == "not_executed"] == [], verdict["results"]
    assert f.results_of(verdict, f.TS1, f.WV_SQL) == ["caught"], verdict["results"]
    assert f.results_of(verdict, f.TS2, f.WV_SQL) == ["survived"], verdict["results"]
    for test in (f.TS1, f.TS2):
        detail = f.rows(verdict, test, f.WV_SQL)[0]["detail"]
        assert f"{f.UNTRACED} {f.SQL_REL}" in detail, f"{test}: {detail!r}"
    assert f.survivor_tests(verdict) == [f.TS2], verdict["survivors"]
    assert not [u for u in verdict["unfinished"] if u["result"] == "not_executed"], verdict["unfinished"]


def test_module_level_change_counts_as_reached(tmp_path):
    # covers: TQ-500g-1-xiv
    # angle: boundary
    # Catches: 'import-time lines attributed to no test'. The constant line runs at import, before any test
    # starts, so it counts for T1 and T2 alike: T2 asserts the constant (caught), T1 does not (survived).
    # Control in the same run: T2 also names the naive-chain version, whose line it never runs, so the
    # check is known to be active (T2 reads not_executed there) while the import-time line is not judged so.
    spec = [f.entry(f.T1, f.WV_CONST), f.entry(f.T2, f.WV_CONST, f.WV_NAIVE)]
    sb = f.build(tmp_path, spec, {f.WV_CONST: f.CONST_LINE, f.WV_NAIVE: f.CHAIN_LINE})
    _proc, verdict = f.run(sb)
    assert f.results_of(verdict, f.T2, f.WV_NAIVE) == ["not_executed"], f"control: the check is not active: {verdict['results']}"
    assert f.results_of(verdict, f.T2, f.WV_CONST) == ["caught"], verdict["results"]
    assert f.results_of(verdict, f.T1, f.WV_CONST) == ["survived"], verdict["results"]
    const_rows = [r for r in verdict["results"] if r["wrong_version"] == f.WV_CONST]
    assert len(const_rows) == 2 and not [r for r in const_rows if r["result"] == "not_executed"], const_rows
    assert f.survivor_tests(verdict) == [f.T1] and verdict["reason"] == "survivor", verdict


def _crlf(text: str) -> bytes:
    return text.replace("\n", "\r\n").encode("utf-8")


def test_changed_lines_of_replace_delete_and_insert():
    # covers: TQ-500g-1-xiv
    # angle: boundary
    # Catches: 'changed lines taken from the altered side's numbering': a one-line replace by two lines and a
    # two-line delete give different numbers on the altered side.
    sys.path.insert(0, str(f.REPO_ROOT / "scripts" / "build_orchestration"))
    from _wvr_effect import changed_lines

    cases = (
        ("a\nb\nc\n", "a\nB\nc\n", {2}),
        ("a\nb\nc\n", "a\nB1\nB2\nc\n", {2}),
        ("a\nb\nc\nd\n", "a\nd\n", {2, 3}),
        ("a\nb\nc\n", "a\nb\nX\nc\n", {2}),
        ("a\nb\n", "X\na\nb\n", {1}),
    )
    for as_written, altered, expected in cases:
        assert changed_lines(as_written.encode("utf-8"), altered.encode("utf-8")) == expected, ("LF", as_written, altered)
        assert changed_lines(_crlf(as_written), _crlf(altered)) == expected, ("CRLF", as_written, altered)
    assert changed_lines(b"a\nb\n", b"a\nb\n") == set(), "control: no alteration, no changed line"


def _add_python_wrong_version(proj: dbfx.Project) -> None:
    """Add pymod.py, a test that never imports it and a wrong version altering it, beside the database test."""
    body = "VALUE = 1\n\n\ndef compute():\n    return VALUE + 1\n"
    altered = body.replace("VALUE + 1", "VALUE + 2")
    (proj.work / "pymod.py").write_bytes(body.encode("utf-8"))
    (proj.work / "fx_tests" / "test_py_gate.py").write_bytes(
        f"def test_py_unrelated():\n    # covers: {dbfx.AC_ID}\n    assert 1 + 1 == 2\n".encode("utf-8"))
    gitfx.commit_all(proj.work, "a python module and a test that never runs it")
    spec = [{"name": dbfx.TEST, "requires_db": True, "must_catch": [dbfx.WV_DROP]},
            {"name": "test_py_unrelated", "must_catch": ["py gate wrong"]}]
    gitfx.write_ac_yaml(proj.ac_root, dbfx.AC_ID, spec)
    copy = proj.root / "altered" / "py_pymod.py"
    copy.write_bytes(altered.encode("utf-8"))
    data = json.loads(proj.manifest.read_text(encoding="utf-8"))
    data["entries"].append({"name": "py gate wrong", "status": "prepared", "reason": None, "diff": "",
                            "files": [{"path": "pymod.py", "altered_copy": str(copy)}]})
    proj.manifest.write_text(json.dumps(data), encoding="utf-8")


def test_trace_and_database_plugins_share_one_run(tmp_path):
    # covers: TQ-500g-1-xiv
    # angle: seam
    # Catches: 'the trace plugin replacing the database plugin in the child'. One baseline run must carry
    # both: the database test is still judged from the catalogue (caught) and the python test is read from
    # the trace output (not_executed).
    with dbfx.Listener() as db:
        proj = dbfx.build_project(tmp_path, address=dbfx.address_for(db.port), source="altered")
        _add_python_wrong_version(proj)
        _proc, verdict = dbfx.run_runner(proj)
    db_rows = [r for r in dbfx.rows(verdict, dbfx.WV_DROP)]
    assert [r["result"] for r in db_rows] == ["caught"], f"database rows lost with the trace plugin loaded: {verdict['results']}"
    py = [r for r in verdict["results"] if str(r["test"]).endswith("::test_py_unrelated") and r["wrong_version"] == "py gate wrong"]
    assert [r["result"] for r in py] == ["not_executed"], f"trace output not read: {verdict['results']}"


@pytest.mark.shared_layout_reader
def test_deployed_runner_loads_the_deployed_trace_plugin(shared_reference_layout, tmp_path):
    # covers: TQ-500g-1-xiv
    # angle: deployed
    # Catches: 'the plugin missing from the deployed layout, so every run silently loses the check'. The
    # DEPLOYED runner (never the source tree's) is run on the T1/T2 fixture and must report T2 not_executed.
    deployed = Path(shared_reference_layout) / ".leafcutter" / "scripts" / "build_orchestration"
    assert (deployed / "wrong_version_runner.py").is_file(), f"no deployed runner under {deployed}"
    sb = f.build(tmp_path, f.spec_t1_t2(), NAIVE)
    _proc, verdict = f.run(sb, deployed / "wrong_version_runner.py")
    assert f.results_of(verdict, f.T2, f.WV_NAIVE) == ["not_executed"], verdict["results"]
    assert f.results_of(verdict, f.T1, f.WV_NAIVE) == ["caught"], verdict["results"]


def test_tq_500g_1_xiv_reachable_from_entry_point(tmp_path):
    # covers: TQ-500g-1-xiv
    # angle: reachability
    # Entry point: python scripts/build_orchestration/wrong_version_runner.py run ... (CLI via subprocess).
    # The not_executed row must stop the work in control flow: exit code 1 with gate_passed false. Control:
    # without T2 the same run exits 0, so the exit code is decided by the not_executed row, not a constant.
    sb = f.build(tmp_path / "stop", f.spec_t1_t2(), NAIVE)
    proc, verdict = f.run(sb)
    assert f.results_of(verdict, f.T2, f.WV_NAIVE) == ["not_executed"], verdict["results"]
    assert proc.returncode == 1 and verdict["gate_passed"] is False and verdict["reason"] == "unfinished"
    ok = f.build(tmp_path / "ok", [f.entry(f.T1, f.WV_NAIVE)], NAIVE)
    proc_ok, v_ok = f.run(ok)
    assert proc_ok.returncode == 0 and v_ok["gate_passed"] is True, v_ok
    assert f.results_of(v_ok, f.T1, f.WV_NAIVE) == ["caught"] and v_ok["unfinished"] == [], v_ok
