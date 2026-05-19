"""
MODULE: commit_guardian.check_file_size
GOAL: Pre-commit hook to block files exceeding line limits to encourage refactoring.
BUSINESS CONTEXT: Keeps file complexity under control by forcing refactors of bloated files.
ARCHITECTURE: Not needed.

Pre-commit hook to block files exceeding line limits.

Line Limits:
- Python (.py): 400 lines max
- SQL (.sql): 600 lines max

Exit Codes:
    0 - All files within limits
    1 - One or more files exceed limits

Usage:
    poetry run python scripts/commit_guardian/check_file_size.py
"""

import subprocess
import sys
from pathlib import Path

# Fix import path when running from root
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import (
    CHECKED_EXTENSIONS,
    DEFAULT_LINE_LIMIT,
    FILE_LINE_LIMITS,
)


def get_staged_files() -> dict[str, bool]:
    """
    Get all staged files with their status (new vs modified).

    Returns:
        Dictionary mapping filepath to is_new_file boolean.
        True = newly added file, False = modified existing file.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-status"],
        capture_output=True,
        text=True,
        check=True,
    )

    staged_files: dict[str, bool] = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[1]
            # "A" = Added (new file), "M" = Modified, etc.
            is_new = status.startswith("A")
            staged_files[filepath] = is_new

    return staged_files


import re

def count_lines(filepath: str) -> int:
    """
    Count logical lines in a file (excluding docstrings, block comments, blank
    lines, and standalone #-comment lines).

    A *logical line* is any line that is not:
    - Blank (zero non-whitespace characters), or
    - A standalone #-comment line (first non-whitespace character is '#'), or
    - Inside a Python triple-quoted docstring (removed before counting), or
    - Inside a SQL/C block comment enclosed by /* ... */ (removed before counting).

    Inline #-comments at the end of code lines (e.g. ``x = 1  # note``) are
    intentionally *not* excluded — those lines contain real code.

    Args:
        filepath: Path to the file to count.

    Returns:
        Number of logical lines in the file, or 0 if the file cannot be read.
    """
    try:
        path = Path(filepath)
        if not path.exists():
            return 0
        content = path.read_text(encoding="utf-8")

        # Strip Python triple-quoted docstrings
        content = re.sub(r'""".*?"""', '', content, flags=re.DOTALL)
        content = re.sub(r"'''.*?'''", '', content, flags=re.DOTALL)

        # Strip SQL/C block comments (/* ... */) — includes the DECISION HISTORY block
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)

        # Count only logical lines: non-blank and not a standalone #-comment line
        logical_count = 0
        for line in content.splitlines():
            stripped = line.strip()
            if not stripped:
                continue          # blank line
            if stripped.startswith('#'):
                continue          # standalone #-comment line (e.g. DECISION HISTORY entries)
            logical_count += 1

        return logical_count
    except Exception:
        return 0


def get_limit_for_extension(filepath: str) -> int:
    """
    Get the line limit for a file based on its extension.

    Args:
        filepath: Path to check.

    Returns:
        Line limit for the file type.
    """
    ext = Path(filepath).suffix.lower()
    return FILE_LINE_LIMITS.get(ext, DEFAULT_LINE_LIMIT)


def should_check_file(filepath: str) -> bool:
    """
    Determine if a file should be checked based on its extension.

    Args:
        filepath: Path to the file.

    Returns:
        True if the file should be checked.
    """
    ext = Path(filepath).suffix.lower()
    return ext in CHECKED_EXTENSIONS


def check_file(filepath: str, is_new_file: bool) -> tuple[bool, int, int]:
    """
    Check if a file passes the size limit.

    Args:
        filepath: Path to the file to check.
        is_new_file: Whether this is a newly added file.

    Returns:
        Tuple of (passes_check, line_count, limit).
    """
    limit = get_limit_for_extension(filepath)
    lines = count_lines(filepath)

    return lines <= limit, lines, limit


def main() -> int:
    """
    Main entry point for the pre-commit hook.

    Returns:
        Exit code (0 = success, 1 = failure).
    """
    # Ensure header output (emojis) works on Windows
    if sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            # Python < 3.7 doesn't support reconfigure, but we're likely on modern Python
            pass

    staged_files = get_staged_files()

    if not staged_files:
        return 0

    failed_files: list[tuple[str, int, int]] = []
    passed_files: list[tuple[str, int, bool]] = []  # (path, lines, is_new)

    for filepath, is_new in staged_files.items():
        if not should_check_file(filepath):
            continue

        passes, lines, limit = check_file(filepath, is_new)

        if passes:
            passed_files.append((filepath, lines, is_new))
        else:
            failed_files.append((filepath, lines, limit))

    # Print results
    print("\n📏 File Size Check\n")

    if failed_files:
        for filepath, lines, limit in failed_files:
            print("❌ FILE TOO LARGE:")
            print(f"   {filepath}")
            print(f"   Logical lines (excluding blank and #-comment lines): {lines} / {limit}")
            print()
            print("   Please refactor and split this file before committing.")
            print("   DO NOT simply delete blank lines, comments, or docstrings to bypass this.")
            print("   You MUST split the file to make it easier and less token consuming for agents.")
            if filepath.endswith(".md"):
                print("   Use the `@documentation-expert` agent to intelligently split this markdown file.")
            elif filepath.endswith(".py"):
                print("   Use the `/code-refactoring-specialist` slash command to intelligently split this Python file.")
            else:
                print("   Use the `/code-refactoring-specialist` slash command or relevant skill to intelligently split the file.")
            print("   (We enforce this check to force refactoring of older files over time).\n")

    if passed_files:
        print(f"✅ PASSED: {len(passed_files)} files checked")
        for filepath, lines, is_new in passed_files:
            status = "new" if is_new else "modified"
            print(f"   - {filepath} ({status}, {lines} lines - OK)")

    if failed_files:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-01 17:31 [Antigravity]: Updated file size check to enforce limits on all changed files, not just new ones, to drive progressive refactoring.
- 2026-03-01 10:00: Initial implementation.
- 2026-05-19 09:30 [python-coder]: Changed count_lines() to count only logical lines (non-blank, non-standalone-#-comment). DECISION HISTORY blocks and banner comments no longer contribute to the 400-line cap. Updated error message to show logical-line count explicitly. (#EPIC-WorkflowGuardrailFixes/02)
====================================================================
"""
