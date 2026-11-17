"""
MODULE: worktree_migrate_guards
GOAL: The read-only checks the ``migrate-legacy`` cut-over takes on one old-style
    workspace BEFORE it acts on it: is something in progress or held that a
    carried-over copy would lose, and which git-ignored files would deleting
    the folder remove (AC BO-4300f-3-iii, BO-4300f-3-iv).
BUSINESS CONTEXT: The cut-over must lose nothing silently. A merge, rebase,
    cherry-pick, revert or bisect in progress, a stash made on the workspace's
    line of work, staged changes (the index is not carried over) and a lock the
    user set are all state that a plain copy of the files would drop, so the
    workspace is kept exactly as it is and listed for a human decision. Ignored
    files (``.env.local``, ``build/``) are in no commit and no clone, so the
    report names them before the folder is deleted.
ARCHITECTURE: Stdlib-only sibling of ``worktree_migrate``. Operation markers and
    the lock text is read by ``worktree_migrate``; the stash list is read from the
    main copy; status calls go through ``worktree_remove.status_entries`` with
    ``no_optional_locks`` so a kept workspace's index is never rewritten.
    Every guard fails CLOSED: a git call that fails keeps the workspace with
    "could not check <what>". Nothing here changes a folder, ref, stash or config.
"""

from __future__ import annotations

import re
from pathlib import Path

import worktree_git as wg
import worktree_remove as wrm

_OPERATIONS = (
    ("MERGE_HEAD", "a merge"),
    ("CHERRY_PICK_HEAD", "a cherry-pick"),
    ("REVERT_HEAD", "a revert"),
    ("BISECT_LOG", "a bisect"),
    ("sequencer", "a multi-commit cherry-pick or revert"),
    ("rebase-merge", "a rebase"),
    ("rebase-apply", "a rebase (or mailbox apply)"),
)
_STASH_BRANCH = re.compile(r"^(?:WIP on|On) (.+?):")
_DETACHED = "(no branch)"
WSL_LOCK = "initializing"  # the exact reason WSL leaves on a stuck registration (removed only when its folder is gone)


def _could_not(what: str) -> str:
    """The reason of a guard whose git call failed (fail closed)."""
    return f"could not check {what}; it is left as it is"


def operation_in_progress(admin: Path) -> str | None:
    """Name the operation (merge, rebase, ...) left unfinished in the registration *admin*, else ``None``."""
    return next((name for marker, name in _OPERATIONS if (admin / marker).exists()), None)


def stash_branches(repo_root: Path) -> set[str] | None:
    """The branches (``(no branch)`` for a detached HEAD) stash entries were made on, or ``None`` if unreadable."""
    proc = wg.run_git(["stash", "list", "--format=%gs"], repo_root)
    if proc.returncode != 0:
        return None
    found = (_STASH_BRANCH.match(line) for line in proc.stdout.splitlines())
    return {m.group(1) for m in found if m}


def _stash_reason(repo_root: Path, branch: str | None) -> str | None:
    """Why a stash keeps the workspace on *branch* (``None`` = detached), else ``None``."""
    stashed = stash_branches(repo_root)
    if stashed is None:
        return _could_not("the stash list")
    if branch in stashed:
        return f"a stash was made on its line of work {branch!r}; a stash would be left behind"
    if branch is None and _DETACHED in stashed:
        return "its HEAD is detached and a stash was made on a detached HEAD; a stash would be left behind"
    return None


def hidden_changes(folder: Path) -> bool | None:
    """True when *folder* has skip-worktree or assume-unchanged entries (status cannot see them); ``None`` if unreadable."""
    proc = wg.run_git(["ls-files", "-v", "-z"], folder)
    if proc.returncode != 0:
        return None
    return any(item[:1].islower() or item[:1] == "S" for item in proc.stdout.split("\0") if item)


def has_staged_changes(folder: Path) -> bool | None:
    """True when anything is staged in *folder*; ``None`` when git could not say."""
    entries, failed = wrm.status_entries(folder, no_optional_locks=True)
    if failed:
        return None
    return any(xy[0] not in " ?!" for xy, _path in entries)


def ignored_paths(folder: Path) -> list[str] | None:
    """The git-ignored paths in *folder*, a wholly ignored folder named as that folder (``build/``); ``None`` if unreadable."""
    entries, failed = wrm.status_entries(folder, no_optional_locks=True,
                                         extra=("--untracked-files=normal", "--ignored"))
    return None if failed else sorted(path for xy, path in entries if xy == "!!")


def _folder_reason(folder: Path) -> str | None:
    """Why the existing *folder* is kept (staged or hidden changes, or unreadable), else ``None``."""
    staged = has_staged_changes(folder)
    if staged is None:
        return _could_not("its staged changes")
    if staged:
        return "it holds staged changes, and the index is not carried over exactly"
    hidden = hidden_changes(folder)
    if hidden is None:
        return _could_not("its skip-worktree and assume-unchanged entries")
    return "it has skip-worktree or assume-unchanged entries that status cannot see" if hidden else None


def blocker(repo_root: Path, admin: Path, folder: Path | None, branch: str | None, lock: str | None) -> str | None:
    """Why the old workspace must be kept exactly as it is, else ``None`` (nothing is changed to find out).

    *lock* is the text of the registration's ``locked`` file (``None`` = no lock). Every lock keeps the
    workspace: WSL's stuck ``initializing`` entry is removed earlier, and only when its folder is gone.
    """
    if lock is not None:
        return f"it is locked (reason: {lock or 'none given'}); a lock is never overridden"
    operation = operation_in_progress(admin)
    if operation is not None:
        return f"{operation} is in progress in it; finish or abort it, then run the cut-over again"
    stash = _stash_reason(repo_root, branch)
    if stash is not None:
        return stash
    return _folder_reason(folder) if folder is not None and folder.exists() else None
