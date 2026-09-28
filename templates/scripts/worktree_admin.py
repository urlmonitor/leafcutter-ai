"""
MODULE: worktree_admin
GOAL: The three read-only/removal verbs of the one workspace maker --
    ``locate``, ``list``, and ``remove`` -- split out of worktree.py's CLI
    dispatch file.
BUSINESS CONTEXT: AC BO-4300a-1 requires ``locate`` and ``list`` to scan the
    landing place's own marker registry rather than any ``git worktree``
    command (no git command lists clones), and ``remove`` to refuse a dirty
    or unpushed workspace unless explicitly forced. Kept in its own module,
    a sibling of worktree.py and worktree_git.py under ``templates/scripts/``,
    so worktree.py itself stays under the package's 400-line file-size
    ratchet -- the same "further helper module the maker imports needs a
    named deploy-manifest entry too" pattern this ticket's own Implementation
    Notes call out for the resolver module.
ARCHITECTURE: Stdlib-only (argparse typing only; no CLI parsing of its own --
    worktree.py owns argument parsing and calls these three functions
    directly with the parsed ``argparse.Namespace``). Depends only on
    ``worktree_git`` for the marker registry, landing-place resolution, and
    git primitives -- never imports ``worktree`` itself, so there is no
    import cycle between this module and its caller.
"""

from __future__ import annotations

import argparse
import logging
import shutil
from pathlib import Path
from typing import Any

import worktree_git as wg

_log = logging.getLogger(__name__)


def _err(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Build the maker's standard non-ok answer: never an 'ok' shape, never a traceback.

    ``status`` is derived from *code* via :func:`worktree_git.status_for_code`
    -- the identical rule worktree.py's own ``_err`` applies, so a caller
    sees one consistent status/code classification regardless of which
    module answered its request.
    """
    return {"status": wg.status_for_code(code), "code": code, "message": message, **extra}


def cmd_locate(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only lookup of a workspace by ``--path``, ``--kind``/``--slug``, or ``--branch``."""
    if args.path:
        workspace_path = Path(args.path).resolve()
        marker = wg.read_marker(workspace_path)
        if marker is None:
            return _err("NOT_FOUND", f"No workspace marker found at {workspace_path}.")
        return {"status": "ok", "workspace_path": str(workspace_path), "marker": marker}

    repo_root = wg.resolve_repo_root(args.repo_root)
    if repo_root is None:
        return _err("NO_REPO", "Could not resolve the main checkout for --kind/--slug/--branch lookup.")
    place = wg.landing_place(repo_root)
    ctx = {"repo_root": str(repo_root), "repo_root_posix": repo_root.as_posix(), "layout": wg.layout_for(repo_root)}

    if args.kind and args.slug:
        slug = wg.normalize_slug(args.slug)
        workspace_path = place / f"{args.kind}-{slug}"
        marker = wg.read_marker(workspace_path)
        if marker is None:
            return {**_err("NOT_FOUND", f"No workspace marker found at {workspace_path}."), **ctx}
        return {**ctx, "status": "ok", "workspace_path": str(workspace_path), "marker": marker}

    if args.branch:
        for workspace_path, marker in wg.iter_markers(place):
            if marker.get("branch") == args.branch:
                return {**ctx, "status": "ok", "workspace_path": str(workspace_path), "marker": marker}
        return {**_err("NOT_FOUND", f"No workspace found for branch {args.branch!r}."), **ctx}

    return _err("USAGE", "locate requires --path, or --kind with --slug, or --branch.")


def cmd_list(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only scan of the landing place's markers -- never ``git worktree list``."""
    repo_root = wg.resolve_repo_root(args.repo_root)
    if repo_root is None:
        return _err("NO_REPO", "Could not resolve the main checkout to list its landing place.")
    place = wg.landing_place(repo_root)
    workspaces = [
        {"workspace_path": str(path), "marker": marker} for path, marker in wg.iter_markers(place)
    ]
    return {
        "status": "ok", "landing_place": str(place), "workspaces": workspaces,
        "repo_root": str(repo_root), "repo_root_posix": repo_root.as_posix(),
        "layout": wg.layout_for(repo_root),
    }


def _branch_pushed(workspace_path: Path, branch: str | None) -> bool:
    """Return ``True`` when *branch* has a matching ``refs/remotes/origin/<branch>``."""
    if not branch:
        return False
    proc = wg.run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}"], workspace_path)
    return proc.returncode == 0


def cmd_remove(args: argparse.Namespace) -> dict[str, Any]:
    """Remove the workspace at ``--path``, refusing a dirty/unpushed one unless ``--force``."""
    workspace_path = Path(args.path).resolve()
    marker = wg.read_marker(workspace_path)
    if marker is None:
        return _err("NOT_FOUND", f"No workspace marker found at {workspace_path}.")

    if not args.force:
        dirty = not wg.is_clean(workspace_path)
        pushed = _branch_pushed(workspace_path, marker.get("branch"))
        if dirty or not pushed:
            return _err(
                "REFUSED",
                f"{workspace_path} has uncommitted changes or an unpushed branch; pass --force to discard it.",
                dirty=dirty, pushed=pushed,
            )

    if args.delete_remote_branch and marker.get("branch"):
        wg.run_git(["push", "origin", "--delete", marker["branch"]], workspace_path)

    try:
        shutil.rmtree(workspace_path)
    except OSError as exc:
        _log.warning("cmd_remove: rmtree failed for %s: %s", workspace_path, exc)
        # PROCESS_HOLDS_FILES is the closest BO-4300c-2 result-contract code
        # to an rmtree failure: on the platforms this maker targets, a
        # directory that survives `git clone --no-checkout --local` almost
        # always fails to remove because some process still holds a file
        # handle inside it (Windows file locking), not because of a git
        # concept "REMOVE_FAILED" never named in the contract's own code enum.
        return _err("PROCESS_HOLDS_FILES", f"Could not remove {workspace_path}: {exc}")

    return {"status": "ok", "workspace_path": str(workspace_path)}


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-27 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Split out of worktree.py to keep that file under the package's 400-line
#   file-size ratchet. locate/list scan the marker registry only -- no git
#   command lists clones. remove refuses a dirty or unpushed workspace
#   unless --force is given, per this ticket's Delivers To contract.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-28 02:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Fixed pr-reviewer H-2 (2026-09-28 00:43): _err() now derives status
#   ok/refused/error from worktree_git.status_for_code() instead of always
#   "error"; BAD_ARGS collapsed onto the contract's own USAGE code;
#   cmd_remove's rmtree OSError now answers PROCESS_HOLDS_FILES instead of
#   the non-contract REMOVE_FAILED; locate/list attach
#   repo_root/repo_root_posix/layout once repo_root resolves.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# ===========================================================================
