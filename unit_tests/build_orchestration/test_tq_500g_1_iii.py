"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_iii.py
GOAL: RED tests for TQ-500g-1-iii -- the code is put back exactly after a
    wrong-version run, even when the run is cut short.
BUSINESS CONTEXT: All cut-short cases use a new-file-only sandbox, so V1
    ("drop the retry_due condition") is the ONLY wrong version run and no later
    run can mask a missing put-back. The fixture T1 cuts the run short only while
    the file carries the marker "altered": X1 sleeps past the tiny timeout set via
    LEAFCUTTER_DONE_PROOF_PYTEST_TIMEOUT_SECONDS, X2 calls os._exit(3), X3 blocks
    until a marker file appears (the runner tree is then hard-killed). Red today
    because the runner CLI does not exist (no JSON, so the assertions fail).
"""

from __future__ import annotations

import subprocess

import unit_tests.build_orchestration._tq500g1_fixtures as fx

TIMEOUT = "12"


def _cut_short_sandbox(tmp_path, hook):
    return fx.build_sandbox(tmp_path, tests=("T1",), t1_must_catch=(fx.WV_DROP,), hook=hook, new_file_only=True)


def _assert_not_run(sb, proc, verdict):
    drop = fx.rows(verdict, fx.T1, fx.WV_DROP)
    assert [(r["result"], r["blocking"]) for r in drop] == [("not_run", True)], drop
    assert sb.target.read_bytes() == sb.as_written, "refresh_config.py not put back byte for byte"
    assert fx.survivor_pairs(verdict) == []
    assert [(u["wrong_version"], u["result"]) for u in verdict["unfinished"]] == [(fx.WV_DROP, "not_run")]
    assert verdict["gate_passed"] is False and verdict["reason"] == "unfinished" and proc.returncode == 1


def test_timeout_puts_code_back_and_reports_not_run(tmp_path):
    # covers: TQ-500g-1-iii
    # angle: failure
    # X1: the fixture test sleeps past the 12 s budget. Catches: 'timeout path returns without
    # restoring' (file still carries the alteration); 'cut-short run reported as survived'.
    # Control: the same sandbox without the hook, same tiny budget, is a normal caught run.
    sb = _cut_short_sandbox(tmp_path / "x1", "sleep")
    proc, verdict = fx.run_runner(sb, timeout_env=TIMEOUT)
    _assert_not_run(sb, proc, verdict)
    ctl = _cut_short_sandbox(tmp_path / "ctl", None)
    _proc, ctl_verdict = fx.run_runner(ctl, timeout_env=TIMEOUT)
    assert [r["result"] for r in fx.rows(ctl_verdict, fx.T1, fx.WV_DROP)] == ["caught"]


def test_crash_puts_code_back_before_anything_else(tmp_path):
    # covers: TQ-500g-1-iii
    # angle: failure
    # X2: under the wrong version the test process dies with os._exit(3) (pytest returncode 3,
    # neither 0 nor 1). Catches: 'crash path reports the wrong version as caught'.
    sb = _cut_short_sandbox(tmp_path, "exit3")
    proc, verdict = fx.run_runner(sb)
    _assert_not_run(sb, proc, verdict)
    assert "caught" not in {r["result"] for r in verdict["results"]}


def test_resumed_drive_restores_altered_file_first(tmp_path):
    # covers: TQ-500g-1-iii
    # angle: reachability
    # Entry point: the runner CLI `recover` step, run as a subprocess on a worktree left altered
    # by a hard-killed `run` (X3). Catches: 'resume trusts the working tree without comparing
    # it with the copy' (the file would stay altered). A second recover finds nothing to do.
    sb = _cut_short_sandbox(tmp_path, "block")
    proc = fx.start_runner_until_altered(sb)
    fx.kill_tree(proc)
    sb.marker.write_text("release any orphaned fixture test", encoding="utf-8")
    assert sb.target.read_bytes() != sb.as_written, "the kill must leave the file altered"
    assert len(sb.copies_of_as_written()) == 1, "the copy must outlive the killed runner"
    rec_proc, rec = fx.run_recover(sb)
    assert rec["ok"] is True and rec_proc.returncode == 0, rec
    assert [fx.norm(p).rsplit("/", 1)[-1] for p in rec["restored"]] == ["refresh_config.py"], rec
    assert sb.target.read_bytes() == sb.as_written
    again_proc, again = fx.run_recover(sb)
    assert again["restored"] == [] and again["ok"] is True and again_proc.returncode == 0, again


def test_failed_put_back_stops_naming_the_copy(tmp_path):
    # covers: TQ-500g-1-iii
    # angle: failure
    # The fixture test replaces refresh_config.py with a DIRECTORY while the wrong version is on
    # disk, so no put-back can make the path match. Catches: 'failed put-back reported as
    # success' (gate_passed true / exit 0); 'copy deleted after a failed put-back'.
    sb = _cut_short_sandbox(tmp_path, "sabotage")
    proc, verdict = fx.run_runner(sb)
    assert sb.target.is_dir(), "precondition: the put-back target must still be unwritable"
    assert verdict["gate_passed"] is False and proc.returncode == 1
    text = fx.norm(" ".join(fx.walk_strings(verdict)))
    assert "may still be altered" in text, text[-400:]
    copies = sb.copies_of_as_written()
    assert len(copies) == 1, "the as-written copy must remain after a failed put-back"
    assert fx.norm(str(copies[0])) in text, f"verdict does not name {copies[0]}"
    assert copies[0].is_absolute()


def test_no_stash_and_no_other_file_changes(tmp_path):
    # covers: TQ-500g-1-iii
    # angle: criterion
    # Catches: 'git stash used' (the fixture test probes `git stash list` while the wrong version
    # is on disk); 'copy kept inside the working tree' (probe finds the as-written bytes in a
    # second work-tree file, and the copy is only ever found under <git-dir>/leafcutter/
    # wrong-version-runs). Exact counts: two probes (V1 and the fix undone), one copy each.
    sb = fx.build_sandbox(tmp_path, tests=("T1", "T4"))
    before, tree_before = fx.git_state(sb.work), fx.tree_digest(sb.work)
    proc, verdict = fx.run_runner(sb)
    assert proc.returncode == 0 and verdict["gate_passed"] is True, verdict
    assert fx.git_state(sb.work) == before == {"stash": "", "status": ""}
    assert fx.tree_digest(sb.work) == tree_before
    probes = fx.jsonl(sb.probe)
    assert len(probes) == 2, probes
    git_dir = fx.norm(subprocess.run(["git", "rev-parse", "--absolute-git-dir"], cwd=sb.work,
                                     capture_output=True, text=True, check=True).stdout.strip())
    for probe in probes:
        assert probe["stash"] == "" and probe["tree_copies"] == [], probe
        assert probe["status"].splitlines() == [" M refresh_config.py"], probe
        assert len(probe["copies"]) == 1 and probe["copies"][0].startswith("leafcutter/wrong-version-runs/")
    assert fx.norm(str(sb.git_dir)) == git_dir
