"""
MODULE: test_tq200b1i_prompt_file
GOAL: Prove the agent eval runner hands an agent's template to the claude CLI through a
    file (--system-prompt-file in label mode, --append-system-prompt-file in artifact
    mode) and never as a command-line argument, so a template over the Windows
    command-line limit (~32,767 chars, WinError 206) still launches. The file must hold
    exactly the prompt during the call and be gone afterwards, even when the call raises.

    No model call: subprocess.run is replaced by a recorder.

Target module: scripts/evals/run_agent_eval.py
AC: TQ-200b-1-i
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

_PROMPT = ("You are a very large agent template. Line with unicode \u00b7 and text.\n" * 1000)[:60_000]
_ENVELOPE = json.dumps({"is_error": False, "result": "ok"})
_ARG_LIMIT = 30_000


def _flag_value(cmd: list[str], flag: str) -> str | None:
    """Return the argument following `flag`, or None when the flag is absent."""
    return cmd[cmd.index(flag) + 1] if flag in cmd else None


def _record_run(monkeypatch: pytest.MonkeyPatch, file_flag: str, *, raises: bool = False) -> dict:
    """Replace subprocess.run; capture argv and the prompt file's content mid-call."""
    seen: dict = {"cmd": None, "path": None, "content": None}

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        seen["cmd"] = list(cmd)
        seen["path"] = _flag_value(cmd, file_flag)
        if seen["path"] is not None and Path(seen["path"]).exists():
            seen["content"] = Path(seen["path"]).read_text(encoding="utf-8")
        if raises:
            raise OSError("simulated launch failure")
        return subprocess.CompletedProcess(cmd, 0, stdout=_ENVELOPE, stderr="")

    monkeypatch.setattr(ev.subprocess, "run", fake_run)
    return seen


def test_label_mode_passes_the_template_through_a_system_prompt_file(monkeypatch: pytest.MonkeyPatch) -> None:
    # covers: TQ-200b-1-i
    seen = _record_run(monkeypatch, "--system-prompt-file")
    ev.invoke_via_cli(_PROMPT, "anything", "haiku", 5)
    cmd = seen["cmd"]
    assert seen["path"] is not None, "argv has no --system-prompt-file"
    assert "--system-prompt" not in cmd
    assert max(len(a) for a in cmd) <= _ARG_LIMIT
    assert seen["content"] == _PROMPT
    assert not Path(seen["path"]).exists()


def test_artifact_mode_passes_the_template_through_an_append_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # covers: TQ-200b-1-i
    seen = _record_run(monkeypatch, "--append-system-prompt-file")
    ev.invoke_agent_writer(_PROMPT, "anything", "opus", 5, tmp_path, "Read")
    cmd = seen["cmd"]
    assert seen["path"] is not None, "argv has no --append-system-prompt-file"
    assert "--append-system-prompt" not in cmd
    assert max(len(a) for a in cmd) <= _ARG_LIMIT
    assert seen["content"] == _PROMPT
    assert not Path(seen["path"]).exists()


def test_prompt_file_is_removed_when_the_cli_call_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    # covers: TQ-200b-1-i
    seen = _record_run(monkeypatch, "--system-prompt-file", raises=True)
    with pytest.raises(ev.ModelInvocationError, match="claude CLI could not be launched"):
        ev.invoke_via_cli(_PROMPT, "anything", "haiku", 5)
    assert seen["path"] is not None, "argv has no --system-prompt-file"
    assert seen["content"] == _PROMPT
    assert not Path(seen["path"]).exists()
