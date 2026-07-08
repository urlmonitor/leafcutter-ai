"""
MODULE: _ac_store_index_disk
GOAL: On-disk JSON cache helpers for _ac_store_index. Handles fingerprint
    computation, cache path resolution, and atomic read/write of the cross-process
    AC store index cache.
BUSINESS CONTEXT: The four AC guardrail hooks each run in their own subprocess.
    Without a cross-process cache the parsed AC store index is re-built from YAML
    in every subprocess even when the store has not changed. This module provides
    the disk-cache layer that hook processes #2–#4 use to load a pre-built index
    instead of re-parsing ~1,790 files.
ARCHITECTURE: Standalone stdlib module — no leafcutter imports. Imported only by
    _ac_store_index.py. Extracted to keep _ac_store_index.py within the 400-line
    project file-size limit (check-file-size pre-commit hook).

    Fingerprint: SHA-256 of a deterministic serialisation of the sorted list of
    (relative_path, st_mtime_ns, st_size) tuples for every *.yaml file under
    store_root, plus the resolved absolute store_root path. Captures additions,
    removals, renames, and in-place edits (including same-second edits via
    nanosecond mtime resolution and size change detection).

    Cache file: <git-dir>/ac_store_index_cache.json, written atomically via
    tempfile + os.replace. Falls back to a tempdir path keyed by a hash of the
    store_root when git-dir resolution fails. Format:
      {"schema_version": "3", "fingerprint": <str>, "index": {id: dict, ...}}

    Type-preserving JSON codec: PyYAML parses unquoted ISO dates in YAML files
    (e.g. `created: 2026-06-24`) as datetime.date objects. Plain json.dump raises
    TypeError for these. The codec encodes datetime.date and datetime.datetime as
    tagged JSON objects ({"__pytype__": "date", "value": "2026-06-24"}) and restores
    them on load via object_hook, so a cache-hit value is type-identical to a
    fresh PyYAML parse. Unknown non-serialisable types fall back to str() with a
    WARNING so the write can never silently fail due to an unexpected type.

    Corrupt/stale/schema-mismatched files degrade gracefully to a full rebuild;
    specific exception types caught: json.JSONDecodeError, OSError, KeyError, ValueError.

DOC_LINKS:
  - docs/reference/ac-schema.md

DECISION HISTORY:
  - 2026-06-30 [python-coder/TICKET-20260629-AC_Hook_Store_Index fix-pass]:
    Created by extracting disk-cache and fingerprint helpers from _ac_store_index.py
    to keep that file within the 400-line project limit. Provides compute_fingerprint,
    resolve_cache_path, load_disk_cache, and write_disk_cache.
  - 2026-06-30 [python-coder/TICKET-20260629-AC_Hook_Store_Index fix-pass-2]:
    Added type-preserving JSON codec (_ac_json_default + _ac_json_object_hook) to
    handle datetime.date / datetime.datetime values produced by PyYAML for unquoted
    ISO-date fields in real AC YAML files (e.g. `created: 2026-06-24`). Without the
    codec, json.dump raised TypeError and the H-4 fix silently skipped the write,
    making the cross-process cache a no-op in production. Bumped CACHE_SCHEMA_VERSION
    to "3" so old schema-v2 cache files are treated as a miss on first run after upgrade.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

# Schema version tag embedded in on-disk cache JSON. Bump when the format changes
# so old cache files are treated as a miss rather than loaded with wrong structure.
# v3: added type-preserving codec for datetime.date / datetime.datetime.
CACHE_SCHEMA_VERSION = "3"

# Tag key used in the encoded form of non-native JSON types.
_PYTYPE_KEY = "__pytype__"


# ---------------------------------------------------------------------------
# Type-preserving JSON codec
# ---------------------------------------------------------------------------


def _ac_json_default(obj: Any) -> Any:  # noqa: ANN401
    """JSON encoder ``default`` function for AC index values.

    PyYAML's ``safe_load`` parses unquoted ISO-date strings in YAML
    (e.g. ``created: 2026-06-24``) into ``datetime.date`` objects.
    Plain ``json.dump`` raises ``TypeError`` for these, silently preventing the
    cache file from ever being written.

    This function encodes ``datetime.date`` and ``datetime.datetime`` as
    tagged JSON objects that ``_ac_json_object_hook`` restores on load,
    preserving the Python type across the cache round-trip.  An unknown
    non-serialisable type falls back to ``str()`` with a stderr WARNING so
    the write can never silently fail due to an unexpected field type.

    Args:
        obj: The non-JSON-serialisable object to encode.

    Returns:
        A JSON-serialisable representation of ``obj``.
    """
    # datetime.datetime is a subclass of datetime.date — check it first.
    if isinstance(obj, datetime.datetime):
        return {_PYTYPE_KEY: "datetime", "value": obj.isoformat()}
    if isinstance(obj, datetime.date):
        return {_PYTYPE_KEY: "date", "value": obj.isoformat()}
    # Catch-all: stringify unknown types so the write never fails.
    sys.stderr.write(
        f"[_ac_store_index] WARNING: non-JSON-serialisable value of type "
        f"{type(obj).__name__!r} stringified in cache; field may lose type fidelity "
        "on cache hit vs cache miss\n"
    )
    return str(obj)


def _ac_json_object_hook(dct: dict[str, Any]) -> Any:  # noqa: ANN401
    """JSON decoder ``object_hook`` that restores tagged date/datetime objects.

    Called by ``json.loads`` / ``json.load`` for every decoded JSON object.
    Checks for the ``__pytype__`` tag written by ``_ac_json_default`` and
    reconstructs ``datetime.date`` or ``datetime.datetime`` instances so that
    a cache-hit value is type-identical to a fresh PyYAML parse.

    Args:
        dct: A decoded JSON object dict.

    Returns:
        Restored Python object when the tag is recognised; the original dict
        otherwise (all other AC fields are passed through unchanged).
    """
    pytype = dct.get(_PYTYPE_KEY)
    if pytype == "date":
        try:
            return datetime.date.fromisoformat(dct["value"])
        except (KeyError, ValueError) as exc:
            sys.stderr.write(
                f"[_ac_store_index] WARNING: cannot restore date from cache: {exc}\n"
            )
            return dct
    if pytype == "datetime":
        try:
            return datetime.datetime.fromisoformat(dct["value"])
        except (KeyError, ValueError) as exc:
            sys.stderr.write(
                f"[_ac_store_index] WARNING: cannot restore datetime from cache: {exc}\n"
            )
            return dct
    return dct


def _prepare_for_json(obj: Any) -> Any:  # noqa: ANN401
    """Recursively normalise an AC index value so json.dump can serialise it.

    json.dump's ``default=`` function is only called for non-serialisable
    **values** — it is never called for non-string dict **keys**.  PyYAML can
    produce datetime.date objects as dict keys (e.g. from a mapping whose keys
    are unquoted ISO dates), causing ``TypeError: keys must be str, int, float,
    bool or None, not date`` before ``default=`` is ever consulted.

    This function recursively walks the structure and:
    - Converts datetime.datetime keys/values to the tagged-dict form.
    - Converts datetime.date keys/values to the tagged-dict form.
    - Converts other non-str dict keys to str with a WARNING.
    - Passes through all JSON-native types (str, int, float, bool, None,
      list, dict-with-str-keys) unchanged to avoid unnecessary copies.

    The in-memory index is never mutated — copies are created only for
    containers that need normalisation.

    Args:
        obj: Any Python value that may appear in an AC parsed-YAML dict.

    Returns:
        A JSON-serialisable equivalent of ``obj``.
    """
    # datetime.datetime is a subclass of datetime.date — check it first.
    if isinstance(obj, datetime.datetime):
        return {_PYTYPE_KEY: "datetime", "value": obj.isoformat()}
    if isinstance(obj, datetime.date):
        return {_PYTYPE_KEY: "date", "value": obj.isoformat()}
    if isinstance(obj, dict):
        normalised: dict[str, Any] = {}
        for k, v in obj.items():
            # Normalise key to str.
            if isinstance(k, datetime.datetime):
                str_key = k.isoformat()
            elif isinstance(k, datetime.date):
                str_key = k.isoformat()
            elif isinstance(k, str):
                str_key = k
            else:
                str_key = str(k)
                sys.stderr.write(
                    f"[_ac_store_index] WARNING: non-string dict key of type "
                    f"{type(k).__name__!r} converted to str in cache\n"
                )
            normalised[str_key] = _prepare_for_json(v)
        return normalised
    if isinstance(obj, list):
        return [_prepare_for_json(item) for item in obj]
    # All other types (str, int, float, bool, None) are JSON-native.
    return obj


# ---------------------------------------------------------------------------
# Fingerprint computation
# ---------------------------------------------------------------------------


def compute_fingerprint(store_root: Path) -> tuple[str, list[Path]]:
    """Walk store_root once, compute a SHA-256 fingerprint, and return yaml paths.

    The fingerprint is the SHA-256 digest of a deterministic serialisation of the
    sorted list of (relative_path, st_mtime_ns, st_size) tuples for every *.yaml
    file, concatenated with the resolved absolute store_root path. This captures
    additions, removals, in-place edits (via mtime_ns and size), and renames.

    Using st_mtime_ns instead of st_mtime shrinks the same-second-edit window
    from ~1 s to ~1 ns on Linux and ~100 ns on macOS/Windows.

    Args:
        store_root: Absolute Path to the AC store directory.

    Returns:
        Tuple of (fingerprint_hex_str, yaml_file_list) where:
          - fingerprint_hex_str is the 64-character SHA-256 hex digest.
          - yaml_file_list is the list of all .yaml Paths found.
    """
    entries: list[tuple[str, int, int]] = []  # (rel_path, mtime_ns, size)
    yaml_files: list[Path] = []

    try:
        for yaml_file in store_root.rglob("*.yaml"):
            yaml_files.append(yaml_file)
            try:
                stat = yaml_file.stat()
                rel = str(yaml_file.relative_to(store_root))
                entries.append((rel, stat.st_mtime_ns, stat.st_size))
            except OSError as exc:
                sys.stderr.write(
                    f"[_ac_store_index] WARNING: cannot stat {yaml_file}: {exc}\n"
                )
    except OSError as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: cannot walk store {store_root}: {exc}\n"
        )

    # Sort by relative path for determinism across OS/FS ordering.
    entries.sort(key=lambda t: t[0])
    # Include the resolved absolute store root so two stores with identical
    # contents at different paths produce different fingerprints.
    canonical = str(store_root.resolve())
    payload = canonical + "\n" + "\n".join(f"{r}\t{m}\t{s}" for r, m, s in entries)
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    return fingerprint, yaml_files


# ---------------------------------------------------------------------------
# On-disk cache path resolution
# ---------------------------------------------------------------------------


def resolve_cache_path(store_root: Path) -> Path:
    """Return the path for the on-disk JSON cache file.

    Preferred location: <git-dir>/ac_store_index_cache.json (per-worktree,
    writable, never committed). Falls back to a tmpdir path keyed by a hash of
    store_root when git-dir resolution fails or the directory is not writable.

    Args:
        store_root: Absolute Path to the AC store directory (used as fallback key).

    Returns:
        Path to the on-disk cache file (may or may not exist yet).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            git_dir = result.stdout.strip()
            if git_dir:
                # resolve() converts the relative ".git" returned in the main
                # worktree to an absolute path, so the cache never lands in cwd.
                cache_path = Path(git_dir).resolve() / "ac_store_index_cache.json"
                if os.access(cache_path.parent, os.W_OK):
                    return cache_path
    except (OSError, subprocess.SubprocessError) as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: git rev-parse failed: {exc}\n"
        )

    # Fallback: deterministic path under the system temp dir.
    store_hash = hashlib.sha256(str(store_root.resolve()).encode()).hexdigest()[:16]
    return Path(tempfile.gettempdir()) / f"ac_store_index_{store_hash}.json"


