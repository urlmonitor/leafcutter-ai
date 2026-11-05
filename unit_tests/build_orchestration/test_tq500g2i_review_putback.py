"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_review_putback.py
GOAL: Review-fix tests H-2 and M-2 of TQ-500g-2-i -- a database put-back that cannot be verified
    stops the drive like a failed one, and two failed put-backs are both reported.
BUSINESS CONTEXT: Real runner CLI (subprocess) over the d1_d2 project with two named wrong versions,
    so "later wrong versions are not run" is read from the stand-in's call log. The ``put-back``
    subprocess of the plugin is made to misbehave by the stand-in's ``TQ_G2I_PUTBACK`` switch.
"""

from __future__ import annotations

import json

import pytest

import unit_tests.build_orchestration._tq500g2i_fixtures as fx
import unit_tests.build_orchestration._tq500g2i_review_fixtures as rv

TWO = [(fx.TEST, [fx.WV_DROP, fx.WV_OTHER])]
BOTH = {fx.WV_DROP: fx.WRONG_DROP, fx.WV_OTHER: fx.WRONG_OTHER}
DB_MESSAGE = "the database was not put back"
FILE_MESSAGE = "the code may still be altered"


@pytest.mark.parametrize("mode", ["crash", "noparse", "notobject", "readfail"])
def test_h2_unverifiable_put_back_stops_the_drive(tmp_path, mode):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'a put-back that printed nothing parseable / printed a non-object / could not re-read the
    # catalogue is only a note' (the drive carries on with the next wrong version over a database that may
    # still hold the wrong code), and 'a last line that is JSON but not an object raises AttributeError'.
    # Control: the stand-in did misbehave (event logged) and only the first wrong version ran.
    with fx.Listener() as db:
        address = fx.address_for(db.port)
        proj = rv.build(tmp_path, address=address, tests=TWO, wrongs=BOTH)
        proj.extra_env["TQ_G2I_PUTBACK"] = mode
        proc, verdict = fx.run_runner(proj)
    reason = str(verdict["reason"])
    assert verdict["gate_passed"] is False and proc.returncode != 0, f"{mode}: {verdict}"
    assert fx.FUNCTION in reason, f"{mode}: the stop reason must name the object, got {reason!r}"
    assert "internal error" not in reason and "AttributeError" not in reason, f"{mode}: {reason!r}"
    assert rv.calls(proj) == 2, f"{mode}: baseline + the first wrong version only, got {rv.calls(proj)}"
    assert not rv.results_for(verdict, fx.WV_OTHER) and not rv.results_for(verdict, fx.WV_UNDONE), verdict["results"]
    assert not rv.leaked(address, db.port, json.dumps(verdict), proc.stdout, proc.stderr), f"{mode}: credentials in the output"
    marker = {"crash": "putback_crash", "noparse": "putback_noparse", "notobject": "putback_notobject", "readfail": "read_raised"}[mode]
    assert any(e.get("ev") == marker for e in fx.events(proj)), f"{mode}: the stand-in never misbehaved ({marker})"


def test_m2_failed_file_restore_and_failed_database_put_back_are_both_reported(tmp_path):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'the database message replaces the file message' (the file that may still be altered is
    # then not named, and the user is told only about the database). Control: the stand-in deleted the gate
    # copy (file restore cannot compare) AND refused the correct re-install (database put-back mismatch).
    with fx.Listener() as db:
        proj = rv.build(tmp_path, address=fx.address_for(db.port), refuse=True)
        proj.extra_env["TQ_G2I_BREAK_RESTORE"] = str(rv.gate_dir(proj))
        proc, verdict = fx.run_runner(proj)
    events = fx.events(proj)
    assert any(e.get("ev") == "restore_broken" for e in events), "the stand-in never removed a gate copy"
    assert any(e.get("ev") == "install_refused" for e in events), "the stand-in never refused the re-install"
    reason = str(verdict["reason"])
    assert verdict["gate_passed"] is False and proc.returncode != 0, verdict
    assert DB_MESSAGE in reason and FILE_MESSAGE in reason, f"both put-back failures must be reported: {reason!r}"
