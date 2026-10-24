"""
MODULE: scripts/evals/produced_tests_db.py
GOAL: The structural check of a produced database test (TQ-200d-4), and the registry of every
    database-setting assertion kind of the test-writer and test-runner sets.
BUSINESS CONTEXT: Both agents must use the project's ``testing_context.db_connection_test`` and no
    other address (INF-1100d-2). A produced test passes only when every part of its connection comes
    from ``resolve_test_db_address``; a literal, an environment variable, or a resolver call whose
    result is not what connects, are all addresses of the test's own.
ARCHITECTURE: ``db_test_uses_setting`` parses the test with ast (docstrings ignored). ``KINDS`` merges
    this module's kind with the command kinds (produced_tests_commands.py) and the report kinds
    (produced_tests_reports.py) and is spread into produced_tests_scoring.KINDS.
"""

from __future__ import annotations

import ast
import re
from collections.abc import Callable

import produced_tests_commands as commands
import produced_tests_reports as reports
from produced_tests_runs import RowContext

ADDRESS_STRING_RE = re.compile(r"postgres(?:ql)?://|\b(?:host|port|dbname|hostaddr)\s*=", re.IGNORECASE)
ADDRESS_KWARGS = frozenset({"host", "port", "dbname", "database", "hostaddr"})
CONNECT_KWARGS = ADDRESS_KWARGS | {"dsn", "conninfo", "url"}
CONNECT_NAMES = frozenset({"connect", "create_engine", "create_connection"})
ENV_KEY_RE = re.compile(r"PG|DATABASE_URL|DSN|DB_", re.IGNORECASE)
RESOLVER = "resolve_test_db_address"


