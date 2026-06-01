"""
AST-based docstring validation helpers for the check_docstrings pre-commit hook.

MODULE: docstring_validators.py
GOAL: Provide reusable validation functions for Google-style docstrings via AST inspection.
BUSINESS CONTEXT: Extracted from check_docstrings.py to keep the CLI orchestrator under the 400-line limit.
ARCHITECTURE: Not needed.
"""

import ast
from pathlib import Path

from docstring_parser import parse as parse_docstring, DocstringStyle
from docstring_parser.common import Docstring

from config import (
    DOCSTRING_TRIVIAL_MAX_LINES,
    ENFORCE_TYPE_ANNOTATIONS,
    EXEMPT_DUNDERS,
)


def _get_function_body_lines(node: ast.FunctionDef) -> int:
    """Count body lines excluding the docstring.

    Args:
        node: AST function node.

    Returns:
        int: Number of body lines after stripping the docstring.
    """
    if not node.body:
        return 0

    body = node.body
    # Skip docstring node (first Expr with Constant str)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]

    if not body:
        return 0

    first_line = body[0].lineno
    last_line = body[-1].end_lineno or body[-1].lineno
    return last_line - first_line + 1


def _get_real_params(node: ast.FunctionDef) -> list[str]:
    """Extract parameter names excluding self and cls.

    Args:
        node: AST function node.

    Returns:
        list[str]: Parameter names that need documentation.
    """
    params = []
    for arg in node.args.args:
        if arg.arg not in ("self", "cls"):
            params.append(arg.arg)
    if node.args.vararg:
        params.append(node.args.vararg.arg)
    if node.args.kwarg:
        params.append(node.args.kwarg.arg)
    return params


def _has_return_value(node: ast.FunctionDef) -> bool:
    """Check if a function has a non-None return annotation or non-bare returns.

    Args:
        node: AST function node.

    Returns:
        bool: True if the function returns something worth documenting.
    """
    if node.returns:
        if isinstance(node.returns, ast.Constant) and node.returns.value is None:
            return False
        if isinstance(node.returns, ast.Name) and node.returns.id == "None":
            return False
        return True

    for child in ast.walk(node):
        if isinstance(child, ast.Return) and child.value is not None:
            return True

    return False


def _is_trivial(node: ast.FunctionDef) -> bool:
    """Check if a function is trivial (≤N body lines OR 0 params)."""
    return _get_function_body_lines(node) <= DOCSTRING_TRIVIAL_MAX_LINES or len(_get_real_params(node)) == 0


def _is_exempt_dunder(name: str) -> bool:
    """Check if a method name is an exempt dunder."""
    return name in EXEMPT_DUNDERS


def _violation(filepath: str, func_name: str, line_no: int, msg: str) -> str:
    """Build a formatted docstring violation message.

    Args:
        filepath: File path for reporting.
        func_name: Name of the offending function.
        line_no: Line number of the function.
        msg: Violation detail.

    Returns:
        str: Formatted violation string.
    """
    return f"❌ DOCSTRING VIOLATION: '{filepath}'\n   Function '{func_name}' (line {line_no}): {msg}"


def _check_params(node: ast.FunctionDef, parsed: Docstring, filepath: str) -> list[str]:
    """Check that all params are documented and none are stale.

    Args:
        node: AST function node.
        parsed: Parsed docstring object.
        filepath: File path for error reporting.

    Returns:
        list[str]: Violation messages for param mismatches.
    """
    violations = []
    actual = _get_real_params(node)
    documented = [p.arg_name for p in parsed.params]
    missing = [p for p in actual if p not in documented]
    if actual and missing:
        violations.append(_violation(
            filepath, node.name, node.lineno,
            f"Missing documented params: {missing}\n"
            f"   FIX: Add these to the Args: section."
        ))
    extra = [p for p in documented if p not in actual]
    if documented and extra:
        violations.append(_violation(
            filepath, node.name, node.lineno,
            f"Stale documented params not in signature: {extra}\n"
            f"   FIX: Remove these from the Args: section."
        ))
    return violations


def _check_returns(node: ast.FunctionDef, parsed: Docstring, filepath: str) -> list[str]:
    """Check that a Returns section exists when the function returns a value.

    Args:
        node: AST function node.
        parsed: Parsed docstring object.
        filepath: File path for error reporting.

    Returns:
        list[str]: Violation messages for missing Returns section.
    """
    if not _has_return_value(node):
        return []
    has_returns = parsed.returns is not None or any(r.description for r in parsed.many_returns)
    if has_returns:
        return []
    hint = ""
    if node.returns:
        try:
            hint = ast.unparse(node.returns)
        except Exception:
            hint = "..."
    return [_violation(
        filepath, node.name, node.lineno,
        f"Has return type{f' {hint!r}' if hint else ''} but no Returns: section.\n"
        f"   FIX: Add a Returns: section documenting the return value."
    )]


