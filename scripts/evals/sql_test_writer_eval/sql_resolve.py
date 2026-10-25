"""
MODULE: scripts/evals/sql_test_writer_eval/sql_resolve.py
GOAL: Find the SQL a produced test actually sends to the database: the SQL argument of every
    ``execute`` / ``executemany`` call (and of every call to a helper that executes its parameter),
    with the names, f-string holes, ``+`` joins and ``text()`` / ``dedent()`` wrappers resolved.
BUSINESS CONTEXT: TQ-200d-2. No database is available to the eval, so the empty-window query is
    checked structurally. Counts that sit in a docstring, a comment, an assert message or a string
    that is never executed do not make a window check fail on an empty or all-NULL window.
ARCHITECTURE: Pure ast helpers. A name resolves in the call's own function first, then its class,
    then the module, so two tests that reuse a name do not read each other's SQL, whatever the
    order. ``self.X`` and ``ClassName.X`` resolve to a class-body attribute. Anything that cannot be
    resolved becomes a blank, so a resolved text never gains words it did not have; a helper's own
    ``execute(sql)`` therefore stays blank and only its call sites count.
"""

from __future__ import annotations

import ast

MAX_DEPTH = 6
BLANK = " "
EXECUTE_NAMES = frozenset({"execute", "executemany"})
WRAPPER_NAMES = frozenset({"text", "dedent"})
SELF_NAMES = frozenset({"self", "cls"})
FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)
NESTED = (*FUNCTIONS, ast.ClassDef, ast.Lambda)
NESTED_FIELDS = ("body", "orelse", "finalbody", "handlers")


def assigned_names(owner: ast.AST) -> dict[str, ast.AST]:
    """``name -> value`` for the plain and annotated assignments directly in *owner*'s scope (not in nested defs)."""
    found: dict[str, ast.AST] = {}
    pending = list(getattr(owner, "body", []))
    while pending:
        node = pending.pop(0)
        if isinstance(node, NESTED):
            continue
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            found[node.target.id] = node.value
        for field in NESTED_FIELDS:
            pending = list(getattr(node, field, None) or []) + pending
    return found


def call_name(call: ast.Call) -> str:
    """The attribute or plain name a call goes through; empty when it is neither."""
    return getattr(call.func, "attr", None) or getattr(call.func, "id", None) or ""


def executed_parameter(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> int | None:
    """The index (``self`` not counted) of the parameter *fn* passes to ``execute``; None when it executes none."""
    params = [a.arg for a in fn.args.args if a.arg not in SELF_NAMES]
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and call_name(node) in EXECUTE_NAMES and node.args:
            first = node.args[0]
            if isinstance(first, ast.Name) and first.id in params:
                return params.index(first.id)
    return None


def helper_index(tree: ast.AST) -> dict[tuple[str, str], int]:
    """``(owner class or "", function name) -> executed parameter index`` for each module function and method that executes a parameter."""
    index: dict[tuple[str, str], int] = {}
    for holder in (tree, *(c for c in ast.walk(tree) if isinstance(c, ast.ClassDef))):
        owner = "" if holder is tree else holder.name
        for fn in (f for f in holder.body if isinstance(f, FUNCTIONS)):
            position = executed_parameter(fn)
            if position is not None:
                index[(owner, fn.name)] = position
    return index


def parameter_names(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Every parameter name of *fn*: positional-only, positional, keyword-only, ``*args`` and ``**kwargs``."""
    args = fn.args
    named = [*args.posonlyargs, *args.args, *args.kwonlyargs, *(a for a in (args.vararg, args.kwarg) if a)]
    return [a.arg for a in named]


def sql_argument(call: ast.Call) -> ast.AST | None:
    """The SQL of an ``execute`` / ``executemany`` call: its first argument or its ``sql=`` keyword."""
    if not isinstance(call.func, ast.Attribute) or call.func.attr not in EXECUTE_NAMES:
        return None
    if call.args:
        return call.args[0]
    return next((k.value for k in call.keywords if k.arg == "sql"), None)


class SqlResolver:
    """Resolve string expressions of one parsed produced test to the text they build."""

    def __init__(self, tree: ast.AST) -> None:
        """Index the module scope, the class-body attributes and the helpers that execute a parameter."""
        self.tree = tree
        self.module = assigned_names(tree)
        self.classes = {c.name: assigned_names(c) for c in ast.walk(tree) if isinstance(c, ast.ClassDef)}
        self.helpers = helper_index(tree)
        self.scopes: list[dict[str, ast.AST]] = []
        self.owner = ""

    def text(self, node: ast.AST, depth: int = 0) -> str:
        """The text *node* evaluates to, with a blank for any part that cannot be resolved."""
        if depth > MAX_DEPTH:
            return BLANK
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return "".join(self.text(v.value if isinstance(v, ast.FormattedValue) else v, depth + 1) for v in node.values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return self.text(node.left, depth + 1) + self.text(node.right, depth + 1)
        if isinstance(node, ast.Call) and node.args and call_name(node) in WRAPPER_NAMES:
            return self.text(node.args[0], depth + 1)
        if isinstance(node, (ast.Name, ast.Attribute)):
            target = self.lookup(node)
            return self.text(target, depth + 1) if target is not None else BLANK
        return BLANK

    def lookup(self, node: ast.Name | ast.Attribute) -> ast.AST | None:
        """The assigned value of a name (function, class, module scope in turn) or of ``self.X`` / ``Class.X``."""
        if isinstance(node, ast.Attribute):
            if not isinstance(node.value, ast.Name):
                return None
            owner = self.owner if node.value.id in SELF_NAMES else node.value.id
            return self.classes.get(owner, {}).get(node.attr)
        for scope in (*reversed(self.scopes), self.classes.get(self.owner, {}), self.module):
            if node.id in scope:
                return scope[node.id]
        return None

    def helper_key(self, call: ast.Call) -> tuple[str, str] | None:
        """The ``(owner, name)`` of the helper a call can reach.

        A bare ``name(...)`` reaches a module function; ``self.`` / ``cls.`` reach a method of the enclosing
        class; ``Class.name(...)`` a method of that class; any other receiver reaches nothing.
        """
        func = call.func
        if isinstance(func, ast.Name):
            return ("", func.id)
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            return (self.owner if func.value.id in SELF_NAMES else func.value.id, func.attr)
        return None

    def query_of(self, call: ast.Call) -> str | None:
        """The lower-cased SQL a call executes (directly, or through a helper), or None when it executes none."""
        arg = sql_argument(call)
        key = self.helper_key(call)
        if arg is None and key in self.helpers and len(call.args) > self.helpers[key]:
            arg = call.args[self.helpers[key]]
        return None if arg is None else self.text(arg).lower()

    def visit(self, node: ast.AST, found: list[str]) -> None:
        """Collect the executed queries under *node*, tracking the enclosing class and function scopes."""
        previous = self.owner
        if isinstance(node, ast.ClassDef):
            self.owner = node.name
        is_function = isinstance(node, FUNCTIONS)
        if is_function:
            blanks = {name: ast.Constant(value=BLANK) for name in parameter_names(node)}
            self.scopes.append({**assigned_names(node), **blanks})
        query = self.query_of(node) if isinstance(node, ast.Call) else None
        if query is not None:
            found.append(query)
        for child in ast.iter_child_nodes(node):
            self.visit(child, found)
        if is_function:
            self.scopes.pop()
        self.owner = previous


def executed_queries(tree: ast.AST) -> list[str]:
    """The lower-cased SQL text of every query the tree executes."""
    found: list[str] = []
    SqlResolver(tree).visit(tree, found)
    return found
