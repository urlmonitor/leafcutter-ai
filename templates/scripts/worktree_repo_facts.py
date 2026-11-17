"""
MODULE: worktree_repo_facts.py
GOAL: Read-only dirty-state helper for the build-feature epic loop (BO-100e-4):
    the staged, unstaged and untracked paths of a workspace, as one
    single-line JSON object on stdout, computed only from git's own output.
BUSINESS CONTEXT: E2 workflows have no module loader and cannot run git
    themselves (ADR-030), so the driver dispatches this script once before an
    epic run continues past a halted ticket. Finding, making or clearing a
    workspace is NOT done here: that is the one workspace maker,
    ``worktree.py`` (docs/how-to/get-a-workspace.md). The former ``facts``,
    ``base`` and ``branch-standing`` lookups were removed by BO-4300f-2 --
    the maker answers where a workspace lives and whether it is reusable.
ARCHITECTURE: Stdlib plus the maker's own git runner (``worktree_git``,
    a sibling in ``templates/scripts/`` and, after deploy, in ``scripts/``);
    this file starts no process of its own. Canonical source is
    templates/scripts/worktree_repo_facts.py (ADR-001); the build deploys it
    to scripts/ verbatim.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import worktree_git as wg


def _anchor_dir(path: Path) -> Path:
    """Resolve *path* to a directory usable as a git cwd (a file maps to its parent)."""
    return path.parent if path.is_file() else path


def worktree_dirty(repo: Path) -> dict:
    """Staged, unstaged and untracked paths of the worktree at *repo* (BO-100e-4).

    Runs ``git status --porcelain -uall -z`` (read-only: it never changes the
    index). ``-z`` leaves names unquoted, so spaces and non-ASCII come back
    verbatim; ``-uall`` expands untracked directories to files. A rename or
    copy entry names its NEW path. A file staged and then edited again is in
    both ``staged`` and ``unstaged``.

    Args:
        repo: A path inside the worktree to inspect.

    Returns:
        ``{ readable, staged, unstaged, untracked }``; ``readable`` is False
        (lists empty) when git could not report the state, e.g. *repo* is not
        a checkout. Never coerced to a clean-looking answer.
    """
    result: dict = {"readable": False, "staged": [], "unstaged": [], "untracked": []}
    proc = wg.run_git(["status", "--porcelain", "-uall", "-z"], _anchor_dir(repo), encoding="utf-8")
    if proc.returncode != 0:
        return result
    entries = proc.stdout.split("\x00")
    index = 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if len(entry) < 4:
            continue
        code, path = entry[:2], entry[3:]
        if code[0] in "RC":
            index += 1  # the old name follows as its own NUL-separated field
        if code == "??":
            result["untracked"].append(path)
            continue
        if code[0] not in " !":
            result["staged"].append(path)
        if code[1] not in " !":
            result["unstaged"].append(path)
    result["readable"] = True
    return result


def _build_parser() -> argparse.ArgumentParser:
    """Build the ``dirty`` subcommand parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    dirty_p = sub.add_parser("dirty", help="Staged/unstaged/untracked paths of a workspace.")
    dirty_p.add_argument("repo", nargs="?", default=".")
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the dirty-state JSON of the requested workspace.

    Returns:
        0 always; an unreadable state is represented IN the JSON
        (``readable: false``), never as a clean-looking answer.
    """
    args = _build_parser().parse_args(argv)
    sys.stdout.write(json.dumps(worktree_dirty(Path(args.repo))))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"worktree_repo_facts: unexpected error: {exc}", file=sys.stderr)
        sys.exit(1)

# DECISION HISTORY
# ================================================================================
# - 2026-09-16 [python-coder]: Initial implementation. A deterministic
#   repository-facts helper (facts / base / branch-standing subcommands) for
#   build-feature.js's worktree step, so BO-4000's reuse/open/refuse decision
#   is made from real git facts rather than an agent's judgement or the
#   resolver's own word. (#BO-4000)
# - 2026-10-07 [python-coder]: Added the `dirty` subcommand (staged / unstaged /
#   untracked, `-z` parsing, rename new-path) so build-feature.js's epic loop
#   can read the worktree once before continuing past a halted ticket; an
#   unreadable state answers readable:false, never clean. (#BO-100e-4)
# - 2026-10-13 [python-coder]: BO-4300f-2 removed the facts / base /
#   branch-standing lookups (the maker answers them) and the file's own git
#   runner; `dirty` now runs through the maker's runner. (#BO-4300f-2)
