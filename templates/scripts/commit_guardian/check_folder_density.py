"""
Pre-commit hook to enforce folder density limits.

Blocks commits when a staged file would cause any directory to exceed the
maximum allowed number of non-markdown files (default: 15). This encourages
developers to create proper sub-folder structures as modules grow.

Counting Rules:
    - Only non-markdown files are counted (.md files are exempt)
    - Hidden files/folders (starting with '.') are ignored
    - __pycache__, .git, .venv, node_modules are ignored
    - __init__.py files are NOT counted (they are structural, not content)
    - The project root directory is skipped (handled by check_root_files.py)

Exit Codes:
    0 - All folders within density limits
    1 - One or more folders exceed the limit

Usage:
    poetry run python scripts/commit_guardian/check_folder_density.py

MODULE: check_folder_density.py
GOAL: Prevent overly flat directory structures by limiting files per folder.
BUSINESS CONTEXT: Encourages modular project structure for maintainability.
ARCHITECTURE: Not needed.
"""

import logging
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()

from config import (
    MAX_FILES_PER_FOLDER,
    DENSITY_EXCLUDED_DIRS,
    DENSITY_EXEMPT_EXTENSIONS,
    DENSITY_EXEMPT_FILENAMES,
)

# Use config-driven constants with local aliases
EXCLUDED_DIRS = DENSITY_EXCLUDED_DIRS
EXEMPT_EXTENSIONS = DENSITY_EXEMPT_EXTENSIONS
EXEMPT_FILENAMES = DENSITY_EXEMPT_FILENAMES

logger = logging.getLogger(__name__)


