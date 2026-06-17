"""
MODULE: check_ac_pattern_refs
GOAL: Pre-commit hook that validates implements_pattern references in AC YAML
    files point to existing ACs with parameterized slots in the store, and
    blocks deletion of pattern ACs that are still referenced by consuming ACs.
BUSINESS CONTEXT: Pattern reuse (ACS-500a) allows AC authors to declare a
    shared behavior once in a pattern AC and have consuming ACs instantiate it
    via implements_pattern + pattern_bindings. A dangling reference (pointing to
    a non-existent AC ID) or a reference to an AC without parameterized slots
    silently breaks the pattern-reuse contract, leading to orphaned bindings and
    untestable specifications. Deleting a pattern AC while consumers still
    reference it creates the same dangling-reference failure. This hook enforces
    both directions of the contract at commit time so broken references never
    enter the repository.
ARCHITECTURE: Reads staged .yaml files from docs/acceptance-criteria/ (via git
    diff --cached or HOOK_TEST_FILES env var for testing). Two checks run:
    (1) For each added/modified file, loads the YAML and checks the
    implements_pattern field. If present, searches the entire AC store tree for
    a YAML file whose `id` field matches the referenced AC ID. Validates that
    the referenced AC has parameterized slots (either via a non-empty
    pattern_slots field, or via {word} placeholders in the criteria field).
    (2) For each deleted file, reads its id from git HEAD content, then scans
    the remaining AC store for any ACs with implements_pattern pointing at that
    id (delegated to _ac_pattern_deletion_guard.py). Blocks with
    "Cannot delete <id>: still referenced by N consuming ACs" if consumers
    exist. Emits a JSON block decision to stdout and diagnostic detail to stderr
    on violations. Fail-open: unexpected exceptions exit 0.

Exit codes:
    0 - All staged AC YAML files pass pattern reference validation (or no AC
        files with implements_pattern are staged)
    1 - One or more implements_pattern reference violations detected

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_ac_pattern_refs.py

DOC_LINKS:
  - docs/acceptance-criteria/ac-store/ACS-500-pattern-reuse/
  - docs/reference/ac-schema.md

DECISION HISTORY:
  - 2026-06-11 [python-coder/ACS-500a-3]: Created check_ac_pattern_refs.py.
    Implements implements_pattern reference validation: checks that referenced
    AC ID exists in the store and that the referenced AC has parameterized slots.
    Two error paths: dangling reference (ID not found) and slot-less reference
    (referenced AC has no {word} patterns or pattern_slots). Fail-open on any
    unexpected exception (mirrors check_ac_governance.py pattern).
  - 2026-06-16 [python-coder/ACS-500d-1-i]: Added deletion-guard check
    (ACS-500d-1-i). Deletion logic is extracted into _ac_pattern_deletion_guard.py
    to stay within the 400-line file limit. This module delegates to
    _ac_pattern_deletion_guard.check_pattern_deletion() and
    _ac_pattern_deletion_guard._get_deleted_ac_paths(). Injected YAML loader
    functions keep the helper module decoupled from this module's internals.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from _ac_pattern_deletion_guard import (
    _get_deleted_ac_paths,
    check_pattern_deletion,
)

_AC_STORE_DIR = "docs/acceptance-criteria"
_HOOK_PREFIX = "[check-ac-pattern-refs]"
_SLOT_PATTERN = re.compile(r"\{[a-zA-Z_][a-zA-Z0-9_]*\}")
"""Regex that matches a named placeholder slot in curly braces, e.g. {columns}."""


# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------


def _find_project_root() -> Path | None:
    """Find the project root (directory containing .git or CLAUDE.md).

    Returns:
        Absolute Path of the project root, or None if not found.
    """
    env_root = os.environ.get("HOOK_ROOT")
    if env_root:
        return Path(env_root)

    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            return ancestor

    return None


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML)
# ---------------------------------------------------------------------------


def _load_yaml_safe(content: str, source_label: str) -> dict | None:
    """Parse a YAML string, returning a dict or None on failure.

    Args:
        content: Raw YAML string.
        source_label: Human-readable label for error messages (e.g. file path).

    Returns:
        Parsed dict on success, None on parse failure (fail-open).
    """
    try:
        import yaml  # type: ignore[import]

        try:
            data = yaml.safe_load(content)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError as exc:
            print(
                f"{_HOOK_PREFIX} WARNING: YAML parse error in {source_label}: {exc}",
                file=sys.stderr,
            )
            return None
    except ImportError:
        pass  # PyYAML absent — fall through to minimal parser

    # Minimal fallback parser: handles simple top-level scalar fields only.
    result: dict = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result or None


def _load_yaml_from_path(file_path: Path) -> dict | None:
    """Load and parse YAML from a file path.

    Args:
        file_path: Absolute or relative path to the YAML file.

    Returns:
        Parsed dict on success, None on failure (fail-open).
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {file_path}: {exc}",
            file=sys.stderr,
        )
        return None
    return _load_yaml_safe(content, source_label=str(file_path))


