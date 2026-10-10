"""
MODULE: unit_tests/build_orchestration/_bo_4300a_1_ii_fixtures.py
GOAL: Shared real-git helpers for the ticket-06 proofs (test_bo_4300a_2.py,
    test_bo_4300a_1_ii.py, test_bo_4300d_3.py, test_bo_4300d_3_i.py,
    test_bo_4300d_4.py): run the DEPLOYED maker against a real bare hub, put
    lines of work and tickets on that hub, and snapshot a folder.
BUSINESS CONTEXT: Every ticket-06 AC asks "which workspace/line is this
    request for"; each proof needs the same hub-line and ticket scaffolding,
    so it lives here once instead of five times.
ARCHITECTURE: Stdlib-only. Builds on _workspace_maker_fixtures.make_project /
    run_maker (BO-4300f-4's locator: the deployed maker, a subprocess, no git
    mock). Fixture writes pin newline="\n" and git runs with the isolated
    HOME / GIT_CONFIG_GLOBAL / GIT_CONFIG_NOSYSTEM of _workspace_maker_builders.

NOT a test file itself (leading underscore).

DECISION HISTORY
====================================================================
- 2026-10-09 12:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06,
  BO-4300a-2]: Created. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
====================================================================
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    make_project,
    run_maker,
)
from unit_tests.build_orchestration._workspace_maker_builders import (
    _isolated_git_env,
    _run_git,
)

TICKET_REL = "tickets/TICKET-20260925-demo.md"
TICKET_CONTENT = "# TICKET-20260925-demo\n\nDemo ticket for BO-4300a-1-ii.\n"
TICKET_EDITED = "# TICKET-20260925-demo\n\nEDITED IN THE MAIN COPY, NEVER PUSHED.\n"


def git(args: list[str], cwd: Path) -> str:
    """Run an isolated git command in *cwd*; return stripped stdout."""
    return _run_git(args, Path(cwd)).stdout.strip()


def maker(args: list[str], cwd: Path) -> dict[str, Any]:
    """Run the deployed maker as a subprocess; returns {answer, exit_code, stdout, stderr}."""
    return run_maker(args, cwd=Path(cwd), env=_isolated_git_env())


def new_project(tmp: Path, name: str = "fx") -> dict[str, Path]:
    """A real bare hub plus a project clone (see make_project)."""
    return make_project(Path(tmp) / name)


def same(a: Any, b: Any) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def push_hub_line(project: Path, branch: str, commits: int = 1) -> list[str]:
    """Put *commits* new commits on hub branch *branch* (off hub main); return their shas.

    The project's local branch is deleted afterwards, so only the hub carries the
    line (the maker consults hub refs, never the main copy's local branches).
    """
    git(["checkout", "-q", "-b", branch, "origin/main"], project)
    safe = branch.replace("/", "_")
    shas: list[str] = []
    for i in range(commits):
        (project / f"{safe}-{i}.txt").write_text(f"{branch} commit {i}\n", encoding="utf-8", newline="\n")
        git(["add", "-A"], project)
        git(["commit", "-q", "-m", f"{branch} commit {i}"], project)
        shas.append(git(["rev-parse", "HEAD"], project))
    git(["push", "-q", "origin", branch], project)
    git(["checkout", "-q", "main"], project)
    git(["branch", "-q", "-D", branch], project)
    return shas


def push_ticket_to_hub(project: Path, rel: str = TICKET_REL, content: str = TICKET_CONTENT) -> None:
    """Commit *rel* in the main copy and push it to the hub's main."""
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    git(["add", "-A"], project)
    git(["commit", "-q", "-m", f"add {rel}"], project)
    git(["push", "-q", "origin", "main"], project)


def commit_ticket_locally_only(project: Path, rel: str = TICKET_REL, content: str = TICKET_CONTENT) -> None:
    """Commit *rel* in the main copy but never push it (ticket absent from the hub)."""
    path = project / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    git(["add", "-A"], project)
    git(["commit", "-q", "-m", f"local only {rel}"], project)


def hub_refs(hub: Path) -> str:
    """Every ref on the hub with its sha, as one comparable string."""
    return git(["for-each-ref", "--format=%(refname) %(objectname)"], hub)


def hub_heads(hub: Path) -> list[str]:
    return sorted(git(["for-each-ref", "--format=%(refname:short)", "refs/heads"], hub).split())


def is_ancestor(sha: str, ref: str, cwd: Path) -> bool:
    """True when *sha* is reachable from *ref* in the repo at *cwd*."""
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, ref],
        cwd=str(cwd), capture_output=True, text=True, env=_isolated_git_env(),
    )
    return proc.returncode == 0


def snapshot(folder: Path) -> dict[str, Any]:
    """Files (bytes, .git excluded) plus HEAD (when a repo) of *folder*, for before/after equality."""
    folder = Path(folder)
    files = {
        str(p.relative_to(folder)): p.read_bytes()
        for p in sorted(folder.rglob("*"))
        if p.is_file() and ".git" not in p.relative_to(folder).parts
    }
    head = None
    if (folder / ".git").exists():
        head = git(["rev-parse", "HEAD"], folder)
    return {"files": files, "head": head}


def landing_entries(landing: Path) -> list[str]:
    """Every path below the landing place (empty when it does not exist)."""
    if not Path(landing).exists():
        return []
    return sorted(str(p.relative_to(landing)) for p in Path(landing).rglob("*") if ".git" not in p.relative_to(landing).parts)
