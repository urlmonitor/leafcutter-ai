"""
MODULE: check_placeholder_defaults
GOAL: Pre-commit hook — uses AST analysis to detect the combined signal of a
    placeholder function and a tainted-default rebinding pattern in the same
    Python module, and blocks the commit unless a default-path-smoke test
    marker is present.
BUSINESS CONTEXT: Prevents placeholder-dispatch defects (like the one that
    shipped in EPIC-GlossaryAutomation) from reaching the repository. The hook
    targets the combined structural signal: a placeholder function (docstring or
    return-value containing a placeholder token) AND a tainted-default rebinding
    to that function in the same module.
ARCHITECTURE: AST-based (ast.walk), scoped to staged .py files only. Two escape
    hatches: a sibling test file with "# default-path-smoke: <module_stem>" or a
    module-level "# noqa: default-path-smoke <reason>" suppression. Both signals
    must be present in the same module for the hook to fire (conservative
    combined-signal approach).

    Detection flow per staged .py file:
    1. Parse the module into an AST.
    2. Identify placeholder functions (signal 1): docstring or return-value
       string literal matches PLACEHOLDER_REGEX.
    3. Identify tainted-default rebinding (signal 2): function with a None-
       defaulted parameter followed by "if x is None: x = <placeholder_fn>".
    4. If both signals are present: check escape hatches.
    5. If no escape hatch: emit actionable message and exit 1.
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PLACEHOLDER_REGEX = re.compile(
    r"(?i)(?:\bplaceholder\b|\bstub\b|\bstandalone[-_ ]mode\b|TODO[: ]|FIXME[: ])"
)

_NOQA_PREFIX = "# noqa: default-path-smoke"

# ---------------------------------------------------------------------------
# Signal 1: placeholder function detection
# ---------------------------------------------------------------------------


def detect_placeholder_functions(tree: ast.AST) -> list[str]:
    """Walk an AST and return names of functions whose docstring or return-value
    string literal matches the placeholder regex.

    Both module-level functions and methods inside class bodies are checked.

    Args:
        tree: A parsed AST (e.g. from ``ast.parse``).

    Returns:
        List of function names (strings) that contain the placeholder signal.
    """
    placeholder_names: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Check docstring
        docstring = ast.get_docstring(node)
        if docstring and PLACEHOLDER_REGEX.search(docstring):
            placeholder_names.append(node.name)
            continue

        # Check any string literal in return statements
        for child in ast.walk(node):
            if isinstance(child, ast.Return):
                if child.value is not None:
                    # Collect all string constants in the return expression
                    for subnode in ast.walk(child.value):
                        if isinstance(subnode, ast.Constant) and isinstance(subnode.value, str):
                            if PLACEHOLDER_REGEX.search(subnode.value):
                                placeholder_names.append(node.name)
                                break
                    else:
                        continue
                    break

    return placeholder_names


# ---------------------------------------------------------------------------
# Signal 2: tainted-default rebinding detection (private helpers)
# ---------------------------------------------------------------------------


def _collect_none_defaulted_params(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Return the set of parameter names that default to None.

    Args:
        node: A function definition AST node.

    Returns:
        Set of parameter name strings whose default value is None.
    """
    result: set[str] = set()
    args = node.args
    n_defaults = len(args.defaults)
    for i, default in enumerate(args.defaults):
        if isinstance(default, ast.Constant) and default.value is None:
            arg_index = len(args.args) - n_defaults + i
            if 0 <= arg_index < len(args.args):
                result.add(args.args[arg_index].arg)
    for kwarg, default in zip(args.kwonlyargs, args.kw_defaults):
        if isinstance(default, ast.Constant) and default.value is None:
            result.add(kwarg.arg)
    return result


def _extract_param_from_is_none_test(test: ast.expr) -> str | None:
    """Extract the variable name from a ``x is None`` comparison node.

    Args:
        test: An AST expression node (expected to be an ast.Compare).

    Returns:
        The variable name string if the pattern matches, otherwise None.
    """
    if not isinstance(test, ast.Compare):
        return None
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Is):
        return None
    comparator = test.comparators[0]
    if not isinstance(comparator, ast.Constant) or comparator.value is not None:
        return None
    if isinstance(test.left, ast.Name):
        return test.left.id
    return None


