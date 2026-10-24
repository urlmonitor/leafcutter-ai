"""
MODULE: worktree_migrate_carry
GOAL: The copy-and-prove half of the ``migrate-legacy`` cut-over: build the
    marker-bearing clone of an old-style workspace, carry its unsent work into
    it, prove the copy exact, and take a comparable snapshot of the old folder
    so the caller can see that nothing changed before it deletes anything
    (AC BO-4300f-3, f-3-i, f-3-iii, f-3-iv).
BUSINESS CONTEXT: A brought-over workspace must hold every unsent commit and
    every uncommitted, untracked, ignored (``.env``-style) file, empty folder
    and symlink the old one held, byte for byte. The old folder is deleted only
    after the copy is proved exact AND the old folder is shown unchanged since
    the proof; anything else keeps both copies for a human decision.
ARCHITECTURE: Stdlib-only sibling of ``worktree_migrate``. The clone comes from
    ``worktree_ensure_steps`` (main checkout, hardlinked, hub as origin); the
    unsent verdict and the status parser are ``worktree_remove``'s; ignored
    listings are ``worktree_migrate_guards``'s. The install folder
    (``.leafcutter/``) is NOT carried: the follow-up ``ensure`` rebuilds it and
    it is reported in ``ignored_removed``. Nothing here deletes the old folder.
"""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import worktree_ensure_steps as wst
import worktree_git as wg
import worktree_identity as wi
import worktree_migrate_guards as wmg
import worktree_paths as wp
import worktree_remove as wrm

_log = logging.getLogger(__name__)

INSTALL_DIR = ".leafcutter"


def _file_hash(path: Path) -> str:
    """The SHA-256 of the file's bytes, read in pieces."""
    digest = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        _log.warning("cannot read %s for its fingerprint: %s", path, exc)
        raise  # unreadable must never compare equal; callers keep the workspace
    return digest.hexdigest()


def fingerprint(path: Path) -> str | None:
    """A comparable text for what is at *path* (file bytes, symlink target, or a folder's whole tree); ``None`` if absent.

    Raises ``OSError`` when something there cannot be read, so a caller never
    mistakes "unreadable" for "equal".
    """
    if os.path.islink(path):
        return "link:" + os.readlink(path)
    if path.is_file():
        return "file:" + _file_hash(path)
    if not path.is_dir():
        return None
    parts: list[str] = []
    for root, dirs, files in os.walk(path):
        dirs.sort()
        rel = Path(root).relative_to(path).as_posix()
        if not dirs and not files:
            parts.append(f"empty:{rel}")
        for name in sorted([*files, *(d for d in dirs if os.path.islink(Path(root) / d))]):
            parts.append(f"{rel}/{name}={fingerprint(Path(root) / name)}")
    return "dir:" + hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def empty_dirs(folder: Path) -> list[str]:
    """Every empty folder below *folder* (git cannot see them), apart from ``.git`` and the install folder."""
    found = []
    for root, dirs, files in os.walk(folder):
        if root == str(folder):
            dirs[:] = [d for d in dirs if d not in (".git", INSTALL_DIR)]
        if not dirs and not files and Path(root) != folder:
            found.append(Path(root).relative_to(folder).as_posix())
    return sorted(found)


def split_ignored(ignored: list[str]) -> tuple[list[str], list[str]]:
    """``(carried, install)``: the ignored paths carried over, and the install folder's (rebuilt, so reported)."""
    install = [p for p in ignored if p.rstrip("/").split("/")[0] == INSTALL_DIR]
    return [p for p in ignored if p not in install], install


def changed_paths(folder: Path) -> set[str] | None:
    """Every path git reports as changed or untracked in *folder* (rename sources included), or ``None``."""
    entries, failed = wrm.status_entries(folder)
    return None if failed else {path for _xy, path in entries}


