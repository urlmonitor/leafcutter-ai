"""
MODULE: unit_tests/build_orchestration/test_tq500g3i_finish_reach.py
GOAL: RED reachability test for TQ-500g-3-i: the sweep check sits on wrong_version_gate.py finish,
    the one entry every route dispatches before commit, FIRST, even with no --ac-ids.
BUSINESS CONTEXT: The CLIs run as subprocesses against a real scratch git repo; the lists are
    recorded through the real record step.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx


def test_sweep_check_through_finish(tmp_path: Path):
    # covers: TQ-500g-3-i
    # angle: reachability
    # must_catch: missing sweep list treated as complete
    # must_catch: finish ignores the sweep verdict
    # must_catch: sweep check skipped when --ac-ids is empty
    # (1) W1: the list leaves test_export.py and the fixture unlisted.
    w1 = fx.build(tmp_path / "w1")
    fx.recorded(w1, fx.W1_LIST, fx.W1_KEY)
    proc, out = fx.finish(w1, fx.W1_KEY)
    assert proc.returncode == 1 and out["gate_passed"] is False, (proc.returncode, out)
    assert out["stopped_at"] == "sweep", out
    assert out["writer"] is None and out["verdict"] is None, "the writer and the runner must not run after a sweep stop"
    assert isinstance(out.get("sweep"), dict) and out["sweep"]["passed"] is False, out.get("sweep")
    assert fx.pairs(out["sweep"]["unlisted"]) >= {(fx.EXPORT, "test_export_csv"), (fx.CONFTEST, fx.FIXTURE)}, out["sweep"]
    assert not fx.manifest_path(w1, fx.W1_KEY).exists(), "a sweep stop must write no wrong-version manifest"
    # (2) A changed existing test and no recorded list at all fails closed.
    nolist = fx.build(tmp_path / "nolist", edits=("refresh",))
    proc, out = fx.finish(nolist, "work-none")
    assert proc.returncode == 1 and out["gate_passed"] is False and out["stopped_at"] == "sweep", out
    assert isinstance(out.get("sweep"), dict) and out["sweep"]["reason"] == "sweep list missing", out.get("sweep")
    assert not fx.manifest_path(nolist, "work-none").exists()
    # (3) W2: the complete list goes on to the writer and the runner.
    w2 = fx.build(tmp_path / "w2")
    fx.recorded(w2, fx.W2_LIST, fx.W2_KEY)
    proc, out = fx.finish(w2, fx.W2_KEY)
    assert isinstance(out.get("sweep"), dict) and out["sweep"]["passed"] is True, out
    assert out["stopped_at"] is None and out["gate_passed"] is True and proc.returncode == 0, (proc.returncode, out)
    assert isinstance(out["writer"], dict) and out["writer"]["written"] is True, out["writer"]
    assert isinstance(out["verdict"], dict), out
    assert fx.manifest_path(w2, fx.W2_KEY).is_file(), "W2 goes on: the writer must have written its manifest"
