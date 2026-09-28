"""Behavioural tests: enforce_commit_delegation recognises a commit by argv.

Covers BP-1100d-3. The hook used to test ``"git commit" in command``, which
missed ``git -C <path> commit`` (and every other global-option spelling) and
blocked commands that only mentioned the phrase inside a quoted argument
(KI-CG-20260925-commit-delegation-hook-misses-git-dash-c, KI-CG-016).

Every test runs the real hook script as a subprocess with a PreToolUse JSON
payload on stdin, the same way Claude Code invokes it. The hook's contract is
"exit 0 always; a block is a JSON ``{"decision": "block"}`` line on stdout",
so each test asserts both the exit code and the presence or absence of that
decision.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_HOOK_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "templates"
    / "hooks"
    / "enforce_commit_delegation.py"
)


def _run_hook(command: str) -> tuple[int, str]:
    """Run the real hook as a subprocess on a Bash PreToolUse payload.

    COMMIT_AGENT_MODE is removed from the child environment so the only
    exemption available is the one spelled inside ``command`` itself.

    Args:
        command: The Bash command string placed in ``tool_input.command``.

    Returns:
        ``(exit_code, stdout)`` of the hook process.
    """
    env = {k: v for k, v in os.environ.items() if k != "COMMIT_AGENT_MODE"}
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc = subprocess.run(
        [sys.executable, str(_HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    return proc.returncode, proc.stdout


def _is_block(stdout: str) -> bool:
    """Return True when the hook's stdout carries a block decision.

    Args:
        stdout: Captured stdout of the hook process.

    Returns:
        True when stdout parses as JSON with ``decision == "block"``.
    """
    text = stdout.strip()
    if not text:
        return False
    return json.loads(text).get("decision") == "block"


_BLOCKED_COMMANDS = [
    "git -C /x commit -m m",
    "git -c user.name=a commit",
    "cd x && git commit -m m",
    "git commit",
    "git --git-dir=/x/.git --work-tree /x commit -m m",
    "/usr/bin/git commit -m m",
    "FOO=1 git -C /x commit --amend",
    "echo $(git -C /x commit -m m)",
    "git status; git -C /x commit -m m",
]

_ALLOWED_COMMANDS = [
    'gh pr create --body "run git commit later"',
    'echo "git commit"',
    "git status",
    "git log --grep commit",
    'gh pr create --title t --body "a && git commit -m x"',
    "git -C /x log --grep commit",
]


@pytest.mark.parametrize("command", _BLOCKED_COMMANDS)
def test_ac_bp1100d3_commit_spellings_are_blocked(command: str) -> None:
    """Every spelling that really runs git's commit subcommand is blocked (covers: BP-1100d-3)."""
    # covers: BP-1100d-3
    exit_code, stdout = _run_hook(command)
    assert exit_code == 0
    assert _is_block(stdout), f"expected a block decision for {command!r}, got {stdout!r}"


@pytest.mark.parametrize("command", _ALLOWED_COMMANDS)
def test_ac_bp1100d3_commands_that_only_mention_commit_are_allowed(command: str) -> None:
    """Quoted mentions and non-commit git subcommands are not blocked (covers: BP-1100d-3)."""
    # covers: BP-1100d-3
    exit_code, stdout = _run_hook(command)
    assert exit_code == 0
    assert not _is_block(stdout), f"expected no block for {command!r}, got {stdout!r}"


def test_ac_bp1100d3_inline_commit_agent_mode_allows_dash_c_commit() -> None:
    """The commit agent's inline COMMIT_AGENT_MODE=1 prefix still exempts -C (covers: BP-1100d-3)."""
    # covers: BP-1100d-3
    exit_code, stdout = _run_hook("COMMIT_AGENT_MODE=1 git -C /x commit -m m")
    assert exit_code == 0
    assert stdout.strip() == ""


def test_ac_bp1100d3_unparseable_quoting_fails_closed() -> None:
    """A segment shlex cannot tokenise is blocked when git precedes commit (covers: BP-1100d-3)."""
    # covers: BP-1100d-3
    exit_code, stdout = _run_hook('git -C "/unterminated commit -m m')
    assert exit_code == 0
    assert _is_block(stdout)