def _docstring_ids(tree: ast.AST) -> set[int]:
    """The ids of the Constant nodes that are docstrings, so prose in them is not read as an address."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body:
            first = body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                ids.add(id(first.value))
    return ids


def _literal_addresses(tree: ast.AST) -> list[str]:
    """Every literal address part in a produced test: a DSN or key=value string, or a host/port/dbname kwarg."""
    skip = _docstring_ids(tree)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip and ADDRESS_STRING_RE.search(node.value):
            found.append(f"the string literal {node.value[:40]!r}")
        elif isinstance(node, ast.keyword) and node.arg in ADDRESS_KWARGS and isinstance(node.value, ast.Constant):
            found.append(f"a literal {node.arg}= argument")
        elif isinstance(node, ast.Dict):
            found += [f"a literal {k.value} entry" for k, v in zip(node.keys, node.values, strict=True)
                      if isinstance(k, ast.Constant) and k.value in ADDRESS_KWARGS and isinstance(v, ast.Constant)]
    return found


def _dotted(node: ast.AST) -> str:
    """``a.b.c`` for a Name/Attribute chain, else an empty string."""
    if isinstance(node, ast.Name):
        return node.id
    return f"{_dotted(node.value)}.{node.attr}" if isinstance(node, ast.Attribute) else ""


def _env_key(node: ast.AST) -> str | None:
    """The string key of an ``os.environ[...]``, ``os.environ.get(...)`` or ``os.getenv(...)`` read, else None."""
    key: ast.AST | None = None
    if isinstance(node, ast.Subscript) and _dotted(node.value) == "os.environ":
        key = node.slice
    elif isinstance(node, ast.Call) and _dotted(node.func) in ("os.environ.get", "os.getenv") and node.args:
        key = node.args[0]
    return key.value if isinstance(key, ast.Constant) and isinstance(key.value, str) else None


def _env_reads(tree: ast.AST) -> list[str]:
    """Environment reads whose key looks like a database address."""
    keys = (_env_key(n) for n in ast.walk(tree))
    return [f"reads the address from the environment ({k})" for k in keys if k and ENV_KEY_RE.search(k)]


def _target_keys(target: ast.AST) -> set[str]:
    """The names an assignment target binds: ``dsn``, ``self.dsn``, or every element of a tuple/list target."""
    if isinstance(target, (ast.Tuple, ast.List)):
        return set().union(*(_target_keys(t) for t in target.elts)) if target.elts else set()
    if isinstance(target, ast.Starred):
        return _target_keys(target.value)
    return {_dotted(target)} - {""}


def _is_fixture(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """True when *fn* is decorated with ``fixture`` (``pytest.fixture``, bare or called)."""
    decorators = (d.func if isinstance(d, ast.Call) else d for d in fn.decorator_list)
    return any(_dotted(d).rsplit(".", 1)[-1] == "fixture" for d in decorators)


class Taint:
    """Which names, attributes and functions of a produced test carry the result of ``resolve_test_db_address``.

    A call is tainted only when it is the resolver (or an import alias of it), a module-level function by its
    bare name, or a ``self.``/``cls.``/``Class.`` method of a matching class; no other attribute call is.
    """

    def __init__(self, tree: ast.AST) -> None:
        """Find the resolver's local names (import aliases included), then spread the taint to a fixed point."""
        self.resolvers = {RESOLVER} | {a.asname for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)
                                       for a in n.names if a.name == RESOLVER and a.asname}
        self.module_ids = {id(n) for n in getattr(tree, "body", [])}
        self.cls_of = {id(d): c.name for c in ast.walk(tree) if isinstance(c, ast.ClassDef) for d in ast.walk(c)}
        self.keys: set[str] = set()
        self.funcs: set[str] = set()
        self.methods: set[str] = set()
        self.fixtures: set[str] = set()
        nodes = list(ast.walk(tree))
        for _ in range(6):
            before = (len(self.keys), len(self.funcs), len(self.methods))
            for node in nodes:
                self._visit(node)
            if before == (len(self.keys), len(self.funcs), len(self.methods)):
                break

    def is_resolver_call(self, node: ast.AST) -> bool:
        """True for a call of the resolver (by name or alias, or as a module attribute)."""
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        return (isinstance(func, ast.Name) and func.id in self.resolvers) or (isinstance(func, ast.Attribute) and func.attr == RESOLVER)

    def _call_tainted(self, call: ast.Call) -> bool:
        """True for the resolver, a tainted module-level function, or a tainted method of the matching class."""
        func = call.func
        if isinstance(func, ast.Name):
            return func.id in self.funcs
        if not isinstance(func, ast.Attribute) or not isinstance(func.value, ast.Name):
            return False
        owner = self.cls_of.get(id(call), "") if func.value.id in ("self", "cls") else func.value.id
        return f"{owner}.{func.attr}" in self.methods

    def tainted(self, expr: ast.AST) -> bool:
        """True when *expr* contains a tainted call or a tainted name/attribute."""
        for node in ast.walk(expr):
            if self.is_resolver_call(node) or (isinstance(node, ast.Call) and self._call_tainted(node)):
                return True
            if isinstance(node, (ast.Name, ast.Attribute)) and _dotted(node) in self.keys:
                return True
        return False

    def _visit(self, node: ast.AST) -> None:
        """Spread the taint through one assignment, annotated assignment, walrus, or function that returns a tainted value."""
        if isinstance(node, ast.Assign) and self.tainted(node.value):
            self.keys.update(*(_target_keys(t) for t in node.targets))
        elif isinstance(node, (ast.AnnAssign, ast.NamedExpr)) and node.value is not None and self.tainted(node.value):
            self.keys |= _target_keys(node.target)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            self._visit_function(node)

    def _visit_function(self, fn: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Record a function that returns a tainted value (module-level function, fixture or method) and taint fixture parameters."""
        returns = any(isinstance(n, (ast.Return, ast.Yield)) and n.value is not None and self.tainted(n.value) for n in ast.walk(fn))
        if returns and id(fn) in self.module_ids:
            self.funcs.add(fn.name)
            if _is_fixture(fn):
                self.fixtures.add(fn.name)
        elif returns and id(fn) in self.cls_of:
            self.methods.add(f"{self.cls_of[id(fn)]}.{fn.name}")
        params = fn.args.posonlyargs + fn.args.args + fn.args.kwonlyargs
        self.keys.update(a.arg for a in params if a.arg in self.fixtures)


def _connect_problems(tree: ast.AST, taint: Taint) -> list[str]:
    """Connection calls whose address parts (first argument, host/port/dbname/dsn keywords, ``**`` dicts) do not come from the resolver."""
    problems: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and _dotted(node.func).rsplit(".", 1)[-1] in CONNECT_NAMES):
            continue
        parts = ([node.args[0]] if node.args else []) + [k.value for k in node.keywords if k.arg in CONNECT_KWARGS]
        star = [k.value for k in node.keywords if k.arg is None]
        if not parts and not any(taint.tainted(v) for v in star):
            problems.append("a connection is opened with no address from resolve_test_db_address")
        problems += [f"a connection address that does not come from resolve_test_db_address ({ast.unparse(p)[:40]})"
                     for p in parts if not taint.tainted(p)]
    return problems


def _resolver_used(tree: ast.AST, taint: Taint) -> bool:
    """True when a resolver call's result is used (not a bare expression statement)."""
    bare = {id(n.value) for n in ast.walk(tree) if isinstance(n, ast.Expr)}
    return any(taint.is_resolver_call(n) and id(n) not in bare for n in ast.walk(tree))


def db_test_uses_setting(ctx: RowContext, spec: dict) -> dict:
    """The produced database test gets its address only from the setting, via resolve_test_db_address.

    A resolver call does not excuse a literal address, an environment read or a differently sourced
    connection argument left beside it.
    """
    path = ctx.test_files.get(spec.get("file", ""))
    if path is None:
        return {"passed": False, "detail": f"the output holds no test file {spec.get('file')!r}, so no address can be checked"}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return {"passed": False, "detail": f"{path.name} does not parse, so its address cannot be checked: {exc}"}
    taint = Taint(tree)
    problems = sorted(set(_literal_addresses(tree) + _env_reads(tree) + _connect_problems(tree, taint)))
    if not _resolver_used(tree, taint):
        problems.append("the address never comes from a used resolve_test_db_address call")
    passed = not problems
    return {"passed": passed, "detail": "the address comes only from resolve_test_db_address; no literal address" if passed
            else "it names an address of its own: " + "; ".join(problems)}


KINDS: dict[str, Callable[[RowContext, dict], dict]] = {
    "db_test_uses_setting": db_test_uses_setting,
    **commands.KINDS,
    **reports.KINDS,
}
