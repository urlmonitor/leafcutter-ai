"""
MODULE: unit_tests/build_orchestration/test_tq_500g_1_i.py
GOAL: RED tests for TQ-500g-1-i -- the shared wrong-version runner holds each
    guarding test to the wrong versions its OWN entry names.
BUSINESS CONTEXT: The runner (scripts/build_orchestration/wrong_version_runner.py,
    not yet written) is driven ONLY through its CLI as a subprocess, so every test
    is red on an assertion today (the CLI file is missing, so there is no JSON).
    Sandbox: real git repo, real T1-T4 tests, real AC store, real pytest; see
    _tq500g1_fixtures.py. T1 names ["revert the fix", "drop the retry_due
    condition"], T2 names ["drop the retry_due condition"] but is inert, T3 names
    nothing, T4 declares the discrimination angle only.
"""

from __future__ import annotations

import json
import subprocess

import unit_tests.build_orchestration._tq500g1_fixtures as fx

RESULT_VALUES = {"caught", "survived", "did_not_load", "not_applied", "invalid", "not_run",
                 "not_in_scope", "not_applicable"}
ROW_KEYS = {"test", "wrong_version", "result", "blocking", "detail"}
VERDICT_KEYS = {"gate_passed", "applicable", "verified", "outcome", "reason", "results",
                "survivors", "unfinished"}


def test_t2_survivor_stops_although_t1_caught_it(tmp_path):
    # covers: TQ-500g-1-i
    # angle: discrimination
    # Catches: 'group verdict: one catching test covers every sibling' (T1 caught, so the
    # gate would pass); 'survivor reported without naming the test' (survivors lack T2);
    # 'manifest claim field read as an outcome' (the manifest claims T2 caught it).
    # Control row: T1 IS caught under the same wrong version in the same run.
    sb = fx.build_sandbox(tmp_path, claims=True)
    proc, verdict = fx.run_runner(sb)
    drop_t1 = fx.rows(verdict, fx.T1, fx.WV_DROP)
    drop_t2 = fx.rows(verdict, fx.T2, fx.WV_DROP)
    assert [r["result"] for r in drop_t1] == ["caught"], f"control T1 row: {drop_t1}"
    assert [r["result"] for r in drop_t2] == ["survived"], f"T2 must survive: {drop_t2}"
    assert drop_t2[0]["blocking"] is True and drop_t1[0]["blocking"] is False
    assert fx.survivor_pairs(verdict) == [(fx.T2, fx.WV_DROP)], verdict["survivors"]
    assert verdict["gate_passed"] is False and verdict["reason"] == "survivor"
    assert proc.returncode == 1
    assert verdict["unfinished"] == []


def test_runner_cli_end_to_end_on_refresh_fixture(tmp_path):
    # covers: TQ-500g-1-i
    # angle: reachability
    # Entry point: python scripts/build_orchestration/wrong_version_runner.py run ... (subprocess).
    # Asserts the JSON shape, the exit code mirroring gate_passed, byte identity afterwards.
    # Control: a passing fixture (no inert T2) exits 0, so exit 1 is not a constant.
    stop = fx.build_sandbox(tmp_path / "stop")
    proc, verdict = fx.run_runner(stop)
    assert set(verdict) == VERDICT_KEYS, sorted(verdict)
    assert verdict["applicable"] is True and verdict["verified"] is True
    assert verdict["results"], "results must list the (test, wrong version) pairs"
    for row in verdict["results"]:
        assert set(row) == ROW_KEYS, row
        assert row["result"] in RESULT_VALUES, row
    assert proc.returncode == (0 if verdict["gate_passed"] else 1) == 1
    assert stop.target.read_bytes() == stop.as_written

    ok = fx.build_sandbox(tmp_path / "ok", tests=("T1", "T3", "T4"))
    proc_ok, v_ok = fx.run_runner(ok)
    assert proc_ok.returncode == 0 and v_ok["gate_passed"] is True and v_ok["reason"] is None
    assert v_ok["survivors"] == [] and v_ok["unfinished"] == []
    assert [r["result"] for r in fx.rows(v_ok, fx.T1, fx.WV_DROP)] == ["caught"]
    assert ok.target.read_bytes() == ok.as_written

    none = subprocess_run_empty_ids(ok)
    assert none["gate_passed"] is True and none["applicable"] is False
    assert none["outcome"] == "wrong-version runs not applicable: no source requirement"


