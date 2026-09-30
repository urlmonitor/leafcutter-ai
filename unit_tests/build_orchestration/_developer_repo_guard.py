"""
MODULE: unit_tests/build_orchestration/_developer_repo_guard.py
GOAL: Session-scoped guard that snapshots a developer repository's
    registered worktrees, refs/branches and local git config before the
    workspace proof suite runs, and fails the session on any difference
    found afterwards -- BO-4300f-4-i's "any difference fails the session".
BUSINESS CONTEXT: ADR-051 decided this guard holds a session-exclusive
    advisory lock on the developer repository for the whole snapshot-to-
    compare window, instead of narrowing its diff, because filtering the
    diff to tell the suite's own leaks apart from a concurrent session's
    changes would silently weaken "any difference fails the session". The
    first attempt at this epic put an equivalent guard under scripts/,
    where it tripped scripts/build.py's own tracked-source guard for every
    other ticket's proof run -- this module lives in test support instead
    (ADR-051 decision 7).
ARCHITECTURE: Stdlib-only (contextlib, dataclasses, logging, os, subprocess,
    sys, time, pathlib; msvcrt on Windows, fcntl on POSIX). The lock file is
    ``<git-common-dir>/bo4300-proof-suite.lock`` so linked worktrees of the
    same repository contend on the same file (ADR-051 decision 1). The
    guard's own snapshot commands run WITHOUT the isolated-git-identity
    overrides other fixtures use, because the real developer repository's
    real config is what this guard measures (ADR-051 decision 6).

NOT a test file itself (leading underscore). Nothing in here is collected
by pytest.

DECISION HISTORY
====================================================================
- 2026-09-28 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02,
  BO-4300f-4-i]: Created this module implementing ADR-051's session-
  exclusive lock (msvcrt/fcntl, bounded timeout,
  DeveloperRepoLockTimeoutError distinct from DeveloperRepoChangedError),
  the unfiltered global snapshot/diff pair, and the developer_repo_guard
  context manager. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02) (ADR-051)
====================================================================
"""
from __future__ import annotations

import contextlib
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_log = logging.getLogger(__name__)

_LOCK_FILE_NAME = "bo4300-proof-suite.lock"
_LOCK_POLL_INTERVAL_S = 0.1
_DEFAULT_LOCK_TIMEOUT_S = 600.0
_GIT_TIMEOUT_S = 60


class DeveloperRepoGuardError(Exception):
    """Base class for this guard's own errors (never raised directly)."""


class DeveloperRepoChangedError(DeveloperRepoGuardError):
    """The developer repository differs between the guard's before/after snapshots.

    Per ADR-051 decision 4, this is a DISTINCT failure from
    :class:`DeveloperRepoLockTimeoutError` -- a real leak, never a stuck
    concurrent session.
    """


class DeveloperRepoLockTimeoutError(DeveloperRepoGuardError):
    """The session-exclusive lock was not acquired within the timeout.

    Per ADR-051 decision 4, this MUST NOT subclass or be reported as
    :class:`DeveloperRepoChangedError` -- a stuck run is diagnosable
    separately from a real leak.
    """


@dataclass
class DeveloperRepoSnapshot:
    """Raw (never sorted/filtered) output of the three measured git commands."""

    worktrees: str
    refs: str
    config: str


def _run_git_real(args: list[str], cwd: Path) -> str:
    """Run ``git`` against the REAL developer repository, no fixture isolation."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT_S,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        _log.warning("_run_git_real: git %s failed in %s: %s", args, cwd, exc.stderr)
        raise
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("_run_git_real: could not launch git %s in %s: %s", args, cwd, exc)
        raise
    return proc.stdout


def snapshot_developer_repo(repo_root: Path) -> DeveloperRepoSnapshot:
    """Capture the developer repository's worktrees, refs and local config.

    Args:
        repo_root: Absolute path to the developer repository.

    Returns:
        A :class:`DeveloperRepoSnapshot` with the raw, unfiltered output of
        ``git worktree list --porcelain``, ``git for-each-ref`` and
        ``git config --local --list``.
    """
    repo_root = Path(repo_root)
    return DeveloperRepoSnapshot(
        worktrees=_run_git_real(["worktree", "list", "--porcelain"], repo_root),
        refs=_run_git_real(["for-each-ref"], repo_root),
        config=_run_git_real(["config", "--local", "--list"], repo_root),
    )


def _normalised_lines(text: str) -> set[str]:
    return {line for line in text.splitlines() if line.strip()}


def diff_snapshots(before: DeveloperRepoSnapshot, after: DeveloperRepoSnapshot) -> list[str]:
    """Return one entry per line-level difference between two snapshots.

    Both snapshots are normalised (split into lines, sorted via a set
    comparison) before comparing (ADR-051 decision 5) -- never filtered by
    path prefix, ref namespace or config key.

    Args:
        before: Snapshot taken before the guarded session.
        after: Snapshot taken after the guarded session.

    Returns:
        Empty list when identical; otherwise one human-readable entry per
        added or removed line, each naming which measured command it came
        from and the changed line itself.
    """
    diffs: list[str] = []
    for label, before_text, after_text in (
        ("worktree registrations", before.worktrees, after.worktrees),
        ("refs/branches", before.refs, after.refs),
        ("local git config", before.config, after.config),
    ):
        before_lines = _normalised_lines(before_text)
        after_lines = _normalised_lines(after_text)
        for line in sorted(after_lines - before_lines):
            diffs.append(f"{label}: added {line!r}")
        for line in sorted(before_lines - after_lines):
            diffs.append(f"{label}: removed {line!r}")
    return diffs


def _git_common_dir(repo_root: Path) -> Path:
    """Resolve *repo_root*'s ``git rev-parse --git-common-dir`` as an absolute path."""
    raw = _run_git_real(["rev-parse", "--git-common-dir"], repo_root).strip()
    common = Path(raw)
    if not common.is_absolute():
        common = (repo_root / common).resolve()
    return common


