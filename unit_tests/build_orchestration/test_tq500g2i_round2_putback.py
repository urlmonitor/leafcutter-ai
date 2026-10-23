"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_round2_putback.py
GOAL: Second-review test of TQ-500g-2-i -- a put-back that cannot be verified ALWAYS stops the drive,
    also when the catalogue was already unreadable during the run itself.
BUSINESS CONTEXT: Real runner CLI (subprocess); the stand-in raises on every catalogue read, so the
    run's own captures AND the put-back's re-read are both unreadable. Two named wrong versions show
    that the second never runs.
"""

from __future__ import annotations

import json

import unit_tests.build_orchestration._tq500g2i_fixtures as fx
import unit_tests.build_orchestration._tq500g2i_review_fixtures as rv

TWO = [(fx.TEST, [fx.WV_DROP, fx.WV_OTHER])]
BOTH = {fx.WV_DROP: fx.WRONG_DROP, fx.WV_OTHER: fx.WRONG_OTHER}


def test_unreadable_in_run_and_in_re_read_stops_naming_the_object(tmp_path):
    # covers: TQ-500g-2-i
    # angle: discrimination
    # Catches: 'unreadable run captures excuse an unverifiable put-back to a note + reason unfinished'.
    # Control: the stand-in raised on catalogue reads (event logged) and no credential reaches the output.
    with fx.Listener() as db:
        address = fx.address_for(db.port)
        proj = rv.build(tmp_path, address=address, tests=TWO, wrongs=BOTH, fail_read=True)
        proc, verdict = fx.run_runner(proj)
    reason = str(verdict["reason"])
    assert verdict["gate_passed"] is False and proc.returncode != 0, verdict
    assert reason != "unfinished" and fx.FUNCTION in reason, f"expected a put-back stop naming the object, got {reason!r}"
    assert "the database was not put back" in reason, reason
    assert rv.calls(proj) == 2, f"baseline + the first wrong version only, got {rv.calls(proj)}"
    assert not rv.results_for(verdict, fx.WV_OTHER) and not rv.results_for(verdict, fx.WV_UNDONE), verdict["results"]
    assert not rv.leaked(address, db.port, json.dumps(verdict), proc.stdout, proc.stderr)
    assert len([e for e in fx.events(proj) if e.get("ev") == "read_raised"]) >= 2, "run and re-read both must have been unreadable"
