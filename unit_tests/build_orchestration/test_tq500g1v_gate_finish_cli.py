"""
MODULE: unit_tests/build_orchestration/test_tq500g1v_gate_finish_cli.py
GOAL: RED tests for the ``finish`` step of the new scripts/build_orchestration/wrong_version_gate.py
    (TQ-500g-1-v): writer's write step, then, only when the writer did not stop, the runner's run
    step; one JSON object {gate_passed, stopped_at, writer, verdict}; exit 0 iff gate_passed.
BUSINESS CONTEXT: The wrapper holds no rule of its own. Each test runs it as a subprocess on a real
    git repo and a real AC store, with the real writer and the real runner behind it. The module
    does not exist yet, so a run prints no JSON and the shared parse helper raises an
    AssertionError: every test fails on an assertion, never on an import.
"""

from __future__ import annotations

import json
from pathlib import Path

import unit_tests.build_orchestration._tq500f3i_fixtures as gitfx
import unit_tests.build_orchestration._tq500g1_fixtures as fx
import unit_tests.build_orchestration._tq500g1ix_fixtures as ix
import unit_tests.build_orchestration._tq500g1v_gate_fixtures as g
import unit_tests.build_orchestration._tq500g1x_fixtures as x


def test_gate_finish_verdict_is_runner_json_verbatim(tmp_path: Path):
    # covers: TQ-500g-1-v
    # angle: seam
    # must_catch: wrapper rewrites or summarises the runner's verdict
    # must_catch: wrapper passes a different base ref or AC root to the runner
    # must_catch: wrapper omits --base-ref from the writer's write step
    sb = x.build(tmp_path)
    owed = x.listed(sb)  # the list step for the base commit: N2 and N9 are derived names
    assert owed[x.N2]["scope"] == "derived" and owed[x.N9]["scope"] == "derived", owed
    proc, out = g.run_finish(sb, g.reply_text())  # --base-ref is the base commit, not HEAD
    g.assert_shape(proc, out)
    assert out["stopped_at"] is None and out["gate_passed"] is True, out
    writer = out["writer"]
    assert writer["written"] is True and isinstance(writer["manifest_path"], str), writer
    # Derived names only get their replacement in refresh_config.py (a COMMITTED change) when the
    # write step reads the same base ref the list step did; with HEAD it is refused as out of scope.
    status = {e["name"]: e["status"] for e in writer["entries"]}
    assert status == {n: "prepared" for n in (x.N1, x.N3, x.N2, x.N9)}, status
    # The verdict is the JSON the runner prints for the same manifest, ids, roots and base ref.
    _, direct = x.run_runner(sb, Path(writer["manifest_path"]))
    assert out["verdict"] == direct, "finish's verdict differs from the runner's own JSON"
    assert out["gate_passed"] == out["verdict"]["gate_passed"]


def test_gate_finish_writer_stop_never_runs_runner(tmp_path: Path):
    # covers: TQ-500g-1-v
    # angle: failure
    # must_catch: runner called without a manifest after the writer stopped
    # must_catch: writer stop reported as gate_passed true
    sb = x.build(tmp_path)
    full = g.reply_text()
    replies = {
        "empty": "",
        "cut_off": full[: len(full) // 2],
        "failed_shape": json.dumps({"status": "failed", "blocker_summary": "no file read", "anomalies": []}),
        "other_work_key": g.reply_text(work_key="another-work"),
    }
    before = x.snapshot(sb)
    for label, reply in replies.items():
        proc, out = g.run_finish(sb, reply)
        g.assert_shape(proc, out)
        assert proc.returncode == 1 and out["gate_passed"] is False, (label, proc.returncode, out)
        assert out["stopped_at"] == "write" and out["verdict"] is None, (label, out)
        err = out["writer"]["error"]
        assert out["writer"]["written"] is False and isinstance(err, str) and err, (label, out)
        assert not (sb.git_dir / "leafcutter" / "wrong-version-runs").exists(), f"{label}: the runner ran after the writer stopped"
        assert x.snapshot(sb) == before, f"{label}: the working tree changed although the writer stopped"


def test_gate_finish_nothing_owed_empty_stdin_still_runs_runner(tmp_path: Path):
    # covers: TQ-500g-1-v
    # angle: boundary
    # must_catch: empty stdin treated as a writer stop when nothing is owed
    sb = x.build(tmp_path)
    # Entries that name no wrong version but carry the discrimination angle owe nothing by name;
    # the runner still holds them to "the fix undone".
    gitfx.write_ac_yaml(sb.ac_root, ix.AC_ID, [{"name": x.E1, "angle": "discrimination"}])
    assert x.listed(sb) == {}, "the sandbox must owe no named wrong version"
    proc, out = g.run_finish(sb, "")
    g.assert_shape(proc, out)
    assert out["stopped_at"] is None and out["gate_passed"] is True, out
    assert out["writer"]["written"] is True, out["writer"]
    runs = [r for r in out["verdict"]["results"] if r["wrong_version"]]  # rows of tests not in scope name none
    assert [(r["wrong_version"], r["result"]) for r in runs] == [(fx.WV_UNDONE, "caught")], runs
    assert out["verdict"]["applicable"] is True
    # No source requirement at all: no ids, so the runner itself answers not applicable.
    proc2, out2 = g.run_finish(sb, "", ac_ids=None)
    g.assert_shape(proc2, out2)
    assert out2["gate_passed"] is True and out2["verdict"]["applicable"] is False, out2
    assert out2["verdict"]["outcome"] == g.NO_SOURCE_OUTCOME, out2["verdict"]["outcome"]


def test_gate_finish_cli_end_to_end(tmp_path: Path):
    # covers: TQ-500g-1-v
    # angle: reachability
    sb = x.build(tmp_path)
    proc, out = g.run_finish(sb, g.reply_text())
    g.assert_shape(proc, out)
    assert out["gate_passed"] is True and proc.returncode == 0, (proc.returncode, out)
    assert out["stopped_at"] is None and isinstance(out["writer"], dict) and isinstance(out["verdict"], dict)
    # TQ-500g-1-xi: run 1 pinned both names for ix.WORK_KEY, so an empty reply would now pass for that key;
    # a fresh work key has no pins, which keeps the empty reply a real stop case.
    stop_proc, stop_out = g.run_finish(sb, "", work_key=ix.WORK_KEY + "-fresh")
    g.assert_shape(stop_proc, stop_out)
    assert stop_out["gate_passed"] is False and stop_proc.returncode == 1, (stop_proc.returncode, stop_out)
