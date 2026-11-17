"""
MODULE: scripts/build_orchestration/_cs_symbols.py
GOAL: Split a test file's source into the named, comparable symbols of the sweep check
    (TQ-500g-3-i): every top-level statement is one or more symbols, nothing is skipped.
BUSINESS CONTEXT: An edit to an existing test or fixture can hide in module-level code (a
    ``pytest.skip`` call, an import, ``pytestmark +=``, a block around the tests). Every top-level
    statement therefore becomes a symbol with a stable name the test writer can list verbatim.
ARCHITECTURE: Pure functions over ``ast``; no I/O. Names: functions and classes by name,
    methods as ``Class::method``, assignments by target name (a tuple one symbol per name,
    ``set:<target>`` for attribute and subscript targets), imports as ``import:<bound name>``,
    expression statements as ``call:<func>`` / ``expr:<kind>``, a block (if/try/with/for/while/
    match) as ``<kind>:<header>`` holding the block with its nested defs cut out, and every def
    inside a block under its own name. Statements of equal name are merged in source order.
    Line endings are normalised and lines cut on a line feed only, so control characters never
    shift the ``ast`` line numbers. Used by ``_cs_edits.py``.
"""

from __future__ import annotations

import ast
import copy
from collections.abc import Iterator
from dataclasses import dataclass

_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)
_BLOCKS = (ast.If, ast.Try, ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While, ast.Match,
           getattr(ast, "TryStar", ast.Try))


@dataclass
class Symbol:
    """One comparable top-level piece of a test file: a test, a fixture, a helper, a constant."""

    source: str
    node: ast.AST | None = None


def normalise(source: str) -> str:
    """Return *source* with every line ending turned into a line feed (the only break used for cutting)."""
    return source.replace("\r\n", "\n").replace("\r", "\n")


def _first_line(node: ast.AST) -> int:
    """The first source line of *node*, its first decorator included."""
    return min([node.lineno, *(d.lineno for d in getattr(node, "decorator_list", []))])  # type: ignore[attr-defined]


def _segment(lines: list[str], node: ast.AST) -> str:
    """The source lines of *node* including its decorators."""
    return "\n".join(lines[_first_line(node) - 1 : node.end_lineno])  # type: ignore[attr-defined]


def _add(out: dict[str, Symbol], name: str, source: str, node: ast.AST | None) -> None:
    """Store a symbol; a second statement of the same name is appended to the first."""
    name = " ".join(name.split())
    known = out.get(name)
    if known is None:
        out[name] = Symbol(source, node)
    else:
        out[name] = Symbol(known.source + "\n" + source, known.node)


def _class_symbols(lines: list[str], cls: ast.ClassDef, out: dict[str, Symbol]) -> None:
    """Add each method as ``Class::method`` and the class shell (methods cut out) as ``Class``."""
    rest = []
    for stmt in cls.body:
        if isinstance(stmt, _DEFS):
            _add(out, f"{cls.name}::{stmt.name}", _segment(lines, stmt), stmt)
        else:
            rest.append(_segment(lines, stmt))
    head = "\n".join(lines[cls.lineno - 1 : _first_line(cls.body[0]) - 1])
    decorators = [_segment(lines, d) for d in cls.decorator_list]
    _add(out, cls.name, "\n".join([*decorators, head, *rest]), None)


def _target_names(target: ast.AST) -> list[str]:
    """The symbol names an assignment target binds: one per name, ``set:<target>`` otherwise."""
    if isinstance(target, ast.Name):
        return [target.id]
    if isinstance(target, (ast.Tuple, ast.List)):
        return [n for elt in target.elts for n in _target_names(elt)]
    if isinstance(target, ast.Starred):
        return _target_names(target.value)
    return [f"set:{ast.unparse(target)}"]


def _assign_names(stmt: ast.stmt) -> list[str]:
    """The distinct symbol names of an assignment statement, in source order."""
    targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]  # type: ignore[attr-defined]
    return list(dict.fromkeys(n for t in targets for n in _target_names(t)))


def _import_names(stmt: ast.stmt) -> list[str]:
    """``import:<bound name>`` for each name an import statement binds."""
    return [f"import:{(a.asname or a.name).split('.')[0]}" for a in stmt.names]  # type: ignore[attr-defined]


