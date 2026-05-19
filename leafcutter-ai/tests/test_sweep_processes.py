"""
MODULE: test_sweep_processes
GOAL: Unit tests for leafcutter/scripts/worktree/sweep_processes.py.
BUSINESS CONTEXT: Validates that the process-sweep helper correctly terminates
    residual worker processes and removes log files before git worktree remove,
    preventing orphaned PIDs and partially-deleted worktree directories.
ARCHITECTURE: pytest-based unit tests using tmp_path and monkeypatch.  No
    database, no Docker, no file output to the project root.  All tests must
    complete in <= 5 seconds.  Platform-conditional skips guard tests that rely
    on OS-specific process detection when that detection is unavailable.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# Ensure the scripts package is importable when tests run from any cwd.
# ---------------------------------------------------------------------------
_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

# All tests must complete in <= 5 seconds (project convention).
# pytest-timeout is optional; tests are designed to be fast without it.

_PSUTIL_REQUIRED = pytest.mark.skipif(
    not _PSUTIL_AVAILABLE,
    reason="psutil not installed — process-detection tests skipped",
)


# ---------------------------------------------------------------------------
# Import the module under test (after path fixup above).
# ---------------------------------------------------------------------------
from worktree.sweep_processes import SweepResult, sweep, sweep_log_files  # noqa: E402


# ---------------------------------------------------------------------------
# Helper: spawn a background sleeping subprocess with its cwd inside tmp_path.
# ---------------------------------------------------------------------------

def _spawn_sleeping_child(tmp_path: Path, seconds: int = 60) -> "subprocess.Popen[bytes]":
    """Spawn a Python sleep subprocess with cwd=tmp_path.

    Args:
        tmp_path: Directory that becomes the subprocess's working directory.
        seconds: How many seconds the child should sleep before exiting.

    Returns:
        The ``subprocess.Popen`` handle.
    """
    import subprocess
    proc = subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({seconds})"],
        cwd=str(tmp_path),
    )
    # Give the OS a moment to register the process in the process table.
    time.sleep(0.1)
    return proc


# ===========================================================================
# test_sweep_result_shape
# ===========================================================================

def test_sweep_result_shape(tmp_path: Path) -> None:
    """SweepResult dataclass has all four required fields with correct defaults.

    Covers: ``test_sweep_result_shape`` from the Test Requirements table.
    Calls sweep() on an empty directory with no matching processes and asserts
    the result shape is correct.
    """
    result = sweep(str(tmp_path))

    assert hasattr(result, "killed_pids"), "SweepResult missing killed_pids"
    assert hasattr(result, "conflict_pids"), "SweepResult missing conflict_pids"
    assert hasattr(result, "removed_logs"), "SweepResult missing removed_logs"
    assert hasattr(result, "error"), "SweepResult missing error"

    assert result.killed_pids == [], f"Expected [], got {result.killed_pids!r}"
    assert result.conflict_pids == [], f"Expected [], got {result.conflict_pids!r}"
    assert result.removed_logs == [], f"Expected [], got {result.removed_logs!r}"
    assert result.error is None, f"Expected None, got {result.error!r}"


# ===========================================================================
# test_sweep_log_files_removes_globs
# ===========================================================================

def test_sweep_log_files_removes_globs(tmp_path: Path) -> None:
    """sweep_log_files() deletes all files matching configured globs inside tmp_path.

    Covers: ``test_sweep_log_files_removes_globs`` from the Test Requirements table.
    Creates test files matching ``*.log`` and ``precommit-autofix*.log`` patterns,
    calls sweep_log_files(), and asserts all created files are removed.
    """
    # Create files that should be swept.
    log1 = tmp_path / "worker.log"
    log2 = tmp_path / "precommit-autofix-20260513.log"
    log3 = tmp_path / "not_a_log.txt"  # Should NOT be removed.

    log1.write_text("log content 1")
    log2.write_text("log content 2")
    log3.write_text("not a log")

    removed = sweep_log_files(str(tmp_path), ["*.log", "precommit-autofix*.log"])

    # Both log files must be in the removed list.
    removed_names = {Path(p).name for p in removed}
    assert "worker.log" in removed_names, f"worker.log not in {removed_names!r}"
    assert "precommit-autofix-20260513.log" in removed_names, (
        f"precommit-autofix-20260513.log not in {removed_names!r}"
    )

    # The non-log file must NOT have been removed.
    assert log3.exists(), "not_a_log.txt was incorrectly removed"

    # The returned list must contain the absolute paths.
    assert len(removed) == 2, f"Expected 2 removed files, got {len(removed)}"

    # The actual files must be gone from disk.
    assert not log1.exists(), "worker.log still exists after sweep_log_files"
    assert not log2.exists(), (
        "precommit-autofix-20260513.log still exists after sweep_log_files"
    )


# ===========================================================================
# test_sweep_processes_kills_worker_in_worktree
# ===========================================================================

@_PSUTIL_REQUIRED
def test_sweep_processes_kills_worker_in_worktree(tmp_path: Path) -> None:
    """sweep() terminates a dummy subprocess whose cwd is inside worktree_path.

    Covers: ``test_sweep_processes_kills_worker_in_worktree`` from the Test
    Requirements table.
    """
    import subprocess

    child = _spawn_sleeping_child(tmp_path)
    pid = child.pid

    try:
        result = sweep(str(tmp_path))
        # The process must have been killed.
        assert pid in result.killed_pids, (
            f"PID {pid} not in killed_pids {result.killed_pids!r}"
        )
        # Verify the subprocess is actually dead.
        assert child.poll() is not None, (
            "Subprocess is still running after sweep()"
        )
    finally:
        # Cleanup: ensure child is terminated regardless of test outcome.
        if child.poll() is None:
            child.kill()
            child.wait()


# ===========================================================================
# test_sweep_processes_skips_protected_path
# ===========================================================================

@_PSUTIL_REQUIRED
def test_sweep_processes_skips_protected_path(tmp_path: Path) -> None:
    """sweep() returns conflict payload and kills nothing when process matches protected_paths.

    Covers: ``test_sweep_processes_skips_protected_path`` from the Test
    Requirements table.
    """
    # Use a distinctive marker in the command line that we can protect.
    protected_marker = "__pdw_protected_test_marker__"

    import subprocess
    child = subprocess.Popen(
        [sys.executable, "-c",
         f"import time; _ = '{protected_marker}'; time.sleep(60)"],
        cwd=str(tmp_path),
    )
    time.sleep(0.1)

    try:
        config: dict[str, Any] = {
            "kill_residual_processes": True,
            "log_globs": ["*.log"],
            "protected_paths": [protected_marker],
        }
        result = sweep(str(tmp_path), config=config)

        # Must have conflict entry, not kill.
        assert result.conflict_pids, (
            "conflict_pids should be non-empty for a protected process"
        )
        assert result.killed_pids == [], (
            f"killed_pids should be empty, got {result.killed_pids!r}"
        )
        assert result.error is not None, (
            "error should be set when sweep aborts due to protected-path conflict"
        )

        # The subprocess must still be alive.
        assert child.poll() is None, (
            "Protected subprocess was killed despite protected_paths match"
        )
    finally:
        child.kill()
        child.wait()


# ===========================================================================
# test_sweep_processes_permission_denied
# ===========================================================================

@_PSUTIL_REQUIRED
def test_sweep_processes_permission_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """sweep() returns structured error payload when kill raises PermissionError.

    Covers: ``test_sweep_processes_permission_denied`` from the Test
    Requirements table.  Uses monkeypatch to simulate PermissionError without
    requiring a real privileged process.
    """
    import psutil as _psutil
    from worktree import sweep_processes as _mod

    # Patch _terminate_process to always return a PermissionError string.
    monkeypatch.setattr(
        _mod,
        "_terminate_process",
        lambda proc: "PermissionError: operation not permitted (monkeypatched)",
    )

    # Spawn a child so sweep() finds a candidate.
    child = _spawn_sleeping_child(tmp_path)
    try:
        result = sweep(str(tmp_path))

        assert result.killed_pids == [], (
            f"killed_pids should be empty when PermissionError, got {result.killed_pids!r}"
        )
        assert result.conflict_pids, (
            "conflict_pids should be non-empty when PermissionError"
        )
        # Verify the reason field contains "PermissionError".
        reasons = [entry.get("reason", "") for entry in result.conflict_pids]
        assert any("PermissionError" in r for r in reasons), (
            f"Expected PermissionError in reasons, got {reasons!r}"
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()


# ===========================================================================
# test_sweep_processes_kill_disabled
# ===========================================================================

@_PSUTIL_REQUIRED
def test_sweep_processes_kill_disabled(tmp_path: Path) -> None:
    """With kill_residual_processes=false, sweep() returns summary without killing.

    Covers: ``test_sweep_processes_kill_disabled`` from the Test Requirements
    table.
    """
    child = _spawn_sleeping_child(tmp_path)
    try:
        config: dict[str, Any] = {
            "kill_residual_processes": False,
            "log_globs": ["*.log"],
            "protected_paths": [],
        }
        result = sweep(str(tmp_path), config=config)

        # No processes must have been killed.
        assert result.killed_pids == [], (
            f"killed_pids should be empty in summary mode, got {result.killed_pids!r}"
        )
        # The running PID should appear in conflict_pids (summary mode).
        pids_in_conflicts = [entry.get("pid") for entry in result.conflict_pids]
        assert child.pid in pids_in_conflicts, (
            f"PID {child.pid} not found in conflict_pids {pids_in_conflicts!r}"
        )
        # The subprocess must still be alive.
        assert child.poll() is None, (
            "Subprocess was killed despite kill_residual_processes=False"
        )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait()
