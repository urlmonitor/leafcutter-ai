"""
MODULE: check_test_ac_tags
GOAL: Pre-commit hook that verifies every Python test function in staged test
    files carries a ``# covers: XX-NNN`` tag linking it to an Acceptance Criterion.
BUSINESS CONTEXT: Ensures machine-readable traceability between tests and ACs
    is enforced at commit time. Without enforcement, test authors forget to add
    the tag and the coverage mapping degrades quickly. The hook launches in
    *warning mode* by default (grace period), exiting 0 even when violations are
    found so existing repos are not flooded with blocked commits. A follow-up
    ticket flips the default to *error mode* once existing tests are backfilled.
ARCHITECTURE: Pure stdlib (``ast`` + ``re``). Accepts a list of file paths as
    CLI arguments (or reads them from the environment variable
    ``CHECK_TEST_AC_TAGS_FILES``). For each path, checks whether it is a test
    file (``test_*.py`` / ``*_test.py``). For matching files, parses the AST to
    find ``def test_*`` functions and looks for a ``# covers: XX-NNN`` comment
    on the line *above* the ``def``, on the *first line of the body*, or in the
    function's *docstring*. Enforcement mode is read from ``commit_guardian.json``
    (key ``test_ac_tag_enforcement``) or overridden via the environment variable
    ``CHECK_TEST_AC_TAGS_MODE``. Exit 0 in warn mode always; exit 1 in error mode
    when violations are found.
    Standalone stdlib script — no leafcutter imports.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

COVERS_REGEX = re.compile(r"covers:\s*[A-Z]{2,6}-[0-9]{3}")
_TEST_FUNCTION_PREFIX = "test_"
_DEFAULT_ENFORCEMENT_MODE = "warn"
_CONFIG_KEY = "test_ac_tag_enforcement"

# ---------------------------------------------------------------------------
# Data Types
# ---------------------------------------------------------------------------


class Violation(NamedTuple):
    """Represents a single missing-tag violation.

    Attributes:
        file_path: Path to the test file.
        function_name: Name of the test function missing the tag.
        lineno: Source line number of the ``def`` statement.
    """

    file_path: str
    function_name: str
    lineno: int


# ---------------------------------------------------------------------------
# File filter
# ---------------------------------------------------------------------------


def is_test_file(path: str | Path) -> bool:
    """Return True when the file is a Python test file.

    A file is a test file iff its basename matches ``test_*.py`` or
    ``*_test.py``.

    Args:
        path: File path to check (string or Path).

    Returns:
        True when the basename matches the test-file naming convention.
    """
    name = Path(path).name
    return name.startswith("test_") or name.endswith("_test.py")


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def find_test_functions(
    tree: ast.Module,
) -> list[tuple[str, int]]:
    """Return a list of (name, lineno) for each top-level ``def test_*`` function.

    Only top-level function definitions are considered; methods inside classes
    are not included (they are typically found via their enclosing class, and
    test frameworks discover them regardless).

    Args:
        tree: Parsed AST module.

    Returns:
        List of ``(function_name, lineno)`` tuples in source order.
    """
    result: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith(
            _TEST_FUNCTION_PREFIX
        ):
            result.append((node.name, node.lineno))
    return result


def has_covers_tag(
    source_lines: list[str],
    func_node: ast.FunctionDef,
) -> bool:
    """Return True when a test function carries a valid ``covers:`` tag.

    Checks three locations in priority order:
    1. The line *above* the ``def`` (index ``func_node.lineno - 2``).
    2. The *first statement* of the function body, if it is a string constant
       (docstring).
    3. Any ``# covers:`` comment on the *first body line*
       (index ``func_node.body[0].lineno - 1``).

    Args:
        source_lines: All source lines of the file (0-indexed).
        func_node: AST node for the test function.

    Returns:
        True when a ``covers: XX-NNN`` tag is found in any checked location.
    """
    # 1. Line above the def (0-based index = lineno - 2, guard against line 1)
    def_line_idx = func_node.lineno - 1  # 0-based
    if def_line_idx > 0:
        line_above = source_lines[def_line_idx - 1]
        if COVERS_REGEX.search(line_above):
            return True

    # 2. Docstring
    first_stmt = func_node.body[0] if func_node.body else None
    if first_stmt is not None and isinstance(first_stmt, ast.Expr):
        value = first_stmt.value
        if isinstance(value, ast.Constant) and isinstance(value.s, str):
            if COVERS_REGEX.search(value.s):
                return True

    # 3. First line of the body (comment or inline tag)
    if first_stmt is not None:
        first_body_line_idx = first_stmt.lineno - 1  # 0-based
        if first_body_line_idx < len(source_lines):
            first_body_line = source_lines[first_body_line_idx]
            if COVERS_REGEX.search(first_body_line):
                return True

    return False


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def read_enforcement_mode(config_path: str | Path | None = None) -> str:
    """Read the enforcement mode from ``commit_guardian.json``.

    Priority order:
    1. Environment variable ``CHECK_TEST_AC_TAGS_MODE`` (highest).
    2. ``test_ac_tag_enforcement`` key in the config file at *config_path*.
    3. Default: ``"warn"``.

    Args:
        config_path: Path to ``commit_guardian.json``. When ``None``, the hook
            looks for the config file relative to the script directory.

    Returns:
        ``"warn"`` or ``"error"``.
    """
    # 1. Environment override (highest priority — used by tests and CI)
    env_mode = os.environ.get("CHECK_TEST_AC_TAGS_MODE", "").strip().lower()
    if env_mode in ("warn", "error"):
        return env_mode

    # 2. Config file
    resolved_path: Path | None = None
    if config_path is not None:
        resolved_path = Path(config_path)
    else:
        # Locate commit_guardian.json relative to this script
        env_config = os.environ.get("COMMIT_GUARDIAN_CONFIG", "")
        if env_config:
            resolved_path = Path(env_config)
        else:
            resolved_path = Path(__file__).parent / "commit_guardian.json"

    if resolved_path is not None and resolved_path.is_file():
        try:
            with open(resolved_path, encoding="utf-8") as fh:
                config = json.load(fh)
            mode = config.get(_CONFIG_KEY, _DEFAULT_ENFORCEMENT_MODE)
            if mode in ("warn", "error"):
                return mode
        except (json.JSONDecodeError, OSError):
            pass  # Fall through to default

    return _DEFAULT_ENFORCEMENT_MODE


# ---------------------------------------------------------------------------
# Core checker
# ---------------------------------------------------------------------------


def check_file(path: Path) -> list[Violation]:
    """Check a single test file for missing ``covers:`` tags.

    Parses the file as an AST, finds all ``def test_*`` functions, and checks
    each for a ``covers:`` tag. Files that fail to parse (syntax error) are
    skipped silently to avoid blocking commits for unrelated reasons.

    Args:
        path: Path to the Python test file.

    Returns:
        List of ``Violation`` instances for each untagged test function.
    """
    try:
        source = path.read_text(encoding="utf-8")
        source_lines = source.splitlines()
        tree = ast.parse(source, filename=str(path))
    except (OSError, SyntaxError):
        # Cannot parse — skip silently
        return []

    violations: list[Violation] = []
    for func_name, lineno in find_test_functions(tree):
        # Retrieve the actual AST node for full detail
        func_node = _get_function_node(tree, func_name, lineno)
        if func_node is None:
            continue
        if not has_covers_tag(source_lines, func_node):
            violations.append(Violation(str(path), func_name, lineno))

    return violations


def _get_function_node(
    tree: ast.Module, func_name: str, lineno: int
) -> ast.FunctionDef | None:
    """Retrieve an AST FunctionDef node by name and line number.

    Args:
        tree: Parsed AST module.
        func_name: Name of the function to locate.
        lineno: Source line number of the function.

    Returns:
        The matching ``ast.FunctionDef`` node, or ``None`` if not found.
    """
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == func_name
            and node.lineno == lineno
        ):
            return node
    return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for the pre-commit hook.

    Accepts a list of file paths as positional arguments. Non-test files are
    skipped silently. Returns 0 in warn mode regardless of violations; returns 1
    in error mode when any violations are found.

    Args:
        argv: List of file paths to check. When ``None``, uses ``sys.argv[1:]``.

    Returns:
        Exit code: 0 on success (or warn mode); 1 on violation in error mode.
    """
    if argv is None:
        argv = sys.argv[1:]

    mode = read_enforcement_mode()
    all_violations: list[Violation] = []

    for raw_path in argv:
        path = Path(raw_path)
        if not is_test_file(path):
            continue
        violations = check_file(path)
        all_violations.extend(violations)

    if not all_violations:
        return 0

    label = "WARNING" if mode == "warn" else "ERROR"
    for v in all_violations:
        print(
            f"{label}: {v.file_path}:{v.lineno}: "
            f"test function '{v.function_name}' is missing a # covers: XX-NNN tag.",
            file=sys.stderr,
        )

    if mode == "error":
        print(
            f"\ncheck_test_ac_tags: {len(all_violations)} violation(s) found. "
            "Add '# covers: XX-NNN' to each test function or its docstring.",
            file=sys.stderr,
        )
        return 1

    # warn mode — exit 0 always
    print(
        f"\ncheck_test_ac_tags: {len(all_violations)} warning(s) — "
        "add '# covers: XX-NNN' tags to suppress these warnings.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