# ---------------------------------------------------------------------------
# Staged file detection
# ---------------------------------------------------------------------------


def _get_staged_ac_paths() -> list[str]:
    """Return staged .yaml file paths under docs/acceptance-criteria/.

    Uses HOOK_TEST_FILES env var (OS path-separator-separated or
    newline-separated list) when set for unit testing.

    Returns:
        List of path strings (absolute when from HOOK_TEST_FILES,
        relative to repo root when from git diff --cached).
    """
    test_files = os.environ.get("HOOK_TEST_FILES")
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
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not run git diff: {exc}",
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


# ---------------------------------------------------------------------------
# AC store index — find all AC YAML files and build an id → path map
# ---------------------------------------------------------------------------


def _build_ac_store_index(ac_store_root: Path) -> dict[str, Path]:
    """Walk the AC store and return a mapping of AC id → file path.

    Parses every .yaml file under ac_store_root to extract the top-level `id`
    field. Files that cannot be parsed are silently skipped (fail-open).

    Args:
        ac_store_root: Absolute path to the docs/acceptance-criteria/ directory.

    Returns:
        Dict mapping AC id strings to their absolute file paths.
    """
    index: dict[str, Path] = {}
    try:
        yaml_files = list(ac_store_root.rglob("*.yaml"))
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not scan AC store at {ac_store_root}: {exc}",
            file=sys.stderr,
        )
        return index

    for yaml_file in yaml_files:
        data = _load_yaml_from_path(yaml_file)
        if data is None:
            continue
        ac_id = data.get("id")
        if ac_id and isinstance(ac_id, str):
            index[ac_id.strip()] = yaml_file

    return index


# ---------------------------------------------------------------------------
# Slot detection helpers
# ---------------------------------------------------------------------------


def _has_parameterized_slots(ac_data: dict) -> bool:
    """Return True if the AC has parameterized slots.

    An AC has parameterized slots if either:
    - Its pattern_slots field is a non-empty list, OR
    - Its criteria field contains at least one {word} placeholder.

    Args:
        ac_data: Parsed YAML dict of the referenced AC.

    Returns:
        True if the AC has parameterized slots, False otherwise.
    """
    pattern_slots = ac_data.get("pattern_slots")
    if isinstance(pattern_slots, list) and len(pattern_slots) > 0:
        return True

    criteria = ac_data.get("criteria")
    if isinstance(criteria, str) and _SLOT_PATTERN.search(criteria):
        return True

    return False


# ---------------------------------------------------------------------------
# Per-file validation
# ---------------------------------------------------------------------------


