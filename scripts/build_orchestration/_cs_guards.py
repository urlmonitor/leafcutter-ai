"""
MODULE: scripts/build_orchestration/_cs_guards.py
GOAL: Rule (d) of the sweep check (TQ-500g-3-iii): an assertion that is still there but is now
    conditional, or sits after an early exit, is "loosened".
BUSINESS CONTEXT: Moving an unchanged assertion under an ``if`` / ``try`` or putting a ``return`` /
    skip above it keeps the test green while it checks less; assertion counts and comparisons do not see it.
ARCHITECTURE: Pure functions over parsed test function nodes (no I/O). Each side's assertions are
    located with their enclosing guards and the exits before them, paired by normalised text (k-th to
    k-th), and compared. ``_cs_asserts`` calls :func:`guard_items` and passes its assertion predicate.
"""

from __future__ import annotations

import ast
from collections.abc import Callable
from typing import NamedTuple

_GUARDS: dict[type, str] = {
    ast.If: "if", ast.While: "while", ast.For: "for", ast.AsyncFor: "for", ast.Match: "match",
    ast.Try: "try", ast.FunctionDef: "function", ast.AsyncFunctionDef: "function", ast.Lambda: "lambda",
    ast.ClassDef: "class"}
if hasattr(ast, "TryStar"):
    _GUARDS[ast.TryStar] = "try"
_SCOPES = frozenset({"function", "lambda", "class"})
_CALL_EXITS = {"pytest.skip": ("skip", "pytest.skip(...)"), "self.skipTest": ("skip", "self.skipTest(...)"),
               "pytest.xfail": ("xfail", "pytest.xfail(...)")}
_RAISE_EXITS = {"SkipTest": "raise SkipTest", "unittest.SkipTest": "raise unittest.SkipTest"}
_WHAT = {"conditional": "assertion now conditional", "return": "assertion after an early return",
         "skip": "assertion after an early skip", "xfail": "assertion after an early xfail"}
_EXIT_ORDER = ("return", "skip", "xfail")


class _Site(NamedTuple):
    """Where one assertion sits: its guards (outermost first) and the exits before it (source order)."""

    text: str
    guards: tuple[str, ...]
    exits: tuple[tuple[str, str], ...]


def _exit_of(node: ast.AST) -> tuple[str, str] | None:
    """``(kind, detail)`` when *node* is an exit statement or call, else ``None``."""
    if isinstance(node, ast.Return):
        return "return", "return"
    if isinstance(node, ast.Call):
        return _CALL_EXITS.get(ast.unparse(node.func))
    if isinstance(node, ast.Raise) and node.exc is not None:
        target = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
        label = _RAISE_EXITS.get(ast.unparse(target))
        return ("skip", label) if label else None
    return None


def _visit(node: ast.AST, guards: tuple[str, ...], exits: list, out: list[_Site], is_assertion: Callable) -> None:
    """Record the assertions under *node*; *exits* grows with the exits met in source order.

    Each block of a compound statement starts from the exits known on entry (an exit in one branch is
    not before an assertion in a sibling branch) and its new exits are appended afterwards. Exits inside a
    nested def / lambda / class do not leak out of it.
    """
    if is_assertion(node):
        out.append(_Site(ast.unparse(node), guards, tuple(exits)))
    found = _exit_of(node)
    if found:
        exits.append(found)
    kind = _GUARDS.get(type(node))
    inner = guards + (kind,) if kind else guards
    scoped = list(exits) if kind in _SCOPES else exits
    entry = len(scoped)
    branches: list[list] = []
    for _, value in ast.iter_fields(node):
        if isinstance(value, list):
            branch = list(scoped)
            for child in (c for c in value if isinstance(c, ast.AST)):
                _visit(child, inner, branch, out, is_assertion)
            branches.append(branch)
        elif isinstance(value, ast.AST):
            _visit(value, inner, scoped, out, is_assertion)
    for branch in branches:
        scoped.extend(branch[entry:])


def _sites(func: ast.AST, is_assertion: Callable) -> list[_Site]:
    """Every assertion site of a test function's body, in source order."""
    out: list[_Site] = []
    exits: list = []
    for stmt in func.body:  # type: ignore[attr-defined]
        _visit(stmt, (), exits, out, is_assertion)
    return out


def _paired(base: list[_Site], now: list[_Site]) -> list[tuple[_Site, _Site]]:
    """``(base, now)`` sites with the same text, in working-tree order.

    Identical ``(guards, exits)`` signatures pair first (so reordering identical assertions pairs nothing
    new); the remaining sites of the same text pair k-th to k-th.
    """
    free = list(range(len(base)))
    match: dict[int, int] = {}
    for i, site in enumerate(now):
        hit = next((j for j in free if base[j] == site), None)
        if hit is not None:
            free.remove(hit)
            match[i] = hit
    for i, site in enumerate(now):
        if i in match:
            continue
        hit = next((j for j in free if base[j].text == site.text), None)
        if hit is not None:
            free.remove(hit)
            match[i] = hit
    return [(base[match[i]], site) for i, site in enumerate(now) if i in match]


def _join(parts: list[str]) -> str:
    """*parts* without repeats, in order, joined by ``", "``."""
    return ", ".join(dict.fromkeys(parts))


def guard_items(base: ast.AST, now: ast.AST, is_assertion: Callable) -> list[tuple[str, str]]:
    """The ``(what, detail)`` items of rule (d) for one changed test, in rule order."""
    guarded: list[str] = []
    cut: dict[str, list[str]] = {kind: [] for kind in _EXIT_ORDER}
    for old, new in _paired(_sites(base, is_assertion), _sites(now, is_assertion)):
        if not old.guards and new.guards:
            guarded.append(f"under {new.guards[-1]}")
        if not old.exits and new.exits:
            cut[new.exits[0][0]].append(new.exits[0][1])
    found = [(_WHAT["conditional"], _join(guarded))] if guarded else []
    found.extend((_WHAT[kind], _join(cut[kind])) for kind in _EXIT_ORDER if cut[kind])
    return found
