"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_review_install.py
GOAL: Review-fix tests M-1 and M-5 of TQ-500g-2-i -- the baseline needs a working install too, and
    an install source holding ``%`` installs through every driver module.
BUSINESS CONTEXT: Real runner CLI (subprocess) over the d1_d2 project; the stand-in driver is
    importable as psycopg2, psycopg or pg8000 (the earlier modules are blocked), and its opt-in
    switches make the plugin's install fail or behave like pg8000's format paramstyle.
"""

from __future__ import annotations

import pytest

import unit_tests.build_orchestration._tq500g2i_fixtures as fx
import unit_tests.build_orchestration._tq500g2i_review_fixtures as rv


@pytest.mark.parametrize("how", ["no_driver", "install_fails"])
def test_m1_baseline_without_a_working_install_is_not_run_not_ok(tmp_path, how):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'the baseline is read only from the suite's own outcome' -- the suite installs its own copy
    # and passes, so a baseline in which the plugin could install nothing (no driver, install raised) read
    # as ok and the wrong-version runs went on over a database the runner could not control.
    # Control: the stand-in did refuse / the driver was blocked, and the suite's test did run once.
    with fx.Listener() as db:
        proj = rv.build(tmp_path, address=fx.address_for(db.port), driver=None if how == "no_driver" else "psycopg2")
        if how == "install_fails":
            proj.extra_env["TQ_G2I_PLUGIN_INSTALL_FAIL"] = "1"
        proc, verdict = fx.run_runner(proj)
    baseline = [r for r in verdict["results"] if r["wrong_version"] == "" and r["test"].endswith("::" + fx.TEST)]
    assert [r["result"] for r in baseline] == ["not_run"], f"{how}: baseline rows {baseline}; all: {verdict['results']}"
    assert baseline[0]["blocking"] is True and baseline[0]["detail"], baseline[0]
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished" and proc.returncode != 0, f"{how}: {verdict}"
    assert not [r for r in verdict["results"] if r["result"] in ("caught", "survived")], f"{how}: {verdict['results']}"
    assert rv.calls(proj) == 1, f"{how}: only the baseline run may have happened, got {rv.calls(proj)} test calls"
    if how == "install_fails":
        assert any(e.get("ev") == "install_failed_by_standin" for e in fx.events(proj)), "the stand-in never failed an install"


@pytest.mark.parametrize("driver", list(rv.DRIVERS))
def test_m5_install_source_with_percent_installs_through_every_driver(tmp_path, driver):
    # covers: TQ-500g-2-i
    # angle: boundary
    # Catches: 'execute(text) with no params argument' -- a pg8000-like driver (format paramstyle) reads the
    # % of RAISE NOTICE '%' / format('%s') as a placeholder; the install then fails and the run reads not_run.
    # Control: the same source installs from the suite itself (no params needed there) and the wrong version
    # is caught, so only the plugin's execute call differs.
    wrongs = {fx.WV_DROP: rv.PCT_WRONG}
    with fx.Listener() as db:
        proj = rv.build(tmp_path, address=fx.address_for(db.port), base_sql=rv.PCT_BASE, written_sql=rv.PCT_WRITTEN,
                        wrongs=wrongs, driver=driver)
        proj.extra_env["TQ_G2I_PARAMSTYLE"] = "format"
        proc, verdict = fx.run_runner(proj)
    events = fx.events(proj)
    assert not [e for e in events if e.get("ev") == "percent_refused"], f"{driver}: a % text was executed without params"
    found = fx.rows(verdict, fx.WV_DROP)
    assert [r["result"] for r in found] == ["caught"], f"{driver}: {verdict['results']}"
    assert verdict["gate_passed"] is True and proc.returncode == 0, f"{driver}: {verdict}"
    assert any(e.get("ev") == "install" and e.get("wrong") for e in events), f"{driver}: the wrong version was never installed"
