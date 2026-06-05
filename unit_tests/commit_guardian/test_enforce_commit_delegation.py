"""Tests for templates/hooks/enforce_commit_delegation.py.

Covers the four test cases specified in AC-4:
  - Allow non-git-commit commands (e.g. git status).
  - Block git commit when COMMIT_AGENT_MODE is unset.
  - Allow git commit when COMMIT_AGENT_MODE=1 is set.
  - Fail-open on malformed stdin.
  - Fail-open when the command key is missing from the payload.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Module loading helpers
# ---------------------------------------------------------------------------

_HOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "hooks"
    / "enforce_commit_delegation.py"
)


def _load_hook_module() -> Any:
    """Dynamically load enforce_commit_delegation.py as a module.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location(
        "enforce_commit_delegation", _HOOK_PATH
    )
    assert spec is not None, f"Could not load spec from {_HOOK_PATH}"
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return module


_hook = _load_hook_module()


# ---------------------------------------------------------------------------
# Helper: invoke main() with controlled stdin and env
# ---------------------------------------------------------------------------


def _run_main(payload: dict | str, env_override: dict | None = None) -> tuple[int, str]:
    """Invoke hook main() with the given payload and env, capturing stdout.

    Args:
        payload: Dict to JSON-encode as stdin, or a raw string for
            malformed-input tests.
        env_override: Optional dict of env var overrides. Keys present with
            value ``None`` are deleted from the effective env; others are set.

    Returns:
        ``(exit_code, stdout_text)`` tuple. Exit code is captured via
        ``SystemExit``; 0 when main returns normally without raising.
    """
    if isinstance(payload, dict):
        stdin_text = json.dumps(payload)
    else:
        stdin_text = payload

    env = os.environ.copy()
    if env_override:
        for k, v in env_override.items():
            if v is None:
                env.pop(k, None)
            else:
                env[k] = v

    stdout_capture = io.StringIO()

    with (
        mock.patch("sys.stdin", io.StringIO(stdin_text)),
        mock.patch.dict(os.environ, env, clear=True),
        mock.patch("sys.stdout", stdout_capture),
    ):
        try:
            _hook.main()
            exit_code = 0
        except SystemExit as exc:
            exit_code = exc.code if exc.code is not None else 0

    return exit_code, stdout_capture.getvalue()


# ---------------------------------------------------------------------------
# AC-4 test cases
# ---------------------------------------------------------------------------


def test_allows_non_commit_command() -> None:
    """AC-4: payload with command 'git status' exits 0 and prints nothing."""
    payload = {"tool_input": {"command": "git status"}}
    exit_code, stdout = _run_main(payload, env_override={"COMMIT_AGENT_MODE": None})
    assert exit_code == 0
    assert stdout == ""


def test_blocks_git_commit_without_env_var() -> None:
    """AC-4: git commit without COMMIT_AGENT_MODE emits a block decision."""
    payload = {"tool_input": {"command": "git commit -m foo"}}
    exit_code, stdout = _run_main(payload, env_override={"COMMIT_AGENT_MODE": None})
    assert exit_code == 0
    assert stdout.strip() != "", "Expected a block decision on stdout"
    decision = json.loads(stdout.strip())
    assert decision.get("decision") == "block"
    assert "reason" in decision
    # Verify the reason covers the three required elements from AC-6
    reason = decision["reason"]
    assert "blocked" in reason.lower() or "block" in reason.lower()
    assert "commit agent" in reason.lower() or "dispatch" in reason.lower()


def test_allows_git_commit_with_env_var() -> None:
    """AC-4: git commit with COMMIT_AGENT_MODE=1 exits 0 and prints nothing."""
    payload = {"tool_input": {"command": "git commit -m foo"}}
    exit_code, stdout = _run_main(payload, env_override={"COMMIT_AGENT_MODE": "1"})
    assert exit_code == 0
    assert stdout == ""


def test_fail_open_on_malformed_stdin() -> None:
    """AC-4: empty / malformed stdin exits 0 and raises no exception."""
    for bad_input in ("", "not json {{{}}", "\x00\x01\x02"):
        exit_code, stdout = _run_main(bad_input, env_override={"COMMIT_AGENT_MODE": None})
        assert exit_code == 0, f"Expected exit 0 on malformed input {bad_input!r}"


def test_fail_open_on_missing_command_key() -> None:
    """AC-4: payload with no 'command' key exits 0 (non-git-commit → allow)."""
    payload = {"tool_input": {"other_key": "some value"}}
    exit_code, stdout = _run_main(payload, env_override={"COMMIT_AGENT_MODE": None})
    assert exit_code == 0
    assert stdout == ""
