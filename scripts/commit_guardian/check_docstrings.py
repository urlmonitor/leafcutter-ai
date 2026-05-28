"""
Pre-commit hook to enforce Google-style docstrings on all Python functions, methods, and classes.
Validates summary, Args, Returns sections and catches stale params using docstring-parser.

MODULE: check_docstrings.py
GOAL: Enforce Google-style docstrings with Args/Returns on all Python functions and classes.
BUSINESS CONTEXT: Ensures code is self-documenting and machine-parseable via docstring-parser.
ARCHITECTURE: Not needed.
"""

import ast
import subprocess
import sys
import argparse
from pathlib import Path
from typing import Optional

from _resolve_root import find_project_root

project_root = find_project_root()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import EXCLUDED_DIRS

# Re-export validators for backward compatibility (used by unit tests)
from scripts.commit_guardian.docstring_validators import (  # noqa: F401
    _get_real_params,
    _has_return_value,
    _is_trivial,
    check_file_docstrings,
    validate_class_docstring,
    validate_function_docstring,
)


def get_staged_files() -> dict[str, str]:
    """Get all staged Python files with their git status."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return {}

    staged_files = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[-1]
            staged_files[filepath] = status

    return staged_files


def is_in_excluded_dir(filepath: str) -> bool:
    """Check if the file is in an excluded directory."""
    path_parts = Path(filepath).parts
    return any(ex_dir in path_parts for ex_dir in EXCLUDED_DIRS)


def configure_stdout() -> None:
    """Ensure output works on Windows with UTF-8."""
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass


def get_files_to_check(target_file: Optional[str]) -> dict[str, str]:
    """Determine which files to check based on arguments.

    Args:
        target_file: Optional specific file path to check instead of staged files.

    Returns:
        dict[str, str]: Mapping of filepaths to status codes.
    """
    if target_file:
        try:
            filepath = Path(target_file).resolve().relative_to(project_root).as_posix()
        except ValueError:
            filepath = Path(target_file).as_posix()
        return {filepath: "M"}
    return get_staged_files()


def should_check_file(filepath: str, status: str) -> bool:
    """Determine whether to apply docstring checks to a given file.

    Args:
        filepath: Relative path to the file from project root.
        status: Git status character ('A', 'M', 'D', etc.).

    Returns:
        bool: True if the file should be checked.
    """
    path = Path(filepath)

    if path.suffix.lower() != ".py":
        return False

    if path.name == "__init__.py":
        return False

    if is_in_excluded_dir(filepath):
        return False

    if status.startswith("D"):
        return False

    return True


def print_results(violations: list[str], passed_count: int) -> int:
    """Print results and return exit code.

    Args:
        violations: List of violation messages.
        passed_count: Number of files that passed all checks.

    Returns:
        int: Exit code (0 for success, 1 for violations found).
    """
    if violations:
        print("\n📝 Docstring Check Failed\n")
        for msg in violations:
            print(msg + "\n")
        print("   AI AGENT ACTION REQUIRED: You must fix all docstring violations.")
        print("   DO NOT ask the user to bypass this rule.\n")
        return 1
    if passed_count > 0:
        print(f"✅ PASSED: {passed_count} files passed docstring checks")
    return 0


def main() -> int:
    """Entry point for the pre-commit hook.

    Returns:
        int: Exit code (0 success, 1 violations found).
    """
    parser = argparse.ArgumentParser(description="Check Python docstring requirements.")
    parser.add_argument("--file", help="Specific file to check (bypasses git staged files).")
    args = parser.parse_args()

    configure_stdout()
    staged_files = get_files_to_check(args.file)

    if not staged_files:
        return 0

    all_violations = []
    passed_count = 0

    for filepath, status in staged_files.items():
        if not should_check_file(filepath, status):
            continue

        file_violations = check_file_docstrings(filepath)
        if file_violations:
            all_violations.extend(file_violations)
        else:
            passed_count += 1

    return print_results(all_violations, passed_count)


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-04-30 16:00 [Hendrik]: Initial implementation. Enforces Google-style
  docstrings on all Python functions/classes with AST parsing + docstring-parser.
  Exemptions: trivial functions (≤5 lines OR 0 params), exempt dunders,
  __init__.py files, excluded directories.
- 2026-05-01 20:30 [AI]: Updated failure message to mandate agent-led refactoring
  for docstring violations. Extracted all AST validation logic to
  docstring_validators.py to stay under the 400-line file size limit.
====================================================================
"""
