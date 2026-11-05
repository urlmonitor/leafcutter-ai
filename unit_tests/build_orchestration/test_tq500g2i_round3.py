"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_round3.py
GOAL: TQ-500g-2-i -- a catalogue that cannot be read DURING a wrong-version run is "not_run", never "caught".
BUSINESS CONTEXT: Real runner CLI as a subprocess. The stand-in (TQ_G2I_FAIL_READ=run) fails the plugin's
    per-test catalogue reads in the pytest child, while the put-back re-read succeeds (a transient failure),
    so the drive does not stop on an unverifiable put-back and the run's own row is what is judged.
"""

from __future__ import annotations

import unit_tests.build_orchestration._tq500g2i_fixtures as fx


def test_transient_run_read_failure_is_not_run_not_caught(tmp_path):
    # covers: TQ-500g-2-i
    # angle: discrimination
    # Catches: 'missing driver or unreadable catalogue read as caught' (an unreadable capture keeping the
    # suite's own result, which is a failed assertion = caught). Reads fail only in the run, so the put-back
    # verifies ok and no stop row can mask the run's own row.
    # Control: the stand-in raised in the run (read_raised) and the put-back re-read did succeed.
    with fx.Listener() as db:
        address = fx.address_for(db.port)
        proj = fx.build_project(tmp_path / "proj", address=address, source="altered")
        proj.extra_env["TQ_G2I_FAIL_READ"] = "run"
        proc, verdict = fx.run_runner_watched(proj, tmp_path / "private_temp")[:2]
    events = fx.events(proj)
    found = fx.rows(verdict, fx.WV_DROP)
    assert [r["result"] for r in found] == ["not_run"], verdict["results"]
    assert found[0]["blocking"] is True and found[0]["detail"], found[0]
    assert "caught" not in [r["result"] for r in verdict["results"]], verdict["results"]
    assert any(e.get("ev") == "read_raised" for e in events), "the stand-in never failed a read in the run"
    reads = [e for e in events if e.get("ev") == "catalog_read"]
    assert len([e for e in events if e.get("ev") == "read_raised"]) < len(reads), "the put-back re-read must succeed"
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished", verdict
    text = proc.stdout + proc.stderr + str(verdict)
    for leak in (fx.PASSWORD, fx.USER, address, f"127.0.0.1:{db.port}"):
        assert leak not in text, f"{leak!r} leaked"
