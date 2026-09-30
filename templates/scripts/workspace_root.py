"""
MODULE: workspace_root
GOAL: Resolve the one project a workspace request means, from any folder in or
    around it, as a single, uncached, stdlib-only lookup any hook or CLI can
    import directly (BO-4300b-1, ADR-018 Amendment 1 A1.8).
BUSINESS CONTEXT: Duplication-audit cluster C4 (KI-CG-20260925-shared-root-
    resolver-accepts-non-repo-workspace-parent) found ~30 hand-written root
    resolvers scattered across hook scripts, each with its own bugs. This
    module is the shared resolver: it is consumed by
    templates/scripts/worktree.py and is meant to replace those ~30 resolvers
    next. It deliberately does NOT reuse, wrap, or copy
    templates/scripts/commit_guardian/_resolve_root.py, which walks up from
    ``__file__`` looking for ``.git``/``CLAUDE.md`` and caches its answer in a
    module global -- both forbidden here. The dev layout's workspace parent
    holds an empty ``.git/`` and a ``CLAUDE.md`` and is not a project.
ARCHITECTURE: One public function, ``resolve(cwd, repo_root)``, importable as
    a top-level module with no import-time side effects. Every call
    recomputes from scratch -- nothing is cached across calls. Order: (1) an
    explicit ``repo_root`` that git confirms is a repository top level; (2)
    the parent of ``git rev-parse --git-common-dir`` run in cwd, replaced by
    the marker's recorded ``project_root`` when that folder is a workspace;
    (3) a search of cwd's immediate children, then -- only when those give no
    candidate -- of cwd's siblings, a candidate counting only when git reports
    the folder itself as its top level, de-duplicated by resolved project;
    (4) ``NO_REPO`` naming ``searched_from``. The location of this file or of
    any installed copy is never consulted.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from pathlib import Path
from typing import Any

import worktree_paths

_log = logging.getLogger(__name__)

_GIT_TIMEOUT_SECONDS = 15
_MARKER_PARTS = (".leafcutter", "workspace.json")


def _git(args: list[str], cwd: Path) -> str | None:
    """Run ``git <args>`` with its working directory set to *cwd*; return stripped stdout.

    Returns ``None`` when git is unavailable, times out, exits non-zero or
    prints nothing (i.e. *cwd* is not inside the repository the query needs).
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("workspace_root: git %s failed in %s: %s", " ".join(args), cwd, exc)
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _same(a: Path, b: Path) -> bool:
    """Return True when two paths name the same folder (case-insensitive on Windows)."""
    return os.path.normcase(str(a.resolve())) == os.path.normcase(str(b.resolve()))


def _is_repo_top(folder: Path) -> bool:
    """Return True only when git, run in *folder*, reports *folder* itself as the top level.

    An empty ``.git`` folder, a plain folder inside some other repository and
    a bare repository all answer False.
    """
    if not folder.is_dir():
        return False
    top = _git(["rev-parse", "--show-toplevel"], folder)
    return bool(top) and _same(Path(top), folder)


def _project_above(cwd: Path) -> Path | None:
    """Return the parent of ``git rev-parse --git-common-dir`` run in *cwd*, or None."""
    common = _git(["rev-parse", "--path-format=absolute", "--git-common-dir"], cwd)
    if common and Path(common).name == ".git":
        return Path(common).parent.resolve()
    top = _git(["rev-parse", "--show-toplevel"], cwd)
    return Path(top).resolve() if top else None


def _read_marker(folder: Path) -> tuple[Path, Any] | None:
    """Return ``(marker path, parsed marker or None)`` when *folder* holds a marker, else None."""
    path = folder.joinpath(*_MARKER_PARTS)
    if not path.is_file():
        return None
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.warning("workspace_root: unreadable marker %s: %s", path, exc)
        return path, None


def _marker_project(folder: Path, marker: Any) -> Path | None:
    """Return the marker's recorded ``project_root`` when it is a real repository, else None."""
    stored = marker.get("project_root") if isinstance(marker, dict) else None
    if not isinstance(stored, str) or not stored:
        return None
    recorded = Path(worktree_paths.from_portable(stored, folder))
    return recorded.resolve() if _is_repo_top(recorded) else None