def subprocess_run_empty_ids(sb):
    cmd = fx.runner_cmd(sb, "run", ac_ids="")
    proc = subprocess.run(cmd, cwd=sb.work, capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, f"empty --ac-ids must exit 0: {proc.stderr[-300:]}"
    return json.loads(proc.stdout)


def test_scope_is_declared_t3_out_t4_fix_undone_only(tmp_path):
    # covers: TQ-500g-1-i
    # angle: boundary
    # Catches: 'scope inferred from the covers tag alone, ignoring test_spec' (T3 would be
    # run: it is in the run log and gets a caught row); 'T3 reported as passed'.
    # T4 survives V1 by construction, so a runner holding T4 to V1 reports a survivor.
    sb = fx.build_sandbox(tmp_path)
    proc, verdict = fx.run_runner(sb)
    t3 = fx.rows(verdict, fx.T3)
    assert t3 and {r["result"] for r in t3} == {"not_in_scope"}, f"T3 rows: {t3}"
    assert all(r["blocking"] is False for r in t3)
    assert fx.T3 not in {e["test"] for e in fx.jsonl(sb.runlog)}, "T3 must never be run"
    held = [r for r in fx.rows(verdict, fx.T4) if r["result"] != "not_in_scope"]
    assert [(r["wrong_version"], r["result"]) for r in held] == [(fx.WV_UNDONE, "caught")], held
    assert fx.T4 not in {t for t, _ in fx.survivor_pairs(verdict)}
    assert [r["result"] for r in fx.rows(verdict, fx.T1, fx.WV_DROP)] == ["caught"]  # control
    assert proc.returncode == 1


def test_fix_undone_group_rule_and_alias(tmp_path):
    # covers: TQ-500g-1-i
    # angle: failure
    # Catches: 'the fix undone skipped when no entry names it' (case a: no row/survivor for
    # it); "'revert the fix' sent to the preparer as a separate wrong version" (case b uses
    # the spelling ' Revert The Fix ' and the manifest has no such entry); 'created file
    # deleted as the fix undone' (case c: new-file-only change, file must stay and the row
    # is not_applicable). Case d is the control: a passing group rule exits 0.
    a = fx.build_sandbox(tmp_path / "a", tests=("T2",), t1_must_catch=())
    proc_a, v_a = fx.run_runner(a)
    assert sorted(w for _, w in fx.survivor_pairs(v_a)) == sorted([fx.WV_DROP, fx.WV_UNDONE]), v_a["survivors"]
    undone_a = fx.rows(v_a, wv=fx.WV_UNDONE)
    assert undone_a and all(r["blocking"] is True for r in undone_a), undone_a
    assert proc_a.returncode == 1 and v_a["reason"] == "survivor"

    spaced = (" Revert The Fix ",)
    b = fx.build_sandbox(tmp_path / "b", tests=("T1", "T4"), t1_must_catch=spaced, weak_t1=True, entries=())
    proc_b, v_b = fx.run_runner(b)
    assert {r["wrong_version"] for r in v_b["results"]} == {fx.WV_UNDONE}, v_b["results"]
    assert fx.survivor_pairs(v_b) == [(fx.T1, fx.WV_UNDONE)], v_b["survivors"]
    assert [r["result"] for r in fx.rows(v_b, fx.T4, fx.WV_UNDONE)] == ["caught"]
    assert proc_b.returncode == 1 and v_b["reason"] == "survivor" and v_b["unfinished"] == []

    d = fx.build_sandbox(tmp_path / "d", tests=("T1", "T4"), t1_must_catch=spaced, entries=())
    proc_d, v_d = fx.run_runner(d)
    assert proc_d.returncode == 0 and v_d["gate_passed"] is True, v_d
    assert [r["result"] for r in fx.rows(v_d, fx.T1, fx.WV_UNDONE)] == ["caught"]

    c = fx.build_sandbox(tmp_path / "c", tests=("T1",), new_file_only=True)
    proc_c, v_c = fx.run_runner(c)
    undone_c = fx.rows(v_c, wv=fx.WV_UNDONE)
    assert [(r["result"], r["blocking"]) for r in undone_c] == [("not_applicable", False)], undone_c
    assert c.target.read_bytes() == c.as_written, "the created file must stay in place"
    assert proc_c.returncode == 0 and v_c["gate_passed"] is True and v_c["unfinished"] == []
    assert [r["result"] for r in fx.rows(v_c, fx.T1, fx.WV_DROP)] == ["caught"]


def test_code_as_written_restored_and_nothing_else_changed(tmp_path):
    # covers: TQ-500g-1-i
    # angle: criterion
    # Catches: 'restore taken from git HEAD instead of the as-written copy' (the file carries
    # an UNCOMMITTED note, so HEAD differs from as-written); 'git stash used for apply or
    # put-back' (the fixture tests probe `git stash list` and `git status` while the wrong
    # version is on disk: exactly two probes, one per wrong version).
    sb = fx.build_sandbox(tmp_path, uncommitted_note=True)
    assert sb.as_written != fx.gitfx.run_git(["show", "HEAD:refresh_config.py"], cwd=sb.work).encode()
    before, tree_before = fx.git_state(sb.work), fx.tree_digest(sb.work)
    test_bytes = {p.name: p.read_bytes() for p in sb.test_root.glob("*.py")}
    proc, verdict = fx.run_runner(sb)
    assert verdict["results"], "the runner must have made runs"
    assert sb.target.read_bytes() == sb.as_written, "not restored to the as-written bytes"
    assert fx.git_state(sb.work) == before and before["status"] == " M refresh_config.py\n"
    assert fx.tree_digest(sb.work) == tree_before
    assert {p.name: p.read_bytes() for p in sb.test_root.glob("*.py")} == test_bytes
    probes = fx.jsonl(sb.probe)
    assert len(probes) == 2, probes
    for probe in probes:
        assert probe["stash"] == "" and probe["status"].splitlines() == [" M refresh_config.py"], probe
    assert proc.returncode == 1