def snapshot(folder: Path, carried: list[str], proof: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """What the old folder holds, comparable with a later snapshot; ``None`` when unreadable (fail closed).

    *proof* is an unsent-work verdict already taken; passing it makes the
    snapshot carry THAT verdict (so a change made after it shows up as a
    difference on the next snapshot) instead of asking again.
    """
    unsent = proof if proof is not None else wrm.unsent_work(folder)[0]
    paths, ignored = changed_paths(folder), wmg.ignored_paths(folder)
    head = wg.run_git(["rev-parse", "HEAD"], folder).stdout.strip()
    if unsent is None or paths is None or ignored is None or not head:
        return None
    try:
        return {"head": head, "commits": list(unsent["commits"]), "files": sorted(unsent["files"]),
                "paths": {rel: fingerprint(folder / rel) for rel in sorted(paths)},
                "ignored": {rel: fingerprint(folder / rel.rstrip("/")) if rel in carried else "" for rel in ignored},
                "empty": empty_dirs(folder)}
    except OSError as exc:
        _log.warning("snapshot: cannot read %s: %s", folder, exc)
        return None


def _copy_one(source: Path, target: Path) -> None:
    """Copy one file, symlink or folder tree from *source* to *target*, keeping links as links."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if os.path.islink(source):
        if os.path.lexists(target):
            target.unlink()
        os.symlink(os.readlink(source), target, target_is_directory=source.is_dir())
    elif source.is_dir():
        shutil.copytree(source, target, symlinks=True, dirs_exist_ok=True)
    else:
        shutil.copy2(source, target)


def _carry(src: Path, dst: Path, paths: set[str], carried: list[str]) -> None:
    """Carry each changed path, each carried ignored path and each empty folder from *src* into *dst*."""
    for rel in sorted(paths):
        source, target = src / rel, dst / rel
        if os.path.lexists(source) and not source.is_dir():
            _copy_one(source, target)
        elif os.path.lexists(target) and not target.is_dir():
            os.chmod(target, stat.S_IWRITE)
            target.unlink()
    for rel in carried:
        _copy_one(src / rel.rstrip("/"), dst / rel.rstrip("/"))
    for rel in empty_dirs(src):
        (dst / rel).mkdir(parents=True, exist_ok=True)


def _lossless(dst: Path, before: dict[str, Any]) -> str | None:
    """Why the clone is NOT provably what the old folder held (*before*), or ``None`` when every check holds."""
    if wg.run_git(["rev-parse", "HEAD"], dst).stdout.strip() != before["head"]:
        return "the clone's HEAD is not the original's"
    for sha in before["commits"]:
        if wg.run_git(["cat-file", "-e", f"{sha}^{{commit}}"], dst).returncode != 0:
            return f"commit {sha} is missing from the clone"
    if changed_paths(dst) != set(before["paths"]):
        return "the clone's changed-file set differs from the original's"
    wanted = {**before["paths"], **{rel.rstrip("/"): fp for rel, fp in before["ignored"].items() if fp}}
    differing = [rel for rel, fp in sorted(wanted.items()) if fingerprint(dst / rel) != fp]
    if differing:
        return f"content differs for {differing[0]}"
    missing = [rel for rel in before["empty"] if not (dst / rel).is_dir()]
    return f"the empty folder {missing[0]} is missing" if missing else None


def _marker(repo_root: Path, hub: str, folder: Path, branch: str, ident: wi.Identity, target: Path) -> dict[str, Any]:
    """The not-yet-ready marker for a brought-over workspace (hub and project stored relative to it)."""
    base = wg.run_git(["rev-parse", "origin/main"], target).stdout.strip() or None
    return {
        "schema_version": 1, "kind": ident.kind, "slug": ident.slug, "branch": branch,
        "hub": wp.portable(hub, target), "project_root": wp.portable(str(repo_root), target),
        "base_commit": base, "maker_version": wg.MAKER_VERSION, "state": "creating", "line_of_work": "resumed",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brought_over_from": str(folder),
    }


def step_reason(step: str) -> str:
    """The reason naming the failed *step*; git's own text is never part of it."""
    return f"the step {step!r} failed (git's own message is on stderr)"


def _git_steps(repo_root: Path, hub: str, branch: str, target: Path) -> str | None:
    """Clone the main checkout to *target*, point it at the hub, check the legacy line out; a reason, or ``None``.

    The legacy line is fetched from the main checkout after the pruning hub
    fetch, because a local-only line has no hub ref (A1).
    """
    refusal = wst.clone_main_checkout(repo_root, target)
    if refusal is None:
        _status, refusal = wst.sync_with_hub(hub, target, False)
    if refusal is not None:
        return step_reason(str(refusal.get("step", "clone")))
    for step, cmd in (("fetch-line", ["fetch", str(repo_root), f"+refs/heads/{branch}:refs/heads/{branch}"]),
                      ("checkout", ["checkout", "-f", branch])):
        proc = wg.run_git(cmd, target)
        if proc.returncode != 0:
            _log.warning("_git_steps: %s failed in %s: %s", step, target, proc.stderr.strip())
            return step_reason(step)
    if wg.run_git(["rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}"], target).returncode == 0:
        wg.run_git(["branch", f"--set-upstream-to=origin/{branch}"], target)
    return None


def build_clone(repo_root: Path, hub: str, folder: Path, branch: str, ident: wi.Identity, target: Path,
                before: dict[str, Any], carried: list[str]) -> str | None:
    """Make the marker-bearing clone at *target*; a reason it could not be proved lossless, else ``None``.

    On any reason the half-made clone is discarded (it is only ever a copy).
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        reason = _git_steps(repo_root, hub, branch, target)
        if reason is None:
            _carry(folder, target, set(before["paths"]), carried)
            reason = _lossless(target, before)
        if reason is None:
            wg.write_marker(target, _marker(repo_root, hub, folder, branch, ident, target))
    except OSError as exc:
        _log.warning("build_clone: %s", exc)
        reason = f"file operation failed: {exc}"
    if reason is not None:
        wrm.delete_whole_folder(target)
        if not any(target.parent.iterdir()):
            target.parent.rmdir()
    return reason
