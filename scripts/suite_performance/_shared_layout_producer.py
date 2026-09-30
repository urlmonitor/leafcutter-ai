"""
MODULE: _shared_layout_producer
GOAL: Lazily produce, exactly once per run, a single shared "reference
    layout" -- a real deployed copy of this package -- and hand its root
    path to every consumer, cross-process-safely.
BUSINESS CONTEXT: TQ-600a-1. Read-only tests that only need to inspect a
    deployed copy of the package must not each pay for their own deploy.
    Before this module existed, 77 measured call sites across 52 test files
    each spawned `python scripts/build.py --target-dir <tmp>` independently
    -- a large share of the ~90-minute full suite wall clock (see
    docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/
    TQ-600.yaml for the measured evidence).
ARCHITECTURE: Private helper imported by
    scripts.suite_performance.pytest_shared_reference_layout (the pytest
    plugin/fixture registration surface). The cross-process coordination
    primitives (run identity, the run-scoped shared directory, the
    execution signal, the lock, the durable success/failure records) live
    in ``_shared_layout_coordination.py`` -- split out to respect the
    project's 400-line file-size limit (see ``build_phases.py`` /
    ``build_helpers.py`` for the precedent). This module owns the actual
    copy/deploy/publish steps and the public
    ``get_or_produce_shared_layout`` entry point.

    Production, once per run:
      1. Fast path -- an in-process cache (module globals) short-circuits
         every call after the first *within this OS process*.
      2. Cross-process path -- ``_shared_layout_coordination.run_lock``
         serialises "who produces" across pytest-xdist worker OS
         processes: the first caller to acquire the lock produces; every
         other caller blocks on the same lock, then observes the
         now-complete (or now-failed) cache instead of retrying.
      3. Production copies this repository (excluding build outputs,
         caches, and VCS metadata -- see ``_EXCLUDED_NAMES``) into a
         PRIVATE staging directory, then runs a real, self-targeting
         ``python <staging>/scripts/build.py --target-dir <staging>``
         subprocess -- the same self-hosting pattern
         ``setup_ticket_worktree.py`` already uses to bootstrap a fresh
         ticket worktree (probing ``<root>/scripts/build.py``, then running
         it with ``--target-dir <root>``). The staging directory is
         published (atomic ``os.rename``) to its final run-scoped path only
         AFTER ``.build_manifest.json`` exists at its root (written near
         the end of ``build.py``'s ``main()`` -- confirmed by reading
         ``scripts/build_main_helpers.py::_write_and_verify_manifest``), so
         no caller can ever observe a partially-written tree.
      4. Both outcomes are cached durably: success as the published root
         path, failure as the captured subprocess diagnostic, so every
         waiter -- in this process or another worker's -- raises from the
         SAME cached failure rather than retrying the deploy.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from scripts.suite_performance._shared_layout_coordination import (
    MANIFEST_FILENAME,
    PRIVATE_DIRNAME,
    PUBLISHED_DIRNAME,
    SharedReferenceLayoutError,
    check_published,
    emit_execution_signal,
    read_failure_record,
    run_base_dir,
    run_lock,
    write_failure_record,
)

__all__ = ["SharedReferenceLayoutError", "get_or_produce_shared_layout"]

_log = logging.getLogger(__name__)

# scripts/suite_performance/_shared_layout_producer.py -> parents[2] == worktree root
_WORKTREE_ROOT = Path(__file__).resolve().parents[2]

# Generous timeout for the real ~60s package deploy (see TQ-600.yaml).
_DEPLOY_SUBPROCESS_TIMEOUT_S = 240

# Names excluded when copying this repository into a staging directory:
# VCS metadata, prior build outputs, and caches -- none of these are part
# of the deployable SOURCE, and copying .git in particular would point the
# copy's git metadata at this worktree's real (shared) object store, which
# is not a risk worth taking for a throwaway staging copy.
_EXCLUDED_NAMES = frozenset(
    {
        ".git",
        ".claude",
        ".leafcutter",
        ".leafcutter.lock",
        ".agents",
        "debugging",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        "node_modules",
        ".env",
        ".gemini",
        ".pre-commit-config.yaml",
        MANIFEST_FILENAME,
        ".venv",
        "venv",
    }
)

# ---------------------------------------------------------------------------
# In-process fast path (module globals -- one set per pytest OS process)
# ---------------------------------------------------------------------------

_in_process_lock = threading.Lock()
_cached_root: Path | None = None
_cached_error_message: str | None = None


def _cache_success(root: Path) -> None:
    global _cached_root  # noqa: PLW0603
    with _in_process_lock:
        _cached_root = root


def _cache_failure(message: str) -> None:
    global _cached_error_message  # noqa: PLW0603
    with _in_process_lock:
        _cached_error_message = message


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------


def _copy_source_tree(dest: Path) -> None:
    """Copy this repository's deployable source tree into *dest*.

    Args:
        dest: Destination directory. Must not already exist.

    Raises:
        SharedReferenceLayoutError: on any OS-level copy failure.
    """
    try:
        shutil.copytree(
            _WORKTREE_ROOT,
            dest,
            symlinks=True,
            ignore=shutil.ignore_patterns(*_EXCLUDED_NAMES),
        )
    except OSError as exc:
        raise SharedReferenceLayoutError(
            f"could not copy source tree from {_WORKTREE_ROOT} to {dest}: {exc}"
        ) from exc


def _run_build_subprocess(target_dir: Path) -> None:
    """Run a real, self-targeting ``build.py --target-dir`` subprocess.

    Emits the execution signal exactly when the subprocess really ran
    (normal completion or timeout-after-launch), never when it could not
    be started at all.

    Args:
        target_dir: Both the copied package root AND the ``--target-dir``
            value -- this is the self-hosting invocation pattern.

    Raises:
        SharedReferenceLayoutError: when the subprocess could not be
            started, timed out, or exited non-zero.
    """
    build_script = target_dir / "scripts" / "build.py"
    cmd = [sys.executable, str(build_script), "--target-dir", str(target_dir)]
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell, internal tool
            cmd,
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            timeout=_DEPLOY_SUBPROCESS_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        emit_execution_signal(target_dir)  # the process really ran, just too long
        _log.warning("shared reference layout deploy subprocess timed out: %s", exc)
        raise SharedReferenceLayoutError(
            f"deploy subprocess {cmd!r} timed out after {_DEPLOY_SUBPROCESS_TIMEOUT_S}s: {exc}"
        ) from exc
    except (subprocess.SubprocessError, OSError) as exc:
        _log.warning(
            "shared reference layout deploy subprocess could not be started: %s", exc
        )
        raise SharedReferenceLayoutError(
            f"deploy subprocess {cmd!r} could not be started: {exc}"
        ) from exc

    emit_execution_signal(target_dir)

    if result.returncode != 0:
        message = (
            f"deploy subprocess {cmd!r} exited {result.returncode}:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        _log.warning("shared reference layout deploy failed: %s", message)
        raise SharedReferenceLayoutError(message)


def _produce(run_base: Path, published: Path) -> Path:
    """Produce the layout into a private staging dir, then publish it.

    The staging dir is only renamed to *published* after
    ``.build_manifest.json`` is confirmed present at its root, so a waiter
    can never observe a partially-written tree.

    Args:
        run_base: The run-scoped shared directory (holds both the private
            staging dir and the final published dir).
        published: The final path to publish the completed layout to.

    Returns:
        *published*, once the layout is confirmed complete and renamed.

    Raises:
        SharedReferenceLayoutError: on any copy, deploy, or publish failure.
    """
    private = run_base / PRIVATE_DIRNAME
    if private.exists():
        # Leftover from a prior attempt whose process died mid-production
        # (flock is released by the kernel on process exit, so a new
        # acquirer reaches here without a stale lock, but may inherit a
        # half-copied staging dir).
        shutil.rmtree(private, ignore_errors=True)

    _copy_source_tree(private)
    _run_build_subprocess(private)

    if not (private / MANIFEST_FILENAME).exists():
        raise SharedReferenceLayoutError(
            f"deploy subprocess exited 0 but {private / MANIFEST_FILENAME} is "
            "missing -- refusing to publish an incomplete layout"
        )

    try:
        os.rename(private, published)
    except OSError as exc:
        raise SharedReferenceLayoutError(
            f"could not publish completed layout {private} -> {published}: {exc}"
        ) from exc
    return published


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def get_or_produce_shared_layout() -> Path:
    """Return the path to this run's single shared reference layout.

    Lazy: nothing is produced until the first call. Idempotent within a
    process (an in-memory cache short-circuits every later call) and across
    pytest-xdist worker processes (a cross-process lock plus an on-disk
    published/failure record serialises production so exactly one real
    deploy happens per run, however many workers or callers there are).

    Returns:
        The absolute path to the deployed, complete package root.

    Raises:
        SharedReferenceLayoutError: when the shared deploy could not be
            produced -- either this call attempted production and it
            failed, or a previous attempt (in this process or another
            worker's) already failed and cached that failure.
    """
    with _in_process_lock:
        if _cached_root is not None:
            return _cached_root
        if _cached_error_message is not None:
            raise SharedReferenceLayoutError(_cached_error_message)

    run_base = run_base_dir()
    published = run_base / PUBLISHED_DIRNAME

    with run_lock(run_base):
        # Re-check under the lock: another worker/thread may have finished
        # (or failed) production while we were waiting to acquire it.
        cached = check_published(published)
        if cached is not None:
            _cache_success(cached)
            return cached
        failure_message = read_failure_record(run_base)
        if failure_message is not None:
            _cache_failure(failure_message)
            raise SharedReferenceLayoutError(failure_message)

        try:
            root = _produce(run_base, published)
        except SharedReferenceLayoutError as exc:
            write_failure_record(run_base, str(exc))
            _cache_failure(str(exc))
            raise

    _cache_success(root)
    return root


# DECISION HISTORY
# ================================================================================
# - 2026-09-21 19:12 [python-coder]: Created get_or_produce_shared_layout()
#   for TQ-600a-1: copies this repository into a private staging dir
#   (excluding build outputs/caches/.git), runs a real self-targeting
#   `build.py --target-dir <staging>` subprocess (the same self-hosting
#   pattern setup_ticket_worktree.py already uses), and publishes the
#   staging dir atomically only once .build_manifest.json confirms the
#   deploy is complete. Both success and failure are cached durably via
#   _shared_layout_coordination, so every waiter -- this process or another
#   pytest-xdist worker's -- gets the identical outcome without repeating
#   the ~60s deploy. (#TQ-600a-1)
