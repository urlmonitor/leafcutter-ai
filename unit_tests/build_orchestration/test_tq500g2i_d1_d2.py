"""
MODULE: unit_tests/build_orchestration/test_tq500g2i_d1_d2.py
GOAL: RED tests for TQ-500g-2-i D1 / D2 -- a database run in which the suite quietly re-installs
    the correct code is "invalid"; one in which the database held the wrong version is valid.
BUSINESS CONTEXT: Driven only through the real runner CLI (subprocess) over a scratch git
    project; the one stand-in is the PostgreSQL driver (see _tq500g2i_fixtures.py).
"""

from __future__ import annotations

import unit_tests.build_orchestration._tq500g2i_fixtures as fx

REDEPLOY = "the suite put the correct code back before the tests ran"


def test_d1_suite_redeployed_correct_code_reported_invalid(tmp_path):
    # covers: TQ-500g-2-i
    # angle: criterion
    # Catches: 'runner trusts the source-file alteration without reading the catalogue' (the row
    # would read "survived"), 'invalid run counted as caught/survived'. Control: D2 below is valid.
    with fx.Listener() as db:
        proj = fx.build_project(tmp_path, address=fx.address_for(db.port), source="unaltered")
        proc, verdict = fx.run_runner(proj)
    found = fx.rows(verdict, fx.WV_DROP)
    assert [r["result"] for r in found] == ["invalid"], f"D1 rows: {verdict['results']}"
    assert found[0]["blocking"] is True
    assert REDEPLOY in found[0]["detail"] and fx.FUNCTION in found[0]["detail"], found[0]
    assert verdict["survivors"] == [], "an invalid run is never a survivor"
    assert not [r for r in verdict["results"] if r["result"] == "caught" and r["wrong_version"] == fx.WV_DROP]
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished" and proc.returncode != 0, verdict
    assert any(u["wrong_version"] == fx.WV_DROP and u["result"] == "invalid" for u in verdict["unfinished"]), verdict["unfinished"]


def _call_window(events: list[dict], nth_call: int) -> tuple[list[dict], dict]:
    """The events from the nth ``call`` to the next ``teardown``, and that ``call`` event."""
    calls = [i for i, e in enumerate(events) if e.get("ev") == "call"]
    start = calls[nth_call]
    end = next(i for i in range(start, len(events)) if events[i].get("ev") == "teardown")
    return events[start + 1:end], events[start]


def test_d2_database_held_wrong_version_is_valid(tmp_path):
    # covers: TQ-500g-2-i
    # angle: discrimination
    # Catches: 'every database run marked invalid' (the row would not be caught), and a catalogue
    # read taken at the wrong time (before the call phase, or after teardown) or on the suite's own
    # connection. Control: D1 above is invalid for the same test over the same detector.
    with fx.Listener() as db:
        proj = fx.build_project(tmp_path, address=fx.address_for(db.port), source="altered")
        proc, verdict = fx.run_runner(proj)
    found = fx.rows(verdict, fx.WV_DROP)
    assert [r["result"] for r in found] == ["caught"], f"D2 rows: {verdict['results']}"
    assert not [r for r in verdict["results"] if r["result"] == "invalid"], verdict["results"]
    assert verdict["gate_passed"] is True and proc.returncode == 0, verdict
    events = fx.events(proj)
    inside, call = _call_window(events, 1)  # call 0 is the baseline, call 1 the wrong-version run
    reads = [e for e in inside if e.get("ev") == "catalog_read"]
    assert len(reads) == 1, f"one catalogue read between the call phase and the teardown, got {inside}"
    assert reads[0]["conn"] != call["conn"], "the plugin reads on its own connection, not the suite's"


def test_put_back_restores_source_file_and_database(tmp_path):
    # covers: TQ-500g-2-i
    # angle: failure
    # Catches: 'put-back restores the file but leaves the database holding the wrong version'.
    # Control: the D2 run really left the wrong version in the catalogue (a wrong install happened).
    with fx.Listener() as db:
        for name, source in (("d1", "unaltered"), ("d2", "altered")):
            proj = fx.build_project(tmp_path / name, address=fx.address_for(db.port), source=source)
            fx.run_runner(proj)
            assert fx.source_bytes(proj) == fx.AS_WRITTEN.encode("utf-8"), f"{name}: source file not put back"
            assert fx.normal(fx.catalogue_text(proj)) == fx.normal(fx.AS_WRITTEN), f"{name}: database holds {fx.catalogue_text(proj)!r}"
            if source == "altered":
                wrong = [e for e in fx.events(proj) if e.get("ev") == "install" and e.get("wrong")]
                assert wrong, "D2 never installed the wrong version, so the put-back proves nothing"
