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
    nothing at the location. ``remove`` acts only on a workspace in its own
    project's landing place (anything else is NOT_FOUND), deletes the hub branch
    before any local deletion, and names a failed git step in a ``step`` field
    without pasting git's text (that goes to stderr). This module is the one home
    of ``delete_whole_folder`` (the only rmtree) and of the ``status -z`` parser
    ``parse_status_z`` / ``status_entries``; it imports ``worktree_admin`` and
    ``worktree_ensure_state``, and neither imports it back.
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
import worktree_git as wg
import worktree_layout as wl
import worktree_paths as wp

_log = logging.getLogger(__name__)

_err = wa.error_answer
_EXTENDED_PREFIX = "\\\\?\\"


def incomplete_answer(workspace: Path, marker: dict[str, Any]) -> dict[str, Any]:
    """Alias of :func:`worktree_admin.incomplete_answer` (resolved at call time: the import cycle forbids a bind)."""
    return worktree_admin.incomplete_answer(workspace, marker)


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


def parse_status_z(raw: str) -> list[tuple[str, str]]:
    """Parse ``git status --porcelain=v1 -z`` output into ``[(XY, path)]``.

    A rename or copy in EITHER column (``R``/``C`` as X or as Y) is followed by
    its source path as its own record; both paths are returned.
    """
    parts = raw.split("\0")
    entries: list[tuple[str, str]] = []
    i = 0
    while i < len(parts):
        item = parts[i]
        i += 1
        if len(item) < 4:
            continue
        xy = item[:2]
        entries.append((xy, item[3:]))
        if "R" in xy or "C" in xy:
            if i < len(parts) and parts[i]:
                entries.append((xy, parts[i]))
            i += 1
    return entries


def status_entries(workspace: Path, no_optional_locks: bool = False,
                   extra: tuple[str, ...] = ()) -> tuple[list[tuple[str, str]], str | None]:
    """Return ``([(XY, path)], failed_step)`` for every uncommitted or untracked (non-ignored) change.

    *no_optional_locks* keeps a read-only caller from refreshing the index; *extra* options come last.
    """
    cmd = ["status", "--porcelain=v1", "-z", "--untracked-files=all", *extra]
    proc = wg.run_git(["--no-optional-locks", *cmd] if no_optional_locks else cmd, workspace)
    if proc.returncode != 0:
        return [], "git status"
    return parse_status_z(proc.stdout), None


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
        return [], "git rev-list"
    return [line for line in proc.stdout.split() if line], None


def _fetch_origin(workspace: Path) -> Any:
    """Fetch ``origin`` without leaving a trace in ``.git/FETCH_HEAD``.

    ``--no-write-fetch-head`` needs git 2.29+. When git rejects it, retry with
    a plain fetch and put the previous FETCH_HEAD bytes back (or remove the
    file when there was none), so a refused remove leaves the folder as found.
    """
    proc = wg.run_git(["fetch", "--no-write-fetch-head", "origin"], workspace)
    if proc.returncode == 0 or "unknown option" not in proc.stderr.lower():
        return proc
    head = workspace / ".git" / "FETCH_HEAD"
    before = head.read_bytes() if head.is_file() else None
    proc = wg.run_git(["fetch", "origin"], workspace)
    try:
        if before is None:
            head.unlink(missing_ok=True)
        else:
            head.write_bytes(before)
    except OSError as exc:
        _log.warning("_fetch_origin: could not restore %s: %s", head, exc)
    return proc


