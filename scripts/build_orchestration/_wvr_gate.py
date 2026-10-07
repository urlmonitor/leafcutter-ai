"""
MODULE: scripts/build_orchestration/_wvr_gate.py
GOAL: The gate files of the wrong-version runner: the copies of the code as
    written, the apply / put-back journal, and the recovery that puts a cut-short
    run's code back.
BUSINESS CONTEXT: TQ-500g-1-iii. A wrong version is applied to the working tree
    for the length of one pytest run. A run that dies with the wrong version on
    disk would let the next step commit it as the fix, so every alteration is
    journalled BEFORE the file is touched, every put-back is byte-compared with
    the copy, and a later invocation finds the copy and finishes the job.
ARCHITECTURE: Everything lives under ``<git-dir>/leafcutter/wrong-version-runs/
    <run-id>/`` (``git rev-parse --absolute-git-dir``): per worktree, outside the
    working tree, so ``git status`` never sees it and it survives a crash. A run
    directory holds the as-written copies plus ``journal.json``. Nothing here
    uses the shared stash, ``git checkout`` or ``git restore``. Correctness never
    depends on POSIX signals: a hard kill leaves the journal open and
    :func:`recover_all` closes it on the next invocation. The journal and every
    file write go through :func:`atomic_write_bytes` (temp file, fsync, atomic
    replace), so a kill never leaves a half-written file.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

_LOG = logging.getLogger("wrong_version_runner")
JOURNAL_NAME = "journal.json"
CLOSED_NAME = "journal.done"
_REPLACE_TRIES = 3


class GateError(Exception):
    """A gate-file operation failed in a way the caller must report."""


def git_text(cwd: Path, *args: str) -> str:
    """Run a read-only git command in *cwd* and return its stdout.

    Args:
        cwd: Directory to run git in.
        *args: The git arguments.

    Returns:
        Stripped stdout.

    Raises:
        GateError: When git cannot run or exits non-zero.
    """
    try:
        proc = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        msg = f"git {' '.join(args)} could not run: {exc}"
        raise GateError(msg) from exc
    if proc.returncode != 0:
        msg = f"git {' '.join(args)} failed: {proc.stderr.strip()[:300]}"
        raise GateError(msg)
    return proc.stdout.strip()


def gate_root(cwd: Path) -> Path:
    """Return ``<git-dir>/leafcutter/wrong-version-runs`` for the worktree at *cwd*.

    Args:
        cwd: Any directory inside the worktree.

    Returns:
        The (possibly not yet existing) gate directory, absolute.
    """
    git_dir = git_text(cwd, "rev-parse", "--absolute-git-dir")
    return Path(git_dir) / "leafcutter" / "wrong-version-runs"


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write *data* to *path* through a sibling temp file and an atomic replace.

    Args:
        path: Target file.
        data: Full new content.

    Raises:
        OSError: When the temp file cannot be written or the replace fails
            (for example the target is a directory or is locked).
    """
    tmp = path.with_name(f".{path.name}.wvr-tmp")
    try:
        with open(tmp, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        if path.exists():
            shutil.copymode(path, tmp)
        for attempt in range(_REPLACE_TRIES):
            try:
                os.replace(tmp, path)
            except PermissionError:
                if attempt == _REPLACE_TRIES - 1:
                    raise
                time.sleep(0.1)
            else:
                return
    finally:
        try:
            tmp.unlink()
        except OSError:
            pass


def _read_or_none(path: Path) -> bytes | None:
    """Return *path*'s bytes; ``None`` ONLY when it does not exist (FileNotFoundError).

    Any other OSError (permissions, a directory, a lock) propagates: an unreadable file
    is never treated as absent.
    """
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None


@dataclass
class RestoreResult:
    """What a put-back or recovery did.

    Attributes:
        restored: Absolute paths of files that differed from their copy and were put back.
        failures: One message per file that still differs; each names the copy.
        copy_dir: The run directory holding a kept copy when *failures* is non-empty.
    """

    restored: list[str] = field(default_factory=list)
    failures: list[str] = field(default_factory=list)
    copy_dir: str | None = None

    @property
    def ok(self) -> bool:
        """True when every open file now equals its copy."""
        return not self.failures


class RunGate:
    """One run's directory of copies and its journal."""

    def __init__(self, root: Path, run_dir: Path) -> None:
        self.root = root
        self.run_dir = run_dir
        self.entries: list[dict] = []

    def _write_journal(self) -> None:
        self.run_dir.mkdir(parents=True, exist_ok=True)
        payload = {"root": str(self.root), "entries": self.entries}
        atomic_write_bytes(self.run_dir / JOURNAL_NAME, json.dumps(payload).encode("utf-8"))

    def _missing_dirs(self, target: Path) -> list[str]:
        """Return the not-yet-existing ancestors of *target* inside the root, outermost first."""
        missing: list[str] = []
        parent = target.parent
        while parent != self.root and not parent.exists() and self.root in parent.parents:
            missing.append(parent.relative_to(self.root).as_posix())
            parent = parent.parent
        return missing[::-1]

    def apply(self, wrong_version: str, files: dict[str, bytes]) -> None:
        """Copy, journal, then alter each file in *files* (relative path to new bytes).

        The copy is written and read back, and the journal entry (including any directory
        the alteration will create) is made durable, BEFORE the working file is altered.

        Args:
            wrong_version: The wrong version being applied (recorded in the journal).
            files: ``{repo-relative POSIX path: altered bytes}``.

        Raises:
            GateError: When a file cannot be read, or a copy or the journal cannot be
                written (nothing altered).
            OSError: When the working file cannot be written (the journal stays open,
                so the caller's put-back still runs).
        """
        planned: list[tuple[dict, Path, bytes]] = []
        try:
            self.run_dir.mkdir(parents=True, exist_ok=True)
            for index, (rel, altered) in enumerate(files.items()):
                target = self.root / rel
                as_written = _read_or_none(target)
                copy_name = None
                if as_written is not None:
                    copy_name = f"copy-{len(self.entries) + index}-{target.name}"
                    atomic_write_bytes(self.run_dir / copy_name, as_written)
                    if _read_or_none(self.run_dir / copy_name) != as_written:
                        msg = f"the copy of {rel} does not match the file"
                        raise GateError(msg)
                entry = {"path": rel, "copy": copy_name, "wrong_version": wrong_version,
                         "dirs": self._missing_dirs(target)}
                planned.append((entry, target, altered))
            self.entries.extend(entry for entry, _t, _a in planned)
            self._write_journal()
        except OSError as exc:
            msg = f"gate files could not be written: {exc}"
            raise GateError(msg) from exc
        for _entry, target, altered in planned:
            target.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_bytes(target, altered)

    def restore(self) -> RestoreResult:
        """Put every open file back from its copy, byte-compare, close the journal, then clear.

        Returns:
            The :class:`RestoreResult`; on failure the copies and the journal are kept.
        """
        result = restore_entries(self.root, self.run_dir, self.entries)
        if result.ok:
            try:
                close_journal(self.run_dir)
            except OSError as exc:
                result.failures.append(_journal_failure(self.run_dir, exc))
                result.copy_dir = str(self.run_dir)
                return result
            self.entries = []
            clear_run_dir(self.run_dir)
        return result


def close_journal(run_dir: Path) -> None:
    """Close a run's journal durably (rename to ``journal.done``) before any copy is removed.

    Raises:
        OSError: When the journal exists but cannot be closed (the caller fails loudly).
    """
    try:
        os.replace(run_dir / JOURNAL_NAME, run_dir / CLOSED_NAME)
    except FileNotFoundError:
        return


def _journal_failure(run_dir: Path, exc: Exception) -> str:
    """Stop message for a journal that cannot be closed (the copies are kept)."""
    return f"the code may still be altered: the journal in {run_dir} could not be closed ({exc}); the copies are kept there"


def _entry_failure(run_dir: Path, entry: dict, why: str) -> str:
    """Build the stop message for one file that may still be altered."""
    copy = entry.get("copy")
    kept = str(run_dir / copy) if copy else str(run_dir)
    return (
        f"the code may still be altered: {entry['path']} {why}; "
        f"the copy of the code as written is kept at {kept}"
    )


def _matches_head(root: Path, rel: str, target_bytes: bytes | None) -> bool:
    """Return whether the target already equals its HEAD blob (a clean state, nothing to put back)."""
    try:
        proc = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=root, capture_output=True, timeout=60, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return proc.returncode == 0 and target_bytes is not None and proc.stdout == target_bytes


def _sweep_temp(target: Path) -> None:
    """Remove a stray ``.<name>.wvr-tmp`` a hard kill left next to *target*."""
    try:
        target.with_name(f".{target.name}.wvr-tmp").unlink()
    except FileNotFoundError:
        return
    except OSError as exc:
        _LOG.warning("stray temp file next to %s could not be removed: %s", target, exc)


def _remove_created_dirs(root: Path, entry: dict) -> None:
    """Remove the directories the alteration created (deepest first), if they are empty."""
    for rel in reversed(entry.get("dirs") or []):
        try:
            (root / rel).rmdir()
        except FileNotFoundError:
            continue
        except OSError as exc:
            _LOG.warning("created directory %s was not removed: %s", rel, exc)


def _restore_one(root: Path, run_dir: Path, entry: dict, result: RestoreResult) -> None:
    """Restore one journal entry's file, verify it, and record the outcome in *result*."""
    target = root / entry["path"]
    copy = entry.get("copy")
    try:
        wanted = _read_or_none(run_dir / copy) if copy else None
        _sweep_temp(target)
        current = _read_or_none(target)
        if copy and wanted is None:
            if _matches_head(root, entry["path"], current):
                return
            result.failures.append(_entry_failure(run_dir, entry, "has no readable copy to compare with"))
            return
        if current != wanted:
            if wanted is None:
                target.unlink()
            else:
                atomic_write_bytes(target, wanted)
            if _read_or_none(target) != wanted:
                result.failures.append(_entry_failure(run_dir, entry, "still differs from its copy after the put-back"))
                return
            result.restored.append(str(target))
        _remove_created_dirs(root, entry)
    except OSError as exc:
        _LOG.warning("put-back of %s failed: %s", target, exc)
        result.failures.append(_entry_failure(run_dir, entry, f"could not be put back or read ({exc})"))


def restore_entries(root: Path, run_dir: Path, entries: list[dict]) -> RestoreResult:
    """Restore each journal entry whose file differs from its copy and verify it.

    Args:
        root: The worktree root the entries' paths are relative to.
        run_dir: The run directory holding the copies.
        entries: Open journal entries (``path``, ``copy``, ``dirs``).

    Returns:
        The :class:`RestoreResult`.
    """
    result = RestoreResult()
    for entry in entries:
        _restore_one(root, run_dir, entry, result)
    if result.failures:
        result.copy_dir = str(run_dir)
    return result


def clear_run_dir(run_dir: Path) -> None:
    """Remove a CLOSED run directory's copies (best effort; the journal is already closed)."""
    shutil.rmtree(run_dir, ignore_errors=True)


def _sweep_closed(run_dir: Path) -> None:
    """Sweep stray temp files named by a closed run, then clear it (best effort)."""
    try:
        data = json.loads((run_dir / CLOSED_NAME).read_text(encoding="utf-8"))
        for entry in data["entries"]:
            _sweep_temp(Path(data["root"]) / entry["path"])
    except (OSError, ValueError, KeyError, TypeError) as exc:
        _LOG.warning("closed run %s could not be swept: %s", run_dir, exc)
    clear_run_dir(run_dir)


def recover_all(gate_dir: Path) -> RestoreResult:
    """Close every open journal under *gate_dir* (the recovery step).

    A run directory without ``journal.json`` is CLOSED: its files are never restored
    (a developer may have edited the code since), only swept and removed best-effort.

    Args:
        gate_dir: ``<git-dir>/leafcutter/wrong-version-runs``.

    Returns:
        The combined :class:`RestoreResult`. A journal that cannot be read counts as
        a failure, never as nothing to do.
    """
    total = RestoreResult()
    if not gate_dir.is_dir():
        return total
    for run_dir in sorted(p for p in gate_dir.iterdir() if p.is_dir()):
        journal = run_dir / JOURNAL_NAME
        if not journal.exists():
            if (run_dir / CLOSED_NAME).exists():
                _sweep_closed(run_dir)
            elif not any(run_dir.iterdir()):
                clear_run_dir(run_dir)
            continue
        try:
            data = json.loads(journal.read_text(encoding="utf-8"))
            root = Path(data["root"])
            entries = list(data["entries"])
        except (OSError, ValueError, KeyError, TypeError) as exc:
            total.failures.append(f"the code may still be altered: journal {journal} is unreadable ({exc}); copies kept in {run_dir}")
            total.copy_dir = str(run_dir)
            continue
        part = restore_entries(root, run_dir, entries)
        total.restored.extend(part.restored)
        total.failures.extend(part.failures)
        if not part.ok:
            total.copy_dir = part.copy_dir
            continue
        try:
            close_journal(run_dir)
        except OSError as exc:
            total.failures.append(_journal_failure(run_dir, exc))
            total.copy_dir = str(run_dir)
            continue
        clear_run_dir(run_dir)
    return total
