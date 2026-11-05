"""
MODULE: worktree_ensure_state
GOAL: Make asking for a workspace again always safe (BO-4300d-1, d-1-i, d-1-ii,
    d-2, d-2-i, d-2-ii, d-2-iii): one request at a time per piece of work, a
    healthy workspace re-readied without touching the work in it, and a
    half-made one finished in place.
BUSINESS CONTEXT: Callers (agents, scripts, people) retry. A retry must never
    produce a second workspace, overwrite a change the work made to a file the
    set-up also rewrites, wipe a folder in which work has since been done, or
    be answered "ready" while any part of readiness is missing. The decisions
    live here so worktree.py (at the file-size ratchet) only wires them in.
ARCHITECTURE: Stdlib-only, deployed beside worktree.py (NAMED entry in the
    build deploy manifest). Five groups: (1) ``ensure_lock`` -- an exclusively
    created lock file per (project, work identity) OUTSIDE the workspace folder
    holding pid, host and start time, a dead holder reclaimed, a bounded wait
    then IN_PROGRESS; (2) ``work_set_aside`` -- the work's uncommitted changes
    to tracked files are copied to ``<ws>/.leafcutter/rescue`` and set aside
    for the set-up (so the build and the canaries run on a clean tree) and put
    back byte for byte afterwards; a leftover rescue folder (a request killed
    in the window) refuses WORK_AT_RISK naming the files; (3) the folder
    state helpers (``empty_folder``, ``checked_out``, ``clear_torn_markers``);
    (4) the not-ready guards for ``verify`` and ``locate``; (5) the abort-only
    TEST SEAM ``LEAFCUTTER_WORKSPACE_ABORT_AT`` (after_clone | after_branch |
    after_install | during_marker): it can only end the process at that stage
    -- it never skips a step and never yields an ok answer. A folder is never
    deleted to be finished: a half-made one is always completed in place.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import logging
import os
import socket
import sys
import time
from pathlib import Path
from typing import Any, Iterator

import worktree_answer as wa
import worktree_git as wg
import worktree_readiness as wr

_log = logging.getLogger(__name__)

ABORT_ENV = "LEAFCUTTER_WORKSPACE_ABORT_AT"
ABORT_STAGES = ("after_clone", "after_branch", "after_install", "during_marker")
_ABORT_EXIT = 75
LOCK_WAIT_ENV = "LEAFCUTTER_WORKSPACE_LOCK_WAIT"
_DEFAULT_LOCK_WAIT = 30.0
_LOCK_DIR = ".leafcutter-locks"
_FOREIGN_STALE_SECONDS = 3600.0
_UNREADABLE_STALE_SECONDS = 10.0
_RESCUE = ("rescue", "manifest.json")
_CHUNK = 100


# ----------------------------------------------------------------- abort seam

def abort_if(stage: str) -> None:
    """End the process at once when the test seam names *stage*; otherwise do nothing.

    TEST SEAM: it can only abort (non-zero exit, no answer on stdout). It
    never skips a step and never produces an ok answer.
    """
    if os.environ.get(ABORT_ENV) == stage:
        sys.stderr.write(f"[worktree] test seam {ABORT_ENV}={stage}: aborting\n")
        sys.stderr.flush()
        os._exit(_ABORT_EXIT)


def arm_after_install() -> None:
    """For the ``after_install`` seam: abort right after the install's shims are in place."""
    if os.environ.get(ABORT_ENV) != "after_install":
        return
    original = wr.install_shims

    def _shims_then_abort(workspace: Path) -> None:
        original(workspace)
        abort_if("after_install")

    wr.install_shims = _shims_then_abort