# ---------------------------------------------------------------------------
# On-disk cache read / write
# ---------------------------------------------------------------------------


def load_disk_cache(
    cache_path: Path, expected_fingerprint: str
) -> dict[str, dict[str, Any]] | None:
    """Attempt to load the on-disk cache; return index dict or None on miss/error.

    Returns None (triggering a full rebuild) when:
    - The file does not exist (OSError on read).
    - The JSON is corrupt (json.JSONDecodeError).
    - The stored schema_version or fingerprint does not match (stale/wrong schema).
    - Required keys are absent (KeyError — truncation or schema mismatch).

    Args:
        cache_path: Path to the on-disk JSON cache file.
        expected_fingerprint: The fingerprint computed from the current store state.

    Returns:
        Parsed index dict on a valid cache hit, None on any miss or error.
    """
    try:
        raw = cache_path.read_text(encoding="utf-8")
    except OSError:
        return None

    try:
        data = json.loads(raw, object_hook=_ac_json_object_hook)
        if data["schema_version"] != CACHE_SCHEMA_VERSION:
            return None
        if data["fingerprint"] != expected_fingerprint:
            return None
        index: dict[str, dict[str, Any]] = data["index"]
        return index
    except json.JSONDecodeError as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: corrupt on-disk cache at {cache_path}: {exc}\n"
        )
        return None
    except (KeyError, ValueError) as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: on-disk cache missing key or bad value {exc!r} at "
            f"{cache_path}; rebuilding\n"
        )
        return None