def unsent_work(workspace: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The BO-4100c-1 verdict, taken after a fetch: ``(unsent, refusal)``.

    ``unsent`` is ``{"commits": [sha], "files": [path]}`` plus the private
    ``entries`` used for the token binding; ``refusal`` is set (and ``unsent``
    ``None``) when the verdict cannot be reached, so unknown is never "nothing".
    """
    fetch = _fetch_origin(workspace)
    if fetch.returncode != 0:
        return None, _err("FETCH_FAILED", f"The step 'git fetch origin' failed in {workspace}; cannot tell what is "
                                          "unsent (git's own message is on stderr).", step="git fetch origin")
    commits, commit_err = _unsent_commits(workspace)
    entries, status_err = status_entries(workspace)
    failed = commit_err or status_err
    if failed:
        return None, _err("GIT_FAILED", f"Could not classify the work in {workspace}: the step {failed!r} failed "
                          "(git's own message is on stderr).", step=failed)
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


def delete_whole_folder(path: Path) -> str | None:
    """Delete the whole folder at *path* (the one rmtree of the workspace maker).

    Uses the Windows extended-length prefix, clears read-only files and checks
    afterwards that nothing remains. Returns ``None`` when nothing remains,
    else a short reason text (no refusal is built here, so every caller words
    its own answer).
    """
    target = _long_path(path)
    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(target, onexc=_rmtree_onerror)
        else:
            shutil.rmtree(target, onerror=_rmtree_onerror)
    except OSError as exc:
        _log.warning("delete_whole_folder: rmtree failed for %s: %s", path, exc)
        return f"Could not remove all of {path} (a program may hold files): {exc}"
    if os.path.lexists(target):
        return f"Part of {path} remains after removal; it is not cleared."
    return None


def _delete_tree(workspace: Path) -> dict[str, Any] | None:
    """Delete the whole folder; ``None`` when nothing remains, else a PROCESS_HOLDS_FILES refusal."""
    reason = delete_whole_folder(workspace)
    return None if reason is None else _err("PROCESS_HOLDS_FILES", reason)


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


def _holder_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Reduce a sweep entry to ``{"pid": int, "name": str}`` (the program's name, never its command line).

    Never raises: any failure to ask the system for the name falls back to the command line's first word.
    """
    pid = 0
    try:
        pid = int(entry.get("pid", 0))
        import psutil  # noqa: PLC0415 - optional dependency
        name = psutil.Process(pid).name()
    except Exception as exc:  # noqa: BLE001 - psutil.Error is not an OSError; the answer must still be built
        _log.warning("_holder_entry: no process name for pid %s: %s", pid, exc)
        words = str(entry.get("cmdline", "")).split()
        name = Path(words[0]).name if words else "unknown"
    return {"pid": pid, "name": str(name)}


def _own_workspace(args: argparse.Namespace, workspace: Path) -> dict[str, Any] | None:
    """Return the marker when *workspace* is one of this project's own workspaces, else ``None``.

    The project is ``--repo-root`` when given, else the one the marker records.
    The path must lie inside that project's landing place (honouring
    ``--landing-root``) and the marker must record that same project.
    """
    marker = wg.read_marker(workspace)
    if marker is None:
        return None
    if args.repo_root:
        project, refusal = wl.resolve_repo_root(args.repo_root)
        if refusal is not None or project is None:
            return None
    else:
        project = wl.project_of(workspace, marker)
        if project is None:
            return None
    place, usage = wl.landing_for(getattr(args, "landing_root", None), project)
    if usage is not None or place is None:
        return None
    resolved, root = workspace.resolve(), place.resolve()
    if wl.other_project_occupant(workspace, marker, project) or not _is_workspace_slot(resolved, root):
        return None
    return marker if _checked_out_branch(resolved) == marker.get("branch") else None


def _is_workspace_slot(resolved: Path, root: Path) -> bool:
    """True when *resolved* is exactly ``<root>/<kind>/<slug>`` (depth 2) with a known kind and its own ``.git``."""
    try:
        parts = resolved.relative_to(root).parts
    except ValueError:
        return False
    return len(parts) == 2 and parts[0] in wg.VALID_KINDS and (resolved / ".git").exists()


def _checked_out_branch(workspace: Path) -> str | None:
    """The branch checked out in the workspace's own repository (``git branch --show-current``), else ``None``."""
    proc = wg.run_git(["branch", "--show-current"], workspace)
    text = proc.stdout.strip() if proc.returncode == 0 else ""
    return text or None


def _unsafe_hub_branch(workspace: Path, branch: str) -> dict[str, Any] | None:
    """Refusal when *branch* must never be deleted on the shared project (protected, empty, or option-like)."""
    if not branch or branch.startswith("-"):
        return _err("NOT_FOUND", f"The workspace at {workspace} records no usable branch ({branch!r}); "
                    "nothing was changed.")
    head = wg.run_git(["symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD"], workspace)
    default = head.stdout.strip().removeprefix("origin/") if head.returncode == 0 else ""
    if branch in {"main", "master", default}:
        return _err("ON_PROTECTED_BRANCH", f"{branch!r} is a protected branch of the shared project; "
                    "its line is never deleted by remove. Nothing was changed.", branch=branch)
    return None


def _delete_hub_branch(workspace: Path, branch: str) -> dict[str, Any] | None:
    """Delete *branch* on the shared project; a GIT_FAILED answer naming the step when it fails."""
    step = f"push origin --delete {branch}"
    if wg.run_git(["ls-remote", "--exit-code", "--heads", "origin", branch], workspace).returncode == 2:
        return None  # the line was never pushed (or is already gone): nothing to delete on the shared project
    if wg.run_git(["push", "origin", "--delete", branch], workspace).returncode == 0:
        return None
    return _err("GIT_FAILED", f"The step {step!r} failed; nothing was removed (git's own message is on stderr).",
                step=step)


def cmd_remove(args: argparse.Namespace) -> dict[str, Any]:
    """Clear the workspace at ``--path``; never reads stdin or prompts.

    The hub branch (when asked for) is deleted first and the local folder only
    after; if the local delete then fails the answer says the hub branch is
    already gone (``hub_branch_deleted``).
    """
    bad_override = wl.override_refusal(args)
    if bad_override is not None:
        return bad_override
    workspace = wp.resolve_arg(args.path)
    marker = _own_workspace(args, workspace)
    if marker is None:
        return _err("NOT_FOUND", f"This project has no workspace at {workspace}; nothing was changed.")
    if args.delete_remote_branch:
        unsafe = _unsafe_hub_branch(workspace, str(marker.get("branch") or ""))
        if unsafe is not None:
            return unsafe
    refusal, discarded = _authorise(workspace, marker, getattr(args, "discard_token", None))
    if refusal is not None:
        return refusal
    holders = [_holder_entry(h) for h in _holding_programs(workspace)]
    if holders:
        named = ", ".join(f"{h['pid']} ({h['name']})" for h in holders)
        return _err("PROCESS_HOLDS_FILES", f"Programs are running in or holding files of {workspace}: {named}. "
                    "Stop them and ask again; nothing was removed.", holders=holders)
    if args.delete_remote_branch:
        failure = _delete_hub_branch(workspace, marker["branch"])
        if failure is not None:
            return failure
    failure = _delete_tree(workspace.resolve())
    if failure is not None:
        if args.delete_remote_branch:
            failure["message"] += " The branch on the shared project was already deleted."
            failure["hub_branch_deleted"] = True
        return failure
    return {"status": "ok", **wp.path_fields(workspace), "removed_path": str(workspace), "discarded": discarded}


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-22 [python-coder/EPIC-WorkspaceMakerHardening/04 rework]:
#   "Already gone" rule: before deleting the hub branch, ``git ls-remote
#   --exit-code --heads origin <branch>``; exit 2 (no such ref) counts as
#   already deleted and the push is skipped, so a never-pushed line does not
#   block a remove. Limits: only exit 2 is trusted (any other ls-remote
#   failure falls through to the push, which then fails closed as GIT_FAILED);
#   a hub that hides refs from ls-remote but would accept the push is treated
#   as "gone"; the check is a point in time, not a lock. remove also acts only
#   on <landing>/<kind>/<slug> whose checked-out branch equals the marker's,
#   and never deletes a protected (main, master, hub default) branch.
# - 2026-10-22 [python-coder/EPIC-WorkspaceMakerHardening/04]:
#   BO-4300e-2-iii/-3-ii: remove acts only inside its own project's landing
#   place (else NOT_FOUND); the hub branch is deleted before any local
#   deletion and a failed push is GIT_FAILED with a ``step``. Failed git steps
#   carry ``step`` and no git text; PROCESS_HOLDS_FILES answers ``holders``
#   [{pid, name}]. Public ``delete_whole_folder``, ``parse_status_z`` (handles
#   the Y-side rename) and ``status_entries`` are the shared helpers.
# - 2026-10-12 17:30 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
#   Created: BO-4300e-1-i/-2/-2-i/-2-ii/-3/-3-i. remove moved here from
#   worktree_admin; the unsent verdict is taken after a fetch (pr-reviewer
#   M-2), refused UNSENT_WORK with a stateless sha256 discard_token (Q8);
#   running programs refuse PROCESS_HOLDS_FILES before anything is deleted
#   (reported, not killed); deletion uses the extended-length prefix and a
#   post-check. INCOMPLETE answers now carry remnant_path. (ADR-018)
# ===========================================================================
