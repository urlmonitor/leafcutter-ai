"""
MODULE: _shared_layout_integrity_compare
GOAL: Low-level, no-pytest-dependency content-digest walk of a directory
    tree: ``capture_record`` and ``compare_record``, the two functions the
    ``shared_layout_integrity`` pytest plugin builds its session-level
    guard on.
BUSINESS CONTEXT: TQ-600a-3. Split out of ``shared_layout_integrity.py`` to
    respect this project's 400-line file-size limit, mirroring the existing
    ``_shared_layout_producer.py`` / ``_shared_layout_coordination.py``
    split (also TQ-600a-1, for the identical reason).
ARCHITECTURE: Re-exported from ``shared_layout_integrity.py`` (``capture_record``
    and ``compare_record`` are imported there and re-exported unchanged) so a
    caller that imports the plugin module directly -- as
    ``unit_tests/suite_performance/test_tq_600a_3.py``'s low-level tests do
    -- can reach them without also importing this private helper module,
    mirroring how ``pytest_shared_reference_layout.py`` re-exports
    ``get_or_produce_shared_layout`` from ``_shared_layout_producer.py``.
    This module owns none of the pytest plugin/session logic itself.
"""

from __future__ import annotations

import hashlib
import logging
import os
from collections.abc import Generator
from pathlib import Path

__all__ = ["capture_record", "compare_record"]

_log = logging.getLogger(__name__)

_EXCLUDED_DIR_NAMES = frozenset({"__pycache__"})
_EXCLUDED_FILE_SUFFIX = ".pyc"

_READ_CHUNK_SIZE = 1 << 20  # 1 MiB


def _iter_files(root: Path) -> Generator[tuple[str, Path], None, None]:
    """Yield ``(relpath_posix, absolute_path)`` for every file under *root*.

    Skips any directory literally named ``__pycache__`` (not descended into
    at all) and any file whose name ends in ``.pyc`` -- the false-positive
    control this AC's Implementation Notes require: importing from a
    deployed tree generates bytecode as a side effect of reading it.

    Args:
        root: Directory to walk. Yields nothing if it does not exist.

    Yields:
        Tuples of (posix-style relative path, absolute file path).
    """
    if not root.exists():
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIR_NAMES]
        for filename in filenames:
            if filename.endswith(_EXCLUDED_FILE_SUFFIX):
                continue
            full = Path(dirpath) / filename
            yield full.relative_to(root).as_posix(), full


def _digest_file(path: Path) -> str | None:
    """Return the SHA-256 hex digest of *path*'s bytes, or None if unreadable.

    A content digest, never mtime or size -- a deploy writes its whole tree
    within a second, so an mtime-based comparison cannot see a same-second
    rewrite (this AC's Implementation Notes point 2).

    Args:
        path: Absolute path to the file to digest.

    Returns:
        The lowercase hex digest, or None when the file could not be read
        (logged as a warning; treated by callers as absent from the walk
        rather than aborting the whole comparison).
    """
    hasher = hashlib.sha256()
    try:
        with open(path, "rb") as fh:
            for chunk in iter(lambda: fh.read(_READ_CHUNK_SIZE), b""):
                hasher.update(chunk)
    except OSError as exc:
        _log.warning("shared_layout_integrity: could not read %s: %s", path, exc)
        return None
    return hasher.hexdigest()


def _digest_tree(root: Path) -> dict[str, str]:
    """Return ``{relpath_posix: sha256_hexdigest}`` for every file under *root*."""
    digests: dict[str, str] = {}
    for relpath, full in _iter_files(root):
        digest = _digest_file(full)
        if digest is not None:
            digests[relpath] = digest
    return digests


def capture_record(root: Path) -> dict:
    """Capture a content-digest record of *root*'s current file tree.

    Must be called immediately after the single deploy that produced *root*
    returns -- a record captured lazily on first consumer request would be
    blind to that consumer's own mutation, which is the likeliest first
    offender (Implementation Notes point 1).

    Args:
        root: The deployed layout's root directory.

    Returns:
        ``{"files": {relpath_posix: sha256_hexdigest, ...}, "count": int}``.
    """
    files = _digest_tree(root)
    return {"files": files, "count": len(files)}


def compare_record(
    root: Path,
    record: dict,
    *,
    consumer_count: int = 0,
    offending_test: str | None = None,
) -> dict:
    """Compare *root*'s CURRENT file tree against a previously captured *record*.

    Re-walks *root* with the identical exclusion rules as ``capture_record``
    and diffs its current file set + digests against ``record["files"]``.
    The added-file check walks the UNION of the current tree and the
    recorded file list, never just the recorded list -- a comparison that
    iterates only ``record["files"]`` is structurally blind to a brand-new
    path it never had a reason to look at.

    Args:
        root: The layout's root directory (may not exist -- treated as
            containing zero files rather than raising).
        record: A record previously returned by ``capture_record``.
        consumer_count: Number of consuming tests to report verbatim.
        offending_test: The pytest node id of the first test whose
            comparison newly reported a difference, or None, reported
            verbatim.

    Returns:
        A dict with ``compared_count`` (the size of the BASELINE, i.e.
        ``len(record["files"])`` -- so a comparison whose baseline was
        itself captured over an empty/absent root is distinguishable at 0
        from one that inspected a real tree and found no differences),
        ``added``, ``changed``, ``missing`` (sorted relpath lists),
        ``consumer_count``, ``offending_test`` (passed through verbatim),
        ``files_ok`` (False when ``compared_count`` is 0 OR any of
        added/changed/missing is non-empty -- a comparison must never
        report ``files_ok=True`` merely because the three lists are empty
        when ``compared_count`` is ALSO 0, per this AC's own
        AC-store-validator precedent), and ``had_consumers``
        (``consumer_count > 0``).
    """
    recorded = record.get("files", {})
    current = _digest_tree(root)

    added = sorted(p for p in current if p not in recorded)
    missing = sorted(p for p in recorded if p not in current)
    changed = sorted(
        p for p in current if p in recorded and current[p] != recorded[p]
    )
    compared_count = len(recorded)
    files_ok = compared_count > 0 and not (added or changed or missing)

    return {
        "compared_count": compared_count,
        "added": added,
        "changed": changed,
        "missing": missing,
        "consumer_count": consumer_count,
        "offending_test": offending_test,
        "files_ok": files_ok,
        "had_consumers": consumer_count > 0,
    }


# DECISION HISTORY
# ================================================================================
# - 2026-09-30 [python-coder]: Split out of shared_layout_integrity.py to
#   respect the project's 400-line file-size limit, mirroring the existing
#   _shared_layout_producer.py / _shared_layout_coordination.py split.
#   Holds capture_record/compare_record -- the content-digest walk excluding
#   __pycache__/*.pyc, digesting by SHA-256 content never mtime/size -- with
#   no pytest dependency. (#TQ-600a-3)
