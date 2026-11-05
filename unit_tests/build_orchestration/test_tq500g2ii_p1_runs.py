"""
MODULE: unit_tests/build_orchestration/test_tq500g2ii_p1_runs.py
GOAL: RED tests for TQ-500g-2-ii P1 -- database tests are held to the named wrong
    version, "the fix undone" and the writer's extra, on the configured database only.
BUSINESS CONTEXT: Driven only through the real runner CLI (subprocess); see
    _tq500g2ii_fixtures.py. DB1 gives (True, False), DB2 gives (True, None): the
    extra "treat a NULL retry_due as true" survives DB1 and is caught by DB2.
"""

from __future__ import annotations

import unit_tests.build_orchestration._tq500g2ii_fixtures as fx


def test_p1_named_undone_and_extra_versions_run_on_configured_database(tmp_path):
    # covers: TQ-500g-2-ii
    # angle: criterion
    # Catches: 'extra wrong versions silently dropped' (no extra rows), 'database tests left
    # out of the runs' (no rows / no connections), a runner that connects elsewhere.
    # Control: the same DB tests are caught under the named version and the fix undone.
    with fx.Listener() as db:
        proj = fx.build_project(tmp_path, setting=fx.address_for(db.port), extras=[(fx.DB1, fx.WV_EXTRA), (fx.DB2, fx.WV_EXTRA)])
        proc, verdict = fx.run_runner(proj)
    for test in (fx.DB1, fx.DB2):
        for wv in (fx.WV_DROP, fx.WV_UNDONE):
            found = fx.rows(verdict, test, wv)
            assert [r["result"] for r in found] == ["caught"], f"{test} under {wv}: {found}"
    db1 = fx.rows(verdict, fx.DB1, fx.WV_EXTRA)
    db2 = fx.rows(verdict, fx.DB2, fx.WV_EXTRA)
    assert [r["result"] for r in db1] == ["survived"], f"extra rows for DB1: {verdict['results']}"
    assert [r["result"] for r in db2] == ["caught"], f"extra rows for DB2: {verdict['results']}"
    assert db1[0]["blocking"] is False and db2[0]["blocking"] is False
    assert verdict["survivors"] == []
    assert verdict["non_blocking_survivors"] == [{"test": fx.label(fx.DB1), "wrong_version": fx.WV_EXTRA}]
    assert verdict["gate_passed"] is True and proc.returncode == 0, verdict
    connections = [e["address"] for e in fx.jsonl(proj.connlog)]
    assert len(connections) == 8, f"baseline + 3 wrong-version runs x 2 DB tests, got {connections}"
    assert set(connections) == {proj.address}