def _expr_name(stmt: ast.Expr) -> str:
    """The name of a bare expression statement."""
    value = stmt.value
    if isinstance(value, ast.Call):
        return f"call:{ast.unparse(value.func)}"
    if isinstance(value, ast.Constant) and isinstance(value.value, str):
        return "expr:docstring"
    return f"expr:{type(value).__name__.lower()}"


def _block_name(stmt: ast.stmt) -> str:
    """``<kind>:<header>`` of a block statement."""
    kind = type(stmt).__name__.lower()
    if isinstance(stmt, (ast.If, ast.While)):
        return f"{kind}:{ast.unparse(stmt.test)}"
    if isinstance(stmt, (ast.For, ast.AsyncFor)):
        return f"{kind}:{ast.unparse(stmt.target)} in {ast.unparse(stmt.iter)}"
    if isinstance(stmt, (ast.With, ast.AsyncWith)):
        return f"{kind}:" + ", ".join(ast.unparse(i.context_expr) for i in stmt.items)
    if isinstance(stmt, ast.Match):
        return f"{kind}:{ast.unparse(stmt.subject)}"
    return kind


class _DropDefs(ast.NodeTransformer):
    """Cut every nested function and class out of a block; an emptied body gets ``pass``."""

    def visit_FunctionDef(self, node: ast.AST) -> None:  # noqa: N802 -- ast visitor protocol
        """Drop the def (the visitor returns ``None`` to remove a node)."""
        return None

    visit_AsyncFunctionDef = visit_ClassDef = visit_FunctionDef  # noqa: N815

    def generic_visit(self, node: ast.AST) -> ast.AST:
        """Visit the children, then keep a body that lost all its statements valid."""
        node = super().generic_visit(node)
        if isinstance(getattr(node, "body", None), list) and not node.body:  # type: ignore[attr-defined]
            node.body = [ast.Pass()]  # type: ignore[attr-defined]
        return node


def _child_lists(stmt: ast.stmt) -> Iterator[list[ast.stmt]]:
    """Every statement list directly inside a block statement."""
    for field in ("body", "orelse", "finalbody"):
        value = getattr(stmt, field, None)
        if isinstance(value, list):
            yield value
    for handler in getattr(stmt, "handlers", []):
        yield handler.body
    for case in getattr(stmt, "cases", []):
        yield case.body


def _nested_defs(lines: list[str], block: ast.stmt, out: dict[str, Symbol]) -> None:
    """Add every def and class inside *block* (however deep in blocks) under its own name."""
    for stmts in _child_lists(block):
        for stmt in stmts:
            if isinstance(stmt, (*_DEFS, ast.ClassDef)):
                _statement(lines, stmt, out)
            elif isinstance(stmt, _BLOCKS):
                _nested_defs(lines, stmt, out)


def _statement(lines: list[str], stmt: ast.stmt, out: dict[str, Symbol]) -> None:
    """Add the symbol(s) of one statement."""
    if isinstance(stmt, _DEFS):
        _add(out, stmt.name, _segment(lines, stmt), stmt)
    elif isinstance(stmt, ast.ClassDef):
        _class_symbols(lines, stmt, out)
    elif isinstance(stmt, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        for name in _assign_names(stmt):
            _add(out, name, _segment(lines, stmt), stmt)
    elif isinstance(stmt, (ast.Import, ast.ImportFrom)):
        for name in _import_names(stmt):
            _add(out, name, _segment(lines, stmt), stmt)
    elif isinstance(stmt, ast.Expr):
        _add(out, _expr_name(stmt), _segment(lines, stmt), stmt)
    elif isinstance(stmt, _BLOCKS):
        _add(out, _block_name(stmt), ast.unparse(_DropDefs().visit(copy.deepcopy(stmt))), stmt)
        _nested_defs(lines, stmt, out)
    else:
        _add(out, f"{type(stmt).__name__.lower()}:{ast.unparse(stmt)}", _segment(lines, stmt), stmt)


def symbols(source: str) -> dict[str, Symbol]:
    """Split *source* into its top-level symbols keyed by name (``Class::method`` for methods).

    Raises ``SyntaxError`` when it does not parse.
    """
    text = normalise(source)
    tree = ast.parse(text)
    lines = text.split("\n")
    out: dict[str, Symbol] = {}
    for stmt in tree.body:
        _statement(lines, stmt, out)
    return out
