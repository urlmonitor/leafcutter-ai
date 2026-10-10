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
      3. Production runs a real, DIRECTED
         ``python <this worktree>/scripts/build.py --target-dir <private>``
         subprocess straight against an EMPTY private staging directory --
         no source copy step first. This is the SAME ``build.py
         --target-dir`` invocation form ``setup_ticket_worktree.py`` uses,
         but the opposite starting point: ``setup_ticket_worktree.py``
         self-targets because its target directory ALREADY IS a source
         checkout -- it probes for ``<root>/scripts/build.py`` and then
         builds into that same ``<root>``, so self-targeting is its only
         option there. This producer instead starts from an EMPTY
         directory and has an actual choice between self-targeting (copy
         the source tree in first, then build onto it) and directing (skip
         the copy, build straight into the empty directory). A directed
         build yields the deployed output ONLY -- byte-identical in shape,
         at the same relative paths, to the deployed half of a
         self-targeting build -- at a measured ~775 files versus ~11,675
         for the self-targeting shape, because the self-targeting shape
         also carries this repository's own package source alongside the
         output it produces. That 15x-ish file-count gap is what
         ``shared_layout_integrity``'s post-reader whole-tree
         walk-and-digest pays on every reader, so the directed shape was
         chosen deliberately, not merely because it happens to be shorter
         code (see TQ-600a's shared-layout-directed-build decision and the
         measured counts in
         ``docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600.yaml``).
         The staging directory is published (atomic ``os.rename``) to its
         final run-scoped path only AFTER ``.build_manifest.json`` exists
         at its root (written near the end of ``build.py``'s ``main()`` --
         confirmed by reading
         ``scripts/build_main_helpers.py::_write_and_verify_manifest``,
         and true for a directed build exactly as for a self-targeting
         one: ``build_helpers.py``'s manifest-writing path computes
         ``repo_root = target_root if target_root is not None else
         package_root``, so a directed build's ``target_root`` -- the
         empty ``--target-dir`` -- is where the manifest lands), so no
         caller can ever observe a partially-written tree.
      4. Both outcomes are cached durably: success as the published root
         path, failure as the captured subprocess diagnostic, so every
         waiter -- in this process or another worker's -- raises from the
         SAME cached failure rather than retrying the deploy.

    KNOWN NON-HERMETIC PROPERTY (recorded, not resolved -- re-measure before
    relying on it): because this producer's ``target_root`` is NOT also the
    ``package_root`` (unlike a self-targeting build, where they are the same
    directory), the written ``.build_manifest.json``'s ``package_root`` field
    becomes a RELATIVE PATH that escapes the private staging directory back
    out into this live worktree (e.g.
    ``"../../../../projects/leafcutter/leafcutter-ai"``), rather than the
    empty string a self-targeting build would record. ``check_build_drift.py``
    (lines ~519-571) resolves template paths through that same offset, so a
    deployed drift-gate run pointed at a directed layout's root would reach
    OUTSIDE the layout, back into the live repository. No current or planned
    consumer of the shared reference layout runs a drift gate against it, so
    this is inert today -- but it makes the directed layout non-hermetic with
    respect to the live repo it was built from. Re-measure this the first time
    any test migrates a drift-gate check onto the shared layout; do not assume
    it has been fixed just because nothing exercises it yet.
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

# Env var naming the tree to build the layout from instead of this file's own checkout.
# Set ONLY by the post-merge fix proof's child session (scripts/ci/post_merge_fix_proof.py,
# TQ-600a-13-xvi), whose code is main's but whose code under test is a pull request's head;
# unset or empty, the root below is exactly what it always was (the post-merge run).
SOURCE_ROOT_ENV_VAR = "LEAFCUTTER_SHARED_LAYOUT_SOURCE_ROOT"

# scripts/suite_performance/_shared_layout_producer.py -> parents[2] == worktree root
_WORKTREE_ROOT = Path(os.environ.get(SOURCE_ROOT_ENV_VAR) or Path(__file__).resolve().parents[2])

# Generous timeout for the real ~60s package deploy (see TQ-600.yaml).
_DEPLOY_SUBPROCESS_TIMEOUT_S = 240

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


