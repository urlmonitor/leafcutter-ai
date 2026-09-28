"""
MODULE: _shared_layout_coordination
GOAL: Cross-process coordination primitives for the shared reference
    layout: run identity, the run-scoped shared directory, the execution
    signal, the cross-process/cross-thread lock, and the durable on-disk
    success/failure records.
BUSINESS CONTEXT: TQ-600a-1. Split out of ``_shared_layout_producer.py`` to
    respect the project's 400-line file-size limit (see
    ``build_phases.py`` / ``build_helpers.py`` for the precedent this
    module-split pattern follows).
ARCHITECTURE: Imported by ``_shared_layout_producer.py``, which owns the
    actual copy/deploy/publish steps and the public
    ``get_or_produce_shared_layout`` entry point. This module owns none of
    the production logic itself -- only the pieces every worker OS process
    needs to independently agree on WHERE the shared layout lives and WHO
    gets to produce it.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - non-POSIX platform
    fcntl = None  # type: ignore[assignment]

_log = logging.getLogger(__name__)

# Env var the assumed production contract (unit_tests/suite_performance/
# test_tq_600a_1.py) uses to observe real deploy executions independently
# of anything the run reports about itself.
EXECUTION_LOG_ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG"

MANIFEST_FILENAME = ".build_manifest.json"
PUBLISHED_DIRNAME = "published"
PRIVATE_DIRNAME = "private"
_LOCK_FILENAME = ".lock"
_FAILURE_FILENAME = "failure.json"


class SharedReferenceLayoutError(Exception):
    """Raised when the shared reference layout could not be produced.

    Carries a human-readable diagnostic (captured subprocess stdout/stderr/
    exit status, or the copy/publish failure) so every waiting consumer --
    in this process or another worker's -- sees the same information
    regardless of who actually attempted production.
    """


# ---------------------------------------------------------------------------
# Run identity and the run-scoped shared directory
# ---------------------------------------------------------------------------

_fallback_run_key: str | None = None


def run_key() -> str:
    """Return the identifier that scopes the shared layout to one run.

    Prefers ``PYTEST_XDIST_TESTRUNUID`` (set identically on every
    pytest-xdist worker OS process for a single ``-n`` invocation), which
    is what lets independent worker processes agree on the same shared
    directory without any IPC beyond that inherited environment variable.
    Falls back to a UUID generated once and cached for this process's
    lifetime when not running under xdist, so a single-process run still
    gets a stable key across all of its own calls without colliding with
    any other run on the same host.

    Returns:
        A filesystem-safe run identifier string.
    """
    global _fallback_run_key  # noqa: PLW0603
    xdist_uid = os.environ.get("PYTEST_XDIST_TESTRUNUID")
    if xdist_uid:
        return xdist_uid
    if _fallback_run_key is None:
        _fallback_run_key = uuid.uuid4().hex
    return _fallback_run_key


def worker_name() -> str:
    """Return the current pytest-xdist worker id, or "master" outside xdist."""
    return os.environ.get("PYTEST_XDIST_WORKER", "master")


def run_base_dir() -> Path:
    """Return the run-scoped shared directory under the OS temp root."""
    return Path(tempfile.gettempdir()) / f"leafcutter-shared-reference-layout-{run_key()}"


def emit_execution_signal(target_dir: Path) -> None:
    """Append one JSONL execution-signal line, if the env var names a log file.

    No-op when ``LEAFCUTTER_SHARED_LAYOUT_EXECUTION_LOG`` is unset, so this
    instrumentation is invisible to a real (non-instrumented) run. Callers
    must invoke this only from the call site where a real deploy subprocess
    actually executed -- never on a cache hit / handout.

    Args:
        target_dir: The ``--target-dir`` path the just-executed subprocess
            was given.
    """
    log_path_str = os.environ.get(EXECUTION_LOG_ENV_VAR)
    if not log_path_str:
        return
    entry = {
        "event": "deploy_executed",
        "target_dir": str(target_dir),
        "pid": os.getpid(),
        "worker": worker_name(),
    }
    try:
        with open(log_path_str, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry) + "\n")
    except OSError as exc:
        _log.warning(
            "emit_execution_signal: could not append to %s: %s", log_path_str, exc
        )


# ---------------------------------------------------------------------------
# Cross-process lock
# ---------------------------------------------------------------------------


@contextmanager
def run_lock(run_base: Path) -> Iterator[None]:
    """Acquire an exclusive, blocking lock scoped to *run_base*.

    Serialises "who produces" across pytest-xdist worker OS processes via
    ``fcntl.flock`` on a lock file under ``run_base``, and across threads
    within one process too: each acquisition opens its own file descriptor,
    and ``flock`` locks are held per open-file-description, so two threads
    that each open the same path independently block each other correctly.

    Args:
        run_base: The run-scoped shared directory (created if absent).

    Yields:
        None. The lock is held for the duration of the ``with`` block.

    Raises:
        SharedReferenceLayoutError: when the lock cannot be acquired
            (including on a platform without ``fcntl``).
    """
    if fcntl is None:
        raise SharedReferenceLayoutError(
            "shared reference layout locking requires POSIX fcntl.flock; "
            "no fallback is implemented for this platform."
        )
    run_base.mkdir(parents=True, exist_ok=True)
    lock_path = run_base / _LOCK_FILENAME
    lock_fh = None
    try:
        lock_fh = open(lock_path, "w", encoding="utf-8")
        try:
            fcntl.flock(lock_fh, fcntl.LOCK_EX)
        except OSError as exc:
            raise SharedReferenceLayoutError(
                f"could not acquire shared-layout lock at {lock_path}: {exc}"
            ) from exc
        yield
    finally:
        if lock_fh is not None:
            try:
                fcntl.flock(lock_fh, fcntl.LOCK_UN)
            except OSError as exc:
                _log.warning(
                    "could not release shared-layout lock at %s: %s", lock_path, exc
                )
            lock_fh.close()


# ---------------------------------------------------------------------------
# Durable (on-disk) success/failure records
# ---------------------------------------------------------------------------


def check_published(published: Path) -> Path | None:
    """Return *published* when it already holds a complete layout, else None."""
    if (published / MANIFEST_FILENAME).exists():
        return published
    return None


def write_failure_record(run_base: Path, message: str) -> None:
    """Persist *message* so every later waiter raises the same failure."""
    failure_path = run_base / _FAILURE_FILENAME
    try:
        failure_path.write_text(json.dumps({"error": message}), encoding="utf-8")
    except OSError as exc:
        _log.warning(
            "could not persist shared-layout failure record at %s: %s",
            failure_path,
            exc,
        )


def read_failure_record(run_base: Path) -> str | None:
    """Return the previously-persisted failure message, if any."""
    failure_path = run_base / _FAILURE_FILENAME
    if not failure_path.exists():
        return None
    try:
        data = json.loads(failure_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _log.warning(
            "could not read shared-layout failure record at %s: %s", failure_path, exc
        )
        return f"shared reference layout previously failed (failure record unreadable: {exc})"
    return data.get("error", "shared reference layout previously failed")


# DECISION HISTORY
# ================================================================================
# - 2026-09-21 19:10 [python-coder]: Created module to hold the cross-process
#   coordination primitives (run identity, run-scoped shared dir, execution
#   signal, fcntl.flock-based lock, durable success/failure records) for
#   TQ-600a-1's shared reference layout. Split out of
#   _shared_layout_producer.py to keep both files under the project's
#   400-line file-size limit, mirroring the build_phases.py /
#   build_helpers.py precedent. (#TQ-600a-1)
