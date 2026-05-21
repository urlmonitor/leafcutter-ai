"""
MODULE: check_pytest_style.py
GOAL: Pre-commit guard that rejects pytest-style test functions (top-level
    ``def test_*()``) in ``unit_tests/live_trader/`` that are not methods of a
    ``unittest.TestCase`` subclass.
BUSINESS CONTEXT: The pre-commit ``run-unit-tests`` hook runs
    ``unittest discover``, which only collects ``TestCase`` subclasses. A
    top-level ``def test_*()`` function is silently skipped, creating the
    illusion that tests pass when none ran (EPIC-MarketStructure failure mode 1).
    This guard catches that pattern at commit time and names the offending file
    and function so the developer can fix it before the silent-skip reaches CI.
ARCHITECTURE: Uses Python's ``ast`` module to walk staged
    ``unit_tests/live_trader/test_*.py`` files. Staged files are enumerated via
    ``git diff --cached --name-only`` (same pattern as ``check_complexity.py``).
    No filenames are received from pre-commit (``pass_filenames: false`` in the
    hook config) — the script self-enumerates staged files matching the target
    pattern. Exit 0 on pass; exit 1 on any violation.

Exit Codes:
    0 - All staged files pass the check.
    1 - One or more files contain pytest-style top-level test functions.

Usage:
    python scripts/commit_guardian/check_pytest_style.py
"""

import ast
import subprocess
import sys
from pathlib import Path

# 2026-05-11 [Hendrik/Claude]: Created for TICKET-20260511 (EPIC-MarketStructure
# learning 1). Enforces unittest.TestCase style in unit_tests/live_trader/ so
# unittest discover in pre-commit does not silently skip pytest-style functions.

_TARGET_PREFIX = "unit_tests/live_trader/"
_TEST_FILE_PATTERN = "test_"
_TESTCASE_BASES = frozenset({"TestCase", "unittest.TestCase"})


def _get_staged_live_trader_tests() -> list[str]:
    """Return staged test file paths under unit_tests/live_trader/.

    Uses ``git diff --cached --name-only`` to enumerate files staged for the
    current commit. Only returns paths that match ``unit_tests/live_trader/test_*.py``
    and that exist on disk (deleted files are excluded).

    Returns:
        List of relative file path strings matching the target pattern.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    paths: list[str] = []
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        normalised = stripped.replace("\\", "/")
        if not normalised.startswith(_TARGET_PREFIX):
            continue
        filename = Path(normalised).name
        if not filename.startswith(_TEST_FILE_PATTERN) or not filename.endswith(".py"):
            continue
        if not Path(stripped).exists():
            continue
        paths.append(stripped)
    return paths


def _is_testcase_subclass(class_node: ast.ClassDef) -> bool:
    """Return True when a class directly inherits from unittest.TestCase or TestCase.

    Checks only ``bases`` at the AST level (single-level name resolution). This
    covers the common ``class MyTests(unittest.TestCase)`` and
    ``class MyTests(TestCase)`` patterns. Deep inheritance chains are accepted
    because the direct parent is expected to be TestCase (or its stdlib alias).

    Args:
        class_node: An ``ast.ClassDef`` node to inspect.

    Returns:
        True if any base resolves to ``TestCase`` or ``unittest.TestCase``.
    """
    for base in class_node.bases:
        if isinstance(base, ast.Name) and base.id in _TESTCASE_BASES:
            return True
        if isinstance(base, ast.Attribute):
            if isinstance(base.value, ast.Name) and base.attr == "TestCase":
                return True
    return False


def _collect_non_testcase_methods(tree: ast.Module) -> list[tuple[int, str]]:
    """Collect test_ methods inside classes that are NOT TestCase subclasses.

    Args:
        tree: Parsed AST module.

    Returns:
        List of ``(line_number, function_name)`` tuples for each violation.
    """
    violations: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if _is_testcase_subclass(node):
            continue
        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if child.name.startswith("test_"):
                    violations.append((child.lineno, child.name))
    return violations


def _collect_toplevel_test_functions(tree: ast.Module) -> list[tuple[int, str]]:
    """Collect test_ functions defined at the module top level (not inside any class).

    Args:
        tree: Parsed AST module.

    Returns:
        List of ``(line_number, function_name)`` tuples for each violation.
    """
    return [
        (node.lineno, node.name)
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    ]


def _find_bare_test_functions(source: str) -> list[tuple[int, str]]:
    """Find test_ functions outside any TestCase subclass in *source*.

    Combines module-level functions and test_ methods inside non-TestCase
    classes. Delegates each concern to a focused helper.

    Args:
        source: Python source code text.

    Returns:
        List of ``(line_number, function_name)`` tuples for each violation.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    return (
        _collect_non_testcase_methods(tree)
        + _collect_toplevel_test_functions(tree)
    )


def check_file(filepath: str) -> list[str]:
    """Check one file for pytest-style test functions and return violation messages.

    Args:
        filepath: Relative or absolute path to a Python source file.

    Returns:
        List of human-readable violation strings (one per offending function).
        Empty list means the file passes.
    """
    try:
        source = Path(filepath).read_text(encoding="utf-8")
    except OSError:
        return []

    bare = _find_bare_test_functions(source)
    messages: list[str] = []
    for lineno, fname in bare:
        messages.append(
            f"{filepath}:{lineno}: top-level pytest-style function '{fname}' "
            f"is not a method of a unittest.TestCase subclass — "
            f"unittest discover will silently skip it"
        )
    return messages


def main() -> int:
    """Entry point: enumerate staged test files and report violations.

    Returns:
        0 when all staged files pass; 1 when any violation is found.
    """
    staged = _get_staged_live_trader_tests()
    all_violations: list[str] = []

    for filepath in staged:
        all_violations.extend(check_file(filepath))

    if all_violations:
        for msg in all_violations:
            print(msg, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-12 00:00 [Hendrik/Claude]: Created for TICKET-20260511 (#EPIC-LeafcutterMVP/01)
  (EPIC-MarketStructure learning 1). Enforces unittest.TestCase style in
  unit_tests/live_trader/ so unittest discover in pre-commit does not
  silently skip pytest-style functions. AST-based; self-enumerates staged
  files via ``git diff --cached --name-only`` (pass_filenames: false in
  .pre-commit-config.yaml).
====================================================================
"""
