"""
MODULE: scripts/suite_performance/pytest_developer_repo_guard.py
GOAL: Prove that running a pytest session leaves the developer's own project
    unchanged: its registered workspaces, branches and local version-control
    settings are identical afterwards, and nothing the session made is
    registered in, or linked from, it.
BUSINESS CONTEXT: A workspace proof that makes real projects, hubs and
    workspaces could register one of them in the developer's own repository, or
    write a fixture identity into its config (BO-4300f-4-i, F14, KI-TQ-012).
    Nobody would see it until the developer's own branches looked wrong.
ARCHITECTURE: Registered as a pytest plugin through ``pytest.ini`` ``addopts``
    (``-p scripts.suite_performance.pytest_developer_repo_guard``). It snapshots
    the repository at the session root at session start (``git worktree list
    --porcelain``, ``git for-each-ref``, ``git config --local --list``),
    compares at session end, prints ``developer-repo-guard: unchanged`` or
    ``developer-repo-guard: CHANGED`` in the terminal summary, and fails the
    session on a change. The snapshot, reference-search and guard helpers are
    plain functions, reused by ``unit_tests/build_orchestration/
    _workspace_maker_fixtures.py``. Read-only git verbs only.
"""
from __future__ import annotations

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

import pytest

_RECORD_KINDS = {
    "worktrees": ("worktree", "list", "--porcelain"),
    "refs": ("for-each-ref",),
    "config": ("config", "--local", "--list"),
}
_STATE: dict = {}


def _git_text(repo: Path, args: tuple) -> str:
    """Return the stdout of one read-only git run in ``repo`` ('' when it fails)."""
    try:
        done = subprocess.run(  # noqa: S603
            ["git", *args], cwd=str(repo), capture_output=True, text=True,
            timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[developer-repo-guard] git {' '.join(args)} failed: {exc}", file=sys.stderr)
        return ""
    return done.stdout if done.returncode == 0 else ""


def developer_repo_snapshot(repo) -> dict:
    """Record the worktrees, refs and local config of ``repo`` as three strings."""
    root = Path(repo)
    return {kind: _git_text(root, args) for kind, args in _RECORD_KINDS.items()}


def _alternates_lines(repo: Path) -> list:
    common = _git_text(repo, ("rev-parse", "--git-common-dir")).strip()
    if not common:
        return []
    path = (repo / common) / "objects" / "info" / "alternates"
    try:
        return path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
    except OSError as exc:
        print(f"[developer-repo-guard] cannot read {path}: {exc}", file=sys.stderr)
        return []


def developer_repo_references_into(folder, repo) -> list:
    """Return every record of ``repo`` that points into ``folder`` ([] when none)."""
    root = Path(repo)
    needles = {str(folder), os.path.realpath(folder)}
    records = [("worktree", line) for line in
               _git_text(root, _RECORD_KINDS["worktrees"]).splitlines()
               if line.startswith("worktree ")]
    records += [("config", line) for line in
                _git_text(root, _RECORD_KINDS["config"]).splitlines()]
    records += [("alternates", line) for line in _alternates_lines(root)]
    return [f"{kind}: {text}" for kind, text in records
            if any(needle in text for needle in needles)]


def changed_kinds(before: dict, after: dict) -> list:
    """Return the record kinds whose text differs between two snapshots."""
    return [kind for kind in _RECORD_KINDS if before.get(kind) != after.get(kind)]


@contextmanager
def developer_repo_guard(repo):
    """Snapshot ``repo`` on entry and raise AssertionError on exit if it changed."""
    before = developer_repo_snapshot(repo)
    yield
    changed = changed_kinds(before, developer_repo_snapshot(repo))
    if changed:
        msg = f"developer repository changed: {', '.join(changed)}"
        raise AssertionError(msg)


def pytest_sessionstart(session) -> None:
    """Record the developer repository before the first test (controller only)."""
    if hasattr(session.config, "workerinput"):
        return
    root = Path(str(session.config.rootpath))
    snap = developer_repo_snapshot(root)
    _STATE.clear()
    _STATE.update(root=root, before=snap if any(snap.values()) else None, changed=[])


def pytest_sessionfinish(session, exitstatus) -> None:
    """Compare against the start snapshot; fail the session on any difference."""
    before = _STATE.get("before")
    if before is None:
        return
    _STATE["changed"] = changed_kinds(before, developer_repo_snapshot(_STATE["root"]))
    if _STATE["changed"] and session.exitstatus == pytest.ExitCode.OK:
        session.exitstatus = pytest.ExitCode.TESTS_FAILED


def pytest_terminal_summary(terminalreporter) -> None:
    """Print the one-line guard verdict."""
    if "root" not in _STATE:
        return
    if _STATE["before"] is None:
        terminalreporter.write_line("developer-repo-guard: unavailable (not a git repository)")
    elif _STATE["changed"]:
        terminalreporter.write_line(
            f"developer-repo-guard: CHANGED ({', '.join(_STATE['changed'])})", red=True)
    else:
        terminalreporter.write_line("developer-repo-guard: unchanged")


# DECISION HISTORY
# ================================================================================
# - 2026-10-16 12:30 [python-coder]: Added the session guard plugin that snapshots the developer repository and fails the session on any change. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/59)
