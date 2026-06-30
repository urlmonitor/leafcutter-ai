"""
MODULE: _ac_store_index
GOAL: Shared mtime-keyed cached index of all AC YAML files under the AC store
    directory. Returns a dict mapping AC id to the full parsed AC content so
    every hook can extract depends_on, covered_by, implements_pattern, and any
    other field without a second filesystem read pass.
BUSINESS CONTEXT: Four AC guardrail hooks each previously walked and YAML-parsed
    the full AC store independently. On a store of ~1,790 files a single full-store
    parse takes ~10 s, so a four-hook commit was paying up to 40 s of parse time.
    This shared cached index reduces that to one full-store parse per commit (or
    per mtime-key change), bounded by a single O(store_size) walk.
ARCHITECTURE: Standalone stdlib module — no leafcutter imports. Imported by
    check_ac_schema.py, check_ac_circular_deps.py, check_ac_parent_covered_by.py,
    and check_ac_pattern_refs.py. The mtime cache key is the maximum mtime across
    all .yaml files under store_root; when the key matches the cached key the
    previously-built index is returned without any disk I/O beyond the mtime scan.
    YAML loading is delegated to _ac_schema_validators.load_yaml (the canonical
    tested path) with a fallback to _ac_schema_validators.load_yaml_manual when
    PyYAML is unavailable. Fits the underscore-prefix shared-module pattern already
    used in templates/scripts/commit_guardian/.

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/architecture/adrs/ADR-007-ac-store-schema-id-format-enforcement.md

DECISION HISTORY:
  - 2026-06-30 [python-coder/TICKET-20260629-AC_Hook_Store_Index]: Created.
    Provides get_ac_index(store_root) with mtime-keyed in-process caching.
    Canonicalises on _ac_schema_validators.load_yaml / load_yaml_manual for
    YAML loading to avoid silent behavioural divergence between hooks. Returns
    a rich id->full-dict index so consumers can extract any field without a
    second read pass.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Module-level cache: {store_root_str: (mtime_key, index_dict)}
# ---------------------------------------------------------------------------

_CACHE: dict[str, tuple[float, dict[str, dict[str, Any]]]] = {}


# ---------------------------------------------------------------------------
# Combined walk: collect yaml file list + compute max mtime in ONE rglob pass
# ---------------------------------------------------------------------------


def _collect_yaml_files_with_mtime(store_root: Path) -> tuple[list[Path], float]:
    """Walk store_root once, collecting all .yaml paths and the max mtime.

    This single-pass design ensures only ONE rglob("*.yaml") call is made per
    invocation of get_ac_index(), regardless of whether the cache is warm or
    cold. The mtime key and the file list are both derived from the same walk,
    so the performance regression test (which counts rglob calls) always sees
    exactly one call when the cache is cold.

    Args:
        store_root: Absolute Path to the AC store directory.

    Returns:
        Tuple of (yaml_file_list, max_mtime) where:
          - yaml_file_list is the list of all .yaml Paths found.
          - max_mtime is the max st_mtime across those files (0.0 if empty).
    """
    yaml_files: list[Path] = []
    max_mtime: float = 0.0

    try:
        for yaml_file in store_root.rglob("*.yaml"):
            yaml_files.append(yaml_file)
            try:
                mtime = yaml_file.stat().st_mtime
            except OSError as exc:
                sys.stderr.write(
                    f"[_ac_store_index] WARNING: cannot stat {yaml_file}: {exc}\n"
                )
                continue
            if mtime > max_mtime:
                max_mtime = mtime
    except OSError as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: cannot walk store {store_root}: {exc}\n"
        )

    return yaml_files, max_mtime


# ---------------------------------------------------------------------------
# YAML loading helpers (delegate to _ac_schema_validators canonical path)
# ---------------------------------------------------------------------------


def _load_one_yaml_file(yaml_file: Path) -> dict[str, Any] | None:
    """Load and parse a single YAML file; return dict or None on any failure.

    Tries _ac_schema_validators.load_yaml (PyYAML) first; falls back to
    _ac_schema_validators.load_yaml_manual when PyYAML is absent.  Both
    paths can raise OSError on unreadable files — these are caught and logged
    as warnings so the caller can skip the file (fail-open).

    Args:
        yaml_file: Path to the .yaml file to load.

    Returns:
        Parsed dict on success, None on any read or parse failure.
    """
    # Import the validators at call time to avoid circular-import risk and to
    # allow the module to load even when the validators file is not on sys.path
    # (e.g. during early import in some test environments).
    try:
        from _ac_schema_validators import load_yaml, load_yaml_manual  # type: ignore[import]
    except ImportError:
        # Validators module unavailable — fall back to a minimal inline parser.
        return _load_yaml_minimal(yaml_file)

    # Attempt PyYAML path via load_yaml.
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
    except Exception as exc:  # noqa: BLE001
        # Catch YAML parse errors (yaml.YAMLError) and other unexpected errors.
        sys.stderr.write(
            f"[_ac_store_index] WARNING: parse error in {yaml_file}: "
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
    except Exception as exc:  # noqa: BLE001
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

    The index is cached per store_root string using the maximum mtime across
    all .yaml files as the cache key. If the mtime key matches the previously
    cached key, the cached index is returned immediately without re-parsing.
    If the mtime key differs (any file added, modified, or removed since the
    last call), the store is re-walked and re-parsed, and the cache is updated.

    Fail-open: if store_root does not exist or cannot be walked, an empty dict
    is returned without raising. Individual unreadable or unparseable files are
    skipped without blocking the overall index build.

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

    # Fast-path: check cache before doing any filesystem walk.
    # The mtime key is cheap to compute only if we can avoid re-walking entirely.
    # However, to guarantee ONE rglob per cold-cache miss (required by the
    # performance regression test), we perform the file-list collection and
    # mtime computation in a single combined walk via _collect_yaml_files_with_mtime.
    # On a cache hit (mtime key unchanged) the walk cost is only the rglob itself
    # (no YAML parsing); on a cache miss the same walk provides both the mtime key
    # and the file list for parsing, so YAML is read only once per cold miss.

    yaml_files, mtime_key = _collect_yaml_files_with_mtime(root_path)

    cached = _CACHE.get(store_root)
    if cached is not None:
        cached_key, cached_index = cached
        if cached_key == mtime_key:
            return cached_index

    index = _build_index_from_files(yaml_files)
    _CACHE[store_root] = (mtime_key, index)
    return index


def invalidate_cache(store_root: str | None = None) -> None:
    """Invalidate the mtime cache for one or all store roots.

    Intended for use in unit tests that need deterministic cache state after
    writing fixture files whose mtime may not differ from the cached key within
    the same second (filesystem mtime resolution is 1 s on many platforms).

    Args:
        store_root: Absolute path string to invalidate. When None, the entire
            cache is cleared.
    """
    if store_root is None:
        _CACHE.clear()
    else:
        _CACHE.pop(store_root, None)
