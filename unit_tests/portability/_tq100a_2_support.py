"""
MODULE: _tq100a_2_support
GOAL: Shared real-git helpers for the TQ-100a-2 / -2-i / -2-ii tests: build a real
    host repository with a linked worktree, run git with a scrubbed environment,
    and read identity keys back exactly as git resolves them.
BUSINESS CONTEXT: A bare temporary directory does not share configuration and so
    cannot exhibit the shared-config identity leak; only a real linked worktree of
    a real repository can.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
IDENTITY_KEYS = ("user.name", "user.email")

FIXTURE_NAME = "Fixture"
FIXTURE_EMAIL = "fixture@example.invalid"
HUMAN_NAME = "Real Human"
HUMAN_EMAIL = "real-human@example.com"

FIXTURE_ENV = {
    "GIT_AUTHOR_NAME": FIXTURE_NAME,
    "GIT_AUTHOR_EMAIL": FIXTURE_EMAIL,
    "GIT_COMMITTER_NAME": FIXTURE_NAME,
    "GIT_COMMITTER_EMAIL": FIXTURE_EMAIL,
}
HUMAN_ENV = {
    "GIT_AUTHOR_NAME": HUMAN_NAME,
    "GIT_AUTHOR_EMAIL": HUMAN_EMAIL,
    "GIT_COMMITTER_NAME": HUMAN_NAME,
    "GIT_COMMITTER_EMAIL": HUMAN_EMAIL,
}


def scrubbed_env(home: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Environment where no global/system git identity is reachable."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    home.mkdir(parents=True, exist_ok=True)
    env.update(
        HOME=str(home),
        USERPROFILE=str(home),
        XDG_CONFIG_HOME=str(home / "xdg"),
        GIT_CONFIG_GLOBAL=str(home / "no-such-global-config"),
        GIT_CONFIG_NOSYSTEM="1",
    )
    env.update(extra or {})
    return env


def git(args: list[str], cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(cwd), env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=120,
    )


def must_git(args: list[str], cwd: Path, env: dict[str, str]) -> str:
    result = git(args, cwd, env)
    if result.returncode != 0:
        msg = f"git {args} failed rc={result.returncode}: {result.stderr}"
        raise AssertionError(msg)
    return result.stdout


def make_host(root: Path, env: dict[str, str], identity: bool = True) -> Path:
    """A real host repository with one commit and, optionally, a recorded identity."""
    host = root / "host"
    host.mkdir()
    must_git(["init", "-q"], host, env)
    if identity:
        must_git(["config", "user.name", HUMAN_NAME], host, env)
        must_git(["config", "user.email", HUMAN_EMAIL], host, env)
    (host / "seed.txt").write_text("seed\n", encoding="utf-8")
    must_git(["add", "seed.txt"], host, env)
    must_git(["commit", "-q", "-m", "seed"], host, dict(env, **HUMAN_ENV))
    return host


def add_worktree(host: Path, root: Path, env: dict[str, str], name: str = "sandbox") -> Path:
    wt = root / name
    must_git(["worktree", "add", "--detach", "-q", str(wt)], host, env)
    return wt


def sandbox_commit(wt: Path, env: dict[str, str]) -> subprocess.CompletedProcess:
    """Commit inside the sandbox the way the fixtures do: identity from env only."""
    (wt / "sandbox.txt").write_text("sandbox\n", encoding="utf-8")
    must_git(["add", "sandbox.txt"], wt, env)
    return git(["commit", "-q", "-m", "sandbox commit"], wt, dict(env, **FIXTURE_ENV))


def read_key(host: Path, key: str, env: dict[str, str]) -> str | None:
    """Value of a key in the host's shared config; None when absent."""
    result = git(["config", "--local", "--get", key], host, env)
    return None if result.returncode != 0 else result.stdout.rstrip("\n")