def _check_param_annotations(node: ast.FunctionDef, filepath: str) -> list[str]:
    """Check that all parameters have type annotations on the signature.

    Args:
        node: AST function node.
        filepath: File path for error reporting.

    Returns:
        list[str]: Violation messages for params missing type hints.
    """
    if not ENFORCE_TYPE_ANNOTATIONS:
        return []
    params = _get_real_params(node)
    if not params:
        return []
    untyped = []
    for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
        if arg.arg in ("self", "cls"):
            continue
        if arg.annotation is None:
            untyped.append(arg.arg)
    if node.args.vararg and node.args.vararg.annotation is None:
        untyped.append(f"*{node.args.vararg.arg}")
    if node.args.kwarg and node.args.kwarg.annotation is None:
        untyped.append(f"**{node.args.kwarg.arg}")
    if untyped:
        return [_violation(
            filepath, node.name, node.lineno,
            f"Parameters missing type annotations: {untyped}\n"
            f"   FIX: Add type hints to the function signature (e.g. 'def foo(x: int) -> str:')."
        )]
    return []


def _check_return_annotation(node: ast.FunctionDef, filepath: str) -> list[str]:
    """Check that the function has a return type annotation.

    Args:
        node: AST function node.
        filepath: File path for error reporting.

    Returns:
        list[str]: Violation messages for missing return type annotation.
    """
    if not ENFORCE_TYPE_ANNOTATIONS:
        return []
    if node.returns is not None:
        return []
    return [_violation(
        filepath, node.name, node.lineno,
        "Missing return type annotation.\n"
        "   FIX: Add a return type to the signature (e.g. '-> None:', '-> str:', '-> list[int]:')."
    )]


def validate_function_docstring(node: ast.FunctionDef, filepath: str) -> list[str]:
    """Validate the docstring of a single function or method.

    Args:
        node: AST function/method node to validate.
        filepath: File path for error reporting.

    Returns:
        list[str]: List of violation messages (empty if no violations).
    """
    if _is_exempt_dunder(node.name):
        return []
    if node.name != "__init__" and _is_trivial(node):
        return []

    docstring = ast.get_docstring(node)
    if not docstring:
        return [_violation(
            filepath, node.name, node.lineno,
            "Missing a docstring.\n   FIX: Add a Google-style docstring with summary, Args, and Returns."
        )]

    parsed = parse_docstring(docstring, style=DocstringStyle.GOOGLE)
    violations = []
    if not parsed.short_description or not parsed.short_description.strip():
        violations.append(_violation(filepath, node.name, node.lineno,
            "Docstring has no summary line.\n   FIX: Add a one-line summary as the first line."))
    violations.extend(_check_params(node, parsed, filepath))
    violations.extend(_check_returns(node, parsed, filepath))
    violations.extend(_check_param_annotations(node, filepath))
    violations.extend(_check_return_annotation(node, filepath))
    return violations


def validate_class_docstring(node: ast.ClassDef, filepath: str) -> list[str]:
    """Validate the docstring of a class definition.

    Args:
        node: AST class node to validate.
        filepath: File path for error reporting.

    Returns:
        list[str]: List of violation messages (empty if no violations).
    """
    if ast.get_docstring(node):
        return []
    return [
        f"❌ DOCSTRING VIOLATION: '{filepath}'\n"
        f"   Class '{node.name}' (line {node.lineno}) is missing a class docstring.\n"
        f"   FIX: Add a docstring describing what this class does."
    ]


def check_file_docstrings(filepath: str) -> list[str]:
    """Parse a Python file and validate all function/class docstrings.

    Args:
        filepath: Path to the Python file to check.

    Returns:
        list[str]: All violations found in the file.
    """
    try:
        content = Path(filepath).read_text(encoding="utf-8")
    except Exception as e:
        return [f"Could not read file '{filepath}': {e}"]

    try:
        tree = ast.parse(content, filename=filepath)
    except SyntaxError as e:
        return [f"Syntax error in '{filepath}': {e}"]

    violations = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            violations.extend(validate_class_docstring(node, filepath))

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            violations.extend(validate_function_docstring(node, filepath))

    return violations


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-01 20:30 [AI]: Extracted from check_docstrings.py to reduce file size
  below 400-line limit. Contains all AST-based validation logic: body line
  counting, param extraction, return checking, trivial/dunder exemptions,
  violation formatting, and per-node validation functions.
====================================================================
"""