def get_staged_files() -> list[str]:
    """
    Get all staged files (added or modified).

    Returns:
        List of staged file paths relative to repo root.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    staged_files = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[-1]
            if status.startswith(("A", "M", "R")):
                staged_files.append(filepath)

    return staged_files


def is_excluded_path(filepath: str) -> bool:
    """
    Check if a file path is within an excluded directory.

    Args:
        filepath: Relative file path.

    Returns:
        True if the path should be excluded from density checks.
    """
    parts = Path(filepath).parts
    for part in parts:
        if part in EXCLUDED_DIRS or part.startswith("."):
            return True
    return False


def is_countable_file(filepath: str) -> bool:
    """
    Determine if a file counts towards the folder density limit.

    Args:
        filepath: Relative file path.

    Returns:
        True if the file should be counted.
    """
    path = Path(filepath)

    # Exempt markdown files
    if path.suffix.lower() in EXEMPT_EXTENSIONS:
        return False

    # Exempt structural files
    if path.name in EXEMPT_FILENAMES:
        return False

    return True


def get_all_tracked_files() -> list[str]:
    """
    Get all files tracked in HEAD -- the commit's PARENT snapshot.

    ``git ls-files`` was used previously, but its own docstring claim
    ("including staged changes") is exactly the defect: it reflects the
    CURRENT INDEX, which already contains whatever THIS commit is staging.
    A folder pushed over the limit by files staged in this very commit then
    has a before_count that already includes them, so it is misclassified
    as pre-existing (a warning) instead of newly-dense (a violation), and
    the commit that caused the crossing is wrongly let through.
    ``git ls-tree -r HEAD --name-only`` reads the parent commit's tree
    instead, so a file only staged now is correctly absent from the BEFORE
    snapshot.

    Returns:
        List of all file paths tracked in HEAD, relative to repo root. Empty
        list when there is no HEAD yet (the repository's first, root commit)
        -- there is genuinely no parent snapshot to report in that case.
    """
    # Locale-independent root-commit detection: the exit code of rev-parse,
    # never git's (localised) stderr text.
    try:
        head = subprocess.run(
            ["git", "rev-parse", "--verify", "-q", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError as exc:
        logger.warning("git rev-parse --verify -q HEAD could not run: %s", exc)
        raise
    if head.returncode != 0:
        return []

    try:
        result = subprocess.run(
            ["git", "ls-tree", "-r", "HEAD", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("git ls-tree -r HEAD --name-only failed: %s", exc)
        raise

    return [f for f in result.stdout.strip().split("\n") if f]


def get_index_files() -> list[str]:
    """
    Get all files in the index -- the state this commit will produce.

    The index already reflects staged additions, deletions and rename
    sources/destinations, so no manual add/subtract is needed.

    Returns:
        List of all indexed file paths relative to repo root.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        logger.warning("git ls-files failed: %s", exc)
        raise

    # An unmerged path is listed once per stage (up to three times); dedupe,
    # preserving order, so mid-conflict runs do not inflate AFTER.
    return list(dict.fromkeys(f for f in result.stdout.strip().split("\n") if f))


def count_files_per_folder(files: list[str]) -> dict[str, int]:
    """
    Count non-markdown, non-exempt files per directory.

    Args:
        files: List of file paths relative to repo root.

    Returns:
        Dictionary mapping directory path to countable file count.
    """
    folder_counts: dict[str, int] = defaultdict(int)

    for filepath in files:
        if is_excluded_path(filepath):
            continue

        if not is_countable_file(filepath):
            continue

        # Get the parent directory
        parent = str(Path(filepath).parent)

        # Skip root directory (handled by check_root_files.py)
        if parent == ".":
            continue

        folder_counts[parent] += 1

    return dict(folder_counts)


def get_folder_file_list(folder: str, files: list[str]) -> list[str]:
    """
    Get the list of countable files in a specific folder.

    Args:
        folder: Directory path relative to repo root.
        files: List of all file paths.

    Returns:
        List of countable file names in the folder.
    """
    result = []
    for filepath in files:
        parent = str(Path(filepath).parent)
        if parent == folder and is_countable_file(filepath) and not is_excluded_path(filepath):
            result.append(Path(filepath).name)
    return sorted(result)


def _print_warnings(warnings: list[tuple[str, int]]) -> None:
    """Print non-blocking warnings for pre-existing dense folders."""
    for folder, count in warnings:
        print(f"⚠️  PRE-EXISTING DENSITY: {folder}/")
        print(f"   Non-markdown files: {count} (limit: {MAX_FILES_PER_FOLDER})")
        print(f"   (Folder was already over the limit — not blocking this commit)\n")


def _print_violations(violations: list[tuple[str, int]], all_files: list[str]) -> None:
    """Print blocking violations for newly-dense folders.

    Args:
        violations: List of (folder, file_count) pairs.
        all_files: Full list of tracked files for folder breakdowns.
    """
    for folder, count in violations:
        print(f"❌ FOLDER TOO DENSE: {folder}/")
        print(f"   Non-markdown files: {count} (limit: {MAX_FILES_PER_FOLDER})")
        file_list = get_folder_file_list(folder, all_files)
        print(f"   Files: {', '.join(file_list[:10])}")
        if len(file_list) > 10:
            print(f"   ... and {len(file_list) - 10} more")
        print()
        print("   AI AGENT ACTION REQUIRED: You must fix this issue by creating sub-folders and moving related files.")
        print("   Use the /code-refactoring-specialist workflow or the complexity-reduction skill.")
        print("   DO NOT ask the user to bypass this rule.\n")


def _classify_folders(
    affected_dirs: set[str],
    before_counts: dict[str, int],
    after_counts: dict[str, int],
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """Classify affected folders into violations (newly-dense) and warnings (pre-existing).

    Args:
        affected_dirs: Set of directory paths that changed.
        before_counts: File counts per folder before commit.
        after_counts: File counts per folder after commit.

    Returns:
        tuple[list, list]: Tuple of (violations, warnings).
    """
    violations: list[tuple[str, int]] = []
    warnings: list[tuple[str, int]] = []
    for folder in sorted(affected_dirs):
        after_count = after_counts.get(folder, 0)
        before_count = before_counts.get(folder, 0)
        if after_count > MAX_FILES_PER_FOLDER:
            if before_count > MAX_FILES_PER_FOLDER:
                warnings.append((folder, after_count))
            else:
                violations.append((folder, after_count))
    return violations, warnings


def main() -> int:
    """
    Main entry point for the pre-commit hook.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    # Ensure emoji output works on Windows
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    staged_files = get_staged_files()
    if not staged_files:
        return 0

    # Get the directories affected by this commit
    affected_dirs = set()
    for filepath in staged_files:
        if not is_excluded_path(filepath):
            parent = str(Path(filepath).parent)
            if parent != ".":
                affected_dirs.add(parent)

    if not affected_dirs:
        return 0

    # BEFORE = the parent commit's tree; AFTER = the index. The two are read
    # independently (AFTER is never derived from BEFORE) so staged deletions
    # and rename sources are correctly absent from AFTER.
    before_counts = count_files_per_folder(get_all_tracked_files())
    all_files = get_index_files()
    after_counts = count_files_per_folder(all_files)

    # Classify folders: only BLOCK if this commit causes the threshold crossing
    violations, warnings = _classify_folders(affected_dirs, before_counts, after_counts)

    # Output results
    print(f"\n📁 Folder Density Check (max {MAX_FILES_PER_FOLDER} non-markdown files per folder)\n")

    if warnings:
        _print_warnings(warnings)

    if violations:
        _print_violations(violations, all_files)
        return 1

    checked_count = len(affected_dirs)
    print(f"✅ PASSED: {checked_count} folder(s) checked, all within limits")
    for folder in sorted(affected_dirs):
        count = after_counts.get(folder, 0)
        print(f"   - {folder}/ ({count} files)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-04-29 10:41 [AI/Antigravity]: Made density check incremental — only blocks
  when THIS commit causes a folder to cross the threshold. Pre-existing dense folders
  are warned but don't block, preventing false positives on established flat structures
  like sql_functions/functions/ (29 files, intentionally flat per SQL standards).
- 2026-04-29 06:09 [AI/Hendrik]: Initial implementation. Limit set to 15
  based on industry best practice (10-50 range, 15 chosen as the
  modularity sweet spot). Only checks folders touched by the commit.
  Excludes .md, __init__.py, hidden dirs, and __pycache__.
- 2026-05-01 20:30 [AI]: Updated failure message to mandate agent-led refactoring for folder density violations.
====================================================================
"""
