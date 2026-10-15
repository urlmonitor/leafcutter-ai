"""
MODULE: workspace_root
GOAL: Answer one question for every caller -- which project is this directory
    part of? -- freshly on every call, from one importable stdlib-only module.
BUSINESS CONTEXT: The workspace maker (worktree.py) and, next, the hand-written
    hook resolvers of duplication-audit cluster C4 all need the project root.
    A resolver that walks up from ``__file__`` or caches its answer in a module
    global gives the wrong project when it runs from a workspace or from a
    non-repo parent that merely contains repositories
    (KI-CG-20260925-shared-root-resolver-accepts-non-repo-workspace-parent).
ARCHITECTURE: Deployed beside the maker as ``<install>/scripts/workspace/workspace_root.py``
    by its own named deploy-manifest entry. Exactly one public function,
    ``resolve_project_root``. Resolution order: an explicit argument, the
    workspace marker found walking up from the cwd, the git common directory of
    the cwd, a search of the cwd's children, a search of the cwd's siblings.
    The landing folder (``worktrees``) and hidden folders are never candidates.
    Nothing is cached and importing has no side effects. It must not import,
    wrap or copy commit_guardian/_resolve_root.py.

# DECISION HISTORY
# ================================================================================
# - 2026-10-14 12:00 [python-coder]: Created as the separate resolver
#   module the ticket requires; the marker file name lives here so the maker
#   and the resolver can never disagree on it. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
# - 2026-10-14 21:00 [python-coder]: A candidate counts only when git confirms
#   it is a repository (an empty .git is not one); a child workspace counts as
#   its recorded project, de-duplicated before the one-match rule; a marker
#   whose recorded project is missing answers NO_REPO naming the marker instead
#   of falling through to the workspace itself. ADR-001 Amendment 1.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08) (BO-4300b-1)
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path

MARKER_NAME = ".leafcutter-workspace.json"
LANDING_NAME = "worktrees"

_log = logging.getLogger("workspace_root")


def _is_repo_root(path: Path) -> bool:
    """Return True when git itself says ``path`` is the top of a repository.

    An empty ``.git`` folder (the dev layout's workspace parent has one) is not
    a repository: git refuses it, so it never counts.
    """
    if not (path.is_dir() and (path / ".git").exists()):
        return False
    try:
        done = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--show-toplevel"], cwd=str(path),
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("git rev-parse failed in %s: %s", path, exc)
        return False
    top = done.stdout.strip()
    return (done.returncode == 0 and bool(top)
            and os.path.realpath(top) == os.path.realpath(path))


def _recorded_project(marker: Path) -> Path | None:
    """Return the project a marker records, or None when it is unreadable or not a repo."""
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.warning("unreadable workspace marker %s: %s", marker, exc)
        return None
    root = data.get("project_root") if isinstance(data, dict) else None
    if isinstance(root, str) and root and _is_repo_root(Path(root)):
        return Path(root)
    return None


def _find_marker(start: Path) -> Path | None:
    """Return the nearest workspace marker file at or above ``start``."""
    for folder in (start, *start.parents):
        marker = folder / MARKER_NAME
        if marker.is_file():
            return marker
    return None


def _common_dir_project(start: Path) -> Path | None:
    """Return the project whose git common directory serves ``start``."""
    try:
        done = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--git-common-dir"], cwd=str(start),
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=30, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("git rev-parse failed in %s: %s", start, exc)
        return None
    out = done.stdout.strip()
    if done.returncode != 0 or not out:
        return None
    common = Path(os.path.abspath(out if os.path.isabs(out) else start / out))
    return common.parent if common.name == ".git" else None


def _child_project(child: Path) -> Path | None:
    """Return the project a child folder stands for: a repository, or a workspace's record."""
    marker = child / MARKER_NAME
    if marker.is_file():
        return _recorded_project(marker)
    return child if _is_repo_root(child) else None


def _repo_children(folder: Path) -> list[Path]:
    """Return the distinct projects of the folders directly inside ``folder``, sorted."""
    try:
        children = sorted(folder.iterdir())
    except OSError as exc:
        _log.warning("cannot list %s: %s", folder, exc)
        return []
    found: dict[str, Path] = {}
    for child in children:
        if child.name.startswith(".") or child.name == LANDING_NAME:
            continue
        project = _child_project(child)
        if project is not None:
            found.setdefault(os.path.realpath(project), project)
    return sorted(found.values())


def _search(folder: Path, how: str) -> dict | None:
    """Answer from the repositories inside ``folder``: one is ok, many is ambiguous."""
    found = _repo_children(folder)
    if len(found) == 1:
        return {"status": "ok", "project_root": str(found[0]), "how": how}
    if found:
        return {"status": "AMBIGUOUS_REPO", "how": how,
                "candidates": [str(c) for c in found]}
    return None


def resolve_project_root(cwd: str | os.PathLike, repo_root: str | os.PathLike | None) -> dict:
    """Resolve the project root for ``cwd``, recomputing on every call.

    Args:
        cwd: Absolute directory the question is asked from.
        repo_root: Absolute project root the caller already knows, or None.

    Returns:
        A dict with ``status`` of ok, NO_REPO or AMBIGUOUS_REPO. ``project_root``
        and ``how`` are present on ok; ``candidates`` on AMBIGUOUS_REPO;
        ``searched_from`` on NO_REPO (plus ``marker`` when a workspace's
        recorded project is gone).
    """
    start = Path(os.path.abspath(cwd))
    if repo_root:
        given = Path(os.path.abspath(repo_root))
        if _is_repo_root(given):
            return {"status": "ok", "project_root": str(given), "how": "argument"}
        return {"status": "NO_REPO", "searched_from": str(given)}
    marker = _find_marker(start)
    if marker is not None:
        # A workspace names its project ONLY through its marker: never itself,
        # never a folder guessed from where it sits.
        root = _recorded_project(marker)
        if root is None:
            return {"status": "NO_REPO", "searched_from": str(start),
                    "marker": str(marker)}
        return {"status": "ok", "project_root": str(root), "how": "workspace-marker"}
    root = _common_dir_project(start)
    if root is not None:
        return {"status": "ok", "project_root": str(root), "how": "git-common-dir"}
    for folder, how in ((start, "child-search"), (start.parent, "sibling-search")):
        answer = _search(folder, how)
        if answer is not None:
            return answer
    return {"status": "NO_REPO", "searched_from": str(start)}
