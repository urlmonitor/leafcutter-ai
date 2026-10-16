"""Completed termination retains bounded evidence without process arguments."""

from types import SimpleNamespace
import json
import subprocess

import pytest

from scripts.background_worker import execution_boundary as boundary


def process_fixture(monkeypatch, stdout, stderr, *, cleanup_fails=False):
    responses = iter([subprocess.TimeoutExpired("not-persisted-secret-command", 1), (stdout, stderr)])
    def communicate(**kwargs):
        value = next(responses)
        if isinstance(value, Exception):
            raise value
        return value
    def kill():
        if cleanup_fails:
            raise OSError("cannot prove termination")
    process = SimpleNamespace(pid=99999, returncode=-9, communicate=communicate, kill=kill)
    from scripts.background_worker import owned_process
    monkeypatch.setattr(owned_process, "start_process", lambda *args, **kwargs: process)
    monkeypatch.setattr(boundary.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess([], 0))
    monkeypatch.setattr(boundary.os, "killpg", lambda *args: None, raising=False)
    ticks = iter([0, 0])
    monkeypatch.setattr(boundary.time, "monotonic", lambda: next(ticks, 2))


def test_timeout_preserves_redacted_bounded_check_output_after_confirmed_kill(tmp_path, monkeypatch):
    # covers: ACD-1300c-1, ACD-1300g-2
    monkeypatch.setenv("TEST_API_KEY", "secret-value-123")
    process_fixture(monkeypatch, "x" * 20000 + "secret-value-123", "check stopped")
    with pytest.raises(boundary.ExecutorError, match="process tree terminated") as caught:
        boundary.run_process(["python", "not-persisted-secret-command"], cwd=tmp_path, timeout=1)
    evidence = caught.value.evidence
    assert evidence["termination_confirmed"] is True and evidence["timed_out"] is True
    assert evidence["stderr"] == "check stopped" and len(evidence["stdout"]) <= 16000
    assert evidence["stdout"].endswith("[REDACTED]")
    assert "secret-value-123" not in json.dumps(evidence)
    assert "not-persisted-secret-command" not in json.dumps(evidence)


def test_local_timeout_uses_event_summary_without_reasoning_or_success_source(tmp_path, monkeypatch):
    # covers: ACD-1300c-1, ACD-1300g-1
    events = [
        {"type": "item.completed", "item": {"type": "reasoning", "text": "private reasoning"}},
        {"type": "item.completed", "item": {"type": "command_execution", "exit_code": 0,
            "aggregated_output": "full source dump", "command": "private command"}},
    ]
    process_fixture(monkeypatch, "\n".join(map(json.dumps, events)), "debug transcript")
    with pytest.raises(boundary.ExecutorError) as caught:
        boundary.run_process(["codex", "exec", "--json"], cwd=tmp_path, timeout=1)
    evidence = caught.value.evidence
    assert evidence["kind"] == "local_harness" and evidence["event_count"] == 2
    assert evidence["tools"] == [{"type": "command_execution", "exit_code": 0}]
    assert all(text not in json.dumps(evidence) for text in (
        "private reasoning", "full source dump", "private command", "debug transcript"))


def test_uncertain_cleanup_never_reports_confirmed_termination(tmp_path, monkeypatch):
    # covers: ACD-1300c-1-i
    process_fixture(monkeypatch, "partial", "", cleanup_fails=True)
    with pytest.raises(boundary.ExecutorError, match="Uncertain process termination") as caught:
        boundary.run_process(["python", "check.py"], cwd=tmp_path, timeout=1)
    assert not getattr(caught.value, "evidence", {}).get("termination_confirmed")
