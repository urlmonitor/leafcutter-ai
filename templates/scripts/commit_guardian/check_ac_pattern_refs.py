"""
MODULE: check_ac_pattern_refs
GOAL: Pre-commit hook that validates implements_pattern references in AC YAML files
    and blocks deletion of pattern ACs that are still referenced by consuming ACs.
BUSINESS CONTEXT: Pattern ACs are the canonical single source of truth for reusable
    behaviors. When a consuming AC references a pattern via implements_pattern, that
    reference must point to a real pattern AC. Allowing dangling references or silent
    deletion of referenced patterns would break the AC store's referential integrity
    and cause build agents to fail when looking up pattern slot definitions.
ARCHITECTURE: Reads staged .yaml files from docs/acceptance-criteria/ (via
    git diff --cached or HOOK_TEST_FILES / HOOK_DELETED_FILES env vars for testing).
    For each staged AC file with implements_pattern set:
      - Checks the referenced AC ID exists anywhere in the store.
      - Checks the referenced AC passes _has_parameterized_slots (non-empty
        pattern_slots list OR at least one {word} placeholder in criteria).
    For each AC file being deleted (detected via git diff --cached --name-status):
      - Checks whether any surviving AC in the store still references this AC's
        id via implements_pattern.
      - If so: emits "Cannot delete <id>: still referenced by N consuming ACs"
        and exits 1.
    Fail-open: any unexpected parse error is logged as a warning and the file is
    skipped (exits 0). This prevents CI storms caused by unrelated YAML issues.

Exit codes:
    0 - All staged AC YAML files pass reference checks (or no AC files staged)
    1 - One or more reference violations detected

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_ac_pattern_refs.py

DOC_LINKS:
  - docs/acceptance-criteria/ac-store/ACS-500-pattern-reuse/

DECISION HISTORY:
  - 2026-06-17 [llm-expert/ACS-500f-2]: Created check_ac_pattern_refs.py.
    Implements _has_parameterized_slots predicate that matches the
    business-analyst pattern-first inventory scan predicate exactly:
    non-empty pattern_slots list OR {word} placeholder in criteria.
    Fail-open on parse errors (exits 0 with stderr warning per ACS-500a-3).
    Deletion guard: checks surviving ACs reference-count before allowing
    pattern AC deletion (ACS-500d-1-i).
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_AC_STORE_DIR = "docs/acceptance-criteria"
_HOOK_PREFIX = "[check-ac-pattern-refs]"

# Regex matching a {word} placeholder: { followed by a Python identifier }
_PLACEHOLDER_PATTERN = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML)
# ---------------------------------------------------------------------------


def _load_yaml_safe(content: str, source_label: str) -> dict | None:
    """Parse a YAML string, returning a dict or None on failure.

    Args:
        content: Raw YAML string to parse.
        source_label: Human-readable label for error messages (e.g. file path).

    Returns:
        Parsed dict on success, None on parse failure (fail-open: caller skips file).
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
    # Sufficient for reading id, implements_pattern, pattern_slots, criteria.
    result: dict = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result or None


def _load_file(file_path: str) -> dict | None:
    """Read and parse a YAML file from disk.

    Args:
        file_path: Absolute or repo-relative path to the YAML file.

    Returns:
        Parsed dict on success, None on read or parse failure.
    """
    path = Path(file_path)
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {file_path}: {exc}",
            file=sys.stderr,
        )
        return None
    return _load_yaml_safe(content, source_label=str(file_path))


# ---------------------------------------------------------------------------
# Pattern-detection predicate (must match business-analyst inventory scan)
# ---------------------------------------------------------------------------


def _has_parameterized_slots(ac_data: dict) -> bool:
    """Return True when ac_data represents a pattern AC.

    An AC is a pattern when EITHER:
    - Its pattern_slots field is a non-empty list, OR
    - Its criteria field contains at least one {word} placeholder (where
      "word" is any Python identifier matching [A-Za-z_][A-Za-z0-9_]*).

    This predicate is the single source of truth used by both the
    business-analyst pattern-first inventory scan (§1 Step 7) and this
    deployed hook. Any change to one MUST be reflected in the other
    (ACS-500f-2).

    Args:
        ac_data: Parsed AC YAML dict.

    Returns:
        True if the AC qualifies as a pattern AC, False otherwise.
    """
    pattern_slots = ac_data.get("pattern_slots")
    if isinstance(pattern_slots, list) and len(pattern_slots) > 0:
        return True

    criteria = ac_data.get("criteria", "")
    if _PLACEHOLDER_PATTERN.search(str(criteria)):
        return True

    return False