def write_ready_marker(workspace: Path, marker: dict[str, Any]) -> None:
    """Record the workspace as ready, atomically; the ``during_marker`` seam stops mid-write.

    The seam leaves a half-written temp file beside the intact earlier marker
    and aborts, which is exactly what an interruption would leave: the
    complete old record, never a torn accepted one.
    """
    if os.environ.get(ABORT_ENV) == "during_marker":
        torn = wg.marker_path(workspace).parent / ".workspace-torn.json.tmp"
        torn.write_text(json.dumps(marker)[: len(json.dumps(marker)) // 2], encoding="utf-8")
        abort_if("during_marker")
    wg.write_marker(workspace, marker)


def clear_torn_markers(workspace: Path) -> None:
    """Remove the maker's own leftover half-written marker temp files in *workspace*."""
    folder = wg.marker_path(workspace).parent
    if not folder.is_dir():
        return
    for stray in folder.glob(".workspace-*.json.tmp"):
        with contextlib.suppress(OSError):
            stray.unlink()


# ----------------------------------------------------------------------- lock

def _pid_alive(pid: int) -> bool:
    """True when process *pid* exists on this host (never signals it)."""
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes  # noqa: PLC0415 - Windows-only
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ctypes.windll.kernel32.GetLastError() == 5  # access denied: it exists
        code = ctypes.c_ulong()
        ok = ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return bool(ok) and code.value == 259  # STILL_ACTIVE
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True
    return True


def _read_holder(path: Path) -> dict[str, Any] | None:
    """The lock's holder record (pid, host, started), or ``None`` when absent or unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("pid"), int) else None


def _holder_is_dead(path: Path) -> bool:
    """True when the lock at *path* was left by a holder that is gone."""
    holder = _read_holder(path)
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    if holder is None:
        return age > _UNREADABLE_STALE_SECONDS
    if holder.get("host") == socket.gethostname():
        return not _pid_alive(holder["pid"])
    return time.time() - float(holder.get("started") or time.time()) > _FOREIGN_STALE_SECONDS


def _reclaim(path: Path) -> None:
    """Take a dead holder's lock away by an atomic rename; put it back if it turns out to be live."""
    grave = path.with_name(f"{path.name}.stale-{os.getpid()}")
    try:
        os.replace(path, grave)
    except OSError:
        return  # someone else reclaimed (or released) it first
    if not _holder_is_dead(grave):
        with contextlib.suppress(OSError):
            os.link(grave, path)  # we grabbed a live holder's lock: give it back
    with contextlib.suppress(OSError):
        grave.unlink()


def _make_dirs(folder: Path) -> list[Path]:
    """Create *folder* and its missing parents; return the ones this call created, outermost first."""
    missing = []
    probe = folder
    while not probe.exists() and probe.parent != probe:
        missing.append(probe)
        probe = probe.parent
    with contextlib.suppress(OSError):
        folder.mkdir(parents=True, exist_ok=True)
    return list(reversed(missing))


def _try_create(path: Path) -> bool:
    """Create the lock file exclusively, stamped with pid, host and start time."""
    _make_dirs(path.parent)
    try:
        fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    except OSError as exc:  # parent vanished under us (a release raced) or unwritable
        _log.warning("_try_create: cannot create %s: %s", path, exc)
        return False
    record = {"pid": os.getpid(), "host": socket.gethostname(), "started": time.time()}
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(json.dumps(record))
    return True


def lock_path(place: Path, repo_root: Path, kind: str, slug: str) -> Path:
    """The lock file of one (project, work identity); lives beside the kind folders, never inside one."""
    key = hashlib.sha1(f"{str(repo_root.resolve()).lower()}|{kind}|{slug}".encode()).hexdigest()[:12]
    return place / _LOCK_DIR / f"{kind}-{slug}-{key}.lock"


def lock_wait_seconds() -> float:
    """How long a waiter waits for the holder (``LEAFCUTTER_WORKSPACE_LOCK_WAIT``, default 30 s)."""
    try:
        return max(0.0, float(os.environ.get(LOCK_WAIT_ENV, _DEFAULT_LOCK_WAIT)))
    except ValueError:
        return _DEFAULT_LOCK_WAIT


@contextlib.contextmanager
def ensure_lock(place: Path, repo_root: Path, kind: str, slug: str) -> Iterator[dict[str, Any] | None]:
    """Hold the one lock for this work; yield ``None`` when held, else the IN_PROGRESS refusal.

    A holder that is gone is reclaimed; a live one is waited for a bounded
    time (never indefinitely). The lock and any folder this call made for it
    are removed on exit.
    """
    path = lock_path(place, repo_root, kind, slug)
    created = _make_dirs(path.parent)
    deadline = time.monotonic() + lock_wait_seconds()
    held = False
    while not held:
        held = _try_create(path)
        if held:
            break
        if _holder_is_dead(path):
            _reclaim(path)
        elif time.monotonic() >= deadline:
            break
        else:
            time.sleep(0.2)
    try:
        if held:
            yield None
        else:
            yield wa.error_answer(
                "IN_PROGRESS", f"The same work ({kind}/{slug}) is already being prepared by another request; "
                "nothing was changed. Ask again shortly.", holder=_read_holder(path))
    finally:
        if held:
            with contextlib.suppress(OSError):
                path.unlink()
        for folder in reversed(created):
            with contextlib.suppress(OSError):
                folder.rmdir()


# ----------------------------------------------------- folder state helpers

def empty_folder(path: Path) -> bool:
    """True when *path* is an existing folder holding nothing at all."""
    try:
        return path.is_dir() and not any(path.iterdir())
    except OSError:
        return False


def checked_out(workspace: Path) -> bool:
    """True once the line of work has been checked out (the index holds files)."""
    proc = wg.run_git(["ls-files", "-z", "--cached"], workspace)
    return proc.returncode == 0 and bool(proc.stdout.strip("\0"))


def head_state(workspace: Path) -> tuple[str, str, str]:
    """``(branch, line_of_work, base_commit)`` read off a workspace whose line is already checked out."""
    branch = wg.run_git(["rev-parse", "--abbrev-ref", "HEAD"], workspace).stdout.strip()
    pushed = wg.run_git(["rev-parse", "--verify", "-q", f"origin/{branch}"], workspace).returncode == 0
    base = wg.run_git(["rev-parse", "origin/main"], workspace).stdout.strip()
    return branch, "resumed" if pushed else "new", base


# ----------------------------------------------------------------- set aside

def _rescue_dir(workspace: Path) -> Path:
    """Where the work's changes are copied while set aside (inside .leafcutter, outside version control)."""
    return wg.marker_path(workspace).parent / _RESCUE[0]


def rescue_refusal(workspace: Path) -> dict[str, Any] | None:
    """WORK_AT_RISK when an earlier request was killed while it held the work's changes aside."""
    manifest = _rescue_dir(workspace) / _RESCUE[1]
    if not manifest.is_file():
        return None
    try:
        files = json.loads(manifest.read_text(encoding="utf-8")).get("files", [])
    except (OSError, ValueError) as exc:
        _log.warning("rescue_refusal: unreadable %s: %s", manifest, exc)
        files = []
    return wa.error_answer(
        "WORK_AT_RISK", f"An earlier request was interrupted while it held the work's changes aside; "
        f"their copies are in {_rescue_dir(workspace)}. Put them back and delete that folder, then ask again. "
        "Nothing was changed.", unsent={"files": files, "rescue": str(_rescue_dir(workspace))})


def _chunks(items: list[str]) -> Iterator[list[str]]:
    """Yield *items* in command-line sized pieces."""
    for start in range(0, len(items), _CHUNK):
        yield items[start:start + _CHUNK]


def _read_or_none(path: Path) -> bytes | None:
    """The file's bytes, or ``None`` when it does not exist."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


def _save_rescue(workspace: Path, saved: dict[str, bytes | None]) -> None:
    """Copy each changed file into the rescue folder (bytes as they are) and write its manifest last."""
    folder = _rescue_dir(workspace)
    folder.mkdir(parents=True, exist_ok=True)
    for index, (rel, data) in enumerate(saved.items()):
        if data is not None:
            (folder / f"{index}.bin").write_bytes(data)
    (folder / _RESCUE[1]).write_text(json.dumps({"files": list(saved)}), encoding="utf-8")


def _remove_rescue(workspace: Path) -> None:
    """Delete the rescue folder after the changes are back in the tree (manifest first)."""
    folder = _rescue_dir(workspace)
    with contextlib.suppress(OSError):
        (folder / _RESCUE[1]).unlink()
    for leftover in folder.glob("*.bin"):
        with contextlib.suppress(OSError):
            leftover.unlink()
    with contextlib.suppress(OSError):
        folder.rmdir()


def _put_back(workspace: Path, saved: dict[str, bytes | None], staged: list[str]) -> None:
    """Write every saved file back byte for byte (deleting what the work had deleted); re-stage what was staged."""
    for rel, data in saved.items():
        target = workspace / rel
        if data is None:
            target.unlink(missing_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    for piece in _chunks(staged):
        wg.run_git(["add", "-A", "--", *piece], workspace)


@contextlib.contextmanager
def work_set_aside(workspace: Path) -> Iterator[list[str]]:
    """Run the body on a tree free of the work's uncommitted tracked changes, then put them back exactly.

    The changes (including staged ones) are copied to ``.leafcutter/rescue``,
    unstaged, and the tracked files returned to HEAD so the build and the
    canaries run on a clean tree; on exit -- even after an error -- every
    changed file is written back byte for byte and re-staged if it was. The
    rescue copy is deleted only after that succeeded. Untracked files are never
    touched.
    """
    changed = wr.tracked_changes(workspace)
    if not changed:
        yield []
        return
    saved = {rel: _read_or_none(workspace / rel) for rel in changed}
    cached = wg.run_git(["diff", "--cached", "--name-only", "-z"], workspace).stdout.split("\0")
    staged = [rel for rel in changed if rel in set(cached)]
    _save_rescue(workspace, saved)
    in_head = set(wg.run_git(["ls-tree", "-r", "-z", "--name-only", "HEAD"], workspace).stdout.split("\0"))
    try:
        for piece in _chunks(changed):
            wg.run_git(["reset", "-q", "HEAD", "--", *piece], workspace)
        for piece in _chunks([rel for rel in changed if rel in in_head]):
            wg.run_git(["checkout", "HEAD", "--", *piece], workspace)
        yield changed
    finally:
        _put_back(workspace, saved, staged)
        _remove_rescue(workspace)


# ------------------------------------------------------------------- guards

def incomplete_refusal(workspace: Path, marker: dict[str, Any]) -> dict[str, Any]:
    """INCOMPLETE: a workspace whose marker is not 'ready' is never answered ok and carries no location."""
    return wa.error_answer(
        "INCOMPLETE", f"The workspace at {workspace} is only partly made (state {marker.get('state')!r}); "
        "ask for it again with ensure to finish it.", marker_state=marker.get("state"))


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-12 09:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
#   Created: BO-4300d-1/-i/-ii and d-2/-i/-ii/-iii. Lock per (project, work)
#   outside the workspace; the work's uncommitted tracked changes are set
#   aside (copied to .leafcutter/rescue) around the set-up and put back byte
#   for byte, so a re-ready or a completion never overwrites them and never
#   deletes the folder. The after_install seam wraps wr.install_shims because
#   worktree_readiness is not this ticket's file. (ADR-018)
# ===========================================================================
