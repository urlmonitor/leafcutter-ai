"""
MODULE: unit_tests/build_orchestration/_bo_4300c_6_fixtures.py
AC: BO-4300c-6 (a protection canary never mistakes a git failure for a pass)
GOAL: Shared real-repo helpers for the BO-4300c-6 proofs: an isolated git env with the
    repository-locating variables removed, a runner for the DEPLOYED canary as its own
    process, a real temporary repo builder, and the one inert proof shared by the
    deployed-canary arm and the reject-everything mutant arm.
NOT a test file (leading underscore).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path

# fixtures first: it and the builders import each other, and only this order resolves.
from unit_tests.build_orchestration._workspace_maker_fixtures import ensure_deployed_layout
from unit_tests.build_orchestration._workspace_maker_builders import (
    _isolated_git_env,
    _run_git,
)

MARKER = "PRECOMMIT_CANARY_REJECTED"
_REPO_VARS = (
    "GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_PREFIX",
)
REPORT = re.compile(r"^precommit_canary: git (?P<args>.+?) exited (?P<rc>\d+): ?(?P<text>.*)$", re.M)


def clean_env() -> dict[str, str]:
    env = _isolated_git_env()
    for name in _REPO_VARS:
        env.pop(name, None)
    return env


def deployed_canary() -> Path:
    return ensure_deployed_layout() / ".leafcutter" / "scripts" / "commit_guardian" / "precommit_canary.py"


def declared(stage: str) -> dict:
    cfg = json.loads((deployed_canary().parent / "commit_guardian.json").read_text(encoding="utf-8"))
    return cfg["stage_canaries"][stage]


def run_canary(args: list[str], cwd: Path, env: dict | None = None, script: Path | None = None):
    """Run the canary as its own program (sys.executable + absolute path), bytes-safe."""
    done = subprocess.run(
        [sys.executable, str(script or deployed_canary()), *args],
        cwd=str(cwd), env=env or clean_env(), capture_output=True,
    )
    done.out = done.stdout.decode("utf-8", "replace")
    done.err = done.stderr.decode("utf-8", "replace")
    return done


def git(args: list[str], cwd: Path, env: dict | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), env=env or clean_env(),
                          capture_output=True, text=True)


def head_commit_bytes(repo: Path) -> bytes:
    return subprocess.run(["git", "cat-file", "commit", "HEAD"], cwd=str(repo), env=clean_env(),
                          capture_output=True).stdout


def write(repo: Path, rel: str, text: str = "x\n") -> None:
    target = repo / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))


def init_repo(tmp: Path, name: str = "proj") -> Path:
    repo = Path(tmp) / name
    _run_git(["init", "-q", "-b", "main"], repo, mkdir=True)
    for key, val in (("user.email", "bo4300@example.com"), ("user.name", "BO"), ("commit.gpgsign", "false")):
        _run_git(["config", key, val], repo)
    write(repo, "base.txt", "base\n")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", "base"], repo)
    return repo


def merge_branch(repo: Path, branch: str, rel: str) -> None:
    """A branch adding *rel*, merged into main with a merge commit (never fast-forward)."""
    _run_git(["checkout", "-q", "-b", branch], repo)
    write(repo, rel)
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", f"add {branch}"], repo)
    _run_git(["checkout", "-q", "main"], repo)
    write(repo, f"main_{branch}.txt")
    _run_git(["add", "-A"], repo)
    _run_git(["commit", "-q", "-m", f"main {branch}"], repo)
    _run_git(["merge", "--no-ff", "-q", "-m", f"merge {branch}", branch], repo)


def stage_bytes_paths(repo: Path, names: list[bytes]) -> None:
    """Stage index entries with arbitrary path bytes through update-index --index-info."""
    blob = subprocess.run(["git", "hash-object", "-w", "--stdin"], cwd=str(repo), env=clean_env(),
                          input=b"x\n", capture_output=True, check=True).stdout.strip()
    info = b"".join(b"100644 " + blob + b"\t" + n + b"\n" for n in names)
    subprocess.run(["git", "update-index", "--add", "--index-info"], cwd=str(repo), env=clean_env(),
                   input=info, capture_output=True, check=True)


def non_repo_env(tmp: Path) -> dict[str, str]:
    """Env whose GIT_DIR names an empty folder that is not a repository."""
    empty = Path(tmp) / "not-a-repo"
    empty.mkdir(exist_ok=True)
    env = clean_env()
    env["GIT_DIR"] = str(empty)
    env["GIT_CEILING_DIRECTORIES"] = str(Path(tmp).parent)
    return env


def parse_report(err: str) -> tuple[list[str], int, str]:
    """(git args, reported rc, first text) of the single git-failure report line."""
    found = REPORT.findall(err)
    if len(found) != 1:
        raise AssertionError(f"expected exactly one git-failure report line, got {len(found)}: {err!r}")
    args, rc, text = found[0]
    return shlex.split(args), int(rc), text


def commit_msg_shim(repo: Path) -> None:
    hook = repo / ".git" / "hooks" / "commit-msg"
    hook.parent.mkdir(exist_ok=True)
    py = Path(sys.executable).as_posix()
    hook.write_bytes(
        f'#!/bin/sh\nexec "{py}" "{deployed_canary().as_posix()}" --stage commit-msg "$1"\n'.encode()
    )
    os.chmod(hook, 0o755)


def observe(script: Path, argmap: dict[str, list[str]], tmp: Path) -> dict:
    """Run the three canary entries (args after the script, per stage) on ordinary work in a real
    repo, asserting the preconditions that make the observation meaningful."""
    repo = init_repo(tmp, "observe")
    write(repo, "ordinary_staged.txt")
    _run_git(["add", "ordinary_staged.txt"], repo)
    staged = git(["diff", "--cached", "--name-only"], repo).stdout.split()
    if staged != ["ordinary_staged.txt"]:
        raise AssertionError(f"precondition: staged list {staged!r}")
    msg = Path(tmp) / "ORDINARY_MSG"
    msg.write_bytes(b"chore: ordinary message\n")
    out = {
        "pre-commit": run_canary(argmap["pre-commit"], repo, script=script),
        "commit-msg": run_canary([*argmap["commit-msg"], str(msg)], repo, script=script),
    }
    _run_git(["commit", "-q", "-m", "ordinary"], repo)
    merge_branch(repo, "ordinary-branch", "ordinary_merged.txt")
    if git(["rev-parse", "-q", "--verify", "ORIG_HEAD"], repo).returncode != 0:
        raise AssertionError("precondition: ORIG_HEAD missing after merge")
    added = git(["diff", "--name-only", "--diff-filter=A", "ORIG_HEAD", "HEAD"], repo).stdout.split()
    if "ordinary_merged.txt" not in added:
        raise AssertionError(f"precondition: merge added {added!r}")
    out["post-merge"] = run_canary(argmap["post-merge"], repo, script=script)
    out["repo"] = repo
    return out


def assert_inert(obs: dict, stages: tuple[str, ...] = ("pre-commit", "commit-msg", "post-merge")) -> None:
    """The shared inert proof: each stage exits 0, no marker, no git-failure report."""
    for stage in stages:
        done = obs[stage]
        text = done.out + done.err
        if done.returncode != 0 or MARKER in text or "exited" in done.err:
            raise AssertionError(f"{stage} canary not inert: rc={done.returncode} {text!r}")