def _candidate_project(child: Path) -> Path | None:
    """Return the project *child* stands for: its recorded project if a workspace, itself if a repo."""
    found = _read_marker(child)
    if found is not None:
        return _marker_project(child, found[1])
    if (child / ".git").exists() and _is_repo_top(child):
        return child.resolve()
    return None


def _search(folder: Path, skip: Path | None = None) -> list[Path]:
    """Return every distinct project among *folder*'s immediate children (sorted, de-duplicated)."""
    try:
        children = sorted(folder.iterdir())
    except OSError as exc:
        _log.warning("workspace_root: cannot list %s: %s", folder, exc)
        return []
    found: dict[str, Path] = {}
    for child in children:
        if (skip is not None and _same(child, skip)) or not child.is_dir():
            continue
        project = _candidate_project(child)
        if project is not None:
            found[os.path.normcase(str(project))] = project
    return list(found.values())


def _no_repo(searched_from: Path, reason: str, **extra: str) -> dict[str, Any]:
    """Build the ``NO_REPO`` answer naming where the search started."""
    return {"status": "NO_REPO", "searched_from": str(searched_from), "reason": reason, **extra}


def _from_candidates(found: list[Path], how: str, cwd: Path) -> dict[str, Any] | None:
    """Turn a search result into an answer: one -> ok, several -> AMBIGUOUS_REPO, none -> None."""
    if len(found) == 1:
        return {"status": "ok", "project_root": str(found[0]), "how": how}
    if found:
        return {"status": "AMBIGUOUS_REPO", "candidates": [str(p) for p in found], "searched_from": str(cwd)}
    return None


def resolve(cwd: str, repo_root: str | None = None) -> dict[str, Any]:
    """Resolve the one project a request started in *cwd* means.

    Args:
        cwd: Absolute path the request started from.
        repo_root: An explicit project folder. It counts only when git
            confirms it is a repository's top level; otherwise the answer is
            ``NO_REPO`` naming it.

    Returns:
        ``{"status": "ok", "project_root", "how"}`` (``how`` one of
        ``argument``, ``git-common-dir``, ``workspace-marker``,
        ``child-search``, ``sibling-search``); ``{"status": "AMBIGUOUS_REPO",
        "candidates": [...], "searched_from"}`` when more than one project
        could be meant; or ``{"status": "NO_REPO", "searched_from", "reason"}``
        (plus ``marker`` when a workspace's recorded project is missing).
        Every call recomputes; nothing is cached.
    """
    cwd_path = Path(cwd).resolve()
    if repo_root is not None:
        explicit = Path(repo_root).resolve()
        if _is_repo_top(explicit):
            return {"status": "ok", "project_root": str(explicit), "how": "argument"}
        return _no_repo(explicit, f"--repo-root {explicit} is not a git repository's top folder")

    above = _project_above(cwd_path)
    if above is not None:
        found = _read_marker(above)
        if found is None:
            return {"status": "ok", "project_root": str(above), "how": "git-common-dir"}
        project = _marker_project(above, found[1])
        if project is None:
            return _no_repo(cwd_path, f"workspace marker {found[0]} records no usable project_root",
                            marker=str(found[0]))
        return {"status": "ok", "project_root": str(project), "how": "workspace-marker"}

    answer = _from_candidates(_search(cwd_path), "child-search", cwd_path)
    if answer is None and cwd_path.parent != cwd_path:
        answer = _from_candidates(_search(cwd_path.parent, skip=cwd_path), "sibling-search", cwd_path)
    return answer or _no_repo(cwd_path, f"no project found in or beside {cwd_path}")


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-27 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Created this module as the separate, uncached project-root resolver
#   BO-4300a-1's maker (templates/scripts/worktree.py) imports rather than
#   re-implementing inline. Implemented only "argument" and "git-common-dir"
#   resolution; the rest was left to BO-4300b-1.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-30 23:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
#   Implemented the full BO-4300b-1 order (ADR-018 Amendment 1 A1.8): explicit
#   argument confirmed by git, git-common-dir with the workspace marker's
#   recorded project, children-then-siblings search (git-confirmed, de-
#   duplicated, AMBIGUOUS_REPO listing every candidate), then NO_REPO naming
#   searched_from. No __file__ anchor, no cache, no upward ".git/CLAUDE.md"
#   walk. (ADR-018)
# ===========================================================================
