"""
MODULE: test_cli_failure_detail
GOAL: Prove that a `claude` CLI exiting non-zero with EMPTY stderr still yields a row
    error naming the real cause: the `result` text of its stdout JSON envelope. This is
    the CI no-credential case, {"is_error":true,"result":"Not logged in · Please run
    /login"}, which used to surface as a blank "exited 1:" message. The tests cover label
    mode (run_label_eval -> invoke_via_cli) and artifact mode (invoke_agent_writer), and
    show that non-empty stderr still takes precedence.

    No model call: subprocess.run is replaced by a recorded CompletedProcess.

Target modules: scripts/evals/cli_envelope.py, scripts/evals/run_agent_eval.py
Ticket: TICKET-20261006-AgentEvalGateHonestAboutCredentials (AC-2)
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "scripts" / "evals"))
import run_agent_eval as ev  # noqa: E402

_NOT_LOGGED_IN = "Not logged in · Please run /login"
_NOT_LOGGED_IN_ENVELOPE = json.dumps({"is_error": True, "result": _NOT_LOGGED_IN})


def _fake_cli(monkeypatch: pytest.MonkeyPatch, *, returncode: int, stdout: str, stderr: str = "") -> None:
    """Make every subprocess.run return this recorded CLI outcome."""

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(ev.subprocess, "run", fake_run)


def _label_row_error(monkeypatch: pytest.MonkeyPatch, **cli: object) -> str:
    """Run one live-mode label row through the real CLI path; return its row error."""
    _fake_cli(monkeypatch, **cli)
    agent_cfg = {"label_axes": ["needs_flow"], "input_field": "request", "model": "haiku"}
    rows = [{"id": "row-1", "request": "anything", "expected": {"needs_flow": False}}]
    [record] = ev.run_label_eval(rows, "system", agent_cfg, self_test=False, timeout=5, backend="cli")
    assert record["score"]["passed"] is False
    return record["parse_error"]


def _artifact_error(monkeypatch: pytest.MonkeyPatch, sandbox: Path, **cli: object) -> str:
    """Invoke the artifact-mode writer against the recorded CLI; return the raised message."""
    _fake_cli(monkeypatch, **cli)
    with pytest.raises(ev.ModelInvocationError) as excinfo:
        ev.invoke_agent_writer("system", "anything", "opus", 5, sandbox, "Read")
    return str(excinfo.value)


def test_empty_stderr_row_error_carries_cli_stdout_result(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # covers: TQ-200b-2
    # angle: criterion
    """Exit 1 + empty stderr + not-logged-in envelope: both modes name the stdout result."""
    label_error = _label_row_error(monkeypatch, returncode=1, stdout=_NOT_LOGGED_IN_ENVELOPE)
    artifact_error = _artifact_error(monkeypatch, tmp_path, returncode=1, stdout=_NOT_LOGGED_IN_ENVELOPE)

    assert label_error == f"claude CLI exited 1: {_NOT_LOGGED_IN}"
    assert artifact_error == f"agent CLI exited 1: {_NOT_LOGGED_IN}"


def test_stderr_still_wins_and_non_json_stdout_is_quoted_raw(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    # covers: TQ-200b-2
    # angle: boundary
    """Stderr keeps precedence; non-JSON stdout is quoted raw; exit 0 still returns the reply."""
    stderr_error = _label_row_error(
        monkeypatch, returncode=1, stdout=_NOT_LOGGED_IN_ENVELOPE, stderr="proxy refused the request\n"
    )
    assert stderr_error == "claude CLI exited 1: proxy refused the request"

    raw_error = _artifact_error(monkeypatch, tmp_path, returncode=2, stdout="  segfault in node  \n")
    assert raw_error == "agent CLI exited 2: segfault in node"

    _fake_cli(monkeypatch, returncode=0, stdout=json.dumps({"result": '{"verdict": "pass"}'}))
    assert ev.invoke_agent_writer("system", "anything", "opus", 5, tmp_path, "Read") == '{"verdict": "pass"}'
    assert ev.invoke_via_cli("system", "anything", "haiku", 5) == '{"verdict": "pass"}'
