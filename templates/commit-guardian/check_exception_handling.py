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
- 2026-06-17 [GE-107]: Two robustness bug fixes.
  Fix 1 — cursor false-positive: _call_matches_io_boundary previously matched
    .execute()/.executemany()/.callproc() on ANY ast.Name receiver, causing
    false IO-001 violations for unrelated objects (command.execute(),
    workflow.executemany(), executor.callproc()). Narrowed to
    _CURSOR_RECEIVER_NAMES frozenset (cursor, cur, crsr, db_cursor, _cursor,
    dbcur) so only recognised cursor identifiers are flagged.
  Fix 2 — uncaught OSError: main() caught only SyntaxError from analyse_file,
    so path.read_text() raising IsADirectoryError/PermissionError on an
    unreadable .py path produced an uncaught traceback and an exit 1 that
    collided with the legitimate "violations found" exit code. Added
    except OSError alongside except SyntaxError, with a skip message to
    stderr and continue, mirroring check_placeholder_defaults' OSError
    handling and satisfying Error Handling Policy Rule 1.
- 2026-06-17 [GE-108a]: Subprocess calls added as mandatory I/O boundaries.
  Per ADR-014 Decision 1, subprocess spawning is external I/O that must be
  wrapped in try/except. Added six subprocess entry-point forms to
  _IO_BOUNDARIES: subprocess.run, subprocess.Popen, subprocess.call,
  subprocess.check_call, subprocess.check_output, subprocess.getoutput.
  The commit_guardian.json io_boundary_calls list was updated in parity.
  Self-hosting non-regression verified: leafcutter's own subprocess calls
  are already wrapped in try/except and produce no IO-001 violations.
- 2026-06-18 [GE-108b]: Blind-catch handler cleared only by WARNING-or-higher
  logging on a real logger object (ADR-014 Decision 2).
  Replaced _LOG_CALL_NAMES (broad name-set) with _WARNING_LOG_METHODS
  (warning, error, critical, exception only). _handler_reraises_or_logs now
  requires calls to be in attribute form (ast.Attribute node), so a bare
  function call like error() or debug() no longer clears the handler regardless
  of name. Sub-WARNING methods (debug, info) and print() are explicitly excluded.
  Self-hosting non-regression verified: all production handlers in leafcutter
  already use WARNING-or-higher logging or re-raise.
- 2026-06-18 [GE-108c]: BLE001 message now renders tuple exception types in full.
  Previously, except (ValueError, Exception): collapsed to just "Exception" in
  the violation message because the type_name branch only handled ast.Name.
  Added an ast.Tuple branch that joins the element names with ", " and wraps
  them in parentheses, producing e.g. "(ValueError, Exception)" in the message.
  Detection logic (what is flagged and at which line/col) is unchanged.