def _check_file(
    file_path: str,
    ac_store_index: dict[str, Path],
) -> list[str]:
    """Validate implements_pattern reference in a single staged AC YAML file.

    Checks:
    1. If implements_pattern is set, the referenced AC ID must exist in the store.
    2. The referenced AC must have parameterized slots (pattern_slots non-empty
       OR criteria contains {word} placeholders).

    Args:
        file_path: Absolute path to the staged AC YAML file.
        ac_store_index: Pre-built mapping of AC id → file path for the store.

    Returns:
        List of human-readable violation strings. Empty list means no violations.
    """
    violations: list[str] = []

    path = Path(file_path)
    data = _load_yaml_from_path(path)
    if data is None:
        return []

    implements_pattern = data.get("implements_pattern")
    if not implements_pattern or not isinstance(implements_pattern, str):
        return []

    implements_pattern = implements_pattern.strip()
    if not implements_pattern:
        return []

    file_label = path.name

    # Check 1: referenced AC must exist in the store
    if implements_pattern not in ac_store_index:
        violations.append(
            f"file '{file_label}': implements_pattern '{implements_pattern}' "
            f"references a non-existent AC in the store"
        )
        return violations

    # Check 2: referenced AC must have parameterized slots
    referenced_path = ac_store_index[implements_pattern]
    referenced_data = _load_yaml_from_path(referenced_path)
    if referenced_data is None:
        # Cannot parse — fail-open for this check
        return violations

    if not _has_parameterized_slots(referenced_data):
        violations.append(
            f"file '{file_label}': implements_pattern '{implements_pattern}' "
            f"references an AC whose criteria contains no parameterized slots"
        )

    return violations


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _emit_block_decision(violations: list[str]) -> None:
    """Print the PreToolUse JSON block decision to stdout.

    stdout carries the structured block decision per the PreToolUse hook contract.
    stderr carries diagnostic detail for humans and CI logs.

    Args:
        violations: List of violation description strings.
    """
    reason = (
        "AC pattern reference violation: "
        + "; ".join(violations)
    )
    decision = {"decision": "block", "reason": reason}
    print(json.dumps(decision))

    print(
        f"\n{_HOOK_PREFIX} BLOCKED — implements_pattern reference violation",
        file=sys.stderr,
    )
    for v in violations:
        print(f"  {v}", file=sys.stderr)
    print(
        "\nEnsure the referenced AC ID exists in the store and its criteria "
        "contains at least one {placeholder} slot (or pattern_slots is non-empty). "
        "When deleting a pattern AC, first remove all implements_pattern references "
        "to it from consuming ACs.",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the AC pattern reference check (add/modify and deletion directions).

    Returns:
        0 when all staged AC YAML files pass validation (or no AC files staged),
        1 when one or more violations are detected.
    """
    if os.environ.get("HOOK_SIMULATE_EXCEPTION"):
        raise RuntimeError("HOOK_SIMULATE_EXCEPTION")  # noqa: TRY003

    # Discover AC store directory (early exit if absent)
    project_root = _find_project_root()
    if project_root is None:
        ac_store = Path(_AC_STORE_DIR)
    else:
        ac_store = project_root / _AC_STORE_DIR

    if not ac_store.is_dir():
        return 0

    all_violations: list[str] = []

    # ------------------------------------------------------------------
    # Check 1: deletion guard — block if a deleted pattern AC still has
    # consumers with implements_pattern referencing it.
    # ------------------------------------------------------------------
    deleted_paths = _get_deleted_ac_paths()
    if deleted_paths:
        deletion_violations = check_pattern_deletion(
            deleted_relative_paths=deleted_paths,
            ac_store_root=ac_store,
            project_root=project_root,
            load_yaml_safe_fn=_load_yaml_safe,
            load_yaml_from_path_fn=_load_yaml_from_path,
        )
        all_violations.extend(deletion_violations)

    # ------------------------------------------------------------------
    # Check 2: forward-reference guard — staged added/modified AC YAML
    # files must not contain dangling implements_pattern references.
    # ------------------------------------------------------------------
    staged_paths = _get_staged_ac_paths()

    if staged_paths:
        # Quick pre-scan: only build the full index if needed
        files_with_pattern: list[str] = []
        for staged_path in staged_paths:
            abs_path = staged_path
            if not Path(staged_path).is_absolute():
                if project_root:
                    abs_path = str(project_root / staged_path)
            data = _load_yaml_from_path(Path(abs_path))
            if data and data.get("implements_pattern"):
                files_with_pattern.append(abs_path)

        if files_with_pattern:
            # Build the full AC store index once
            ac_store_index = _build_ac_store_index(ac_store)

            # Merge staged files into the index so that a staged AC can
            # reference another AC also staged in the same commit.
            for staged_path in staged_paths:
                abs_path = staged_path
                if not Path(staged_path).is_absolute():
                    if project_root:
                        abs_path = str(project_root / staged_path)
                p = Path(abs_path)
                data = _load_yaml_from_path(p)
                if data is None:
                    continue
                ac_id = data.get("id")
                if (
                    ac_id
                    and isinstance(ac_id, str)
                    and ac_id.strip() not in ac_store_index
                ):
                    ac_store_index[ac_id.strip()] = p

            for abs_path in files_with_pattern:
                file_violations = _check_file(abs_path, ac_store_index)
                all_violations.extend(file_violations)

    if not all_violations:
        return 0

    _emit_block_decision(all_violations)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"{_HOOK_PREFIX} unexpected error (fail-open): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
