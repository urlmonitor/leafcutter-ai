"""
MODULE: unit_tests/build_orchestration/test_tq500g2ii_writer_list.py
GOAL: RED test for TQ-500g-2-ii -- the writer's ``list`` and the runner read the
    to-run-later extras through one reader, so they cannot drift.
BUSINESS CONTEXT: Real ``wrong_version_writer.py list`` piped against the real
    runner on the same project; the extras file is at
    <git-dir>/leafcutter/to-run-later/<ac-id>.json (user decision OQ-1 (A)).
"""

from __future__ import annotations

import unit_tests.build_orchestration._tq500g2ii_fixtures as fx


def test_writer_list_shows_extras_like_runner(tmp_path):
    # covers: TQ-500g-2-ii
    # angle: seam
    # Catches: 'writer list and runner read different extras'. Producer: writer list
    # output; consumer: the runner's rows. Control: the named version is owed and run too.
    with fx.Listener() as db:
        proj = fx.build_project(tmp_path, setting=fx.address_for(db.port), extras=[(fx.DB1, fx.WV_EXTRA), (fx.DB2, fx.WV_EXTRA)])
        listed_proc, listed = fx.run_writer_list(proj)
        assert listed_proc.returncode == 0 and listed["error"] is None, listed
        owed = {o["name"]: o for o in listed["owed"]}
        assert set(owed) == {fx.WV_DROP, fx.WV_EXTRA}, listed
        assert owed[fx.WV_EXTRA] == {"name": fx.WV_EXTRA, "files": ["refresh_config.py"], "scope": "derived",
                                     "blocking": False, "origin": "to_run_later"}, owed[fx.WV_EXTRA]
        assert owed[fx.WV_DROP]["scope"] == "derived" and "origin" not in owed[fx.WV_DROP]
        _proc, verdict = fx.run_runner(proj)
    ran_versions = {r["wrong_version"] for r in verdict["results"]} - {"", fx.WV_UNDONE}
    assert ran_versions == set(owed), f"runner ran {ran_versions}, list printed {set(owed)}"
    extra_rows = fx.rows(verdict, wv=fx.WV_EXTRA)
    assert sorted(r["test"] for r in extra_rows) == [fx.label(fx.DB1), fx.label(fx.DB2)]
    assert all(r["blocking"] is False for r in extra_rows)
