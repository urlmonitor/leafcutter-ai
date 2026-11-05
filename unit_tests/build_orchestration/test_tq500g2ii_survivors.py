"""
MODULE: unit_tests/build_orchestration/test_tq500g2ii_survivors.py
GOAL: RED test for TQ-500g-2-ii -- an extra's survivor is reported, never blocking;
    a named version's survivor still blocks; a same-named extra stays blocking.
BUSINESS CONTEXT: Pins user decision Q2 in both directions through the real runner CLI.
"""

from __future__ import annotations

import unit_tests.build_orchestration._tq500g2ii_fixtures as fx

NB = "non_blocking_survivors"


def _run(root, tests, extras):
    with fx.Listener() as db:
        proj = fx.build_project(root, setting=fx.address_for(db.port), tests=tests, extras=extras)
        return fx.run_runner(proj)


def test_extra_survivor_reported_but_not_blocking(tmp_path):
    # covers: TQ-500g-2-ii
    # angle: discrimination
    # Catches: "writer's extra wrong versions block the work" (A: gate must pass),
    # 'named-version survivor made non-blocking' (B: DB3 must stop the work),
    # 'extra named like a must_catch name downgrades it to non-blocking' (C).
    # Control: B/C share A's surviving extra row and the caught DB1/DB2 rows.
    a_proc, a = _run(tmp_path / "a", (fx.DB1, fx.DB2), [(fx.DB1, fx.WV_EXTRA)])
    survived = fx.rows(a, fx.DB1, fx.WV_EXTRA)
    assert [r["result"] for r in survived] == ["survived"] and survived[0]["blocking"] is False, a["results"]
    assert a[NB] == [{"test": fx.label(fx.DB1), "wrong_version": fx.WV_EXTRA}]
    assert a["survivors"] == [] and a["gate_passed"] is True and a_proc.returncode == 0, a

    b_proc, b = _run(tmp_path / "b", (fx.DB1, fx.DB2, fx.DB3), [(fx.DB1, fx.WV_EXTRA)])
    assert b["survivors"] == [{"test": fx.label(fx.DB3), "wrong_version": fx.WV_DROP}], b["survivors"]
    assert b[NB] == [{"test": fx.label(fx.DB1), "wrong_version": fx.WV_EXTRA}]
    assert b["gate_passed"] is False and b["reason"] == "survivor" and b_proc.returncode == 1
    named = fx.rows(b, fx.DB3, fx.WV_DROP)
    assert [r["blocking"] for r in named] == [True], named

    spelled = "  Drop the RETRY_due condition "
    c_proc, c = _run(tmp_path / "c", (fx.DB1, fx.DB2, fx.DB3), [(fx.DB3, spelled)])
    assert c["survivors"] == [{"test": fx.label(fx.DB3), "wrong_version": fx.WV_DROP}], c["survivors"]
    assert c[NB] == [], c.get(NB)
    drop_rows = [r for r in fx.rows(c, fx.DB3) if r["wrong_version"] not in ("", fx.WV_UNDONE)]
    assert [(r["wrong_version"], r["blocking"]) for r in drop_rows] == [(fx.WV_DROP, True)], drop_rows
    assert c["gate_passed"] is False and c_proc.returncode == 1


def test_non_blocking_survivors_always_present_without_to_run_later_file(tmp_path):
    # covers: TQ-500g-2-ii
    # angle: boundary
    # Catches: 'non_blocking_survivors emitted only when a to-run-later file was read'.
    # Boundary: no file at all (and a survivor-free pass) still carries the key, as [].
    with fx.Listener() as db:
        proj = fx.build_project(tmp_path, setting=fx.address_for(db.port), tests=(fx.DB1, fx.DB2))
        assert not proj.to_run_later.exists()
        proc, verdict = fx.run_runner(proj)
    assert NB in verdict, sorted(verdict)
    assert verdict[NB] == [], verdict[NB]
    assert verdict["gate_passed"] is True and proc.returncode == 0, verdict
