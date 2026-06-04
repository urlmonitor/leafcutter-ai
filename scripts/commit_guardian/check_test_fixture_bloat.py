"""
MODULE: check_test_fixture_bloat.py
GOAL: Pre-commit hook that scans staged test_*.py files for oversized inline
    data and warns (or blocks) authors when fixture convention thresholds are
    exceeded.
BUSINESS CONTEXT: Prevents test files from bloating past maintainability
    thresholds and nudges authors toward the fixture convention (ADR-007).
    The hook ships ``enabled: false`` (warn-only) so it can be merged without
    immediately breaking the existing codebase.
ARCHITECTURE: Uses Python's ``ast`` module to walk each staged test file.
    Staged files are enumerated via ``git diff --cached --name-only`` when
    called from pre-commit, or received as the ``staged_files`` argument when
    called programmatically (unit-test path). Config is read from
    ``commit_guardian.json`` under the ``test_fixture_bloat`` key.
    Exit 0 on pass or warn-only mode; exit 1 when enforce mode is active and
    any violation is found.

Exit Codes:
    0 - All staged test files pass the check, OR enabled=false (warn-only).
    1 - One or more violations found and enabled=true (enforce mode).

Usage (pre-commit, via run_hook.py):
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_test_fixture_bloat.py

Usage (direct / programmatic):
    from check_test_fixture_bloat import main
    exit_code = main(staged_files=["/abs/path/test_foo.py"], config={...})
"""

# 2026-06-04 [Claude]: Created for EPIC-TestFixtureConvention/02.
# Implements AST-based inline-data bloat detection for staged test files.
# Follows check_pytest_style.py pattern for staged-file enumeration.

import ast
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class _Violation(NamedTuple):
    """A single bloat violation found in a test file."""

    path: str
    line: int
    kind: str  # "line_count" | "inline_dict" | "parametrize_rows"
    detail: str


# ---------------------------------------------------------------------------
# Staged-file enumeration (pre-commit path)
# ---------------------------------------------------------------------------

