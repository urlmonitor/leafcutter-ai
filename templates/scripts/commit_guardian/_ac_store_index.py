"""
MODULE: _ac_store_index
GOAL: Shared fingerprint-keyed cached index of all AC YAML files under the AC store
    directory. Returns a dict mapping AC id to the full parsed AC content so
    every hook can extract depends_on, covered_by, implements_pattern, and any
    other field without a second filesystem read pass.
BUSINESS CONTEXT: Four AC guardrail hooks each previously walked and YAML-parsed
    the full AC store independently — each hook runs in its own subprocess, so a
    per-process in-memory cache was a no-op. On a store of ~1,790 files a single
    full-store parse takes ~10 s, so a four-hook commit was paying up to 40 s of
    parse time. This module eliminates that cost by persisting the parsed index to
    a JSON file inside the git-dir so hook process #2/#3/#4 load from disk instead
    of re-walking and re-parsing YAML.
ARCHITECTURE: Standalone stdlib module — no leafcutter imports. Imported by
    check_ac_schema.py, check_ac_circular_deps.py, check_ac_parent_covered_by.py,
    and check_ac_pattern_refs.py. Disk-cache and fingerprint helpers live in the
    sibling module _ac_store_index_disk.py (extracted to stay within the 400-line
    project file-size limit).

    Cache key (fingerprint): SHA-256 of a deterministic serialisation of the sorted
    list of (relative_path, st_mtime_ns, st_size) for every *.yaml file under
    store_root, plus the resolved absolute store_root path. This single fingerprint
    is used as both the in-memory cache key and the on-disk cache validity check.
    It inherently captures additions, removals, and modifications, including
    same-second edits detected via nanosecond mtime and size changes.

    In-memory cache: module-level _CACHE keyed on store_root_str, storing
    (fingerprint, index_dict). On-disk cache: JSON at <git-dir>/ac_store_index_cache.json,
    written atomically via tmp-file + os.replace, managed by _ac_store_index_disk.

    get_ac_index() flow:
      1. Compute fingerprint (single rglob walk via _ac_store_index_disk).
      2. If in-memory _CACHE has a matching fingerprint → return immediately.
      3. Elif on-disk cache fingerprint matches → load, warm in-memory cache, return.
      4. Else rebuild from YAML → warm both caches, return.

    Corrupt/unreadable/schema-mismatched disk cache degrades gracefully to a full
    rebuild. YAML loading delegates to _ac_schema_validators.load_yaml (canonical
    tested path) with a fallback to load_yaml_manual when PyYAML is absent.

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-008-ac-store-schema-id-format-enforcement.md

DECISION HISTORY:
  - 2026-06-30 [python-coder/TICKET-20260629-AC_Hook_Store_Index]: Created.
    Provides get_ac_index(store_root) with mtime-keyed in-process caching.
    Canonicalises on _ac_schema_validators.load_yaml / load_yaml_manual for
    YAML loading to avoid silent behavioural divergence between hooks. Returns
    a rich id->full-dict index so consumers can extract any field without a
    second read pass.
  - 2026-06-30 [python-coder/TICKET-20260629-AC_Hook_Store_Index fix-pass]:
    Fixed cross-process cache no-op (was per-process in-memory dict only — hooks
    run in separate subprocesses so each process started from empty cache).
    Added on-disk JSON cache (see _ac_store_index_disk.py) keyed by SHA-256
    fingerprint of sorted (rel_path, mtime_ns, size) tuples + store_root.
    Replaced max-mtime cache key with the fingerprint so removals and same-second
    edits are correctly detected. Replaced blind except Exception # noqa: BLE001
    with specific yaml.YAMLError / OSError catches per repo Ruff TRY/BLE001 policy.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Disk-cache and fingerprint helpers (extracted to keep this file ≤ 400 lines).
# Only ImportError is caught — SyntaxError / AttributeError from a broken
# _ac_store_index_disk.py should propagate so a defective deployment is visible
# rather than silently degrading to the memory-only fallback path.
try:
    from _ac_store_index_disk import (  # type: ignore[import]
        compute_fingerprint,
        load_disk_cache,
        resolve_cache_path,
        write_disk_cache,
    )
    _DISK_HELPERS_OK = True
except ImportError:
    _DISK_HELPERS_OK = False

# ---------------------------------------------------------------------------
# Module-level in-memory cache: {store_root_str: (fingerprint, index_dict)}
# ---------------------------------------------------------------------------

_CACHE: dict[str, tuple[str, dict[str, dict[str, Any]]]] = {}


# ---------------------------------------------------------------------------
# YAML loading helpers (delegate to _ac_schema_validators canonical path)
# ---------------------------------------------------------------------------


def _load_one_yaml_file(yaml_file: Path) -> dict[str, Any] | None:
    """Load and parse a single YAML file; return dict or None on any failure.

    Tries _ac_schema_validators.load_yaml (PyYAML) first; falls back to
    _ac_schema_validators.load_yaml_manual when PyYAML is absent. Both
    paths can raise OSError on unreadable files — these are caught and logged
    as warnings so the caller can skip the file (fail-open).

    Args:
        yaml_file: Path to the .yaml file to load.

    Returns:
        Parsed dict on success, None on any read or parse failure.
    """
    try:
        from _ac_schema_validators import load_yaml, load_yaml_manual  # type: ignore[import]
    except ImportError:
        return _load_yaml_minimal(yaml_file)

    # Attempt PyYAML path via load_yaml.
    # _ac_schema_validators.load_yaml calls yaml.safe_load() and only catches
    # OSError; yaml.YAMLError (malformed YAML) propagates uncaught from it.
    # We must catch it here to preserve the long-standing fail-open behaviour
    # (warn + skip the file, never crash the hook).
    try:
        import yaml as _yaml  # type: ignore[import]
        _yaml_error_type: type[Exception] = _yaml.YAMLError
    except ImportError:
        _yaml_error_type = ValueError  # broad stand-in; yaml absent means no YAMLError

    try:
        data = load_yaml(yaml_file)
        return data if isinstance(data, dict) else None
    except ImportError:
        pass  # PyYAML absent — try manual parser
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: cannot read {yaml_file}: {exc}\n"
        )
        return None
    except _yaml_error_type as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: YAML parse error in {yaml_file}: "
            f"{type(exc).__name__}: {exc}\n"
        )
        return None

    # Fallback: minimal line-oriented parser from _ac_schema_validators.
    try:
        data = load_yaml_manual(yaml_file)
        return data if isinstance(data, dict) else None
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: cannot read {yaml_file} (manual): {exc}\n"
        )
        return None


def _load_yaml_minimal(yaml_file: Path) -> dict[str, Any] | None:
    """Minimal inline YAML fallback when _ac_schema_validators is unavailable.

    Handles only top-level scalar key: value lines. Sufficient for reading
    id, depends_on, covered_by, implements_pattern, and similar fields.

    Args:
        yaml_file: Path to the .yaml file to parse.

    Returns:
        Parsed dict on success, None on read or parse failure.
    """
    try:
        content = yaml_file.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: cannot read {yaml_file}: {exc}\n"
        )
        return None

    try:
        import yaml  # type: ignore[import]

        data = yaml.safe_load(content)
        return data if isinstance(data, dict) else None
    except ImportError:
        pass
    except yaml.YAMLError as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: YAML parse error in {yaml_file}: {exc}\n"
        )
        return None

    # Pure line-based fallback: top-level scalars only.
    result: dict[str, Any] = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result or None


# ---------------------------------------------------------------------------
# Index builder
# ---------------------------------------------------------------------------


def _build_index_from_files(yaml_files: list[Path]) -> dict[str, dict[str, Any]]:
    """Build an id->parsed-dict index from a pre-collected list of yaml Paths.

    Files that cannot be read or parsed are silently skipped (fail-open).
    When two files share the same AC id, the first file encountered wins.

    Args:
        yaml_files: Pre-collected list of .yaml file Paths to parse.

    Returns:
        Dict mapping AC id string to parsed YAML content dict for every
        parseable .yaml file in the list.
    """
    index: dict[str, dict[str, Any]] = {}
    for yaml_file in yaml_files:
        data = _load_one_yaml_file(yaml_file)
        if data is None:
            continue
        ac_id = str(data.get("id", "")).strip()
        if not ac_id:
            continue
        if ac_id not in index:
            index[ac_id] = data
    return index


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_ac_index(store_root: str) -> dict[str, dict[str, Any]]:
    """Return a full AC id->parsed-dict index for all .yaml files under store_root.

    The index is cached using a SHA-256 fingerprint of the sorted set of
    (relative_path, st_mtime_ns, st_size) tuples for every .yaml file, plus the
    resolved store_root path. This fingerprint is used as both the in-memory cache
    key (per-process) and the on-disk cache validity token (cross-process).

    Cross-process cache hit flow:
      1. Compute fingerprint (one rglob walk; no YAML parsing yet).
      2. Check in-memory _CACHE: if fingerprint matches, return immediately.
      3. Load on-disk JSON cache: if stored fingerprint matches, warm in-memory
         cache and return (YAML not re-parsed in this process).
      4. Full rebuild: walk + YAML-parse all files, warm both caches, return.

    Fail-open: if store_root does not exist or cannot be walked, an empty dict
    is returned without raising. A corrupt or stale on-disk cache degrades to a
    full rebuild (never crashes or serves wrong data).

    Args:
        store_root: Absolute path string to the AC store directory
            (e.g. "/path/to/docs/acceptance-criteria").

    Returns:
        Dict mapping AC id string to full parsed YAML content dict.
        Empty dict when store_root is absent or no parseable .yaml files exist.
    """
    root_path = Path(store_root)

    if not root_path.is_dir():
        return {}

    if _DISK_HELPERS_OK:
        return _get_ac_index_with_disk_cache(store_root, root_path)
    return _get_ac_index_memory_only(store_root, root_path)


def _get_ac_index_with_disk_cache(
    store_root: str, root_path: Path
) -> dict[str, dict[str, Any]]:
    """Implement get_ac_index() with both in-memory and on-disk cache layers.

    Args:
        store_root: Absolute path string (used as cache key).
        root_path: Path object for store_root (already verified to be a directory).

    Returns:
        Full AC id->parsed-dict index.
    """
    # Step 1: fingerprint + yaml file list in one rglob pass.
    fingerprint, yaml_files = compute_fingerprint(root_path)

    # Step 2: in-memory cache check.
    cached = _CACHE.get(store_root)
    if cached is not None:
        cached_fp, cached_index = cached
        if cached_fp == fingerprint:
            return cached_index

    # Step 3: on-disk cache check.
    cache_path = resolve_cache_path(root_path)
    disk_index = load_disk_cache(cache_path, fingerprint)
    if disk_index is not None:
        _CACHE[store_root] = (fingerprint, disk_index)
        return disk_index

    # Step 4: full rebuild.
    index = _build_index_from_files(yaml_files)
    _CACHE[store_root] = (fingerprint, index)
    write_disk_cache(cache_path, fingerprint, index)
    return index


def _get_ac_index_memory_only(
    store_root: str, root_path: Path
) -> dict[str, dict[str, Any]]:
    """Fallback implementation of get_ac_index() using in-memory cache only.

    Used when _ac_store_index_disk failed to import (e.g. file missing from
    sys.path during tests or incomplete deployment). Provides correct but
    non-persistent caching behaviour.

    Args:
        store_root: Absolute path string (used as cache key).
        root_path: Path object for store_root (already verified to be a directory).

    Returns:
        Full AC id->parsed-dict index.
    """
    yaml_files: list[Path] = []
    try:
        yaml_files = list(root_path.rglob("*.yaml"))
    except OSError as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: cannot walk store {root_path}: {exc}\n"
        )
        return {}

    # Use a simple mtime-based key as a best-effort fallback.
    max_mtime: float = 0.0
    for f in yaml_files:
        try:
            mtime = f.stat().st_mtime
            if mtime > max_mtime:
                max_mtime = mtime
        except OSError as exc:
            sys.stderr.write(
                f"[_ac_store_index] WARNING: cannot stat {f} for mtime key: {exc}\n"
            )

    mtime_key = str(max_mtime)
    cached = _CACHE.get(store_root)
    if cached is not None and cached[0] == mtime_key:
        return cached[1]

    index = _build_index_from_files(yaml_files)
    _CACHE[store_root] = (mtime_key, index)
    return index


def invalidate_cache(store_root: str | None = None) -> None:
    """Invalidate the in-memory cache for one or all store roots.

    Clears in-memory entries only; the on-disk cache is left in place (it will
    be treated as a hit if the fingerprint still matches, or a miss on content
    change). Intended for use in unit tests that need deterministic cache state.

    Args:
        store_root: Absolute path string to invalidate. When None, the entire
            in-memory cache is cleared.
    """
    if store_root is None:
        _CACHE.clear()
    else:
        _CACHE.pop(store_root, None)


def invalidate_disk_cache(store_root: str) -> None:
    """Remove the on-disk cache file for a store root (test utility).

    Useful in tests that need to simulate a fresh-process start without a
    pre-existing disk cache. Only removes the file; does not affect the
    in-memory cache (call invalidate_cache() for that).

    Args:
        store_root: Absolute path string of the store whose disk cache to remove.
    """
    if not _DISK_HELPERS_OK:
        return
    cache_path = resolve_cache_path(Path(store_root))
    try:
        cache_path.unlink(missing_ok=True)
    except OSError as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: cannot remove disk cache {cache_path}: {exc}\n"
        )
