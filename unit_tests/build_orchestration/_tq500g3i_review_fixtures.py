"""
MODULE: unit_tests/build_orchestration/_tq500g3i_review_fixtures.py
GOAL: Shared drivers for the TQ-500g-3-i review-fix tests: a repo with a chosen base file, the
    check / record CLIs with extra environment, and an in-process loader of consumer_sweep.
BUSINESS CONTEXT: Same real scratch git repos as _tq500g3i_fixtures; nothing the CLIs print is typed
    by hand.
ARCHITECTURE: Not a test file (leading underscore). Builds on _tq500g3i_fixtures.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

import unit_tests.build_orchestration._tq500g3i_fixtures as fx


def with_base(tmp: Path, rel: str, base_src: str, now_src: str) -> fx.Repo:
    """A repo whose base commit holds *rel* = *base_src*; the working tree holds *now_src*."""
    repo = fx.build(tmp, edits=(), add_new_file=False)
    fx.write(repo.path(rel), base_src)
    fx.gitfx.commit_all(repo.root, "base with the file under review")
    fx.write(repo.path(rel), now_src)
    return repo


def run_cli(repo: fx.Repo, args: list[str], stdin: str = "", env_extra: dict | None = None):
    """Run consumer_sweep.py with *args*; return ``(proc, JSON)`` (an AssertionError if no JSON)."""
    env = dict(fx.ix._env(), **(env_extra or {}))  # noqa: SLF001 -- the one shared env builder
    raw = subprocess.run([sys.executable, str(fx.SWEEP), *args], cwd=repo.root, input=stdin.encode("utf-8"),
                         capture_output=True, timeout=600, env=env)
    proc = subprocess.CompletedProcess(raw.args, raw.returncode, raw.stdout.decode("utf-8", "replace"),
                                       raw.stderr.decode("utf-8", "replace"))
    return proc, fx.ix.parse_one_json(proc, "consumer_sweep")


def check_args(repo: fx.Repo) -> list[str]:
    return ["check", "--test-root", str(repo.root), "--base-ref", "HEAD"]


def record_raw(repo: fx.Repo, key: str, raw_stdin: str):
    """Run ``record`` with the given raw stdin text and work key."""
    return run_cli(repo, ["record", "--work-key", key, "--test-root", str(repo.root), "--base-ref", "HEAD"],
                   raw_stdin)


def load_sweep(monkeypatch):
    """Import consumer_sweep in-process (its siblings are bare imports); return ``(sweep, _cs_edits)``."""
    monkeypatch.syspath_prepend(str(fx.SCRIPTS))
    return importlib.import_module("consumer_sweep"), importlib.import_module("_cs_edits")


def run_main(sweep, capsys, repo: fx.Repo) -> tuple[int, dict]:
    """Call ``sweep.main`` in-process; return ``(exit code, the single JSON object on stdout)``."""
    try:
        code = sweep.main(check_args(repo))
    except (RuntimeError, OSError, ValueError, TypeError) as exc:
        pytest.fail(f"main() let {exc!r} escape instead of printing a JSON object")
    lines = [ln for ln in capsys.readouterr().out.splitlines() if ln.strip()]
    assert len(lines) == 1, f"stdout must hold exactly one JSON object, got {lines!r}"
    return code, json.loads(lines[0])


def work_dir_empty(repo: fx.Repo) -> bool:
    """True when no list was written under the git dir."""
    base = repo.git_dir() / "leafcutter" / "work"
    return not base.exists() or not any(base.rglob("*.json"))