====================================================================
"""

from __future__ import annotations

import ast
import json
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
    ("subprocess", "run"),
    ("subprocess", "Popen"),
    ("subprocess", "call"),
    ("subprocess", "check_call"),
    ("subprocess", "check_output"),
    ("subprocess", "getoutput"),
]

# Recognised cursor receiver names for IO boundary detection.
# Only ast.Name receiver ids in this set trigger IO-001 for cursor methods
# (execute, executemany, callproc). Names outside this set are not database
# cursors and must not be flagged, avoiding false positives on objects such
# as command.execute(), workflow.executemany(), executor.callproc().
_CURSOR_RECEIVER_NAMES: frozenset[str] = frozenset({
    "cursor",
    "cur",
    "crsr",
    "db_cursor",
    "_cursor",
    "dbcur",
})

# Exception type names considered "blind" — too broad without reraise/log
_BLIND_EXCEPTION_NAMES: frozenset[str] = frozenset({"Exception", "BaseException"})

# WARNING-or-higher method names that clear a blind-catch handler when called as
# an attribute on an object (e.g. ``logger.warning(...)``).  Only attribute-call
# form is accepted — bare function calls like ``error()`` do NOT clear the handler
# regardless of name (ADR-014 Decision 2 / GE-108b).
_WARNING_LOG_METHODS: frozenset[str] = frozenset({
    "warning",
    "error",
    "critical",
    "exception",
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
    """Return True if the handler body contains a reraise or WARNING-or-higher logging.

    A handler is non-silent when it:
    - Re-raises the exception (bare ``raise`` or ``raise NewError from exc``), OR
    - Calls a WARNING-or-higher log method as an **attribute** on an object, i.e.
      ``<expr>.warning(...)``, ``<expr>.error(...)``, ``<expr>.critical(...)``,
      or ``<expr>.exception(...)``.

    What does NOT clear the handler (ADR-014 Decision 2 / GE-108b):
    - A bare function call whose name coincidentally matches a log-level name,
      e.g. ``error()`` — these are NOT attribute calls on a real logger object.
    - Sub-WARNING log calls: ``logger.debug(...)``, ``logger.info(...)``.
    - ``print(...)`` or any non-logger call.

    The detection is purely AST-based: the receiver of the attribute call is NOT
    resolved to a concrete type; it is sufficient that the call is in attribute
    form (``ast.Attribute`` node) with a WARNING-or-higher method name, so that
    a name-coincidence bare call (``ast.Name``) is always rejected.

    Args:
        handler: The ExceptHandler node to examine.

    Returns:
        True if the handler body re-raises or contains genuine WARNING-or-higher
        logging on a real (attribute-accessed) logger object.
    """
    for node in ast.walk(ast.Module(body=handler.body, type_ignores=[])):
        if isinstance(node, ast.Raise):
            # Any raise (bare re-raise or raise SomeError from exc) is non-silent.
            return True
        if isinstance(node, ast.Call):
            func = node.func
            # ONLY accept attribute-call form: <obj>.warning(...) etc.
            # A bare Name call (e.g. error()) is always rejected — name
            # coincidence with a log level does not indicate a real logger.
            if isinstance(func, ast.Attribute):
                if func.attr in _WARNING_LOG_METHODS:
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
                # For cursor methods (execute, executemany, callproc): only match
                # receiver names that are recognised cursor identifiers
                # (_CURSOR_RECEIVER_NAMES). This prevents false positives on
                # unrelated objects such as command.execute(), executor.callproc().
                if mod == "cursor" and isinstance(value, ast.Name) and value.id in _CURSOR_RECEIVER_NAMES:
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
                if isinstance(node.type, ast.Name):
                    type_name = node.type.id
                elif isinstance(node.type, ast.Tuple):
                    inner = ", ".join(
                        elt.id for elt in node.type.elts if isinstance(elt, ast.Name)
                    )
                    type_name = f"({inner})"
                else:
                    type_name = "Exception"
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
# Agent registry lookup (mirrors check_complexity.py pattern)
# ---------------------------------------------------------------------------


def _get_agent_for_extension(ext: str) -> str | None:
    """Return the agent id whose owns_file_extensions contains the given extension.

    Reads ``agent_registry.json`` relative to this script's project root.
    Fails open: returns ``None`` when the registry is missing, unreadable,
    or contains no matching entry.

    Args:
        ext: File extension with leading dot, e.g. ``".py"``.

    Returns:
        Agent id string (e.g. ``"python-coder"``) if a match is found,
        else ``None``.
    """
    script_dir = Path(__file__).resolve().parent
    # Search for the registry relative to the script location (handles both
    # source layout scripts/commit_guardian/ and deployed layout).
    for ancestor in [script_dir, *script_dir.parents]:
        candidate = ancestor / "leafcutter" / "config" / "agent_registry.json"
        if candidate.exists():
            registry_path = candidate
            break
    else:
        return None

    try:
        with open(registry_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None

    for entry in data.get("agents", []):
        extensions = entry.get("owns_file_extensions") or []
        if ext in extensions:
            return entry.get("id")
    return None


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
        except OSError as exc:
            # path.read_text() raises OSError (IsADirectoryError, PermissionError,
            # etc.) when the path ends in .py but cannot be read as a text file.
            # Catch and skip rather than letting the traceback propagate — mirrors
            # check_placeholder_defaults' OSError handling and satisfies Error
            # Handling Policy Rule 1 (external I/O must be wrapped).
            print(
                f"check_exception_handling: cannot read {file_path}: {exc}",
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

    if found_any:
        # Machine-readable autofix hint — parsed by the precommit-autofix skill
        # to route directly to the correct coder. Looked up from agent_registry.json
        # via owns_file_extensions; falls back to python-coder when the lookup
        # returns None (exception-handling violations are always Python).
        agent = _get_agent_for_extension(".py") or "python-coder"
        print(f"AUTOFIX_AGENT: {agent}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
