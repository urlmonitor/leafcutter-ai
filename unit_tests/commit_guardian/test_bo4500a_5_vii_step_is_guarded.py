"""BO-4500a-5-vii -- running the shared commit step is guarded exactly like a direct commit.

The shared step (templates/scripts/commit_changes.py, deployed as
.leafcutter/scripts/commit_changes.py) records a commit internally, so a guard that only
looks for a ``git commit`` argv cannot see it. Every test feeds a real PreToolUse Bash
payload on stdin to the real hook as a subprocess and reads its decision, against BOTH the
template copy (templates/hooks/) and the DEPLOYED copy (.claude/hooks/ inside the shared
reference layout, read-only: ``shared_layout_reader``; no private build).

RED BASELINE (expected, correct): the two "step is blocked" tests (1 and 4) are red today
because the hook allows the step call (assertion red, the hook ran and decided "allow").
Tests 2 and 3 are the must-not-regress halves and are GREEN today by design: the step call
and the quoted mention are allowed now and must stay allowed after the change.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent.parent
_TEMPLATE_HOOK = _REPO / "templates" / "hooks" / "enforce_commit_delegation.py"

_STEP_ARGS = "--message-file m.txt a.py"
_STEP_CALL = f"python3 .leafcutter/scripts/commit_changes.py {_STEP_ARGS}"
_DIRECT_COMMIT = "git commit -m m"


def _hooks(layout: Path) -> dict[str, Path]:
    """Return the template and the deployed hook copies, keyed by label."""
    return {
        "template": _TEMPLATE_HOOK,
        "deployed": layout / ".claude" / "hooks" / "enforce_commit_delegation.py",
    }


def _decide(hook: Path, command: str, commit_agent_env: bool = False) -> tuple[int, dict | None, str]:
    """Run ``hook`` on a Bash payload; return (exit code, parsed decision or None, stdout)."""
    assert hook.is_file(), f"{hook} does not exist (deploy-manifest gap?)"
    env = {k: v for k, v in os.environ.items() if k != "COMMIT_AGENT_MODE"}
    if commit_agent_env:
        env["COMMIT_AGENT_MODE"] = "1"
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc = subprocess.run(
        [sys.executable, str(hook)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
        check=False,
    )
    text = proc.stdout.strip()
    return proc.returncode, (json.loads(text) if text else None), proc.stdout


def _blocked(decision: dict | None) -> bool:
    return decision is not None and decision.get("decision") == "block"


@pytest.mark.shared_layout_reader
def test_non_commit_agent_running_the_step_is_blocked(shared_reference_layout: Path) -> None:
    # covers: BO-4500a-5-vii
    # angle: criterion
    """A non-commit-agent Bash call running the shared step is blocked with the SAME message
    the hook gives a direct `git commit`.

    Wrong version caught: matching only the literal string `git commit` (the step call has
    no such argv, so it would be allowed).
    """
    for label, hook in _hooks(shared_reference_layout).items():
        code, direct, _ = _decide(hook, _DIRECT_COMMIT)
        assert code == 0 and _blocked(direct), f"[{label}] control: direct commit must block: {direct}"
        code, step, out = _decide(hook, _STEP_CALL)
        assert code == 0, f"[{label}] hook exit {code}"
        assert _blocked(step), f"[{label}] step call was not blocked: {out!r}"
        assert step is not None and direct is not None
        assert step["reason"] == direct["reason"], f"[{label}] block message differs from direct commit"


@pytest.mark.shared_layout_reader
def test_commit_agent_running_the_step_is_allowed(shared_reference_layout: Path) -> None:
    # covers: BO-4500a-5-vii
    # angle: criterion
    """The commit agent's call (inline COMMIT_AGENT_MODE=1 prefix, or process env) is allowed.

    Must-not-regress half: green today, must stay green once the step is guarded.
    """
    for label, hook in _hooks(shared_reference_layout).items():
        code, inline, out = _decide(hook, f"COMMIT_AGENT_MODE=1 {_STEP_CALL}")
        assert code == 0 and not _blocked(inline), f"[{label}] inline-prefix call blocked: {out!r}"
        code, via_env, out = _decide(hook, _STEP_CALL, commit_agent_env=True)
        assert code == 0 and not _blocked(via_env), f"[{label}] env-var call blocked: {out!r}"


@pytest.mark.shared_layout_reader
def test_step_name_inside_quoted_text_is_allowed(shared_reference_layout: Path) -> None:
    # covers: BO-4500a-5-vii
    # angle: boundary
    """A `gh pr create` whose --body only mentions the step's name is not a commit: allowed.

    Must-not-regress half: green today; catches a naive substring match on the step name.
    """
    command = 'gh pr create --title x --body "runs commit_changes.py --message-file m a.py"'
    for label, hook in _hooks(shared_reference_layout).items():
        code, decision, out = _decide(hook, command)
        assert code == 0 and not _blocked(decision), f"[{label}] quoted mention blocked: {out!r}"


_BLOCKED_VARIANTS = [
    f"python .leafcutter/scripts/commit_changes.py {_STEP_ARGS}",
    f"python3 .leafcutter/scripts/commit_changes.py {_STEP_ARGS}",
    f"python3 templates/scripts/commit_changes.py {_STEP_ARGS}",
    f"./templates/scripts/commit_changes.py {_STEP_ARGS}",
    f".leafcutter/scripts/commit_changes.py {_STEP_ARGS}",
    f"python3 /home/u/proj/.leafcutter/scripts/commit_changes.py {_STEP_ARGS}",
    f"/home/u/proj/.leafcutter/scripts/commit_changes.py {_STEP_ARGS}",
    f"/usr/bin/python3 /home/u/proj/templates/scripts/commit_changes.py {_STEP_ARGS}",
    f"env FOO=1 python3 .leafcutter/scripts/commit_changes.py {_STEP_ARGS}",
    f"sh -c 'python3 .leafcutter/scripts/commit_changes.py {_STEP_ARGS}'",
    f"echo hi && python3 .leafcutter/scripts/commit_changes.py {_STEP_ARGS}",
]


@pytest.mark.shared_layout_reader
def test_path_and_interpreter_variants_are_all_recognised(shared_reference_layout: Path) -> None:
    # covers: BO-4500a-5-vii
    # angle: discrimination
    """Every interpreter / path / wrapper spelling of the step is blocked outside the commit
    agent; an unrelated script is allowed (control).

    Wrong versions caught: recognising only `python3` + one relative path; only the deployed
    (or only the template) location; ignoring env/sh -c wrappers; blocking every python call.
    """
    failures: list[str] = []
    for label, hook in _hooks(shared_reference_layout).items():
        for command in _BLOCKED_VARIANTS:
            code, decision, _ = _decide(hook, command)
            if code != 0 or not _blocked(decision):
                failures.append(f"[{label}] not blocked: {command}")
        code, other, _ = _decide(hook, "python3 scripts/other.py --message-file m.txt a.py")
        if code != 0 or _blocked(other):
            failures.append(f"[{label}] control wrongly blocked: python3 scripts/other.py")
    assert not failures, "\n".join(failures)
