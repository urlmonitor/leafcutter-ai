"""
MODULE: _ac_pattern_deletion_guard
GOAL: Helper functions for the AC pattern deletion guard in check_ac_pattern_refs.py.
    Detects when a pattern AC YAML file is staged for deletion and blocks the commit
    if any surviving AC in the store still references it via implements_pattern.
BUSINESS CONTEXT: Deleting a pattern AC while consumers still point at it via
    implements_pattern creates dangling references that silently break the
    pattern-reuse contract (ACS-500a). This guard enforces referential integrity
    from the deletion direction, complementing the forward-reference check in
    check_ac_pattern_refs.py (ACS-500a-3).
ARCHITECTURE: Standalone helper module imported by check_ac_pattern_refs.py. All
    functions are pure or perform a single subprocess call (fail-open on error).
    Uses HOOK_DELETED_FILES env var for unit-test isolation (mirrors the
    HOOK_TEST_FILES convention used by _get_staged_ac_paths). For each deleted
    AC file, reads the file's id from git show HEAD:<path> so the id is available
    even though the file has been removed from the working tree. Scans all
    remaining YAML files in docs/acceptance-criteria/ for implements_pattern
    references. Excluded paths (files also being deleted in the same commit) are
    not counted as blocking consumers.

DOC_LINKS:
  - docs/acceptance-criteria/ac-store/ACS-500-shared-pattern-specs/
  - docs/reference/ac-schema.md

DECISION HISTORY:
  - 2026-06-16 [python-coder/ACS-500d-1-i]: Created as a split of
    check_ac_pattern_refs.py to stay within the 400-line file limit.
    Implements _get_deleted_ac_paths, _get_head_yaml_content,
    _find_consumers_of_pattern, and check_pattern_deletion.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_AC_STORE_DIR = "docs/acceptance-criteria"
_HOOK_PREFIX = "[check-ac-pattern-refs]"


def _get_deleted_ac_paths() -> list[str]:
    """Return staged .yaml file paths under docs/acceptance-criteria/ that are being deleted.

    Uses HOOK_DELETED_FILES env var (OS path-separator-separated or
    newline-separated list) when set for unit testing.

    Returns:
        List of relative path strings for deleted AC YAML files.
    """
    test_files = os.environ.get("HOOK_DELETED_FILES")
    if test_files:
        raw_paths = test_files.replace(os.pathsep, "\n").splitlines()
        return [
            p.strip()
            for p in raw_paths
            if p.strip() and p.strip().endswith(".yaml")
        ]

    if os.environ.get("HOOK_NO_GIT"):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=D"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not run git diff (deletion check): {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
        and _AC_STORE_DIR in line
        and line.strip().endswith(".yaml")
    ]


def _get_head_yaml_content(relative_path: str) -> str | None:
    """Read the YAML content of a file as it existed at HEAD (before deletion).

    Args:
        relative_path: Path relative to the git repository root.

    Returns:
        File content as a string, or None on failure (fail-open).
    """
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{relative_path}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not read HEAD:{relative_path}: {exc}",
            file=sys.stderr,
        )
        return None

    if result.returncode != 0:
        print(
            f"{_HOOK_PREFIX} WARNING: git show HEAD:{relative_path} failed "
            f"(exit {result.returncode}): {result.stderr.strip()}",
            file=sys.stderr,
        )
        return None

    return result.stdout


def _find_consumers_of_pattern(
    pattern_id: str,
    ac_store_root: Path,
    excluded_paths: set[str],
    load_yaml_fn: object,
) -> list[str]:
    """Scan the AC store and return IDs of ACs whose implements_pattern matches pattern_id.

    Only files that still exist on disk (not in excluded_paths) are scanned.

    Args:
        pattern_id: The AC ID of the pattern being deleted.
        ac_store_root: Absolute path to the docs/acceptance-criteria/ directory.
        excluded_paths: Set of absolute path strings for files being deleted
            in the same commit (excluded from consumer scan — deleting the
            consumer alongside the pattern is not a blocking reference).
        load_yaml_fn: Callable matching signature ``(Path) -> dict | None``.
            Injected to reuse the YAML loader from the parent module.

    Returns:
        Sorted list of AC id strings that reference pattern_id via implements_pattern.
    """
    consumer_ids: list[str] = []

    try:
        yaml_files = list(ac_store_root.rglob("*.yaml"))
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not scan AC store at {ac_store_root}: {exc}",
            file=sys.stderr,
        )
        return consumer_ids

    for yaml_file in yaml_files:
        abs_str = str(yaml_file.resolve())
        if abs_str in excluded_paths:
            continue

        data = load_yaml_fn(yaml_file)
        if data is None:
            continue

        impl = data.get("implements_pattern")
        if not isinstance(impl, str):
            continue
        if impl.strip() == pattern_id:
            ac_id = data.get("id")
            if ac_id and isinstance(ac_id, str):
                consumer_ids.append(ac_id.strip())

    return sorted(consumer_ids)


def check_pattern_deletion(
    deleted_relative_paths: list[str],
    ac_store_root: Path,
    project_root: Path | None,
    load_yaml_safe_fn: object,
    load_yaml_from_path_fn: object,
) -> list[str]:
    """Check each deleted AC YAML for referencing consumers still in the store.

    For each deleted file, reads the AC id from git HEAD content, then
    searches the remaining store for ACs whose implements_pattern points
    at that id. Returns one violation string per blocked deletion.

    The violation message follows the exact format required by ACS-500d-1-i:
    ``"Cannot delete <id>: still referenced by N consuming ACs"`` followed by
    the list of referencing AC IDs.

    Args:
        deleted_relative_paths: List of repo-relative paths for deleted YAML files.
        ac_store_root: Absolute path to the docs/acceptance-criteria/ directory.
        project_root: Absolute path to the project root, or None if unknown.
        load_yaml_safe_fn: Callable ``(str, str) -> dict | None`` for parsing
            YAML strings (reuses the parent module's implementation).
        load_yaml_from_path_fn: Callable ``(Path) -> dict | None`` for loading
            YAML from a file path (injected from parent module).

    Returns:
        List of human-readable violation strings (one per blocked deletion).
    """
    violations: list[str] = []

    # Build the set of absolute paths being deleted so _find_consumers_of_pattern
    # can exclude them from the scan. A consumer deleted in the same commit as the
    # pattern it references does not count as a blocking reference.
    excluded_abs: set[str] = set()
    for rel_path in deleted_relative_paths:
        if project_root:
            excluded_abs.add(str((project_root / rel_path).resolve()))

    for rel_path in deleted_relative_paths:
        head_content = _get_head_yaml_content(rel_path)
        if head_content is None:
            # Fail-open: cannot read HEAD content; skip this file
            continue

        data = load_yaml_safe_fn(head_content, f"HEAD:{rel_path}")
        if data is None:
            continue

        pattern_id = data.get("id")
        if not pattern_id or not isinstance(pattern_id, str):
            continue
        pattern_id = pattern_id.strip()

        consumer_ids = _find_consumers_of_pattern(
            pattern_id=pattern_id,
            ac_store_root=ac_store_root,
            excluded_paths=excluded_abs,
            load_yaml_fn=load_yaml_from_path_fn,
        )

        if consumer_ids:
            count = len(consumer_ids)
            noun = "consuming AC" if count == 1 else "consuming ACs"
            violations.append(
                f"Cannot delete {pattern_id}: still referenced by {count} {noun}. "
                f"Referencing IDs: {', '.join(consumer_ids)}"
            )

    return violations
