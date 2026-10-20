"""
MODULE: scripts/build_orchestration/_wvr_records.py
GOAL: Read the AC records the wrong-version scope needs in ONE pass over the AC store, instead
    of one full store parse per record per question.
BUSINESS CONTEXT: TQ-500g-1-v. The writer's ``list`` step took 5 to 11 s (82 s on a larger store)
    because ``resolve_scope`` asked the store for each id three times (declared names, must_catch,
    in_scope_files) and every ask parsed every YAML file until it hit the id. This is the cause
    and this module is the fix; ``list``, ``write`` and the runner all read through it, so their
    names, files and order cannot drift apart.
    The test root is read the same way: only ``.py`` files that mention a wanted id are scanned
    for ``# covers:`` tags (the old reader parsed every test file in the repository).
ARCHITECTURE: One sorted walk of the store (same order as ``scan_ac_store._load_ac_by_id``, so the
    first file carrying an id still wins). A file is parsed only when its bytes contain a wanted
    id, so the walk costs a file read per file rather than a YAML parse. Pure reads, no writes.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import yaml

from _fl_red_baseline_support import _is_declared_test_spec_entry
from done_proof import _EXCLUDED_SCAN_DIRS, _is_excluded_path, _scan_single_test_file


def load_records(ac_ids: list[str], ac_root: Path) -> dict[str, dict | None]:
    """Return ``{ac id: record or None}`` for *ac_ids*, reading the store once.

    Args:
        ac_ids: The requirement ids wanted.
        ac_root: Root of the AC YAML store.

    Returns:
        A record per id, in the order of *ac_ids*; ``None`` when no file carries the id as its
        ``id`` or the file cannot be parsed (the same answer ``_load_ac_by_id`` gives).
    """
    pending = list(dict.fromkeys(ac_ids))
    found: dict[str, dict | None] = {}
    for path in sorted(ac_root.rglob("*.yaml")) if pending else ():
        try:
            data = path.read_bytes()
        except OSError:
            continue
        hits = {i for i in pending if i.encode("utf-8") in data}  # not findall: it stops at the first alternative
        record = _parse(path, data) if hits else None
        for ac_id in [i for i in pending if i in hits]:
            if record is not None and record.get("id") == ac_id:
                found[ac_id] = record
                pending.remove(ac_id)
        if not pending:
            break
    return {i: found.get(i) for i in ac_ids}


def _alternation(ids: list[str]) -> re.Pattern[bytes]:
    """Return one compiled pattern matching any of *ids* literally (bytes)."""
    return re.compile(b"|".join(re.escape(i.encode("utf-8")) for i in ids))


def _parse(path: Path, data: bytes) -> dict | None:
    """Parse one AC file like ``scan_ac_store._load_ac`` (SafeLoader result plus ``_path``), else ``None``."""
    try:
        loaded = yaml.load(data, Loader=getattr(yaml, "CSafeLoader", yaml.SafeLoader))  # noqa: S506 -- a safe loader
    except yaml.YAMLError as exc:
        print(f"ERROR: {path}: {exc}", file=sys.stderr)
        return None
    if not isinstance(loaded, dict):
        return None
    loaded["_path"] = str(path)
    return loaded


def declared_names(records: dict[str, dict | None]) -> tuple[set[str], list[str]]:
    """Return ``(declared test names, ids with no record)`` for *records*.

    Same rule as ``_fl_red_baseline_support._load_declared_test_names``: a ``test_spec`` entry
    is declared by a non-empty ``must_catch`` or ``angle: discrimination``.
    """
    declared: set[str] = set()
    unavailable: list[str] = []
    for ac_id, record in records.items():
        if record is None:
            unavailable.append(ac_id)
            continue
        for entry in record.get("test_spec") or []:
            name = entry.get("name") if isinstance(entry, dict) else None
            if name and _is_declared_test_spec_entry(entry):
                declared.add(name)
    return declared, unavailable


def covers_tags(test_root: Path, ac_ids: list[str]) -> list[dict]:
    """Return the ``# covers:`` tags of *ac_ids* under *test_root* (same dicts and order as the full scan).

    Walks the tree pruning the excluded directories of ``done_proof`` (``.git``, ``node_modules``,
    ``.venv`` and the like) and scans only the ``.py`` files whose bytes contain a wanted id, in
    sorted path order. A tag of another id is never kept by the caller, so skipping those files
    changes nothing but the time taken.
    """
    if not ac_ids or _is_excluded_path(test_root):
        return []
    wanted = _alternation(ac_ids)
    files: list[Path] = []
    for folder, dirs, names in os.walk(test_root):
        dirs[:] = [d for d in dirs if d not in _EXCLUDED_SCAN_DIRS]
        for name in names:
            path = Path(folder) / name
            if name.endswith(".py") and _mentions(path, wanted):
                files.append(path)
    tags: list[dict] = []
    for path in sorted(files):
        tags.extend(_scan_single_test_file(path))
    return tags


_TAG_BYTES = re.compile(rb"(?:#|//)\s*covers:\s*(\S+)")


def _mentions(path: Path, wanted: re.Pattern[bytes]) -> bool:
    """Return whether a ``covers:`` tag of *path* contains a wanted id (``False`` when unreadable)."""
    try:
        data = path.read_bytes()
    except OSError:
        return False
    tokens = _TAG_BYTES.findall(data)
    return bool(tokens) and wanted.search(b" ".join(tokens)) is not None
