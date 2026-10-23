"""
MODULE: worktree_remove
GOAL: The workspace maker's ``remove`` verb and the definite ``locate`` answer:
    clear a workspace completely or not at all, never wait for input, and lose
    unsent work only when the request itself carries the one-time discard token
    its refusal returned (AC BO-4300e-1-i, e-2, e-2-i, e-2-ii, e-3, e-3-i).
BUSINESS CONTEXT: Finalize and clean-up run unattended, so a remove that
    prompts deadlocks them, and one that deletes unsent work silently destroys
    it. The unsent verdict (BO-4100c-1) is: commits on the workspace's line that
    are reachable from neither ``origin/<branch>`` nor ``origin/main`` after a
    fetch, plus uncommitted and untracked changes. A refusal returns a
    ``discard_token`` bound to exactly that loss; the maker stores nothing, it
    recomputes the binding from the workspace's current state on every request.
ARCHITECTURE: Stdlib-only. ``unsent_work`` is the exported verdict (ticket 12's
    cut-over calls it). ``discard_token`` is a stateless sha256 digest over the
    workspace's canonical path, its marker record, its unsent shas and its
    unsent files with content; it is read only from ``--discard-token`` and
    written only into the refusal answer. ``scripts/worktree/sweep_processes.py``
    is loaded from beside the maker when deployed; a program found running in or
    holding the workspace refuses PROCESS_HOLDS_FILES naming it, before anything
    is deleted. Deletion uses the Windows extended-length prefix, clears
    read-only files, runs no prune, and answers ok only after a post-check finds
    nothing at the location. Imports ``worktree_ensure_state`` (which imports
    ``worktree_admin``); ``worktree_admin`` never imports this module.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import logging
import os
import shutil
import stat
import sys
from pathlib import Path
from typing import Any

import worktree_admin
import worktree_answer as wa
import worktree_ensure_state as wes
import worktree_git as wg
import worktree_layout as wl
import worktree_paths as wp

_log = logging.getLogger(__name__)

_err = wa.error_answer
_EXTENDED_PREFIX = "\\\\?\\"


def incomplete_answer(workspace: Path, marker: dict[str, Any]) -> dict[str, Any]:
    """INCOMPLETE answer for a half-made workspace: names ``remnant_path``, never a ``workspace_path``."""
    return {**wes.incomplete_refusal(workspace, marker), "remnant_path": str(workspace)}


def cmd_locate(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only ``locate``: ok only for a ready workspace; a half-made one is INCOMPLETE with its remnant."""
    answer = worktree_admin.cmd_locate(args)
    marker = answer.get("marker")
    if answer.get("status") != "ok" or not isinstance(marker, dict) or marker.get("state", "ready") == "ready":
        return answer
    carried = {k: v for k, v in answer.items() if k in ("repo_root", "repo_root_posix", "layout")}
    return {**incomplete_answer(Path(answer.get("workspace_path", "")), marker), **carried}


def _long_path(path: Path) -> str:
    """Return *path* spelled so a path over 260 characters is reachable (Windows extended-length prefix)."""
    text = str(path)
    if os.name != "nt" or text.startswith(_EXTENDED_PREFIX):
        return text
    return _EXTENDED_PREFIX + "UNC\\" + text[2:] if text.startswith("\\\\") else _EXTENDED_PREFIX + text


def _status_entries(workspace: Path) -> tuple[list[tuple[str, str]], str | None]:
    """Return ``([(XY, path)], error)`` for every uncommitted or untracked (non-ignored) change."""
    proc = wg.run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], workspace)
    if proc.returncode != 0:
        return [], f"git status failed: {proc.stderr.strip()}"
    parts = proc.stdout.split("\0")
    entries: list[tuple[str, str]] = []
    i = 0
    while i < len(parts):
        item = parts[i]
        i += 1
        if len(item) < 4:
            continue
        entries.append((item[:2], item[3:]))
        if item[0] in "RC":
            i += 1  # the rename/copy source path follows as its own record
    return entries, None


