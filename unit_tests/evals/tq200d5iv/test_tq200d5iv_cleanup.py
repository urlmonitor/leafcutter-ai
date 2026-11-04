"""MODULE: test_tq200d5iv_cleanup

GOAL: Prove a temp folder of a produced-tests row that cannot be deleted (faked Windows file-in-use lock) is
    retried, then left behind with a warning, and never ends the run, replaces a row's real error, or turns a
    failed row into a pass; and that the README and how-to quote the warning the code logs.

Target modules: scripts/evals/produced_tests_mode.py, produced_tests_runs.py, produced_tests_scoring.py
AC: TQ-200d-5-iv
"""

from __future__ import annotations

import copy
import json
import logging
import re

import pytest

import unit_tests.evals.tq200d5._docs as docs
import unit_tests.evals.tq200d5._fake as fk
import unit_tests.evals.tq200d5._runs as rn
import unit_tests.evals.tq200d5iv._lock as lk

LOCKED_TEXT = "used by another process"
REFUSED = FileNotFoundError(2, "Das System kann die angegebene Datei nicht finden.", None, 2)


def _warnings(result: rn.Run) -> list[str]:
    return [m for lvl, m in result.logged if lvl == logging.WARNING and lk.PREFIX in m]


def test_locked_row_folder_does_not_end_the_run(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-iv
    # angle: criterion
    # must_catch: revert the fix (the cleanup error escapes score_one and ends the run)
    # must_catch: the cleanup error recorded as the first row's failure
    # must_catch: no warning naming the folder
    (tmp_path / "ok").mkdir()
    control = rn.run("produced", tmp_path / "ok", monkeypatch, capsys, caplog, [rn.ok_reply("produced")], rows=2)
    lock = lk.install(monkeypatch, "row", first_only=True)
    try:
        result = rn.run("produced", tmp_path, monkeypatch, capsys, caplog, [rn.ok_reply("produced")], rows=2)
        assert result.payload is not None, "no results file was written"
        assert [r["id"] for r in result.rows] == ["p1", "p2"], [r["id"] for r in result.rows]
        assert any("accuracy=" in line for line in result.printed), "the aggregate score was not printed"
        first = lock.roots[0]
        assert first.exists(), "the locked folder should have been left behind"
        named = [m for m in _warnings(result) if first.name in m]
        assert len(named) == 1, f"expected exactly one warning naming {first.name}: {_warnings(result)}"
        assert result.rows[0]["score"] == control.rows[0]["score"], "first row's result is not the one its outputs earned"
        assert not result.rows[0].get("error"), result.rows[0].get("error")
        assert result.rows[1]["score"] == control.rows[1]["score"]
    finally:
        lock.cleanup()


def test_cleanup_that_succeeds_on_retry_leaves_nothing_and_warns_nothing(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-iv
    # angle: boundary
    # must_catch: no retry before giving up
    # must_catch: a warning logged after a successful retry
    lock = lk.install(monkeypatch, "all", fail_first=1)
    try:
        result = rn.run("produced", tmp_path, monkeypatch, capsys, caplog, [rn.ok_reply("produced")], rows=2)
        assert [r["id"] for r in result.rows] == ["p1", "p2"]
        assert lock.roots and lock.left_behind() == [], f"folders left behind: {lock.left_behind()}"
        assert max(lock.attempts.values()) >= 2, "a failing delete was never retried"
        assert _warnings(result) == [], _warnings(result)
        assert not any(r.get("error") for r in result.rows), [r.get("error") for r in result.rows]
    finally:
        lock.cleanup()


@pytest.mark.parametrize("scope", ["sandbox", "all"])  # "all" also locks the row's own temp folder
def test_agent_failure_is_recorded_not_the_locked_sandbox(scope, tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-iv
    # angle: failure
    # must_catch: the cleanup error replaces the agent error
    plan = [fk.exits(1, stderr="API Error: Connection closed mid-response")]
    lock = lk.install(monkeypatch, scope)
    try:
        result = rn.run("produced", tmp_path, monkeypatch, capsys, caplog, plan, rows=2)
        assert len(result.rows) == 2, f"rows scored: {[r['id'] for r in result.rows]}"
        for row in result.rows:
            assert "Connection closed mid-response" in row.get("error", ""), row.get("error")
            assert LOCKED_TEXT not in row.get("error", ""), row.get("error")
            assert row["score"]["passed"] is False
    finally:
        lock.cleanup()


def test_other_row_failures_stay_failed_with_their_reason(tmp_path, monkeypatch):
    # covers: TQ-200d-5-iv
    # angle: boundary
    # must_catch: cleanup tolerance turns a failed row into a pass
    # must_catch: the row's own error dropped
    mode = fk.module("produced_tests_mode")
    harness = fk.module("run_agent_eval")
    cfg = json.loads((fk.EVALS / "agent_eval_config.json").read_text(encoding="utf-8"))["agents"]["test-runner"]
    line = json.loads((fk.EVALS / "sets" / "test-runner.jsonl").read_text(encoding="utf-8").splitlines()[0])
    row = copy.deepcopy(line)
    row["expected"]["fixture"] = "scripts/evals/fixtures/does-not-exist-tq200d5iv"
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    lock = lk.install(monkeypatch, "all")
    try:
        record = mode.score_one(row, cfg, "", fk.REPO, harness, score_gold=True, timeout=5)
        assert record["score"]["passed"] is False
        assert "cannot copy fixture" in record["error"], record["error"]
        assert LOCKED_TEXT not in record["error"]
    finally:
        lock.cleanup()


def test_agent_that_cannot_be_launched_still_stops_the_run(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-iv
    # angle: boundary
    # must_catch: a broadened catch swallows the launch failure
    lock = lk.install(monkeypatch, "all")
    try:
        result = rn.run("produced", tmp_path, monkeypatch, capsys, caplog, [fk.cannot_start(REFUSED)], rows=2)
        assert result.code == 3, f"a launch failure must exit 3, got {result.code}"
        assert result.payload is not None and "harness_failure" in result.payload, result.payload
        assert result.rows == []
        assert len(result.fake.calls) == 1
    finally:
        lock.cleanup()


@pytest.mark.parametrize("agent", ["test-writer", "sql-test-writer", "test-runner"])
def test_score_gold_replay_with_locked_folders_keeps_its_scores(agent, tmp_path, monkeypatch):
    # covers: TQ-200d-5-iv
    # angle: reachability
    # must_catch: a locked scoring sandbox changes a gold row's result
    ev = fk.module("run_agent_eval")
    plain = tmp_path / "plain.json"
    code_plain = ev.main(["--agent", agent, "--score-gold", "--results-file", str(plain)])
    locked_file = tmp_path / "locked.json"
    lock = lk.install(monkeypatch, "all")
    try:
        code_locked = ev.main(["--agent", agent, "--score-gold", "--results-file", str(locked_file)])
        assert locked_file.is_file(), "no results file written under the lock"
        a = json.loads(plain.read_text(encoding="utf-8"))
        b = json.loads(locked_file.read_text(encoding="utf-8"))
        assert code_locked == code_plain
        assert [(r["id"], r["score"]["passed"]) for r in b["rows"]] == [(r["id"], r["score"]["passed"]) for r in a["rows"]]
        assert b["aggregate"]["accuracy"] == a["aggregate"]["accuracy"]
        assert lock.roots, "the lock was never reached"
    finally:
        lock.cleanup()


def test_docs_state_the_left_behind_folder_warning(tmp_path, monkeypatch, capsys, caplog):
    # covers: TQ-200d-5-iv
    # angle: real_artifact
    lock = lk.install(monkeypatch, "row", first_only=True)
    try:
        result = rn.run("produced", tmp_path, monkeypatch, capsys, caplog, [rn.ok_reply("produced")], rows=1)
        warned = _warnings(result)
        assert warned, "the helper logged no warning to quote"
        message, name = warned[0], lock.roots[0].name
        lead = re.split(r"[A-Za-z]:|/|\\", message.split(name)[0])[0].strip()
    finally:
        lock.cleanup()
    assert len(lead) >= 10, f"warning has no fixed wording before the folder: {message!r}"
    readme = docs.text_of(docs.README)
    howto = docs.text_of(docs.HOW_TO)
    assert "Temp folders." in readme and re.search(r"never stops? the run", readme), "README bullet missing"
    part = docs.section(howto, "A temp folder left behind")
    assert part.strip(), "how-to has no section 'A temp folder left behind'"
    assert lead in part, f"how-to does not quote the warning wording {lead!r}"
    assert lead in readme, f"README does not quote the warning wording {lead!r}"
    assert re.search(r"(not stop|never stop|does not end)", part), "how-to does not say the run is not stopped"