if sys.platform == "win32":
    import msvcrt

    def _lock_file(fh) -> None:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(fh) -> None:
        fh.seek(0)
        with contextlib.suppress(OSError):
            msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
else:
    import fcntl

    def _lock_file(fh) -> None:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    def _unlock_file(fh) -> None:
        with contextlib.suppress(OSError):
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)


def _lock_timeout_from_env() -> float:
    raw = os.environ.get("BO4300_GUARD_LOCK_TIMEOUT_S")
    if not raw:
        return _DEFAULT_LOCK_TIMEOUT_S
    try:
        return float(raw)
    except ValueError:
        _log.warning(
            "BO4300_GUARD_LOCK_TIMEOUT_S=%r is not a number; using default %s",
            raw, _DEFAULT_LOCK_TIMEOUT_S,
        )
        return _DEFAULT_LOCK_TIMEOUT_S


@contextlib.contextmanager
def _session_lock(repo_root: Path, timeout_s: float):
    """Hold a real OS advisory lock on *repo_root*'s proof-suite lock file.

    A real ``msvcrt``/``fcntl`` advisory lock, not a create-exclusive spin
    (ADR-051 decision 2) -- the kernel releases it automatically if this
    process dies, so a crashed run never leaves a lock that needs manual
    cleanup.
    """
    common_dir = _git_common_dir(repo_root)
    common_dir.mkdir(parents=True, exist_ok=True)
    lock_path = common_dir / _LOCK_FILE_NAME

    fh = open(lock_path, "a+b")  # noqa: SIM115 -- held across the whole session window
    try:
        fh.seek(0, os.SEEK_END)
        if fh.tell() == 0:
            fh.write(b"0")
            fh.flush()

        deadline = time.monotonic() + timeout_s
        acquired = False
        while not acquired:
            try:
                _lock_file(fh)
                acquired = True
            except OSError:
                if time.monotonic() >= deadline:
                    msg = (
                        f"timed out after {timeout_s}s waiting for the developer-repo "
                        f"proof-suite lock at {lock_path}"
                    )
                    raise DeveloperRepoLockTimeoutError(msg) from None
                time.sleep(_LOCK_POLL_INTERVAL_S)
        try:
            yield
        finally:
            _unlock_file(fh)
    finally:
        fh.close()


@contextlib.contextmanager
def developer_repo_guard(repo_root: Path, lock_timeout_s: float | None = None):
    """Session-scoped guard: lock, snapshot, run the guarded session, compare.

    Acquires ADR-051's session-exclusive advisory lock on *repo_root*,
    snapshots it, yields, then snapshots it again and raises
    :class:`DeveloperRepoChangedError` (never silently) if anything
    differs -- regardless of whether the guarded session itself raised.

    Args:
        repo_root: Absolute path to the developer repository to guard.
        lock_timeout_s: Overrides ``BO4300_GUARD_LOCK_TIMEOUT_S`` /
            the 600s default.

    Raises:
        DeveloperRepoLockTimeoutError: the lock was not acquired in time.
        DeveloperRepoChangedError: the repository changed during the session.
    """
    repo_root = Path(repo_root)
    timeout = lock_timeout_s if lock_timeout_s is not None else _lock_timeout_from_env()
    with _session_lock(repo_root, timeout):
        before = snapshot_developer_repo(repo_root)
        try:
            yield
        finally:
            after = snapshot_developer_repo(repo_root)
            diff = diff_snapshots(before, after)
            if diff:
                joined = "\n".join(f"  - {entry}" for entry in diff)
                msg = (
                    f"developer repository at {repo_root} changed during the "
                    f"workspace proof suite session:\n{joined}"
                )
                raise DeveloperRepoChangedError(msg)
