"""
MODULE: unit_tests/build_orchestration/test_tq500g3ii_weakened.py
GOAL: RED tests for TQ-500g-3-ii: what the base-vs-now pytest runs report as weakened / removed.
BUSINESS CONTEXT: Real scratch git repos, real pytest on both sides, the real consumer_sweep.py
    record / check CLIs. Edits to existing tests are recorded as strengthened so TQ-500g-3-i passes.
"""

from __future__ import annotations

import json
from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3ii_fixtures as ix

PARAM_BASE = ("import pytest\n\n\n@pytest.mark.parametrize('n', [1, 2, 3])\n"
              "def test_square_positive(n):\n    assert n * n > 0\n")


def test_skip_xfail_and_removed_tests_reported_weakened(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: criterion
    # must_catch: skip mark added to an existing test not detected
    # must_catch: deleted test missed because only surviving node ids are compared
    # must_catch: XFAIL read as passed
    work = {ix.REFRESH: lambda t: ix.strengthen_d(ix.skip_a(t)), ix.RETRY: ix.xfail_b, ix.EXPORT: ix.drop_c,
            ix.LEGACY: ix.drop_e}
    repo = ix.scenario(tmp_path, work)
    fx.recorded(repo, [ix.listed(ix.REFRESH, ix.A), ix.listed(ix.REFRESH, ix.D), ix.listed(ix.RETRY, ix.B),
                       ix.listed(ix.EXPORT, ix.C), ix.listed(ix.LEGACY, ix.E, "removed", ix.E_NOTE)])
    proc, out = ix.run_check(repo)
    fx.assert_check_shape(proc, out)
    assert out["unlisted"] == [], f"TQ-500g-3-i must pass here so only the runs decide: {out['unlisted']}"
    assert ix.whats(out) == {ix.A: "skipped", ix.B: "expected to fail", ix.C: "removed"}, out["weakened"]
    assert out["passed"] is False and proc.returncode == 1, (proc.returncode, out)
    assert fx.pairs(out["weakened"]) == {(ix.REFRESH, ix.A), (ix.RETRY, ix.B), (ix.EXPORT, ix.C)}, out["weakened"]
    assert all(i["nodeid"].startswith(i["file"] + "::") for i in out["weakened"]), out["weakened"]


def test_strengthened_test_not_reported(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: discrimination
    # must_catch: any change to an existing test reported as weakened
    repo = ix.scenario(tmp_path, {ix.REFRESH: lambda t: ix.strengthen_d(ix.skip_a(t))})
    fx.recorded(repo, [ix.listed(ix.REFRESH, ix.A), ix.listed(ix.REFRESH, ix.D)])
    proc, out = ix.run_check(repo)
    fx.assert_check_shape(proc, out)
    # control row: A (skipped) is reported -- so the runs ran -- while D (assertion added, still passing) is not.
    assert ix.whats(out) == {ix.A: "skipped"}, out["weakened"]
    assert all(i["test"] != ix.D for i in out["weakened"] + out["removed"] + out["unlisted"]), out
    # D alone: strengthened, nothing weakened, the check passes.
    solo = ix.scenario(tmp_path / "solo", {ix.REFRESH: ix.strengthen_d})
    fx.recorded(solo, [ix.listed(ix.REFRESH, ix.D)])
    proc, out = ix.run_check(solo)
    fx.assert_check_shape(proc, out)
    assert out["applicable"] is True and out["passed"] is True, out
    assert out["weakened"] == [] and out["removed"] == [] and out["inconclusive"] == [], out


def test_removed_with_listed_reason_is_not_weakened(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: boundary
    # must_catch: removal exit granted without a recorded reason
    # must_catch: removed entry excuses a skipped test
    # (1) E deleted and recorded as removed with a reason: removed, with that reason, not weakened.
    repo = ix.scenario(tmp_path / "e", {ix.LEGACY: ix.drop_e})
    fx.recorded(repo, [ix.listed(ix.LEGACY, ix.E, "removed", ix.E_NOTE)])
    proc, out = ix.run_check(repo)
    fx.assert_check_shape(proc, out)
    assert [(r["file"], r["test"], r["reason"]) for r in out["removed"]] == [(ix.LEGACY, ix.E, ix.E_NOTE)], out
    assert out["weakened"] == [] and out["passed"] is True, out
    # (2) the same deletion with no 'removed' entry is weakened (removed), with no reason to give.
    bare = ix.scenario(tmp_path / "bare", {ix.LEGACY: ix.drop_e})
    fx.recorded(bare, [ix.listed(ix.LEGACY, "test_legacy_noop", "unaffected")])
    proc, out = ix.run_check(bare)
    fx.assert_check_shape(proc, out)
    assert ix.whats(out) == {ix.E: "removed"} and out["removed"] == [] and out["passed"] is False, out
    # (3) a 'removed' entry excuses absence only: a skip mark on a surviving test is still weakened.
    skip = ix.scenario(tmp_path / "skip", {ix.LEGACY: lambda t: ix.sub(t, f"def {ix.E}", f"{ix.SKIP_MARK}def {ix.E}")})
    fx.recorded(skip, [ix.listed(ix.LEGACY, ix.E, "removed", ix.E_NOTE)])
    proc, out = ix.run_check(skip)
    fx.assert_check_shape(proc, out)
    assert ix.whats(out) == {ix.E: "skipped"} and out["removed"] == [] and out["passed"] is False, out
    # (4) the stored list can be altered outside `record` (hand-edited, corrupted): a 'removed' entry whose
    # note is empty, whitespace-only or missing grants no exit -- E stays weakened (removed), no reason given.
    for label, alter in (("empty", lambda e: e.update(note="")), ("blank", lambda e: e.update(note="  	 ")),
                         ("missing", lambda e: e.pop("note"))):
        alt = ix.scenario(tmp_path / f"alt_{label}", {ix.LEGACY: ix.drop_e})
        fx.recorded(alt, [ix.listed(ix.LEGACY, ix.E, "removed", ix.E_NOTE)])
        stored = alt.git_dir() / "leafcutter" / "work" / fx.W1_KEY / "consumer_sweep.json"
        data = json.loads(stored.read_bytes().decode("utf-8"))
        hit = [e for e in data["entries"] if e.get("status") == "removed"]
        assert len(hit) == 1, data
        alter(hit[0])
        stored.write_bytes(json.dumps(data, indent=2).encode("utf-8"))
        proc, out = ix.run_check(alt)
        fx.assert_check_shape(proc, out)
        assert ix.whats(out) == {ix.E: "removed"}, (label, out)
        assert out["removed"] == [] and out["passed"] is False and proc.returncode == 1, (label, out)


def test_dropped_parametrize_case_reported_weakened(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: boundary
    # must_catch: comparison by function name hides a dropped parametrize case
    repo = ix.scenario(tmp_path, {ix.PARAM: lambda t: ix.sub(t, "[1, 2, 3]", "[1, 2]")}, base={ix.PARAM: PARAM_BASE})
    fx.recorded(repo, [ix.listed(ix.PARAM, "test_square_positive")])
    proc, out = ix.run_check(repo)
    fx.assert_check_shape(proc, out)
    assert [(i["nodeid"], i["what"]) for i in out["weakened"]] == [
        (f"{ix.PARAM}::test_square_positive[3]", "removed")], out["weakened"]
    assert out["passed"] is False and proc.returncode == 1, (proc.returncode, out)