def _run_build_subprocess(target_dir: Path) -> None:
    """Run a real, DIRECTED ``build.py --target-dir`` subprocess.

    Invokes THIS worktree's own ``scripts/build.py`` (never a copy) against
    *target_dir* -- an empty private staging directory that is neither the
    package root nor a source checkout. This is deliberately NOT the
    self-targeting form (``<target_dir>/scripts/build.py --target-dir
    <target_dir>``): that would require a source copy into *target_dir*
    first, which is exactly the extra ~10,900 files (see TQ-600a's measured
    11,675-vs-775 comparison) this producer exists to stop paying for. See
    this module's docstring for the full self-targeting-vs-directed
    rationale and the non-hermetic ``package_root`` caveat that follows from
    *target_dir* no longer being the package root.

    Emits the execution signal exactly when the subprocess really ran
    (normal completion or timeout-after-launch), never when it could not
    be started at all.

    Args:
        target_dir: The empty staging directory to pass as ``--target-dir``.
            Not copied into, not the package root.

    Raises:
        SharedReferenceLayoutError: when the subprocess could not be
            started, timed out, or exited non-zero.
    """
    build_script = _WORKTREE_ROOT / "scripts" / "build.py"
    cmd = [sys.executable, str(build_script), "--target-dir", str(target_dir)]
    try:
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell, internal tool
            cmd,
            cwd=str(_WORKTREE_ROOT),
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
    """Produce the layout via a directed build into an empty private dir,
    then publish it.

    No source-tree copy: *private* is left for ``build.py`` itself to
    create (its ``--target-dir`` writes the deployed output straight into
    it) -- see ``_run_build_subprocess``'s docstring for why this is a
    DIRECTED build rather than the self-targeting form. The staging dir is
    only renamed to *published* after ``.build_manifest.json`` is confirmed
    present at its root, so a waiter can never observe a partially-written
    tree.

    Args:
        run_base: The run-scoped shared directory (holds both the private
            staging dir and the final published dir).
        published: The final path to publish the completed layout to.

    Returns:
        *published*, once the layout is confirmed complete and renamed.

    Raises:
        SharedReferenceLayoutError: on any deploy or publish failure.
    """
    private = run_base / PRIVATE_DIRNAME
    if private.exists():
        # Leftover from a prior attempt whose process died mid-production
        # (flock is released by the kernel on process exit, so a new
        # acquirer reaches here without a stale lock, but may inherit a
        # half-deployed staging dir).
        shutil.rmtree(private, ignore_errors=True)

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
# - 2026-10-06 [python-coder]: Changed `_produce` from a self-targeting
#   build (copy this repo into `private` via `_copy_source_tree`, then run
#   `<private>/scripts/build.py --target-dir <private>`) to a DIRECTED build
#   (`_WORKTREE_ROOT/scripts/build.py --target-dir <private>`, no copy, into
#   an empty `private`). A prior investigation measured the self-targeting
#   shape as producing package source PLUS deployed output -- 11,675 files
#   -- versus 775 for the directed shape, with the deployed tree
#   byte-identical in shape at the same relative paths (493
#   output_mappings in both manifests, no errors in either). The real cost
#   was never mainly the build subprocess: `shared_layout_integrity`
#   re-walks and re-digests the WHOLE published tree after every
#   reader-marked test, so the self-targeting shape's extra ~10,900 files
#   were a ~16x per-reader tax (measured ~6.00s vs ~0.24s per reader on the
#   authoring investigation's box; see this file's VERIFY section in the
#   TQ-600a-shared-layout-directed-build ticket for this session's own
#   ratios). Removed `_copy_source_tree` and its `_EXCLUDED_NAMES` constant
#   from this module as dead code -- confirmed via grep that
#   `pytest_shared_reference_layout.py`'s own `_produce_private_copy`
#   (the mutator/undeclared route) keeps its OWN separate copytree and
#   `_EXCLUDED_NAMES`, untouched by this change, since a mutator legitimately
#   needs `templates/` and `scripts/build.py` present to alter the package
#   before building. CAVEAT (recorded, not resolved): a directed build's
#   `.build_manifest.json` records `package_root` as a relative path
#   escaping back into the live worktree (confirmed via
#   `build_helpers.py`'s `repo_root = target_root if target_root is not
#   None else package_root`), so `check_build_drift.py` would resolve
#   outside the layout if ever pointed at it -- inert today, re-measure the
#   first time a drift-gate test migrates onto the shared layout.
#   (#TQ-600a-shared-layout-directed-build)
