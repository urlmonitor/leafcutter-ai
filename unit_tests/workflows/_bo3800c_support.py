"""Shared helpers for the BO-3800c tests (the demand a refusal states reaches the
restructuring specialist intact).

Builds on ``_bo3800b_support`` (which EXECUTES build-feature.js / build-ticket.js
through the driver harness and reports what the run actually dispatched).

Fixture authenticity (BO-3800c-2)
---------------------------------
The complexity refusal record is NEVER hand-typed. ``real_complexity_record``
builds a real git repository (source generated, not a checked-in literal), stages
a real change, and runs the real ``check_complexity.py`` against it. The record
is then read from that run's own output.

The exact transport of the machine-readable record (marker text, key name) is the
coder's decision (GE-132a-3 fixes only its content: one entry per refused
function, ``{path, function, score, ceiling, reason}``, in refusal order), so
``extract_record`` accepts any output line that carries a JSON list of such
entries. It does NOT accept the human sentence: the run must never parse it.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import _bo3800b_support as S  # noqa: F401  (re-exported for the test files)

H = S.H
CHECK = Path(H.REPO_ROOT) / "templates" / "scripts" / "commit_guardian" / "check_complexity.py"
RECORD_KEYS = {"path", "function", "score", "ceiling", "reason"}
GIT_TIMEOUT = 60


def _git(args, cwd):
    done = subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True, timeout=GIT_TIMEOUT, check=False
    )
    assert done.returncode == 0, f"git {args}: {done.stdout}{done.stderr}"
    return done.stdout


def function_source(name: str, score: int) -> str:
    """Source for a function scoring exactly ``score`` (base 1, +1 per ``if``)."""
    body = "".join(f"    if x == {i}:\n        pass\n" for i in range(score - 1))
    return f"def {name}(x):\n{body}    return x\n"


def extract_record(output: str):
    """The machine-readable record in ``output``: the first JSON list whose entries
    all carry exactly the GE-132a-3 keys; ``None`` when the output has none."""
    for line in output.splitlines():
        for opener in ("[",):
            at = line.find(opener)
            if at < 0:
                continue
            try:
                value = json.loads(line[at:])
            except ValueError:
                continue
            if isinstance(value, list) and value and all(
                isinstance(e, dict) and set(e) == RECORD_KEYS for e in value
            ):
                return value
    return None


def real_complexity_record(root: Path, baseline: dict[str, int], staged: dict[str, int]):
    """Run the REAL check on a real staged change in a scratch repo.

    ``baseline`` maps function name -> score committed in scripts/planner.py;
    ``staged`` maps function name -> score staged on top of it.
    Returns ``(record_or_None, combined_output, exit_code)``.
    """
    root.mkdir(parents=True)
    target = root / "scripts" / "planner.py"
    target.parent.mkdir()
    target.write_text("".join(function_source(n, s) for n, s in baseline.items()) or "X = 1\n", encoding="utf-8")
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "bo3800c@example.com"], root)
    _git(["config", "user.name", "BO-3800c fixture"], root)
    _git(["add", "-A"], root)
    _git(["commit", "-q", "--no-verify", "-m", "baseline"], root)
    target.write_text("".join(function_source(n, s) for n, s in staged.items()), encoding="utf-8")
    _git(["add", "scripts/planner.py"], root)
    env = {k: v for k, v in os.environ.items() if not k.startswith("CLAUDE") and k != "COMMIT_AGENT_MODE"}
    done = subprocess.run(
        [sys.executable, str(CHECK)], cwd=str(root), capture_output=True, text=True,
        timeout=GIT_TIMEOUT, check=False, env=env,
    )
    output = done.stdout + done.stderr
    return extract_record(output), output, done.returncode


def result_text(obs) -> str:
    """The stop a run reported, as text (message plus the whole result for context)."""
    result = obs.get("result") or {}
    return f"{result.get('message', '')} || {json.dumps(result, sort_keys=True)}"


__all__ = [
    "S", "H", "real_complexity_record", "function_source", "extract_record", "result_text",
]