def _unsent_commits(workspace: Path) -> tuple[list[str], str | None]:
    """Return the commits on HEAD reachable from neither ``origin/<branch>`` nor ``origin/main``."""
    if wg.run_git(["rev-parse", "--verify", "--quiet", "HEAD"], workspace).returncode != 0:
        return [], None  # no commit yet (half-made): nothing can be unsent
    branch = wg.run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], workspace).stdout.strip()
    cmd = ["rev-list", "HEAD"]
    for ref in ("origin/main", f"origin/{branch}" if branch else ""):
        if ref and wg.run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}"], workspace).returncode == 0:
            cmd.append(f"^refs/remotes/{ref}")
    proc = wg.run_git(cmd, workspace)
    if proc.returncode != 0:
        return [], f"git rev-list failed: {proc.stderr.strip()}"
    return [line for line in proc.stdout.split() if line], None


def unsent_work(workspace: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The BO-4100c-1 verdict, taken after a fetch: ``(unsent, refusal)``.

    ``unsent`` is ``{"commits": [sha], "files": [path]}`` plus the private
    ``entries`` used for the token binding; ``refusal`` is set (and ``unsent``
    ``None``) when the verdict cannot be reached, so unknown is never "nothing".
    """
    fetch = wg.run_git(["fetch", "origin"], workspace)
    if fetch.returncode != 0:
        return None, _err("FETCH_FAILED", f"git fetch origin failed in {workspace}; cannot tell what is unsent: "
                                          f"{fetch.stderr.strip()}")
    commits, commit_err = _unsent_commits(workspace)
    entries, status_err = _status_entries(workspace)
    if commit_err or status_err:
        return None, _err("GIT_FAILED", f"Could not classify the work in {workspace}: {commit_err or status_err}")
    return {"commits": commits, "files": [path for _xy, path in entries], "entries": entries}, None


def _content_digest(workspace: Path, rel: str) -> str:
    """sha256 of the file's bytes, or a marker string when it is absent or unreadable."""
    target = workspace / rel
    try:
        return hashlib.sha256(Path(_long_path(target)).read_bytes()).hexdigest()
    except OSError:
        return "<absent>"


def discard_token(workspace: Path, marker: dict[str, Any], unsent: dict[str, Any]) -> str:
    """Stateless one-time token bound to this workspace and exactly the work a remove would lose.

    Recomputed on every request: any change to the workspace path, its marker
    record, its unsent commits, or its unsent files (set or content) changes it.
    """
    binding = {
        "path": os.path.normcase(str(workspace)),
        "marker": marker,
        "commits": sorted(unsent["commits"]),
        "files": sorted([xy, path, _content_digest(workspace, path)] for xy, path in unsent["entries"]),
    }
    return hashlib.sha256(json.dumps(binding, sort_keys=True).encode("utf-8")).hexdigest()[:32]


def _unsent_refusal(workspace: Path, unsent: dict[str, Any], token: str, presented: str | None) -> dict[str, Any]:
    """UNSENT_WORK refusal listing what would be lost and carrying the fresh ``discard_token``."""
    why = (" The discard token presented does not match this workspace's current unsent work."
           if presented else "")
    return _err(
        "UNSENT_WORK",
        f"{workspace} holds work not on the shared project: {len(unsent['commits'])} unpushed commit(s), "
        f"{len(unsent['files'])} uncommitted file(s).{why} Repeat the request with --discard-token to discard it.",
        unsent={"commits": unsent["commits"], "files": unsent["files"]}, discard_token=token,
    )


def _ancestor_pids() -> frozenset[int]:
    """This process and its ancestors (their command line names the workspace being cleared)."""
    pids = {os.getpid(), os.getppid()}
    try:
        import psutil  # noqa: PLC0415 - optional dependency
        pids.update(p.pid for p in psutil.Process().parents())
    except (ImportError, OSError, ValueError) as exc:
        _log.warning("_ancestor_pids: could not walk ancestors: %s", exc)
    return frozenset(pids)


def _load_sweep() -> Any | None:
    """Load the deployed ``worktree/sweep_processes.py`` beside this maker, or ``None`` when absent."""
    path = Path(__file__).resolve().parent / "worktree" / "sweep_processes.py"
    if not path.is_file():
        _log.warning("_load_sweep: %s is not deployed; running programs are not checked", path)
        return None
    spec = importlib.util.spec_from_file_location("leafcutter_sweep_processes", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except (ImportError, SyntaxError, OSError) as exc:
        _log.warning("_load_sweep: could not load %s: %s", path, exc)
        return None
    return module


def _holding_programs(workspace: Path) -> list[dict[str, Any]]:
    """Programs started from, or holding files in, *workspace* (reported, never killed)."""
    sweep = _load_sweep()
    if sweep is None:
        return []
    config = {"kill_residual_processes": False, "protected_paths": []}
    result = sweep.sweep(str(workspace), config=config, exclude_pids=_ancestor_pids())
    return list(result.conflict_pids)


def _rmtree_onerror(func: Any, target: str, _exc: Any) -> None:
    """Clear the read-only bit (git objects on Windows) and retry the failed deletion once."""
    os.chmod(target, stat.S_IWRITE)
    func(target)


def _delete_tree(workspace: Path) -> dict[str, Any] | None:
    """Delete the whole folder; ``None`` when nothing remains, else a PROCESS_HOLDS_FILES refusal."""
    target = _long_path(workspace)
    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(target, onexc=_rmtree_onerror)
        else:
            shutil.rmtree(target, onerror=_rmtree_onerror)
    except OSError as exc:
        _log.warning("_delete_tree: rmtree failed for %s: %s", workspace, exc)
        return _err("PROCESS_HOLDS_FILES", f"Could not remove all of {workspace} (a program may hold files): {exc}")
    if os.path.lexists(target):
        return _err("PROCESS_HOLDS_FILES", f"Part of {workspace} remains after removal; it is not cleared.")
    return None


def _authorise(workspace: Path, marker: dict[str, Any], presented: str | None,
               ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return ``(refusal, discarded)``: refuse unsent work unless *presented* matches its exact binding."""
    unsent, refusal = unsent_work(workspace)
    if refusal is not None or unsent is None:
        return refusal, {}
    discarded = {"commits": unsent["commits"], "files": unsent["files"]}
    if not unsent["commits"] and not unsent["files"]:
        return None, discarded
    token = discard_token(workspace, marker, unsent)
    if presented is not None and presented == token:
        return None, discarded
    return _unsent_refusal(workspace, unsent, token, presented), discarded


def cmd_remove(args: argparse.Namespace) -> dict[str, Any]:
    """Clear the workspace at ``--path`` completely or not at all; never reads stdin or prompts."""
    bad_override = wl.override_refusal(args)
    if bad_override is not None:
        return bad_override
    workspace = wp.resolve_arg(args.path)
    marker = wg.read_marker(workspace)
    if marker is None:
        return _err("NOT_FOUND", f"No workspace marker found at {workspace}.")
    refusal, discarded = _authorise(workspace, marker, getattr(args, "discard_token", None))
    if refusal is not None:
        return refusal
    holders = _holding_programs(workspace)
    if holders:
        named = ", ".join(f"{h.get('pid')} ({h.get('cmdline', '?')})" for h in holders)
        return _err("PROCESS_HOLDS_FILES", f"Programs are running in or holding files of {workspace}: {named}. "
                    "Stop them and ask again; nothing was removed.", processes=holders)
    if args.delete_remote_branch and marker.get("branch"):
        wg.run_git(["push", "origin", "--delete", marker["branch"]], workspace)
    failure = _delete_tree(workspace)
    if failure is not None:
        return failure
    return {"status": "ok", **wp.path_fields(workspace), "removed_path": str(workspace), "discarded": discarded}


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-12 17:30 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
#   Created: BO-4300e-1-i/-2/-2-i/-2-ii/-3/-3-i. remove moved here from
#   worktree_admin; the unsent verdict is taken after a fetch (pr-reviewer
#   M-2), refused UNSENT_WORK with a stateless sha256 discard_token (Q8);
#   running programs refuse PROCESS_HOLDS_FILES before anything is deleted
#   (reported, not killed); deletion uses the extended-length prefix and a
#   post-check. INCOMPLETE answers now carry remnant_path. (ADR-018)
# ===========================================================================
