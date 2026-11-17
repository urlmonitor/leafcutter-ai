"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_failclosed.py
GOAL: RED tests for TQ-500g-2-i fail-closed paths -- a refused database put-back stops the
    drive, a missing driver or unreadable catalogue is "not_run", and no credential is shown.
BUSINESS CONTEXT: Real runner CLI as a subprocess; the stand-in PostgreSQL driver refuses an
    install (TQ_G2I_REFUSE), has no module (blocker dir) or raises with the address in its text
    (TQ_G2I_FAIL_READ). See _tq500g2i_fixtures.py.
"""

from __future__ import annotations

import unit_tests.build_orchestration._tq500g2i_fixtures as fx


def test_database_put_back_mismatch_stops_naming_object(tmp_path):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'database put-back mismatch ignored' (later wrong versions would still run).
    # Control: the stand-in refused (event logged), so the mismatch is real, not a fixture slip.
    with fx.Listener() as db:
        proj = fx.build_project(tmp_path, address=fx.address_for(db.port), source="altered", others=True, refuse=True)
        proc, verdict = fx.run_runner(proj)
    assert verdict["gate_passed"] is False and proc.returncode != 0, verdict
    assert fx.FUNCTION in str(verdict["reason"]), verdict["reason"]
    assert "127.0.0.1" not in str(verdict["reason"]) and fx.PASSWORD not in str(verdict["reason"])
    runs = [e for e in fx.events(proj) if e.get("ev") == "call"]
    assert len(runs) == 2, f"baseline + the first wrong version only; later ones must not run, got {len(runs)}"
    assert not fx.rows(verdict, fx.WV_OTHER) and not fx.rows(verdict, fx.WV_UNDONE), verdict["results"]
    assert any(e.get("ev") == "install_refused" for e in fx.events(proj)), "the stand-in never refused the re-install"


def test_no_driver_is_not_run_and_unfinished(tmp_path):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'missing driver read as caught'. The suite's own assertion fails under the wrong
    # version (kind: assertion), so only the catalogue step can stop it counting. Nothing was
    # installed, so there is nothing to put back and the drive is merely unfinished.
    # Control: D2 in the d1_d2 file is caught with a working driver.
    with fx.Listener() as db:
        proj = fx.build_project(tmp_path / "nodriver", address=fx.address_for(db.port), source="altered", no_driver=True)
        _proc, verdict = fx.run_runner(proj)
    found = fx.rows(verdict, fx.WV_DROP)
    assert [r["result"] for r in found] == ["not_run"], verdict["results"]
    assert found[0]["blocking"] is True and found[0]["detail"], found[0]
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished", verdict
    assert "no PostgreSQL driver importable in the test interpreter" in found[0]["detail"]


def test_unreadable_catalogue_stops_after_the_first_wrong_version(tmp_path):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'a put-back whose re-read fails is only a note when the run already could not read
    # the catalogue' (the drive would carry on over a database that may still hold wrong code).
    # Control: the stand-in did raise on a catalogue read; baseline + first wrong version ran.
    with fx.Listener() as db:
        address = fx.address_for(db.port)
        proj = fx.build_project(tmp_path / "badread", address=address, source="altered", others=True, fail_read=True)
        proc, verdict = fx.run_runner(proj)
    reason = str(verdict["reason"])
    assert verdict["gate_passed"] is False and proc.returncode != 0, verdict
    assert reason != "unfinished" and fx.FUNCTION in reason, f"the stop reason must name the object, got {reason!r}"
    assert "127.0.0.1" not in reason and fx.PASSWORD not in reason
    runs = [e for e in fx.events(proj) if e.get("ev") == "call"]
    assert len(runs) == 2, f"baseline + the first wrong version only, got {len(runs)}"
    assert not fx.rows(verdict, fx.WV_OTHER) and not fx.rows(verdict, fx.WV_UNDONE), verdict["results"]
    assert any(e.get("ev") == "read_raised" for e in fx.events(proj)), "the stand-in never raised on a catalogue read"


def test_credentials_never_in_verdict_or_logs(tmp_path):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'driver error text with the address copied into a row'. Control: the stand-in did
    # raise with the address in its text and was handed the password; the poller saw the plugin
    # output files (a non-empty private TEMP), so "absent" is not an artefact of looking nowhere.
    with fx.Listener() as db:
        address = fx.address_for(db.port)
        proj = fx.build_project(tmp_path / "proj", address=address, source="altered", fail_read=True)
        proc, verdict, files = fx.run_runner_watched(proj, tmp_path / "private_temp")
    events = fx.events(proj)
    leaks = (fx.PASSWORD, fx.USER, address, f"127.0.0.1:{db.port}")
    # every distinct snapshot of every temp file is scanned (none is overwritten by a later read)
    surfaces = {"stdout": proc.stdout, "stderr": proc.stderr,
                **{f"file {k} snapshot {i}": snap for k, snaps in files.items() for i, snap in enumerate(snaps)}}
    for name, text in surfaces.items():
        for leak in leaks:
            assert leak not in text, f"{leak!r} leaked into {name}"
    assert [r["result"] for r in fx.rows(verdict, fx.WV_DROP)] == ["not_run"], verdict["results"]
    assert any(e.get("ev") == "read_raised" for e in events), "the stand-in never raised"
    assert any(fx.PASSWORD in str(e.get("address", "")) for e in events if e.get("ev") == "connect")
    assert any(snap for snaps in files.values() for snap in snaps), "no runner temporary file content was seen in the private TEMP"
