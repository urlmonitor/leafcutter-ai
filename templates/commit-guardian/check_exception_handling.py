"""
MODULE: check_exception_handling
GOAL: Pre-commit AST hook that flags exception-handling violations in Python
    source files: bare except: clauses, blind except Exception: without
    re-raise or logging, and calls to known I/O boundaries (requests.get,
    open, cursor.execute) that are not enclosed by a try/except block.
BUSINESS CONTEXT: Prevents silently swallowed exceptions from reaching commit.
    This is the static-analysis complement to the Ruff rules (E722, BLE001,
    TRY) that the pre-commit config also runs; Ruff catches the exception-
    clause violations, this script catches the missing-wrapper pattern at I/O
    call sites. Together they enforce the error-handling policy from
    EPIC-ErrorHandlingEnforcement.
ARCHITECTURE: Pure-stdlib AST visitor; no external dependencies, no
    leafcutter-internal imports. Designed for portability — this file is
    copied verbatim by build.py to any target project under
    scripts/commit_guardian/. Accepts a single positional argument: the path
    to the Python file to analyse. Exits 0 on clean, 1 on violations.

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-01 [EPIC-ErrorHandlingEnforcement/01]: Initial implementation.
  Three violation classes:
    1. Bare except: (E722 equivalent)
    2. Blind except Exception: without re-raise or logger call (BLE001 equivalent)
    3. I/O boundary calls (requests.get, open, cursor.execute) not enclosed
       in a try/except block.
  Exit code 1 on any violation; 0 on clean file.
  Self-contained: only stdlib imports (ast, sys, pathlib).
====================================================================
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Violation type
# ---------------------------------------------------------------------------


class Violation(NamedTuple):
    """A single violation found in the source file.

    Attributes:
        line: 1-based line number of the offending code.
        col: 1-based column number of the offending code.
        code: Short rule code (e.g. E722, BLE001, IO-001).
        message: Human-readable description of the violation.
    """

    line: int
    col: int
    code: str
    message: str


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# I/O boundary calls that must be enclosed in try/except.
# Each entry is (module_prefix_or_None, method_name):
#   - module_prefix: the dotted object prefix (e.g. "requests"), or None for builtins
#   - method_name: the call's attribute/function name (e.g. "get", "open")
_IO_BOUNDARIES: list[tuple[str | None, str]] = [
    ("requests", "get"),
    ("requests", "post"),
    ("requests", "put"),
    ("requests", "patch"),
    ("requests", "delete"),
    ("requests", "head"),
    ("requests", "options"),
    ("requests", "request"),
    (None, "open"),
    ("cursor", "execute"),
    ("cursor", "executemany"),
    ("cursor", "callproc"),
]

# Exception type names considered "blind" — too broad without reraise/log
_BLIND_EXCEPTION_NAMES: frozenset[str] = frozenset({"Exception", "BaseException"})

# Call attributes/names whose presence in an except body signals non-silent handling
_LOG_CALL_NAMES: frozenset[str] = frozenset({
    "log",
    "logger",
    "logging",
    "warn",
    "warning",
    "error",
    "critical",
    "exception",
    "info",
    "debug",
    "print",
})


# ---------------------------------------------------------------------------
# Helper: walk a node and collect all its descendant nodes
# ---------------------------------------------------------------------------

def _descendants(node: ast.AST) -> list[ast.AST]:
    """Return all descendants of *node* (excluding *node* itself).

    Args:
        node: The root AST node.

    Returns:
        Flat list of all descendant AST nodes.
    """
    result: list[ast.AST] = []
    for child in ast.walk(node):
        if child is not node:
            result.append(child)
    return result


# ---------------------------------------------------------------------------
# Helper: check whether a handler is blind
# ---------------------------------------------------------------------------

def _handler_is_blind(handler: ast.ExceptHandler) -> bool:
    """Return True if the handler catches a blind (too-broad) exception type.

    A handler is blind when it has no type (bare except:) or catches
    Exception/BaseException.

    Args:
        handler: The ExceptHandler node to examine.

    Returns:
        True if the handler is considered blind.
    """
    if handler.type is None:
        return True  # bare except:
    if isinstance(handler.type, ast.Name) and handler.type.id in _BLIND_EXCEPTION_NAMES:
        return True
    if isinstance(handler.type, ast.Tuple):
        for elt in handler.type.elts:
            if isinstance(elt, ast.Name) and elt.id in _BLIND_EXCEPTION_NAMES:
                return True
    return False


def _handler_reraises_or_logs(handler: ast.ExceptHandler) -> bool:
    """Return True if the handler body contains a reraise or a log/print call.

    This signals that the exception is not silently swallowed even if the
    handler catches a broad type.

    Args:
        handler: The ExceptHandler node to examine.

    Returns:
        True if the handler body re-raises or logs the exception.
    """
    for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if isinstance(node, ast.Raise):
            # Any raise (bare re-raise or raise SomeError) is non-silent
            return True
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id.lower() in _LOG_CALL_NAMES:
                return True
            if isinstance(func, ast.Attribute):
                if func.attr.lower() in _LOG_CALL_NAMES:
                    return True
                if isinstance(func.value, ast.Name) and func.value.id.lower() in _LOG_CALL_NAMES:
                    return True
    return False


# ---------------------------------------------------------------------------
# Helper: check whether a Call node is a known I/O boundary
# ---------------------------------------------------------------------------

def _call_matches_io_boundary(call: ast.Call) -> tuple[str, str] | None:
    """Return (module_label, attr) if *call* is a known I/O boundary call.

    Args:
        call: The Call AST node to test.

    Returns:
        (module_label, attr_name) if the call is an I/O boundary, else None.
    """
    func = call.func
    if isinstance(func, ast.Attribute):
        attr = func.attr
        value = func.value
        for mod, boundary_attr in _IO_BOUNDARIES:
            if mod is not None and attr == boundary_attr:
                # Named module: requests.get, cursor.execute, etc.
                if isinstance(value, ast.Name) and value.id == mod:
                    return (mod, attr)
                # For cursor.execute: match any variable name whose attr is execute
                if mod == "cursor" and isinstance(value, ast.Name):
                    return (value.id, attr)
        return None
    if isinstance(func, ast.Name):
        for mod, boundary_attr in _IO_BOUNDARIES:
            if mod is None and func.id == boundary_attr:
                return ("", boundary_attr)
    return None


# ---------------------------------------------------------------------------
# Core analysis function
# ---------------------------------------------------------------------------

def _collect_try_node_ids(tree: ast.AST) -> set[int]:
    """Collect the object ids of all AST nodes that are inside a try block.

    Specifically: any node that is a descendant of the *body* of a Try node
    (not a handler, finalbody, or orelse) is "enclosed in try/except".

    Args:
        tree: The root AST node to walk.

    Returns:
        Set of ``id(node)`` for every node enclosed in a try body.
    """
    enclosed: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            for stmt in node.body:
                for descendant in ast.walk(stmt):
                    enclosed.add(id(descendant))
        # Python 3.11+ TryStar
        if hasattr(ast, "TryStar") and isinstance(node, ast.TryStar):
            for stmt in node.body:
                for descendant in ast.walk(stmt):
                    enclosed.add(id(descendant))
    return enclosed


def analyse_file(path: Path) -> list[Violation]:
    """Parse and analyse one Python source file for exception-handling violations.

    Args:
        path: Absolute or relative path to the .py file.

    Returns:
        List of Violation instances; empty if the file is clean.

    Raises:
        SyntaxError: If the file cannot be parsed as valid Python.
    """
    source = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(source, filename=str(path))

    violations: list[Violation] = []

    # Precompute the set of node ids that are inside a try body
    enclosed_ids = _collect_try_node_ids(tree)

    for node in ast.walk(tree):

        # ---- Except-handler checks (E722 / BLE001) ----
        if isinstance(node, ast.ExceptHandler):
            if node.type is None:
                # Bare except:
                violations.append(Violation(
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code="E722",
                    message=(
                        f"bare except: clause at line {node.lineno} — "
                        "specify the exception type(s) explicitly (E722)"
                    ),
                ))
            elif _handler_is_blind(node) and not _handler_reraises_or_logs(node):
                type_name = (
                    node.type.id
                    if isinstance(node.type, ast.Name)
                    else "Exception"
                )
                violations.append(Violation(
                    line=node.lineno,
                    col=node.col_offset + 1,
                    code="BLE001",
                    message=(
                        f"blind except {type_name}: at line {node.lineno} without "
                        "re-raise or log — silently swallowed exceptions hide bugs (BLE001)"
                    ),
                ))

        # ---- I/O boundary call checks (IO-001) ----
        if isinstance(node, ast.Call):
            match = _call_matches_io_boundary(node)
            if match is not None:
                mod, attr = match
                call_repr = f"{mod}.{attr}()" if mod else f"{attr}()"
                if id(node) not in enclosed_ids:
                    violations.append(Violation(
                        line=node.lineno,
                        col=node.col_offset + 1,
                        code="IO-001",
                        message=(
                            f"{call_repr} at line {node.lineno} is not enclosed in "
                            "a try/except block — wrap I/O boundary calls to handle "
                            "network and filesystem failures (IO-001)"
                        ),
                    ))

    # Sort by line number for deterministic output
    violations.sort(key=lambda v: (v.line, v.col))
    return violations


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the exception-handling check on one or more .py files from argv.

    When called from pre-commit with ``pass_filenames: true``, receives a list
    of staged file paths as positional arguments. Processes each file in turn
    and exits 1 if any violations are found across all files.

    Returns:
        0 if all files are clean, 1 if any violations are found, 2 on usage error.
    """
    if len(sys.argv) < 2:
        print("Usage: check_exception_handling.py <path.py> [path2.py ...]", file=sys.stderr)
        return 2

    file_paths = [Path(p) for p in sys.argv[1:]]
    found_any = False

    for file_path in file_paths:
        if not file_path.exists():
            print(
                f"check_exception_handling: file not found: {file_path}",
                file=sys.stderr,
            )
            continue

        if file_path.suffix != ".py":
            # Non-Python files are silently skipped
            continue

        try:
            violations = analyse_file(file_path)
        except SyntaxError as exc:
            # Syntax errors are already caught by other hooks (e.g. ruff); skip.
            print(
                f"check_exception_handling: syntax error in {file_path}: {exc}",
                file=sys.stderr,
            )
            continue

        if not violations:
            continue

        found_any = True
        print(
            f"check_exception_handling: {len(violations)} violation(s) in {file_path}:"
        )
        for v in violations:
            print(f"  {file_path}:{v.line}:{v.col}: {v.code} {v.message}")

    return 1 if found_any else 0


if __name__ == "__main__":
    sys.exit(main())