def _tainted_fn_from_assignment(
    body_stmt: ast.stmt,
    param_name: str,
    tainted_set: set[str],
) -> str | None:
    """Check whether a statement is ``param_name = <tainted_fn>``.

    Args:
        body_stmt: A statement from an if-block body.
        param_name: The None-defaulted parameter being checked.
        tainted_set: Set of known placeholder function names.

    Returns:
        The tainted function name if the pattern matches, otherwise None.
    """
    if not isinstance(body_stmt, ast.Assign):
        return None
    if len(body_stmt.targets) != 1:
        return None
    target = body_stmt.targets[0]
    if not isinstance(target, ast.Name) or target.id != param_name:
        return None
    val = body_stmt.value
    if isinstance(val, ast.Name) and val.id in tainted_set:
        return val.id
    if isinstance(val, ast.Attribute) and val.attr in tainted_set:
        return val.attr
    return None


def _check_if_rebinding(
    if_node: ast.If,
    none_defaulted_params: set[str],
    tainted_set: set[str],
) -> str | None:
    """Check whether an if-statement is a tainted rebinding for any None-default param.

    Args:
        if_node: An if-statement AST node.
        none_defaulted_params: Parameters that default to None in the enclosing function.
        tainted_set: Set of known placeholder function names.

    Returns:
        The tainted function name if a rebinding is detected, otherwise None.
    """
    param_name = _extract_param_from_is_none_test(if_node.test)
    if param_name is None or param_name not in none_defaulted_params:
        return None
    for body_stmt in if_node.body:
        tainted = _tainted_fn_from_assignment(body_stmt, param_name, tainted_set)
        if tainted is not None:
            return tainted
    return None


def _scan_function_for_rebinding(
    fn_node: ast.FunctionDef | ast.AsyncFunctionDef,
    tainted_set: set[str],
) -> str | None:
    """Check a function definition for the tainted-default rebinding pattern.

    Args:
        fn_node: A function definition AST node.
        tainted_set: Set of known placeholder function names.

    Returns:
        The tainted function name if the pattern is detected, otherwise None.
    """
    none_defaulted_params = _collect_none_defaulted_params(fn_node)
    if not none_defaulted_params:
        return None
    for stmt in ast.walk(fn_node):
        if isinstance(stmt, ast.If):
            tainted = _check_if_rebinding(stmt, none_defaulted_params, tainted_set)
            if tainted is not None:
                return tainted
    return None


def detect_tainted_defaults(
    tree: ast.AST,
    placeholder_fn_names: list[str],
) -> list[tuple[str, str]]:
    """Walk an AST and return (caller_fn, tainted_fn) pairs where a function
    has a None-defaulted parameter that is rebound to a placeholder function.

    Detection pattern (structural):
        def caller(x=None):
            if x is None:
                x = <tainted_fn>

    The ``<tainted_fn>`` must be in ``placeholder_fn_names``.

    Args:
        tree: A parsed AST.
        placeholder_fn_names: Names of functions identified as placeholders.

    Returns:
        List of ``(caller_function_name, tainted_fn_name)`` tuples.
    """
    if not placeholder_fn_names:
        return []

    tainted_set = set(placeholder_fn_names)
    results: list[tuple[str, str]] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        tainted = _scan_function_for_rebinding(node, tainted_set)
        if tainted is not None:
            results.append((node.name, tainted))

    return results


# ---------------------------------------------------------------------------
# Escape hatch 1: smoke-test marker in sibling test file
# ---------------------------------------------------------------------------


def has_smoke_marker(module_path: Path) -> bool:
    """Return True if a file under ``unit_tests/`` contains the marker
    ``# default-path-smoke: <module_stem>``.

    Searches all .py files under the ``unit_tests/`` directory at the
    repository root (parent of ``leafcutter/`` or ``scripts/``).

    Args:
        module_path: Absolute path to the Python module being checked.

    Returns:
        True if a smoke-test marker for this module is found.
    """
    module_stem = module_path.stem
    marker = f"# default-path-smoke: {module_stem}"

    # Walk up to find the repo root (contains unit_tests/)
    repo_root = _find_repo_root(module_path)
    if repo_root is None:
        return False

    unit_tests_dir = repo_root / "unit_tests"
    if not unit_tests_dir.is_dir():
        return False

    for test_file in unit_tests_dir.rglob("*.py"):
        try:
            content = test_file.read_text(encoding="utf-8", errors="replace")
            if marker in content:
                return True
        except OSError:
            continue
    return False


# ---------------------------------------------------------------------------
# Escape hatch 2: noqa suppression at module top
# ---------------------------------------------------------------------------


def has_noqa_suppression(module_path: Path) -> bool:
    """Return True if the first 5 lines of the module contain a
    ``# noqa: default-path-smoke`` comment.

    Args:
        module_path: Absolute path to the Python module being checked.

    Returns:
        True if the module explicitly opts out of the check.
    """
    try:
        with module_path.open(encoding="utf-8", errors="replace") as fh:
            for i, line in enumerate(fh):
                if i >= 5:
                    break
                if _NOQA_PREFIX in line:
                    return True
    except OSError:
        pass
    return False


