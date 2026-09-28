"""
MODULE: workspace_root
GOAL: Resolve the absolute project root for a given working directory, as a
    single, uncached, stdlib-only lookup any hook or CLI can import directly.
BUSINESS CONTEXT: Duplication-audit cluster C4 (KI-CG-20260925-shared-root-
    resolver-accepts-non-repo-workspace-parent) found ~30 hand-written root
    resolvers scattered across hook scripts, each with its own bugs. This
    module is the first shared resolver: it is consumed by
    templates/scripts/worktree.py today and is meant to replace those ~30
    resolvers next. It deliberately does NOT reuse, wrap, or copy
    templates/scripts/commit_guardian/_resolve_root.py, which walks up from
    ``__file__`` looking for ``.git``/``CLAUDE.md`` and caches its answer in a
    module global -- both forbidden here (BO-4300a-1's own Implementation
    Notes).
ARCHITECTURE: One public function, ``resolve(cwd, repo_root)``, importable as
    a top-level module with no import-time side effects. Every call
    recomputes from scratch -- nothing is cached across calls, so a caller
    that changes directory (or is a long-lived process serving several
    requests) always sees the current answer. The resolution order beyond
    "explicit argument, then git" is deferred to BO-4300b-1's
    it_requirements; this module intentionally implements only the two
    orderings BO-4300a-1 itself needs (``argument`` and ``git-common-dir``)
    and leaves ``workspace-marker`` / ``child-search`` / ``sibling-search``
    for that ticket to add.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_GIT_TIMEOUT_SECONDS = 15


def _git_show_toplevel(cwd: Path) -> str | None:
    """Run ``git -C <cwd> rev-parse --show-toplevel`` and return its output.

    Args:
        cwd: Absolute directory to resolve the enclosing git repository from.

    Returns:
        The stripped stdout (an absolute path string) on success, or ``None``
        when git is unavailable, times out, or exits non-zero (i.e. *cwd* is
        not inside a git repository).
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("workspace_root: git rev-parse failed from %s: %s", cwd, exc)
        return None
    if result.returncode != 0:
        return None
    output = result.stdout.strip()
    return output or None


def resolve(cwd: str, repo_root: str | None = None) -> dict[str, Any]:
    """Resolve the absolute project root for *cwd*.

    Order: an explicit, existing *repo_root* argument wins outright (``how``
    ``"argument"``); otherwise the enclosing git repository of *cwd* is used
    (``how`` ``"git-common-dir"``). Neither branch consults or writes any
    cache -- every call redoes the work.

    Args:
        cwd: Absolute path to resolve from (the caller's current directory).
        repo_root: An optional, already-known project root. When given and it
            is an existing directory, it is trusted outright.

    Returns:
        A dict with ``status`` one of ``"ok"``, ``"NO_REPO"``,
        ``"AMBIGUOUS_REPO"``. On ``"ok"`` it also carries ``project_root``
        (absolute path string) and ``how``. On ``"NO_REPO"`` it carries
        ``searched_from`` (the absolute *cwd*). ``"AMBIGUOUS_REPO"`` is not
        yet produced by this module (no ordering here has more than one
        candidate) but is a valid member of the status enum this function's
        callers must handle.
    """
    cwd_path = Path(cwd).resolve()

    if repo_root is not None:
        candidate = Path(repo_root).resolve()
        if candidate.is_dir():
            return {"status": "ok", "project_root": str(candidate), "how": "argument"}

    toplevel = _git_show_toplevel(cwd_path)
    if toplevel:
        return {
            "status": "ok",
            "project_root": str(Path(toplevel).resolve()),
            "how": "git-common-dir",
        }

    return {"status": "NO_REPO", "searched_from": str(cwd_path)}


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-27 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Created this module as the separate, uncached project-root resolver
#   BO-4300a-1's maker (templates/scripts/worktree.py) imports rather than
#   re-implementing inline. Implements only "argument" and "git-common-dir"
#   resolution -- the ordering and exclusions for "workspace-marker",
#   "child-search" and "sibling-search" are BO-4300b-1's own
#   it_requirements and are deliberately left for that ticket.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# ===========================================================================
