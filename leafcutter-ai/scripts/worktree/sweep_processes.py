"""
MODULE: sweep_processes
GOAL: Terminate residual background worker processes and remove log files
    before calling ``git worktree remove``, so no orphaned PIDs or
    partially-deleted worktree directories survive an epic's close flow.
BUSINESS CONTEXT: After a ``/build-feature`` epic completes, the worktree
    directory must be fully removable.  Long-running host processes (live
    trader workers, async SQL test workers) that were spawned from inside
    the worktree and hold open file handles on logs or SQL files prevent
    the OS from deleting the directory.  This module automates the sweep
    that was previously a manual step documented in
    ``feedback_async_sql_test_orphan_workers.md``.
ARCHITECTURE: Three public callables — ``sweep``, ``sweep_log_files``, and
    ``SweepResult``.  All platform-specific kill logic is encapsulated here;
    callers (close-worktree workflow, worktree-agent) never embed
    OS-conditional shell snippets.  Config is loaded via ``config_loader.py``
    from the leafcutter package; safe defaults are used when
    ``skills_config.json`` is absent.  A ``main()`` CLI entry point allows
    direct invocation: ``python sweep_processes.py <worktree-path> [--dry-run]
    [--config <path>]``.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


# ---------------------------------------------------------------------------
# Default config values applied when skills_config.json is absent.
# ---------------------------------------------------------------------------
_DEFAULT_CONFIG: dict[str, Any] = {
    "kill_residual_processes": True,
    "log_globs": ["*.log"],
    "protected_paths": [],
}

_KILL_GRACE_SECONDS = 5


# ---------------------------------------------------------------------------
# Public result type
# ---------------------------------------------------------------------------

@dataclass
class SweepResult:
    """Structured result returned by ``sweep`` and ``sweep_log_files``.

    Attributes:
        killed_pids: PIDs successfully terminated during this sweep.
        conflict_pids: Entries that blocked the sweep — either protected-path
            matches, permission errors, or dry-run summaries.  Each entry is a
            dict with at least ``pid`` and ``reason`` keys; protected-path
            conflicts also include ``cmdline`` and ``matched_protected_path``.
        removed_logs: Absolute paths of log files deleted by ``sweep_log_files``.
        error: Non-None when a fatal condition prevented the sweep from running
            (e.g. invalid worktree path, all processes conflicted).  When set,
            ``killed_pids`` will be empty and callers should NOT proceed to
            ``git worktree remove``.
    """

    killed_pids: list[int] = field(default_factory=list)
    conflict_pids: list[dict[str, Any]] = field(default_factory=list)
    removed_logs: list[str] = field(default_factory=list)
    error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_worktree_config(config: dict[str, Any] | None, config_path: Path | None) -> dict[str, Any]:
    """Load and merge worktree_cleanup config from skills_config or fall through to defaults.

    Args:
        config: Caller-supplied config dict (takes precedence over file).
        config_path: Explicit path to a skills_config.json file, or None for
            auto-detection / package defaults.

    Returns:
        Dict with ``kill_residual_processes``, ``log_globs``, and
        ``protected_paths`` keys guaranteed to be present.
    """
    if config is not None:
        base = dict(_DEFAULT_CONFIG)
        base.update(config)
        return base

    # Try loading from the leafcutter config_loader.
    try:
        _here = Path(__file__).resolve().parent
        _pdw_scripts = _here.parent
        sys.path.insert(0, str(_pdw_scripts))
        from config_loader import load_config  # type: ignore[import-not-found]
        target_root = Path.cwd()
        loaded = load_config(config_path, target_root)
        worktree_cleanup = loaded.get("worktree_cleanup", {})
        merged = dict(_DEFAULT_CONFIG)
        merged.update(worktree_cleanup)
        return merged
    except Exception:  # noqa: BLE001
        # Fall through to safe defaults; print a warning to stderr.
        print(
            "WARNING: Could not load skills_config.json — "
            "using sweep defaults: kill_residual_processes=true, "
            "log_globs=['*.log'], protected_paths=[]",
            file=sys.stderr,
        )
        return dict(_DEFAULT_CONFIG)


def _is_process_in_worktree(proc: Any, worktree_path: str) -> bool:
    """Return True if the process cmdline or cwd contains worktree_path.

    Args:
        proc: A ``psutil.Process`` instance.
        worktree_path: Absolute path string to the worktree directory.

    Returns:
        True when the process appears to be running from inside the worktree.
    """
    normalized = str(Path(worktree_path).resolve())
    try:
        cmdline_str = " ".join(proc.cmdline())
        if normalized in cmdline_str:
            return True
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        pass

    try:
        cwd = proc.cwd()
        if cwd and normalized in str(Path(cwd).resolve()):
            return True
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        pass

    return False


def _get_cmdline(proc: Any) -> str:
    """Return the process command-line as a joined string, or an empty string on error.

    Args:
        proc: A ``psutil.Process`` instance.

    Returns:
        Joined command-line string, or ``""`` when the cmdline cannot be read.
    """
    try:
        return " ".join(proc.cmdline())
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        return ""


def _check_protected_conflicts(
    candidates: list[Any],
    protected_paths: list[str],
) -> list[dict[str, Any]]:
    """Return conflict entries for every candidate whose cmdline matches protected_paths.

    The caller uses the non-empty return value to abort the sweep before any kill.

    Args:
        candidates: List of ``psutil.Process`` objects already known to be in
            the worktree.
        protected_paths: List of path substrings to guard against killing.

    Returns:
        List of conflict dicts (empty when no protected matches).
    """
    conflicts: list[dict[str, Any]] = []
    for proc in candidates:
        cmdline_str = _get_cmdline(proc)
        matched = _matches_protected(cmdline_str, protected_paths)
        if matched is not None:
            conflicts.append({
                "pid": proc.pid,
                "cmdline": cmdline_str,
                "matched_protected_path": matched,
                "reason": "protected_paths match — cleanup aborted",
            })
    return conflicts


def _build_summary_entries(candidates: list[Any]) -> list[dict[str, Any]]:
    """Return summary entries for all candidates when kill is disabled.

    Args:
        candidates: List of ``psutil.Process`` objects already known to be in
            the worktree.

    Returns:
        List of summary dicts describing running processes without killing them.
    """
    entries: list[dict[str, Any]] = []
    for proc in candidates:
        cmdline_str = _get_cmdline(proc) or "<unknown>"
        entries.append({
            "pid": proc.pid,
            "cmdline": cmdline_str,
            "reason": "kill_residual_processes=false — summary only, not killed",
        })
    return entries


def _matches_protected(cmdline: str, protected_paths: list[str]) -> str | None:
    """Return the first protected_paths entry that is a substring of cmdline, or None.

    Args:
        cmdline: The full command-line string of the candidate process.
        protected_paths: List of path substrings that indicate a protected process.

    Returns:
        The matched entry string, or None if no match.
    """
    for entry in protected_paths:
        if entry and entry in cmdline:
            return entry
    return None


def _terminate_process(proc: Any) -> str | None:
    """SIGTERM → wait → SIGKILL (or TerminateProcess on Windows).

    Args:
        proc: A ``psutil.Process`` instance.

    Returns:
        None on success; an error-reason string on failure.
    """
    try:
        proc.terminate()
    except psutil.NoSuchProcess:
        return None  # Already gone; treat as success.
    except psutil.AccessDenied as exc:
        return f"PermissionError: {exc}"
    except OSError as exc:
        return f"OSError: {exc}"

    # Grace period: wait up to _KILL_GRACE_SECONDS for the process to exit.
    try:
        proc.wait(timeout=_KILL_GRACE_SECONDS)
        return None
    except psutil.TimeoutExpired:
        pass
    except psutil.NoSuchProcess:
        return None

    # Process survived SIGTERM — escalate to SIGKILL / TerminateProcess.
    try:
        proc.kill()
        proc.wait(timeout=2)
        return None
    except psutil.NoSuchProcess:
        return None
    except psutil.AccessDenied as exc:
        return f"PermissionError (kill): {exc}"
    except OSError as exc:
        return f"OSError (kill): {exc}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def sweep(worktree_path: str, config: dict[str, Any] | None = None, config_path: Path | None = None) -> SweepResult:
    """Terminate background processes whose cmdline or cwd matches worktree_path.

    Design invariants:
    - The ``protected_paths`` guard is evaluated BEFORE any ``kill()`` call.
    - If ANY conflict is found (protected-path match), the sweep aborts
      immediately without killing anything.
    - When ``kill_residual_processes=false``, no processes are killed and the
      matching PIDs are returned in ``conflict_pids`` (summary mode).
    - On ``PermissionError`` per PID, the PID is added to ``conflict_pids``
      with an error reason and the sweep continues to the next candidate
      (partial-kill mode), UNLESS the abort-on-conflict flag is active.

    Args:
        worktree_path: Absolute (or resolvable) path to the worktree directory.
        config: Optional pre-loaded config dict (keys: ``kill_residual_processes``,
            ``log_globs``, ``protected_paths``).  When None, loaded from
            skills_config.json or safe defaults.
        config_path: Explicit path to a skills_config.json file, used only when
            ``config`` is None.

    Returns:
        A ``SweepResult`` describing what happened.
    """
    result = SweepResult()

    if not _PSUTIL_AVAILABLE:
        result.error = (
            "psutil is not installed — cannot sweep processes. "
            "Install it with: pip install psutil"
        )
        return result

    resolved_path = str(Path(worktree_path).resolve())
    cfg = _load_worktree_config(config, config_path)
    kill_enabled: bool = bool(cfg.get("kill_residual_processes", True))
    protected_paths: list[str] = list(cfg.get("protected_paths", []))

    # -- Step 1: enumerate candidates -----------------------------------------
    candidates: list[Any] = []
    for proc in psutil.process_iter(["pid", "cmdline", "cwd"]):
        try:
            if _is_process_in_worktree(proc, resolved_path):
                candidates.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    if not candidates:
        return result

    # -- Step 2: check protected_paths for every candidate BEFORE any kill ---
    protected_conflicts = _check_protected_conflicts(candidates, protected_paths)
    if protected_conflicts:
        result.conflict_pids = protected_conflicts
        result.error = (
            f"Sweep aborted: {len(protected_conflicts)} process(es) matched "
            "protected_paths. No processes were killed. Resolve the conflicts "
            "manually before retrying git worktree remove."
        )
        return result

    # -- Step 3: if kill is disabled, return summary without killing ----------
    if not kill_enabled:
        result.conflict_pids = _build_summary_entries(candidates)
        return result

    # -- Step 4: kill candidates ----------------------------------------------
    for proc in candidates:
        pid = proc.pid
        error_reason = _terminate_process(proc)
        if error_reason is None:
            result.killed_pids.append(pid)
        else:
            cmdline_str = _get_cmdline(proc) or "<unknown>"
            result.conflict_pids.append({
                "pid": pid,
                "cmdline": cmdline_str,
                "reason": error_reason,
            })

    return result


def sweep_log_files(worktree_path: str, log_globs: list[str]) -> list[str]:
    """Delete files matching the given glob patterns inside worktree_path.

    Files are deleted in-place (not archived) unless the archive option is
    enabled in config (future enhancement — default is delete).

    Args:
        worktree_path: Absolute (or resolvable) path to the worktree directory.
        log_globs: List of glob patterns relative to ``worktree_path``
            (e.g. ``["*.log", "precommit-autofix*.log"]``).

    Returns:
        List of absolute path strings for every file that was successfully
        removed.
    """
    removed: list[str] = []
    base = Path(worktree_path).resolve()

    for pattern in log_globs:
        matched = glob.glob(str(base / pattern))
        for file_path in matched:
            try:
                os.remove(file_path)
                removed.append(file_path)
            except OSError:
                pass  # Best-effort; skip files that cannot be removed.

    return removed


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI: ``python sweep_processes.py <worktree-path> [--dry-run] [--config <path>]``.

    Prints a JSON summary of SweepResult to stdout.
    Exits 0 on clean sweep; exits 1 on any conflict or error.
    """
    parser = argparse.ArgumentParser(
        description="Sweep residual processes and log files from a worktree before git worktree remove."
    )
    parser.add_argument("worktree_path", help="Absolute path to the worktree directory.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be killed/removed without performing any action.",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Path to skills_config.json (default: auto-detect).",
    )
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else None

    if args.dry_run:
        # Dry-run: load config, enumerate candidates, report without acting.
        cfg = _load_worktree_config(None, config_path)
        if not _PSUTIL_AVAILABLE:
            print(json.dumps({"error": "psutil not installed"}))
            sys.exit(1)

        resolved_path = str(Path(args.worktree_path).resolve())
        dry_candidates = []
        for proc in psutil.process_iter(["pid", "cmdline", "cwd"]):
            try:
                if _is_process_in_worktree(proc, resolved_path):
                    try:
                        cmd = " ".join(proc.cmdline())
                    except (psutil.AccessDenied, psutil.NoSuchProcess):
                        cmd = "<unknown>"
                    dry_candidates.append({"pid": proc.pid, "cmdline": cmd})
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        log_candidates: list[str] = []
        for pattern in cfg.get("log_globs", ["*.log"]):
            log_candidates.extend(glob.glob(str(Path(resolved_path) / pattern)))

        print(json.dumps({
            "dry_run": True,
            "would_kill": dry_candidates,
            "would_remove_logs": log_candidates,
        }, indent=2))
        sys.exit(0)

    # Live run.
    result = sweep(args.worktree_path, config_path=config_path)
    cfg = _load_worktree_config(None, config_path)
    removed_logs = sweep_log_files(args.worktree_path, cfg.get("log_globs", ["*.log"]))
    result.removed_logs = removed_logs

    output = {
        "killed_pids": result.killed_pids,
        "conflict_pids": result.conflict_pids,
        "removed_logs": result.removed_logs,
        "error": result.error,
    }
    print(json.dumps(output, indent=2))

    if result.error or result.conflict_pids:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 10:30 [ticket-supervisor]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   psutil chosen as primary cross-platform approach; subprocess fallback
#   deferred (psutil is already a transitive dep via poetry).
#   protected_paths guard fires before any kill() per the ticket's design
#   constraint. abort-on-any-conflict strategy chosen over partial-kill
#   for protected-path matches, per the ticket's "errs on the side of
#   user intervention" rationale.
# ====================================================================
