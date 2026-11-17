"""
MODULE: worktree_remove
GOAL: The workspace maker's ``remove`` verb and the definite ``locate`` answer:
    clear a workspace completely or not at all, never wait for input, and lose
    unsent work only when the request itself carries the one-time discard token
    its refusal returned (AC BO-4300e-1-i, e-2, e-2-i, e-2-ii, e-3, e-3-i, e-2-ix..xii).
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
    ``worktree_ensure_state``, and neither imports it back. Once the checks
    passed the record is rewritten ``clearing`` and the content goes before the
    repository and the record (``delete_whole_folder(in_order=True)``); a stop is
    answered PROCESS_HOLDS_FILES saying asking again finishes it, and
    ``worktree_remove_half`` recognises what a stop left (finished without a
    second check, or with the one-time token for exactly the unchecked files).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import shutil
import sys
from pathlib import Path
from typing import Any

import worktree_admin
import worktree_answer as wa
import worktree_git as wg
import worktree_layout as wl
import worktree_paths as wp
import worktree_remove_checks as wrc
import worktree_remove_half as wrh

_log = logging.getLogger(__name__)

_err = wa.error_answer


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
    if marker.get("state") == wrh.HALF_CLEARED_STATE:
        return {**wrh.half_cleared_answer(Path(answer.get("workspace_path", ""))), **carried}
    return {**incomplete_answer(Path(answer.get("workspace_path", "")), marker), **carried}


_long_path = wrc.long_path
_holder_entry = wrc.holder_entry


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


def _unsent_commits(workspace: Path, line: str | None = None) -> tuple[list[str], str | None]:
    """Return the commits on HEAD (and, when detached, on the workspace's own *line*) reachable from neither
    ``origin/<branch>`` nor ``origin/main``."""
    if wg.run_git(["rev-parse", "--verify", "--quiet", "HEAD"], workspace).returncode != 0:
        return [], None  # no commit yet (half-made): nothing can be unsent
    attached = wg.run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], workspace).stdout.strip()
    branch = attached or line or ""
    cmd = ["rev-list", "HEAD"]
    if not attached and branch and wg.run_git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
                                              workspace).returncode == 0:
        cmd.append(f"refs/heads/{branch}")
    for ref in ("origin/main", f"origin/{branch}" if branch else ""):
        if ref and wg.run_git(["rev-parse", "--verify", "--quiet", f"refs/remotes/{ref}"], workspace).returncode == 0:
            cmd.append(f"^refs/remotes/{ref}")
    proc = wg.run_git(cmd, workspace)
    if proc.returncode != 0:
        return [], "git rev-list"
    return [sha for sha in proc.stdout.split() if sha], None


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


def unsent_work(workspace: Path, line: str | None = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    """The BO-4100c-1 verdict, taken after a fetch: ``(unsent, refusal)``.

    ``unsent`` is ``{"commits": [sha], "files": [path]}`` plus the private
    ``entries`` used for the token binding; ``refusal`` is set (and ``unsent``
    ``None``) when the verdict cannot be reached, so unknown is never "nothing". *line* is the
    workspace's recorded line of work, checked too when the workspace is detached (``detached`` key).
    """
    fetch = _fetch_origin(workspace)
    if fetch.returncode != 0:
        return None, _err("FETCH_FAILED", f"The step 'git fetch origin' failed in {workspace}; cannot tell what is "
                                          "unsent (git's own message is on stderr).", step="git fetch origin")
    commits, commit_err = _unsent_commits(workspace, line)
    entries, status_err = status_entries(workspace)
    failed = commit_err or status_err
    if failed:
        return None, _err("GIT_FAILED", f"Could not classify the work in {workspace}: the step {failed!r} failed "
                          "(git's own message is on stderr).", step=failed)
    detached = wg.run_git(["symbolic-ref", "--quiet", "HEAD"], workspace).returncode == 1
    return {"commits": commits, "files": [path for _xy, path in entries], "entries": entries,
            "detached": detached}, None


def discard_token(workspace: Path, marker: dict[str, Any], unsent: dict[str, Any]) -> str:
    """Stateless one-time token bound to this workspace and exactly the work a remove would lose.

    Recomputed on every request: any change to the workspace path, its marker
    record, its unsent commits, or its unsent files (set or content) changes it.
    """
    binding = {
        "path": os.path.normcase(str(workspace)),
        "marker": marker,
        "commits": sorted(unsent["commits"]),
        "files": sorted([xy, path, wrc.content_digest(workspace, path)] for xy, path in unsent["entries"]),
    }
    return hashlib.sha256(json.dumps(binding, sort_keys=True).encode("utf-8")).hexdigest()[:32]


def _unsent_refusal(workspace: Path, unsent: dict[str, Any], token: str, presented: str | None) -> dict[str, Any]:
    """UNSENT_WORK refusal listing what would be lost and carrying the fresh ``discard_token``."""
    why = (" The discard token presented does not match this workspace's current unsent work."
           if presented else "")
    if unsent.get("detached"):
        why += " The workspace is not on its line of work (detached), so the commit it sits on was checked too."
    return _err(
        "UNSENT_WORK",
        f"{workspace} holds work not on the shared project: {len(unsent['commits'])} unpushed commit(s), "
        f"{len(unsent['files'])} uncommitted file(s).{why} Repeat the request with --discard-token to discard it.",
        unsent={"commits": unsent["commits"], "files": unsent["files"]}, discard_token=token,
    )


def delete_whole_folder(path: Path, in_order: bool = False) -> str | None:
    """Delete the whole folder at *path* (the one rmtree of the workspace maker).

    Uses the Windows extended-length prefix, clears read-only files and checks
    afterwards that nothing remains. With *in_order* the content goes first, then
    the repository folder, then the record, and a stop leaves the repository
    folder in place when anything else could not go (so a later ask finishes
    it). Returns ``None`` when nothing remains, else a short reason text (no
    refusal is built here, so every caller words its own answer).
    """
    target = _long_path(path)
    failed: list[str] = []

    def _collect(func: Any, item: str, exc: Any) -> None:
        # An item that still cannot go is noted and rmtree carries on with the rest; raising here would
        # abort the whole delete (on POSIX) and leave rmtree's last error, the non-empty folder, as the reason.
        try:
            wrc.rmtree_onerror(func, item, exc)
        except OSError as err:
            _log.warning("delete_whole_folder: could not delete %s: %s", item, err)
            failed.append(item)

    def _rmtree(item: str) -> None:
        if sys.version_info >= (3, 12):
            shutil.rmtree(item, onexc=_collect)
        else:
            shutil.rmtree(item, onerror=_collect)

    try:
        if in_order:
            wrc.delete_children_first(target, _rmtree, _collect, failed)
        if not failed:
            _rmtree(target)
    except OSError as exc:
        _log.warning("delete_whole_folder: rmtree failed for %s: %s", path, exc)
        return f"Could not remove all of {path} (a program may hold files): {exc}"
    if failed:
        return f"Could not remove all of {path} (a program may hold files): {wrc.named_failures(target, failed)}"
    if os.path.lexists(target):
        return f"Part of {path} remains after removal; it is not cleared."
    return None


def _delete_tree(workspace: Path) -> dict[str, Any] | None:
    """Delete the whole folder; ``None`` when nothing remains, else a PROCESS_HOLDS_FILES refusal saying to ask again."""
    reason = delete_whole_folder(workspace, in_order=True)
    if reason is None:
        return None
    return _err("PROCESS_HOLDS_FILES", f"{reason} The clearing stopped part-way and is not finished: make the same "
                "request again and it finishes (no token, fetch or second check of unsent work is needed).")


def _authorise(workspace: Path, marker: dict[str, Any], presented: str | None,
               ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Return ``(refusal, discarded)``: refuse unsent work unless *presented* matches its exact binding."""
    unsent, refusal = unsent_work(workspace, str(marker.get("branch") or "") or None)
    if refusal is not None or unsent is None:
        return refusal, {}
    discarded = {"commits": unsent["commits"], "files": unsent["files"]}
    if not unsent["commits"] and not unsent["files"]:
        return None, discarded
    token = discard_token(workspace, marker, unsent)
    if presented is not None and presented == token:
        return None, discarded
    return _unsent_refusal(workspace, unsent, token, presented), discarded


def _own_workspace(args: argparse.Namespace, workspace: Path) -> dict[str, Any] | None:
    """Return the marker when *workspace* is one of this project's own workspaces, else ``None``.

    The project is ``--repo-root`` when given, else the one the marker records.
    The path must lie inside that project's landing place (honouring
    ``--landing-root``) and the marker must record that same project. A
    workspace switched onto a bare commit (detached) is still its own.
    """
    marker = wg.read_marker(workspace)
    project, root = wrh.project_and_root(args, workspace, marker)
    if marker is None or project is None or root is None:
        return None
    resolved = workspace.resolve()
    if wl.other_project_occupant(workspace, marker, project) or not _is_workspace_slot(resolved, root):
        return None
    return marker if _on_own_line(resolved, marker) else None


def _on_own_line(resolved: Path, marker: dict[str, Any]) -> bool:
    """True when the checked-out branch is the recorded one, or HEAD is detached (not on any branch)."""
    current = _checked_out_branch(resolved)
    if current is not None:
        return current == marker.get("branch")
    return wg.run_git(["symbolic-ref", "--quiet", "HEAD"], resolved).returncode == 1


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


def _blocked_by_programs(workspace: Path) -> dict[str, Any] | None:
    """PROCESS_HOLDS_FILES refusal when programs work inside *workspace* or the program check cannot run."""
    holders, unavailable = wrc.program_check(workspace)
    if unavailable is not None:
        return _err("PROCESS_HOLDS_FILES", f"The program check is unavailable ({unavailable}), so it cannot be "
                    f"told whether programs are working inside {workspace}; nothing was removed.")
    if not holders:
        return None
    named = ", ".join(f"{h['pid']} ({h['name']})" for h in holders)
    return _err("PROCESS_HOLDS_FILES", f"Programs are working inside {workspace}: {named}. "
                "Stop them and ask again; nothing was removed.", holders=holders)


def _finish_half(args: argparse.Namespace, workspace: Path, marker: dict[str, Any], kind: str) -> dict[str, Any]:
    """Finish a clearing left part-way, or refuse: files in it cannot be checked, so they go only with their token.

    The shared project is never touched. A record-less folder not shown to be this project's is NOT_FOUND,
    listing its files and returning no token. A clearing that checked its work first (``resume``) needs none.
    """
    files = wrc.remaining_files(workspace)
    if kind == "foreign" or (kind == "gone" and not marker and files):
        return _err("NOT_FOUND", f"{workspace} holds files but is not shown to be a workspace of this project "
                    "(no workspace record naming it); nothing was changed.", files=files)
    blocked = _blocked_by_programs(workspace)
    if blocked is not None:
        return blocked
    needs_token = kind != "resume" and (bool(files) or (kind == "unreadable" and marker.get("state") == "ready"))
    presented = getattr(args, "discard_token", None)
    token = wrc.half_token(workspace, marker or None, files) if needs_token else ""
    if needs_token and presented != token:
        return wrc.half_refusal(workspace, files, token, presented, unreadable=kind == "unreadable")
    failure = _delete_tree(workspace.resolve())
    if failure is not None:
        return failure
    return {"status": "ok", **wp.path_fields(workspace), "removed_path": str(workspace),
            "discarded": {"commits": [], "files": files if needs_token else []}}


def _mark_clearing(args: argparse.Namespace, workspace: Path, marker: dict[str, Any]) -> dict[str, Any] | None:
    """Record, atomically and before anything is deleted, that the checks passed (``None``, or a refusal when it cannot)."""
    project, _root = wrh.project_and_root(args, workspace, marker)
    _state, sha = wrh.head_state(workspace.resolve())
    try:
        wg.write_marker(workspace, wrh.clearing_marker(marker, workspace, project or workspace.parent, sha))
    except OSError as exc:
        return _err("PROCESS_HOLDS_FILES", f"The record of {workspace} could not be rewritten ({exc}); nothing was removed.")
    return None


def cmd_remove(args: argparse.Namespace) -> dict[str, Any]:
    """Clear the workspace at ``--path`` (or named by ``--kind``/``--slug``); never reads stdin or prompts.

    Programs working inside it are checked first (nothing is fetched, pushed or
    deleted while one runs). The hub branch (when asked for) is deleted before
    the local folder; if the local delete then fails the answer says the hub
    branch is already gone (``hub_branch_deleted``). Once the checks passed the
    record says ``clearing``, so a clearing that stops part-way is finished by
    asking again; a clearing already started whose checked commit is unchanged
    is finished without a second check.
    """
    if (bad_override := wl.override_refusal(args)) is not None:
        return bad_override
    workspace, refusal = wrh.target_path(args)
    if workspace is None:
        return refusal or _err("USAGE", "remove requires --path.")
    half = wrh.half_state(args, workspace)
    if half is not None and half[1] != "resume":
        return _finish_half(args, workspace, *half)
    marker = _own_workspace(args, workspace)
    if marker is None:
        return _err("NOT_FOUND", f"This project has no workspace at {workspace}; nothing was changed.")
    if args.delete_remote_branch and (unsafe := _unsafe_hub_branch(workspace, str(marker.get("branch") or ""))):
        return unsafe
    if half is not None:
        return _finish_half(args, workspace, *half)
    if (blocked := _blocked_by_programs(workspace)) is not None:
        return blocked
    refusal, discarded = _authorise(workspace, marker, getattr(args, "discard_token", None))
    if refusal is not None:
        return refusal
    return _clear_checked(args, workspace, marker, discarded)


def _clear_checked(args: argparse.Namespace, workspace: Path, marker: dict, discarded: dict) -> dict[str, Any]:
    """Delete the hub branch (when asked for), mark the clearing, then delete the folder."""
    if args.delete_remote_branch and (failure := _delete_hub_branch(workspace, marker["branch"])) is not None:
        return failure
    failure = _mark_clearing(args, workspace, marker) or _delete_tree(workspace.resolve())
    if failure is not None:
        if args.delete_remote_branch:
            failure["message"] += " The branch on the shared project was already deleted."
            failure["hub_branch_deleted"] = True
        return failure
    return {"status": "ok", **wp.path_fields(workspace), "removed_path": str(workspace), "discarded": discarded}


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-11-03 [python-coder/fast-lane bo-4300e-2, BO-4300e-2-ix..xii]:
#   remove can name the work (--kind/--slug); the record is rewritten
#   ``clearing`` once the checks passed and before any deletion; deletion goes
#   content, repository, record; a stopped clearing is finished by asking
#   again (no token, fetch or second check when the checked commit is
#   unchanged); an unreadable repository and an identified record-less leftover
#   are half-cleared (token for the remaining files). Recognition moved to
#   worktree_remove_half. (#fast-lane/BO-4300e-2) (ADR-018)
# - 2026-10-26 [python-coder/fast-lane bo-4300e-2, BO-4300e-2-iv..viii]:
#   Program check moved to worktree_remove_checks and runs FIRST, failing
#   closed; half-cleared folders (no .git) are finished or token-refused;
#   a detached workspace is found and its own line is checked too; a
#   vanished item is not a deletion failure (a real failure still is).
#   (#fast-lane/BO-4300e-2) (ADR-018)
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