# ---------------------------------------------------------------------------
# Project root and AC store discovery
# ---------------------------------------------------------------------------


def _find_project_root() -> Path | None:
    """Find the project root by walking up from cwd until .git or CLAUDE.md.

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


def _iter_all_ac_files(project_root: Path) -> list[Path]:
    """Return all .yaml files under the AC store directory.

    Args:
        project_root: Absolute path to the project root.

    Returns:
        List of absolute Path objects for every .yaml file in the AC store.
    """
    ac_store = project_root / _AC_STORE_DIR
    if not ac_store.is_dir():
        return []
    return list(ac_store.rglob("*.yaml"))


# ---------------------------------------------------------------------------
# Staged file detection (added/modified and deleted)
# ---------------------------------------------------------------------------


def _get_staged_ac_paths() -> list[str]:
    """Return added/modified .yaml file paths under docs/acceptance-criteria/.

    Uses HOOK_TEST_FILES env var for unit testing.

    Returns:
        List of path strings relative to repo root (or absolute from env var).
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


def _get_deleted_ac_paths() -> list[str]:
    """Return deleted .yaml file paths under docs/acceptance-criteria/.

    Uses HOOK_DELETED_FILES env var for unit testing.

    Returns:
        List of path strings relative to repo root (or absolute from env var).
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
            f"{_HOOK_PREFIX} WARNING: could not run git diff for deletions: {exc}",
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


def _get_deleted_ac_id_from_head(rel_path: str, project_root: Path) -> str | None:
    """Read the id field from the HEAD version of a deleted AC file.

    Args:
        rel_path: Repo-relative path of the deleted file.
        project_root: Absolute path to the project root.

    Returns:
        The AC id string, or None if not readable or not parseable.
    """
    if os.environ.get("HOOK_NO_GIT"):
        return None

    env_root = os.environ.get("HOOK_ROOT")
    git_cmd = ["git"]
    if env_root:
        git_cmd = ["git", "-C", env_root]

    try:
        result = subprocess.run(
            [*git_cmd, "show", f"HEAD:{rel_path}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: git show failed for {rel_path}: {exc}",
            file=sys.stderr,
        )
        return None

    if result.returncode != 0:
        return None

    data = _load_yaml_safe(result.stdout, source_label=f"HEAD:{rel_path}")
    if data is None:
        return None
    ac_id = data.get("id")
    return str(ac_id) if ac_id is not None else None


# ---------------------------------------------------------------------------
# Core check logic
# ---------------------------------------------------------------------------


def _check_implements_pattern_refs(
    staged_paths: list[str],
    project_root: Path,
) -> list[str]:
    """Validate implements_pattern references in staged AC files.

    For each staged file that has implements_pattern set:
    1. Check that the referenced AC ID exists in the store.
    2. Check that the referenced AC _has_parameterized_slots.

    Args:
        staged_paths: Repo-relative paths of staged AC YAML files.
        project_root: Absolute path to the project root.

    Returns:
        List of human-readable violation strings. Empty list = no violations.
    """
    violations: list[str] = []
    all_ac_files = _iter_all_ac_files(project_root)

    # Build an index of all ACs in the store: id -> parsed dict
    ac_index: dict[str, dict] = {}
    for ac_file in all_ac_files:
        data = _load_file(str(ac_file))
        if data is None:
            continue  # fail-open: skip unparseable files
        ac_id = data.get("id")
        if ac_id is not None:
            ac_index[str(ac_id)] = data

    for rel_path in staged_paths:
        abs_path = rel_path
        if not Path(rel_path).is_absolute():
            abs_path = str(project_root / rel_path)

        staged_data = _load_file(abs_path)
        if staged_data is None:
            continue  # fail-open: skip unparseable files

        implements_pattern = staged_data.get("implements_pattern")
        if implements_pattern is None:
            continue  # no pattern reference — nothing to check

        ref_id = str(implements_pattern)
        file_label = Path(rel_path).name

        # Check 1: referenced pattern AC must exist
        if ref_id not in ac_index:
            violations.append(
                f"file '{file_label}': implements_pattern references '{ref_id}' "
                f"which does not exist in the AC store"
            )
            continue

        # Check 2: referenced AC must have parameterized slots
        pattern_data = ac_index[ref_id]
        if not _has_parameterized_slots(pattern_data):
            violations.append(
                f"file '{file_label}': implements_pattern references '{ref_id}' "
                f"but '{ref_id}' is not a pattern AC (it has neither a non-empty "
                f"pattern_slots list nor any {{word}} placeholder in its criteria)"
            )

    return violations


def _check_pattern_deletion_safety(
    deleted_paths: list[str],
    project_root: Path,
) -> list[str]:
    """Block deletion of a pattern AC when consuming ACs still reference it.

    For each deleted file, reads its id from HEAD, then counts how many
    surviving (non-deleted) ACs in the store reference it via implements_pattern.

    Args:
        deleted_paths: Repo-relative paths of deleted AC YAML files.
        project_root: Absolute path to the project root.

    Returns:
        List of human-readable violation strings. Empty list = no violations.
    """
    if not deleted_paths:
        return []

    violations: list[str] = []
    deleted_rel_set = {p.lstrip("/") for p in deleted_paths}

    # Collect ids of all deleted ACs
    deleted_ids: set[str] = set()
    for rel_path in deleted_paths:
        ac_id = _get_deleted_ac_id_from_head(rel_path, project_root)
        if ac_id is not None:
            deleted_ids.add(ac_id)

    if not deleted_ids:
        return []

    # Find all surviving AC files (not in the deleted set)
    all_ac_files = _iter_all_ac_files(project_root)
    surviving_files = [
        f for f in all_ac_files
        if not any(
            str(f).endswith(rel.lstrip("/"))
            or rel.lstrip("/") in str(f)
            for rel in deleted_rel_set
        )
    ]

    # Count references from surviving ACs to each deleted id
    ref_counts: dict[str, int] = {ac_id: 0 for ac_id in deleted_ids}
    for ac_file in surviving_files:
        data = _load_file(str(ac_file))
        if data is None:
            continue  # fail-open: skip unparseable files
        ref = data.get("implements_pattern")
        if ref is not None and str(ref) in deleted_ids:
            ref_counts[str(ref)] += 1

    for deleted_id, count in ref_counts.items():
        if count > 0:
            violations.append(
                f"Cannot delete '{deleted_id}': still referenced by {count} consuming AC"
                + ("s" if count != 1 else "")
            )

    return violations


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the AC pattern-reference check.

    Returns:
        0 when all staged AC YAML files pass reference checks (or no files staged),
        1 when one or more violations are detected.
    """
    project_root = _find_project_root()
    if project_root is None:
        ac_store = Path(_AC_STORE_DIR)
    else:
        ac_store = project_root / _AC_STORE_DIR

    if not ac_store.is_dir():
        # No AC store present — exit 0 without error
        return 0

    staged_paths = _get_staged_ac_paths()
    deleted_paths = _get_deleted_ac_paths()

    if not staged_paths and not deleted_paths:
        return 0  # Nothing to check

    root = project_root if project_root is not None else Path.cwd()

    all_violations: list[str] = []

    # Check implements_pattern references in staged files
    if staged_paths:
        ref_violations = _check_implements_pattern_refs(staged_paths, root)
        all_violations.extend(ref_violations)

    # Check deletion safety for pattern ACs
    if deleted_paths:
        del_violations = _check_pattern_deletion_safety(deleted_paths, root)
        all_violations.extend(del_violations)

    if not all_violations:
        return 0

    print(f"\n{_HOOK_PREFIX} BLOCKED — AC pattern-reference violation", file=sys.stderr)
    for v in all_violations:
        print(f"  {v}", file=sys.stderr)

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
