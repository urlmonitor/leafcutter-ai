"""
MODULE: unit_tests/build_orchestration/test_tq500g2ii_notes.py
GOAL: RED test for TQ-500g-2-ii -- a to-run-later source the runner cannot use gives one
    non-blocking note row naming it; it is never dropped silently and never blocks.
BUSINESS CONTEXT: Real runner CLI on a real project; the unusable source is
    a malformed file. (An id failing the plain-id rule is already a blocking `invalid`
    row from the AC lookup, so it cannot reach the to-run-later reader.)
"""

from __future__ import annotations

import unit_tests.build_orchestration._tq500g2ii_fixtures as fx

def test_unusable_to_run_later_source_gives_one_non_blocking_note(tmp_path):
    # covers: TQ-500g-2-ii
    # angle: failure
    # Catches: 'unreadable or malformed to-run-later source dropped silently' and
    # 'unusable source stops the work'. Control: the same run without the bad source passes.
    with fx.Listener() as db:
        control = fx.build_project(tmp_path / "ok", setting=fx.address_for(db.port), tests=(fx.DB1, fx.DB2))
        _cproc, cv = fx.run_runner(control)
        assert cv["gate_passed"] is True and not [r for r in cv["results"] if r["result"] == "not_in_scope"], cv

        malformed = fx.build_project(tmp_path / "mal", setting=fx.address_for(db.port), tests=(fx.DB1, fx.DB2))
        malformed.to_run_later.parent.mkdir(parents=True, exist_ok=True)
        malformed.to_run_later.write_text("{not json", encoding="utf-8")
        mproc, mv = fx.run_runner(malformed)
        mnotes = [r for r in mv["results"] if fx.AC_ID in r["test"] and r["result"] == "not_in_scope"]
        assert len(mnotes) == 1 and mnotes[0]["blocking"] is False, (mnotes, mv["results"])
        assert mv["gate_passed"] is True and mproc.returncode == 0, mv
