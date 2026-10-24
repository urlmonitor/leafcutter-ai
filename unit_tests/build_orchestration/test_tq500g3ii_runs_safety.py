"""
MODULE: unit_tests/build_orchestration/test_tq500g3ii_runs_safety.py
GOAL: RED tests for TQ-500g-3-ii: an inconclusive run stops, the base run leaves the work untouched,
    and the decision comes from the runs through wrong_version_gate.py finish.
BUSINESS CONTEXT: Real scratch git repos, real pytest on both sides, the real CLIs as subprocesses.
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500g3i_fixtures as fx
import unit_tests.build_orchestration._tq500g3ii_fixtures as ix

TIMEOUT_ENV = "LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS"
SLEEP_BASE = {ix.RETRY: f"import time\n\n\ndef {ix.B}():\n    time.sleep(12)\n    assert 5 == 5\n"}


def test_inconclusive_run_stops_never_passes(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: failure
    # must_catch: timed-out base run read as nothing weakened
    # must_catch: collection failure read as nothing weakened
    # (1) the base run is slow and the budget tiny: the run times out.
    slow = ix.scenario(tmp_path / "slow", {ix.RETRY: lambda t: ix.sub(t, "    time.sleep(12)\n", "")}, base=SLEEP_BASE)
    fx.recorded(slow, [ix.listed(ix.RETRY, ix.B)])
    proc, out = ix.run_check(slow, {TIMEOUT_ENV: "2"})
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and proc.returncode == 1, (proc.returncode, out)
    assert ix.RETRY in {i["file"] for i in out["inconclusive"]}, out["inconclusive"]
    assert all(i["detail"] for i in out["inconclusive"]) and out["weakened"] == [], out
    # (2) a working-tree file that no longer collects: inconclusive, not "nothing weakened".
    broken = ix.scenario(tmp_path / "broken", {ix.RETRY: lambda t: "import no_such_module_tq500g3ii\n\n\n" + t})
    fx.recorded(broken, [ix.listed(ix.RETRY, ix.B), ix.listed(ix.RETRY, "import:no_such_module_tq500g3ii")])
    proc, out = ix.run_check(broken)
    fx.assert_check_shape(proc, out)
    assert out["passed"] is False and proc.returncode == 1, (proc.returncode, out)
    assert ix.RETRY in {i["file"] for i in out["inconclusive"]}, out["inconclusive"]
    assert out["reason"] == "inconclusive", out["reason"]


def test_base_run_leaves_worktree_untouched(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: real_artifact
    # must_catch: base run checks out or stashes in the working tree
    # must_catch: export dir left behind
    repo = ix.scenario(tmp_path / "w", {ix.REFRESH: lambda t: ix.strengthen_d(ix.skip_a(t)), ix.EXPORT: ix.drop_c})
    fx.recorded(repo, [ix.listed(ix.REFRESH, ix.A), ix.listed(ix.REFRESH, ix.D), ix.listed(ix.EXPORT, ix.C)])
    priv = tmp_path / "private_tmp"
    priv.mkdir()
    before = (ix.snapshot(repo), ix.git_text(repo, "status", "--porcelain"), ix.git_text(repo, "stash", "list"),
              ix.git_text(repo, "worktree", "list"), ix.git_text(repo, "rev-parse", "HEAD"))
    proc, out = ix.run_check(repo, {"TEMP": str(priv), "TMP": str(priv), "TMPDIR": str(priv)})
    fx.assert_check_shape(proc, out)
    assert ix.whats(out) == {ix.A: "skipped", ix.C: "removed"}, "the base run must have happened: " + str(out["weakened"])
    after = (ix.snapshot(repo), ix.git_text(repo, "status", "--porcelain"), ix.git_text(repo, "stash", "list"),
             ix.git_text(repo, "worktree", "list"), ix.git_text(repo, "rev-parse", "HEAD"))
    assert after == before, "the check changed the working tree, the index, the stash, the worktrees or HEAD"
    assert after[2] == "", "no stash entry may exist"
    assert list(priv.iterdir()) == [], f"the export dir (or other temp) was left behind: {list(priv.iterdir())}"


def test_decision_from_runs_not_from_list(tmp_path: Path):
    # covers: TQ-500g-3-ii
    # angle: reachability
    # must_catch: check reads the sweep list only
    repo = ix.scenario(tmp_path, {ix.REFRESH: ix.skip_a})
    fx.recorded(repo, [ix.listed(ix.REFRESH, ix.A, "unaffected", "no consumer reads this")])
    proc, out = fx.finish(repo)
    assert proc.returncode == 1 and out["gate_passed"] is False, (proc.returncode, out)
    assert out["stopped_at"] == "sweep", out.get("stopped_at")
    assert out["writer"] is None and out["verdict"] is None, "nothing may run after a sweep stop"
    sweep = out["sweep"]
    assert ix.whats(sweep) == {ix.A: "skipped"}, sweep  # the list says unaffected; the run says skipped
    assert sweep["passed"] is False, sweep
