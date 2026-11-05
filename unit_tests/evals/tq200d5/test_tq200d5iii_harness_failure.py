"""MODULE: test_tq200d5iii_harness_failure

GOAL: Prove a run whose agent cannot be started stops at the first row as a harness failure (one message that
    names the launch failure and its operating-system reason, exit status 3, a results file marked
    ``harness_failure`` with no score at all, never a fresh eval receipt), while a failure after the start
    (a timeout, a non-zero exit, an unreadable reply) still scores every row; and that the README and the
    how-to name the exit status and the marker the code uses.

Target modules: scripts/evals/run_agent_eval.py, scripts/evals/produced_tests_mode.py,
    scripts/evals/agent_launch/command.py, scripts/evals/eval_selector.py
AC: TQ-200d-5-iii
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import pytest

import unit_tests.evals.tq200d5._docs as docs
import unit_tests.evals.tq200d5._fake as fk
import unit_tests.evals.tq200d5._runs as rn

PREFIX = "agent CLI could not be launched"
REFUSED = FileNotFoundError(2, "Das System kann die angegebene Datei nicht finden.", None, 2)
FIRST_ROW = {"label": "r1", "artifact": "a1", "produced": "p1", "produced-plain": "p1"}
SCORE_KEYS = ("accuracy", "pass_rate", "pass-rate", "passrate", "per_assertion", "per_axis", "exact_match")
SCORE_NAMES = ("score", "aggregate", "rows", "passed")


def _keys(node) -> list[str]:
    if isinstance(node, dict):
        return [str(k) for k in node] + [k for v in node.values() for k in _keys(v)]
    return [k for v in node for k in _keys(v)] if isinstance(node, list) else []


def _failed_launch(kind, tmp_path, monkeypatch, capsys, caplog, rows=8):
    return rn.run(kind, tmp_path, monkeypatch, capsys, caplog, [fk.cannot_start(REFUSED)], rows=rows)


@pytest.mark.parametrize("kind", rn.KINDS)
def test_first_launch_failure_stops_the_run(tmp_path, monkeypatch, capsys, caplog, kind):
    # covers: TQ-200d-5-iii
    # angle: discrimination
    # must_catch: run keeps scoring rows after a launch failure
    # must_catch: stop message drops the operating-system reason
    # must_catch: produced-tests row loop not stopped
    result = _failed_launch(kind, tmp_path, monkeypatch, capsys, caplog)
    assert len(result.fake.calls) == 1, f"{kind}: {len(result.fake.calls)} launches were attempted for 8 rows"
    assert result.rows == [], f"{kind}: rows were scored: {[r['id'] for r in result.rows]}"
    said = [line for line in result.stop_lines() if "could not be launched" in line and str(REFUSED) in line]
    assert said, f"{kind}: no printed or error-level message names the launch failure and its reason: {result.stop_lines()}"
    assert len(said) <= 3, f"{kind}: the failure was reported {len(said)} times (once per row?)"
    ok_dir = tmp_path / "ok"
    ok_dir.mkdir()
    control = rn.run(kind, ok_dir, monkeypatch, capsys, caplog, [rn.ok_reply(kind)], rows=2)
    assert len(control.fake.calls) == 2 and len(control.rows) == 2, "control: with a working agent every row is started and scored"


@pytest.mark.parametrize("kind", rn.KINDS)
def test_harness_failure_exit_status_differs_from_below_threshold(tmp_path, monkeypatch, capsys, caplog, kind):
    # covers: TQ-200d-5-iii
    # angle: discrimination
    # must_catch: harness failure returns the below-threshold status 1
    # must_catch: harness failure returns 0
    launch = _failed_launch(kind, tmp_path, monkeypatch, capsys, caplog, rows=2)
    below = tmp_path / "below"
    below.mkdir()
    scored = rn.run(kind, below, monkeypatch, capsys, caplog, [fk.exits(1, "boom")], rows=2, threshold=0.5)
    assert len(scored.rows) == 2 and all(not r["score"]["passed"] for r in scored.rows), "control: rows that failed after the start"
    assert scored.code == 1, f"{kind}: a run that scored below its threshold exits 1, got {scored.code}"
    assert launch.code == 3, f"{kind}: a harness failure exits 3, got {launch.code}"
    assert launch.code not in (0, 1, 2) and launch.code != scored.code


@pytest.mark.parametrize("kind", rn.KINDS)
def test_harness_failure_results_file_carries_no_score(tmp_path, monkeypatch, capsys, caplog, kind):
    # covers: TQ-200d-5-iii
    # angle: discrimination
    # must_catch: accuracy 0.0 written for a harness failure
    # must_catch: pass-rate written for a harness failure
    # must_catch: harness_failure marker missing from the results file
    result = _failed_launch(kind, tmp_path, monkeypatch, capsys, caplog)
    payload = result.payload
    assert payload is not None, "no results file was written"
    assert payload.get("harness_failure") == {"cause": "agent_launch_failed", "row": FIRST_ROW[kind],
                                              "detail": f"{PREFIX}: {type(REFUSED).__name__}: {REFUSED}"}, payload
    assert payload.get("agent") == "agent-x" and payload.get("timestamp"), "the existing keys are kept"
    if kind.startswith("produced"):
        assert payload.get("run_context") == "local"
    keys = _keys(payload)
    assert not [k for k in keys if any(s in k.lower() for s in SCORE_KEYS) or k.lower() in SCORE_NAMES], f"score keys in {keys}"
    # control: a run that started has the keys the check above looks for
    ok_dir = tmp_path / "ok"
    ok_dir.mkdir()
    control = rn.run(kind, ok_dir, monkeypatch, capsys, caplog, [rn.ok_reply(kind)], rows=2)
    assert "harness_failure" not in control.payload and "aggregate" in control.payload and "accuracy" in control.payload["aggregate"]


@pytest.mark.parametrize("kind", rn.KINDS)
def test_failure_after_start_still_scores_every_row(tmp_path, monkeypatch, capsys, caplog, kind):
    # covers: TQ-200d-5-iii
    # angle: boundary
    # must_catch: timeout treated as a launch failure and stops the run
    # must_catch: non-zero exit after start treated as a harness failure
    plan = [fk.times_out(30), fk.exits(1, "boom"), fk.unreadable(), rn.ok_reply(kind)]
    result = rn.run(kind, tmp_path, monkeypatch, capsys, caplog, plan, rows=4, threshold=0.9)
    assert len(result.fake.calls) == 4, f"{kind}: {len(result.fake.calls)} of 4 rows were started"
    assert "harness_failure" not in (result.payload or {}) and result.code in (0, 1), (result.code, result.payload)
    assert result.code == 1, "scored below its threshold, so the status is 1"
    assert [r["id"] for r in result.rows] == [f"{FIRST_ROW[kind][0]}{i}" for i in (1, 2, 3, 4)]
    failed, last = result.rows[:3], result.rows[3]
    assert all(not r["score"]["passed"] for r in failed), "the three rows that failed after the start count as failed"
    assert all((r.get("parse_error") or r.get("error")) for r in failed), "each carries its error"
    assert not any(PREFIX in (r.get("parse_error") or r.get("error") or "") for r in failed), "none is a launch failure"
    assert last["score"]["passed"] is True or last["score"]["assertions"], "the row after them was scored"
    assert result.payload["aggregate"]["accuracy"] == pytest.approx(sum(r["score"]["passed"] for r in result.rows) / 4)


def test_harness_failure_file_is_not_a_fresh_receipt(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-iii
    # angle: failure
    # must_catch: harness-failure results file accepted as a fresh eval receipt
    real = _failed_launch("label", tmp_path, monkeypatch, capsys, caplog, rows=2)
    marker = (real.payload or {}).get("harness_failure")
    assert marker, "the real harness-failure marker is needed to build the file the gate reads"
    root, results = tmp_path / "repo", tmp_path / "repo-results"
    (root / "templates" / "agents").mkdir(parents=True)
    results.mkdir()
    (root / "templates" / "agents" / "agent-a.md").write_text("prompt A v1\n", encoding="utf-8")
    triggers = ["templates/agents/agent-a.md"]
    config = tmp_path / "selector-config.json"
    config.write_text(json.dumps({"agents": {"agent-a": {"triggers": triggers}}}), encoding="utf-8")
    shas = fk.module("eval_selector").resolve_trigger_shas(root, triggers)

    def check() -> tuple[int, dict]:
        done = subprocess.run([sys.executable, str(fk.EVALS / "eval_selector.py"), "--check", "--changed-files",
                               "templates/agents/agent-a.md", "--repo-root", str(root), "--config", str(config),
                               "--results-dir", str(results)], capture_output=True, text=True, encoding="utf-8", timeout=120, check=False)
        return done.returncode, json.loads(done.stdout)["status"]

    receipt = {"agent": "agent-a", "trigger_shas": shas}
    (results / "agent-a.json").write_text(json.dumps(receipt), encoding="utf-8")
    assert check() == (0, {"agent-a": "fresh"}), "control: the same file without the marker is a fresh receipt"
    (results / "agent-a.json").write_text(json.dumps({**receipt, "harness_failure": marker}), encoding="utf-8")
    code, status = check()
    assert code == 3 and status["agent-a"] != "fresh", (code, status)


def test_cli_run_with_no_claude_exits_as_harness_failure(tmp_path):
    # covers: TQ-200d-5-iii
    # angle: reachability
    empty = tmp_path / "empty-path"
    empty.mkdir()
    env = {k: v for k, v in os.environ.items() if k not in ("LEAFCUTTER_EVAL_CLAUDE_CLI", "LEAFCUTTER_EVAL_USE_API", "ANTHROPIC_API_KEY")}
    env.update(PATH=str(empty), PYTHONUTF8="1")
    results = tmp_path / "results.json"
    done = subprocess.run([sys.executable, str(fk.EVALS / "run_agent_eval.py"), "--agent", "pt-classifier", "--results-file", str(results)],
                          cwd=fk.REPO, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=300, check=False)
    first = json.loads(next(iter((fk.REPO / "docs/product-truth/classifier/eval.jsonl").read_text(encoding="utf-8").splitlines())))["id"]
    assert done.returncode == 3, (done.returncode, (done.stdout + done.stderr)[-1500:])
    payload = json.loads(results.read_text(encoding="utf-8"))
    assert payload["harness_failure"]["cause"] == "agent_launch_failed" and payload["harness_failure"]["row"] == first
    assert payload["harness_failure"]["detail"].startswith(PREFIX) and "rows" not in payload and "aggregate" not in payload
    assert (done.stdout + done.stderr).count(PREFIX) <= 3, "one launch attempt, one message (not one per row)"


def test_docs_name_the_harness_failure_exit_status_and_marker(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-iii
    # angle: real_artifact
    readme, how_to = docs.text_of(docs.README), docs.text_of(docs.HOW_TO)
    result = _failed_launch("label", tmp_path, monkeypatch, capsys, caplog, rows=2)
    marker = [k for k in (result.payload or {}) if "harness" in k]
    assert marker == ["harness_failure"], f"the results file marker is {marker}"
    status = f"exit status {result.code}"
    assert status in readme.lower() and status in docs.section(how_to, "A run that stops as a harness failure").lower()
    for text in (readme, how_to):
        assert f"`{marker[0]}`" in text, "the marker the code writes is named in backticks"
    statuses = docs.section(readme, "Exit statuses")
    assert set(re.findall(r"`(\d)`", statuses)) == {"0", "1", "2", "3"}, "the four exit statuses are listed"
    three = next(line for line in statuses.splitlines() if "`3`" in line)
    assert "harness failure" in three.lower() and "threshold" in next(line for line in statuses.splitlines() if "`1`" in line).lower()
    stops = docs.section(how_to, "A run that stops as a harness failure")
    assert "Reading a launch failure" in stops and re.search(r"no (score|accuracy)", stops, re.I), "the how-to says what to read and that there is no score"
    old = "Classifier invocation or malformed-response failures stay in the accuracy denominator without becoming fabricated negative predictions."
    launch_word = re.compile(r"launch|start", re.I)
    assert not launch_word.search(old), "probe: the old sentence is what the check must reject"
    stale = [s for s in docs.sentences(readme) if "denominator" in s and not launch_word.search(s)]
    assert stale == [], f"the README still says invocation failures stay in the denominator without the launch exception: {stale}"