def _get_staged_test_files() -> list[str]:
    """Return staged test_*.py file paths via ``git diff --cached --name-only``.

    Returns:
        List of absolute file-path strings for staged test files that exist
        on disk.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"[check_test_fixture_bloat] WARNING: git diff failed: {exc}",
            file=sys.stderr,
        )
        return []

    paths: list[str] = []
    for line in result.stdout.splitlines():
        p = Path(line.strip())
        if p.name.startswith("test_") and p.suffix == ".py" and p.exists():
            paths.append(str(p.resolve()))
    return paths


# ---------------------------------------------------------------------------
# Detection helpers
# ---------------------------------------------------------------------------

def _has_noqa(source: str) -> bool:
    """Return True if *source* contains the ``# noqa: fixture-bloat`` comment.

    Args:
        source: Full text content of the test file.

    Returns:
        True when the file should be skipped entirely.
    """
    return "# noqa: fixture-bloat" in source


def _check_line_count(path: str, source: str, config: dict) -> list[_Violation]:
    """Check whether the file exceeds ``max_test_file_lines``.

    Args:
        path: Absolute path to the file (for error reporting).
        source: Full text content of the file.
        config: The ``test_fixture_bloat`` config dict.

    Returns:
        List with one _Violation if the file is over the threshold, else [].
    """
    max_lines: int = config.get("max_test_file_lines", 500)
    line_count = source.count("\n") + (0 if source.endswith("\n") else 1)
    if line_count > max_lines:
        return [
            _Violation(
                path=path,
                line=line_count,
                kind="line_count",
                detail=(
                    f"File has {line_count} lines "
                    f"(limit: {max_lines}). "
                    "Extract large inline fixtures to JSON fixture files."
                ),
            )
        ]
    return []


class _DictKeyVisitor(ast.NodeVisitor):
    """AST visitor that flags ``ast.Dict`` nodes exceeding the key-count limit."""

    def __init__(self, max_keys: int) -> None:
        self.max_keys = max_keys
        self.violations: list[tuple[int, int]] = []  # (lineno, key_count)

    def visit_Dict(self, node: ast.Dict) -> None:  # noqa: N802
        """Visit an ast.Dict node and flag if key count exceeds the limit."""
        key_count = len(node.keys)
        if key_count > self.max_keys:
            self.violations.append((node.lineno, key_count))
        self.generic_visit(node)


def _check_inline_dicts(path: str, tree: ast.AST, config: dict) -> list[_Violation]:
    """Check for inline dicts with more keys than ``max_inline_dict_keys``.

    Args:
        path: Absolute path to the file (for error reporting).
        tree: Parsed AST of the file.
        config: The ``test_fixture_bloat`` config dict.

    Returns:
        List of _Violation objects for each over-limit dict literal found.
    """
    max_keys: int = config.get("max_inline_dict_keys", 5)
    visitor = _DictKeyVisitor(max_keys=max_keys)
    visitor.visit(tree)
    violations: list[_Violation] = []
    for lineno, key_count in visitor.violations:
        violations.append(
            _Violation(
                path=path,
                line=lineno,
                kind="inline_dict",
                detail=(
                    f"Inline dict at line {lineno} has {key_count} keys "
                    f"(limit: {max_keys}). "
                    "Extract the dict to a fixture JSON file under tests/fixtures/."
                ),
            )
        )
    return violations


class _ParametrizeVisitor(ast.NodeVisitor):
    """AST visitor that flags pytest.mark.parametrize calls with too many rows."""

    def __init__(self, max_rows: int) -> None:
        self.max_rows = max_rows
        self.violations: list[tuple[int, int]] = []  # (lineno, row_count)

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        """Visit an ast.Call node and flag over-limit parametrize tables."""
        if self._is_parametrize(node.func):
            # The second argument to pytest.mark.parametrize is the test table.
            if len(node.args) >= 2:
                table_arg = node.args[1]
                row_count = self._count_rows(table_arg)
                if row_count is not None and row_count > self.max_rows:
                    self.violations.append((node.lineno, row_count))
        self.generic_visit(node)

    @staticmethod
    def _is_parametrize(func_node: ast.expr) -> bool:
        """Return True when the callee matches ``pytest.mark.parametrize``."""
        # Handles both ``pytest.mark.parametrize(...)`` and
        # ``@pytest.mark.parametrize`` as a decorator callee.
        if isinstance(func_node, ast.Attribute):
            if func_node.attr == "parametrize":
                # func_node.value should be pytest.mark
                parent = func_node.value
                if isinstance(parent, ast.Attribute) and parent.attr == "mark":
                    grand = parent.value
                    if isinstance(grand, ast.Name) and grand.id == "pytest":
                        return True
        return False

    @staticmethod
    def _count_rows(table_arg: ast.expr) -> int | None:
        """Return the number of rows in a parametrize table argument.

        Args:
            table_arg: The second argument to ``pytest.mark.parametrize``.

        Returns:
            Integer row count if the argument is a list or tuple literal,
            else ``None`` (cannot be determined statically).
        """
        if isinstance(table_arg, (ast.List, ast.Tuple)):
            return len(table_arg.elts)
        return None


def _check_parametrize_rows(
    path: str, tree: ast.AST, config: dict
) -> list[_Violation]:
    """Check for parametrize tables with more rows than ``max_parametrize_rows``.

    Args:
        path: Absolute path to the file (for error reporting).
        tree: Parsed AST of the file.
        config: The ``test_fixture_bloat`` config dict.

    Returns:
        List of _Violation objects for each over-limit parametrize table.
    """
    max_rows: int = config.get("max_parametrize_rows", 3)
    visitor = _ParametrizeVisitor(max_rows=max_rows)
    visitor.visit(tree)
    violations: list[_Violation] = []
    for lineno, row_count in visitor.violations:
        violations.append(
            _Violation(
                path=path,
                line=lineno,
                kind="parametrize_rows",
                detail=(
                    f"pytest.mark.parametrize at line {lineno} has {row_count} rows "
                    f"(limit: {max_rows}). "
                    "Extract the table to a fixture JSON file under tests/fixtures/."
                ),
            )
        )
    return violations


# ---------------------------------------------------------------------------
# Core check function (testable entry point)
# ---------------------------------------------------------------------------

def _scan_file(path: str, config: dict) -> list[_Violation]:
    """Scan a single test file and return all bloat violations found.

    Args:
        path: Absolute path to a test_*.py file.
        config: The ``test_fixture_bloat`` config dict.

    Returns:
        List of _Violation objects; empty list means the file is clean.
    """
    try:
        source = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"[check_test_fixture_bloat] WARNING: cannot read {path}: {exc}",
            file=sys.stderr,
        )
        return []

    if _has_noqa(source):
        print(
            f"[check_test_fixture_bloat] skip {path} (# noqa: fixture-bloat)",
            file=sys.stderr,
        )
        return []

    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        print(
            f"[check_test_fixture_bloat] WARNING: syntax error in {path}: {exc}",
            file=sys.stderr,
        )
        return []

    violations: list[_Violation] = []
    violations.extend(_check_line_count(path, source, config))
    violations.extend(_check_inline_dicts(path, tree, config))
    violations.extend(_check_parametrize_rows(path, tree, config))
    return violations


def main(staged_files: list[str] | None = None, config: dict | None = None) -> int:
    """Run the fixture-bloat check on a list of staged test files.

    This function is the canonical entry point for both the pre-commit hook
    (called with no arguments — files and config are loaded internally) and
    unit tests (called with explicit ``staged_files`` and ``config``).

    Args:
        staged_files: List of absolute paths to test_*.py files to scan.
            When ``None``, files are enumerated via ``git diff --cached``.
        config: The ``test_fixture_bloat`` config dict. When ``None``, config
            is loaded from ``commit_guardian.json``.

    Returns:
        0 if no violations found, or if ``enabled`` is ``False`` (warn-only).
        1 if violations found and ``enabled`` is ``True`` (enforce mode).
    """
    # ------------------------------------------------------------------
    # Resolve config
    # ------------------------------------------------------------------
    if config is None:
        try:
            from config import load_config
            raw = load_config()
            config = raw.get("test_fixture_bloat", {})
        except Exception as exc:  # noqa: BLE001
            print(
                f"[check_test_fixture_bloat] WARNING: could not load config: {exc}",
                file=sys.stderr,
            )
            config = {}

    enabled: bool = config.get("enabled", False)
    max_lines: int = config.get("max_test_file_lines", 500)
    max_dict_keys: int = config.get("max_inline_dict_keys", 5)
    max_parametrize_rows: int = config.get("max_parametrize_rows", 3)
    grandfathered: list[str] = config.get("grandfathered_paths", [])

    # ------------------------------------------------------------------
    # Resolve staged files
    # ------------------------------------------------------------------
    if staged_files is None:
        staged_files = _get_staged_test_files()

    # Filter to test_*.py only (caller may pass mixed lists)
    test_files = [
        f for f in staged_files
        if Path(f).name.startswith("test_") and Path(f).suffix == ".py"
    ]

    # ------------------------------------------------------------------
    # Scan each file
    # ------------------------------------------------------------------
    all_violations: list[_Violation] = []

    for path in test_files:
        resolved = str(Path(path).resolve())

        # Grandfathered-path check (match on resolved absolute or basename)
        if any(
            resolved == str(Path(gf).resolve()) or resolved.endswith(gf)
            for gf in grandfathered
        ):
            print(
                f"[check_test_fixture_bloat] [grandfathered] skip {path}",
                file=sys.stderr,
            )
            continue

        violations = _scan_file(resolved, config)
        all_violations.extend(violations)

    # ------------------------------------------------------------------
    # Report
    # ------------------------------------------------------------------
    if not all_violations:
        return 0

    prefix = "ERROR" if enabled else "WARNING"
    for v in all_violations:
        print(
            f"[check_test_fixture_bloat] {prefix}: {v.path} — {v.detail}",
            file=sys.stderr,
        )

    if not enabled:
        # Warn-only mode: print but do not block
        return 0

    # Enforce mode: block the commit
    print(
        f"[check_test_fixture_bloat] {len(all_violations)} violation(s) found. "
        "Commit blocked. Set enabled=false for warn-only or add "
        "# noqa: fixture-bloat to suppress per-file.",
        file=sys.stderr,
    )
    return 1


# ---------------------------------------------------------------------------
# Pre-commit entry point (called by run_hook.py with no arguments)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