def write_disk_cache(
    cache_path: Path, fingerprint: str, index: dict[str, dict[str, Any]]
) -> None:
    """Write the index to the on-disk cache file atomically.

    Uses a temp file + os.replace for atomicity so a partial write never leaves
    a corrupt cache that blocks future hook invocations.

    Args:
        cache_path: Destination path for the JSON cache file.
        fingerprint: The fingerprint this index was built from.
        index: The full id->parsed-dict index to persist.
    """
    payload = {
        "schema_version": CACHE_SCHEMA_VERSION,
        "fingerprint": fingerprint,
        "index": _prepare_for_json(index),
    }
    tmp_path: str | None = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=cache_path.parent,
            prefix=".ac_store_index_cache_",
            suffix=".tmp",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, ensure_ascii=False, default=_ac_json_default)
        except (OSError, TypeError):
            # Clean up the tmp file on any write failure (OSError = I/O problem;
            # TypeError = non-JSON-serialisable value in index) so we never leak
            # an incomplete file and never reach os.replace with corrupt content.
            if tmp_path is not None:
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
            raise
        os.replace(tmp_path, cache_path)
        tmp_path = None  # ownership transferred; do not unlink on exit
    except (OSError, TypeError) as exc:
        sys.stderr.write(
            f"[_ac_store_index] WARNING: cannot write on-disk cache to "
            f"{cache_path}: {type(exc).__name__}: {exc}\n"
        )
