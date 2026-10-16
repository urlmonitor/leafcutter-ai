#!/usr/bin/env python3
"""
MODULE: commit_step_base
GOAL: The pieces every part of the shared commit step (commit_changes.py) leans on:
    the refusal type, the one answer object with every contract key, the git
    runners, and the step's configuration read from config/commit_step.json.
BUSINESS CONTEXT: Split out of commit_changes.py so the step can grow (BO-4500a-4
    moves its codes and vocabulary into config) without crossing the file-size
    limit. Behaviour is unchanged by the split.
ARCHITECTURE: Stdlib only. Lives beside commit_changes.py in scripts/ (source tree
    and deployed install alike), so the script's own directory on sys.path is
    enough to import it; no package or path manipulation.

DECISION HISTORY:
  - 2026-10-16 [BO-4500]: Created by moving StepRefusal, _answer, _git, _git_out
    and _ceiling out of commit_changes.py verbatim.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

_CONFIG_ENV = "LEAFCUTTER_COMMIT_STEP_CONFIG"
_CEILING_KEY = "max_automated_fix_retries"
_DEFAULT_CEILING = 3


class StepRefusal(Exception):
    """A request the step declines; carries the answer's reason_code and reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def answer(status: str, **fields: object) -> dict:
    """Build the one answer object with every contract key present."""
    result: dict = {"status": status, "sha": None, "paths": [], "added_parents": [], "unlisted_changes": []}
    result.update(hook_name=None, failing_files=[], reason_code=None, reason=None, hook_output=None)
    result.update(autofixed=[], skip_request_ignored=[], remedy=None, handoff=None)
    result.update(fields)
    return result


def git(args: list[str], cwd: Path, env: dict | None = None, stdin: str | None = None):
    """Run git; an unrunnable git is a refusal, a non-zero exit is the caller's to read."""
    try:
        return subprocess.run(["git", *args], cwd=cwd, env=env, input=stdin, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise StepRefusal("git_unavailable", f"cannot run git: {exc}") from exc


def git_out(args: list[str], cwd: Path, env: dict | None = None) -> str:
    """Run git and return stdout, refusing on a non-zero exit."""
    proc = git(args, cwd, env)
    if proc.returncode != 0:
        raise StepRefusal("git_error", f"git {' '.join(args[:2])} failed: {proc.stderr.strip()}")
    return proc.stdout


def ceiling() -> int:
    """Read max_automated_fix_retries once, before any check runs (BO-4500a-3-ii).

    Source: the file named by LEAFCUTTER_COMMIT_STEP_CONFIG, else config/commit_step.json
    beside the source tree or the deployed install; default 3 when no file exists.
    """
    here = Path(__file__).resolve().parent
    override = os.environ.get(_CONFIG_ENV)
    for path in [Path(override)] if override else [here.parent.parent / "config" / "commit_step.json", here.parent / "config" / "commit_step.json"]:
        if not path.is_file():
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get(_CEILING_KEY, _DEFAULT_CEILING)
        except (OSError, ValueError, AttributeError) as exc:
            raise StepRefusal("step_config_unreadable", f"cannot read {path}: {exc}") from exc
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise StepRefusal("step_config_unreadable", f"{path}: {_CEILING_KEY} must be a non-negative integer")
        return value
    return _DEFAULT_CEILING