# ---------------------------------------------------------------------------
# Helper: locate repo root
# ---------------------------------------------------------------------------


def _find_repo_root(start: Path) -> Path | None:
    """Walk up from ``start`` until a directory containing ``.git`` is found.

    Args:
        start: Starting path (file or directory).

    Returns:
        Absolute Path of the repository root, or None if not found.
    """
    current = start if start.is_dir() else start.parent
    for _ in range(20):
        if (current / ".git").exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


# ---------------------------------------------------------------------------
# Staged file enumeration
# ---------------------------------------------------------------------------


def _get_staged_py_files(repo_root: Path) -> list[Path]:
    """Return absolute paths of staged .py files.

    Args:
        repo_root: Repository root.

    Returns:
        Sorted list of absolute Path objects for staged Python files.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"check-placeholder-defaults: WARNING — git diff failed: "
            f"{(exc.stderr or '').strip()}",
            file=sys.stderr,
        )
        return []

    files: list[Path] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        p = repo_root / line
        if p.suffix == ".py" and p.is_file():
            files.append(p)
    return sorted(files)


# ---------------------------------------------------------------------------
# Per-file check
# ---------------------------------------------------------------------------


def check_file(module_path: Path) -> str | None:
    """Check a single Python module for the combined placeholder-default signal.

    Returns an actionable error message if the combined signal is detected
    without a bypass, or None if the file is clean.

    Args:
        module_path: Absolute path to the Python module.

    Returns:
        Error message string on detection, or None on clean pass.
    """
    try:
        source = module_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    # Escape hatch 2: noqa suppression (fast, no parse needed)
    if has_noqa_suppression(module_path):
        return None

    # Parse AST
    try:
        tree = ast.parse(source, filename=str(module_path))
    except SyntaxError:
        return None

    # Signal 1: placeholder functions
    placeholder_fns = detect_placeholder_functions(tree)
    if not placeholder_fns:
        return None

    # Signal 2: tainted-default rebinding
    tainted_pairs = detect_tainted_defaults(tree, placeholder_fns)
    if not tainted_pairs:
        return None

    # Escape hatch 1: smoke-test marker
    if has_smoke_marker(module_path):
        return None

    # Combined signal detected — build actionable message
    caller_fn, tainted_fn = tainted_pairs[0]
    rel = module_path
    try:
        repo_root = _find_repo_root(module_path)
        if repo_root:
            rel = module_path.relative_to(repo_root)
    except ValueError:
        pass

    return (
        f"check-placeholder-defaults: BLOCKED — {rel}\n"
        f"  Placeholder function '{tainted_fn}' (signal 1) + "
        f"tainted default in '{caller_fn}' (signal 2) detected.\n"
        f"  The production dispatch path is never exercised if callers always "
        f"override the default parameter.\n"
        f"  Fix options:\n"
        f"    A) Add '# default-path-smoke: {module_path.stem}' in a test file "
        f"under unit_tests/ that exercises the {caller_fn}() default path.\n"
        f"    B) Add '# noqa: default-path-smoke <reason>' in the first 5 lines "
        f"of {module_path.name} to explicitly opt out (requires review justification).\n"
        f"    C) Replace '{tainted_fn}' with a real implementation before committing."
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def main(staged_files: list[Path] | None = None) -> int:
    """Run the placeholder-default check on staged (or supplied) Python files.

    Args:
        staged_files: Optional explicit list of files to check. When None,
            staged .py files are discovered via ``git diff --cached``.

    Returns:
        0 on clean pass, 1 if any file has the combined signal without bypass.
    """
    if staged_files is None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip())
        except subprocess.CalledProcessError:
            # Not in a git repo
            return 0
        staged_files = _get_staged_py_files(repo_root)

    errors: list[str] = []
    for py_file in staged_files:
        msg = check_file(py_file)
        if msg:
            errors.append(msg)

    if errors:
        for msg in errors:
            print(msg, file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-18 00:00 [python-coder/EPIC-UserSurfaceVerification/01]: Created. (#EPIC-UserSurfaceVerification/01)
#   Combined-signal AST hook.
#   Targets: placeholder function (docstring/return token) AND tainted-default
#   rebinding in the same module. Both must be present (combined signal).
#   Escape hatches: # default-path-smoke: <module_stem> in unit_tests/,
#   or # noqa: default-path-smoke <reason> at module top.
#   Retroactively detects the check_glossary_coverage.py + glossary_bootstrap.py
#   pattern from EPIC-GlossaryAutomation.
# ====================================================================
