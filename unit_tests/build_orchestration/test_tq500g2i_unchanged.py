"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_unchanged.py
GOAL: RED test for TQ-500g-2-i -- a run that alters only a .py file over tests without
    requires_db gives the same verdict as before and contacts no database.
BUSINESS CONTEXT: Reuses the TQ-500g-2-ii sandbox (a .py fix, PLAIN control test with
    requires_db false) with a REACHABLE configured database and a logging stand-in driver, so
    "no database contacted" is read from the driver's log. The seam is the new plugin module:
    it must ship beside the runner yet stay dormant for this run.
"""

from __future__ import annotations

import subprocess
import sys

import unit_tests.build_orchestration._tq500g2ii_fixtures as fx2

VERDICT_KEYS = {"gate_passed", "applicable", "verified", "outcome", "reason", "results", "survivors", "unfinished",
                "non_blocking_survivors"}


def test_run_without_sql_alteration_is_unchanged(tmp_path):
    # covers: TQ-500g-2-i
    # angle: seam
    # Catches: a plugin that is loaded or a database that is contacted on every run (connection
    # log non-empty), a changed verdict shape (key set) or result words. Also pins that the plugin
    # module exists to be loaded: a fresh interpreter must import it from the runner's directory.
    with fx2.Listener() as db:
        proj = fx2.build_project(tmp_path, setting=fx2.address_for(db.port), tests=(), with_plain=True)
        proc, verdict = fx2.run_runner(proj)
    assert set(verdict) == VERDICT_KEYS, set(verdict) ^ VERDICT_KEYS
    got = sorted((r["test"].split("::")[-1], r["wrong_version"], r["result"], r["blocking"]) for r in verdict["results"])
    assert got == sorted([(fx2.PLAIN, fx2.WV_DROP, "caught", False), (fx2.PLAIN, fx2.WV_UNDONE, "caught", False)]), got
    assert verdict["gate_passed"] is True and verdict["reason"] is None and proc.returncode == 0, verdict
    assert fx2.jsonl(proj.connlog) == [], "a run without database tests must not contact the database"
    assert fx2.ran_tests(proj) == [fx2.PLAIN] * 3, "baseline + the named wrong version + the fix undone"
    check = [sys.executable, "-c", "import _wvr_db_plugin"]
    fresh = subprocess.run(check, capture_output=True, text=True, timeout=60, cwd=fx2.SCRIPTS / "build_orchestration")
    assert fresh.returncode == 0, f"the plugin module is not importable cold: {fresh.stderr[-300:]}"
