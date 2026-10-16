#!/usr/bin/env python3
"""
MODULE: commit_step_base
GOAL: The pieces every part of the shared commit step (commit_changes.py) leans on:
    the refusal type, the one answer object with every contract key (keys, empty
    values and version all read from config/commit_step.json), the guard that keeps
    every emitted reason_code inside its family, and the git runners.
BUSINESS CONTEXT: Split out of commit_changes.py so the step can grow (BO-4500a-4
    moves its codes and vocabulary into config) without crossing the file-size
    limit.
ARCHITECTURE: Stdlib only. Lives beside commit_changes.py in scripts/ (source tree
    and deployed install alike), so the script's own directory on sys.path is
    enough to import it; no package or path manipulation. The vocabulary is loaded
    once by commit_step_config.load_config() and read here through loaded(); this
    module holds no copy of it. The one exception is the bootstrap answer: when the
    config itself could not be loaded there are no keys to read, so answer() prints
    the five C6 keys the criteria require plus reason_code and reason.

DECISION HISTORY:
  - 2026-10-16 [BO-4500]: Created by moving StepRefusal, _answer, _git, _git_out
    and _ceiling out of commit_changes.py verbatim.
  - 2026-10-16 [python-coder/BO-4500a-4]: answer() builds from the loaded config and
    guards reason_code family membership (a violation becomes refused +
    step_vcs_error, visible to callers, rather than a silently wrong code); the
    ceiling comes from the config with no default; retired git_unavailable,
    git_error (-> step_vcs_error) and added step_index_locked detection.
"""

from __future__ import annotations

import copy
import re
import subprocess
import sys
from pathlib import Path

from commit_step_config import ConfigError, allowed_codes, load_config, loaded

_LOCK_PATTERN = re.compile(r"Unable to create '[^']*\.lock': File exists")


class StepRefusal(Exception):
    """A request the step declines; carries the answer's reason_code and reason."""

    def __init__(self, code: str, reason: str) -> None:
        super().__init__(reason)
        self.code = code
        self.reason = reason


def load_contract() -> dict:
    """Load and validate the step's config once; an unusable file is a refusal."""
    try:
        return load_config()
    except ConfigError as exc:
        raise StepRefusal("step_config_unreadable", f"cannot use config/commit_step.json: {exc}") from exc


def _compose(config: dict, status: str, fields: dict) -> dict:
    """Every configured key at its empty value, then status, version and *fields*."""
    result = copy.deepcopy(config["answer_keys"])
    result.update(status=status, answer_version=config["answer_version"])
    result.update(fields)
    return result


def _violation(config: dict, status: str, fields: dict) -> str | None:
    """Why this answer breaks the contract (unknown key, code outside its family), else None."""
    unknown = [k for k in ("status", "answer_version", *fields) if k not in config["answer_keys"]]
    if unknown:
        return f"answer key(s) not declared in config answer_keys: {', '.join(unknown)}"
    code = fields.get("reason_code")
    if code is None and status == "committed":
        return None
    if code is None or code not in allowed_codes(config, status):
        return f"reason_code {code!r} is not allowed for status {status!r}"
    return None


def answer(status: str, **fields: object) -> dict:
    """Build the one answer object; a contract violation is returned as refused + step_vcs_error."""
    config = loaded()
    if config is None:
        # Bootstrap: no config means no keys to read. The approved criteria still
        # require the five C6 keys on every answer, so those plus the refusal's code
        # and reason are the one fixed shape the step carries in code.
        return {"status": status, "reason_code": fields.get("reason_code"), "reason": fields.get("reason"),
                "sha": None, "paths": [], "hook_name": None, "failing_files": []}
    problem = _violation(config, status, fields)
    if problem is None:
        return _compose(config, status, fields)
    print(f"[commit_changes] contract violation: {problem}", file=sys.stderr)
    return _compose(config, "refused", {"reason_code": "step_vcs_error", "reason": f"contract violation: {problem}"})


def _failure(args: list[str], proc: subprocess.CompletedProcess) -> StepRefusal:
    """Map a failed git call to step_index_locked (a held .lock) or step_vcs_error."""
    detail = proc.stderr.strip()
    if _LOCK_PATTERN.search(detail):
        return StepRefusal("step_index_locked", f"git {' '.join(args[:2])} could not take a lock: {detail}")
    return StepRefusal("step_vcs_error", f"git {' '.join(args[:2])} failed: {detail}")


def lock_refusal(output: str) -> StepRefusal | None:
    """A step_index_locked refusal when *output* reports a held .lock file, else None."""
    if _LOCK_PATTERN.search(output):
        return StepRefusal("step_index_locked", f"git could not take a lock: {output.strip()[-400:]}")
    return None


def git(args: list[str], cwd: Path, env: dict | None = None, stdin: str | None = None):
    """Run git; an unrunnable git is a refusal, a non-zero exit is the caller's to read."""
    try:
        return subprocess.run(["git", *args], cwd=cwd, env=env, input=stdin, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise StepRefusal("step_vcs_error", f"cannot run git: {exc}") from exc


def git_out(args: list[str], cwd: Path, env: dict | None = None) -> str:
    """Run git and return stdout, refusing on a non-zero exit."""
    proc = git(args, cwd, env)
    if proc.returncode != 0:
        raise _failure(args, proc)
    return proc.stdout


def refuse_protected_branch(root: Path) -> None:
    """Refuse (BO-4500a-4-i) when the workspace is on no branch, main, master or origin's default.

    Reads only locally recorded state (no network) and runs before any staging or check.
    """
    current = git(["symbolic-ref", "-q", "--short", "HEAD"], root)
    branch = current.stdout.strip()
    if current.returncode != 0 or not branch:
        raise StepRefusal("policy_detached_head", "the workspace is on no branch (detached checkout); commit onto a branch of your own")
    protected = {"main", "master"}
    recorded = git(["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"], root)
    if recorded.returncode == 0 and recorded.stdout.strip().startswith("origin/"):
        protected.add(recorded.stdout.strip()[len("origin/"):])
    if branch in protected:
        raise StepRefusal("policy_protected_branch", f"refusing to commit onto protected branch {branch}; work on a branch of your own")


def ceiling() -> int:
    """max_automated_fix_retries from the loaded config; there is no built-in default."""
    config = loaded()
    if config is None:
        raise StepRefusal("step_config_unreadable", "config/commit_step.json was not loaded")
    return config["max_automated_fix_retries"]
