"""
MODULE: unit_tests/build_orchestration/test_tq500g2ii_failclosed.py
GOAL: RED tests for TQ-500g-2-ii P2 / P3 / invalid / config_error -- when the test
    database check reports anything but "reachable", database tests are never run
    (the baseline included), their rows are not_run, and the work stays unfinished.
BUSINESS CONTEXT: Real runner CLI, real .claude/skills_config.json, real
    scripts/db_check checker; no server is needed. A non-database control test
    still runs ("non-database in-scope tests run as before"). Stand-in driver logs
    prove no connection to any address (the runner never picks one).
"""

from __future__ import annotations

import re
import sys

import unit_tests.build_orchestration._tq500g2ii_fixtures as fx

RAW_INVALID = "RAWVALUE-g2ii-not-an-address"
EXTRAS = [(fx.DB1, fx.WV_EXTRA)]
CREDENTIALED_URL = re.compile(r"postgres(?:ql)?://[^\s/]*@")


def _assert_test_rows_not_run(verdict, test: str, expect_in_detail: list[str]) -> None:
    found = fx.rows(verdict, test)
    assert found, f"{test} has no rows at all: {verdict['results']}"
    named = [r for r in found if r["wrong_version"] != fx.WV_EXTRA]
    extra = [r for r in found if r["wrong_version"] == fx.WV_EXTRA]
    assert {r["wrong_version"] for r in named} >= {"", fx.WV_DROP, fx.WV_UNDONE}, found
    for r in named:
        assert r["result"] == "not_run" and r["blocking"] is True, r
    # An extra of a blocked database test: one non-blocking not_run row, same status detail.
    want = sum(1 for t, _wv in EXTRAS if t == test)
    assert len(extra) == want, (test, "expected exactly one row per extra", extra)
    for r in extra:
        assert r["result"] == "not_run" and r["blocking"] is False, r
        assert r["detail"] == named[0]["detail"], (r, named[0])
    for r in found:
        for needle in expect_in_detail:
            assert needle in r["detail"].lower(), (needle, r)


def _assert_no_leak(proc, raw_value: str | None) -> None:
    out = fx.all_output(proc)
    assert fx.PASSWORD not in out, "the configured password must never be printed"
    assert not CREDENTIALED_URL.search(out), "no credentialed address may be printed"
    if raw_value is not None:
        assert raw_value not in out, "the raw configured value must never be printed"


def _assert_db_not_run(proj, proc, verdict, expect_in_detail: list[str], raw_value: str | None = None) -> None:
    for test in (fx.DB1, fx.DB2):
        _assert_test_rows_not_run(verdict, test, expect_in_detail)
    db_rows = [r for r in verdict["results"] if r["test"].endswith(("::" + fx.DB1, "::" + fx.DB2))]
    assert not [r for r in db_rows if r["result"] in ("caught", "survived")], db_rows
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished" and proc.returncode == 1, verdict
    ran = fx.ran_tests(proj)
    assert fx.PLAIN in ran, f"the non-database control test must still run: {ran}"
    assert fx.DB1 not in ran and fx.DB2 not in ran, f"database tests were selected into a pytest run: {ran}"
    assert fx.jsonl(proj.connlog) == [], "no run may connect to any address"
    assert [r["result"] for r in fx.rows(verdict, fx.PLAIN, fx.WV_DROP)] == ["caught"]
    _assert_no_leak(proc, raw_value)


def test_p2_not_configured_reports_not_run_and_unfinished(tmp_path):
    # covers: TQ-500g-2-ii, TQ-500g-2
    # angle: reachability
    # Entry point: python scripts/build_orchestration/wrong_version_runner.py run (subprocess).
    # Catches: 'not-configured database runs reported as passed', 'runner falls back to a
    # default address' (connection log), 'database tests run without the check' (run log).
    # Control: the non-database test runs and is caught, so not_run is not a blanket outcome.
    proj = fx.build_project(tmp_path, setting=None, extras=EXTRAS, with_plain=True)
    proc, verdict = fx.run_runner(proj)
    _assert_db_not_run(proj, proc, verdict, [fx.SETTING])


def test_p3_unreachable_reports_not_run(tmp_path):
    # covers: TQ-500g-2-ii
    # angle: failure
    # Catches: 'unreachable database read as caught' (a gate that ran the tests anyway
    # would log connections and give caught rows). Closed loopback port from the OS.
    proj = fx.build_project(tmp_path, setting=fx.address_for(fx.closed_port()), extras=EXTRAS, with_plain=True)
    proc, verdict = fx.run_runner(proj)
    _assert_db_not_run(proj, proc, verdict, ["could not be reached", fx.SETTING])
    port = proj.address.rsplit("@", 1)[1].split("/")[0].split(":")[1]
    for r in verdict["results"]:
        if r["test"].endswith(("::" + fx.DB1, "::" + fx.DB2)):
            for leak in ("127.0.0.1", f":{port}", "g2ii_db", "g2ii_user"):
                assert leak not in r["detail"], (f"detail leaks {leak!r} of the configured address", r)


def test_invalid_or_unreadable_setting_fails_closed(tmp_path):
    # covers: TQ-500g-2-ii
    # angle: failure
    # Catches: 'invalid setting treated as reachable'. The expected detail is the real
    # checker's own message for the same project, never the raw configured value.
    sys.path.insert(0, str(fx.SCRIPTS))
    from db_check.checker import check_test_db

    cases = {"invalid": dict(setting=RAW_INVALID), "config_error": dict(setting=None, config_text="{not json: " + RAW_INVALID)}
    for status, kwargs in cases.items():
        proj = fx.build_project(tmp_path / status, extras=EXTRAS, with_plain=True, **kwargs)
        report = check_test_db(proj.work)
        assert report["status"] == status, report
        proc, verdict = fx.run_runner(proj)
        _assert_db_not_run(proj, proc, verdict, [], raw_value=RAW_INVALID)
        for test in (fx.DB1, fx.DB2):
            for r in fx.rows(verdict, test):
                assert report["message"] in r["detail"] and status in r["detail"], (status, r)
