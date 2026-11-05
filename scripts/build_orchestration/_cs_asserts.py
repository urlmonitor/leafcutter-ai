"""
MODULE: scripts/build_orchestration/_cs_asserts.py
GOAL: The static assertion comparison of the sweep check (TQ-500g-3-iii): an existing test the work
    changed that now asserts less, compares more loosely, or tolerates more is "loosened".
BUSINESS CONTEXT: A test can keep passing and still say less than it did. The writer's list never
    exempts such a test; the decision comes from the test's code at the base ref against the
    working tree -- never from running or importing the test module, and never from a model.
ARCHITECTURE: Pure functions over the parsed base and current function nodes that ``_cs_edits.Edit``
    carries (no I/O, no subprocess). Rules: (a) fewer assertions, (b) a strict comparison (== / is,
    assertEqual ...) lost on some subject, (c) a ``pytest.approx`` tolerance widened,
    (d) an assertion made conditional or cut off by an early exit (``_cs_guards``). Output order
    is by file, then the test's line in the working tree, then rule; no set or dict order leaks.
    ``consumer_sweep.check`` calls :func:`loosened_of` once and prints the items as ``loosened``.
"""

from __future__ import annotations

import ast
from collections import Counter
from collections.abc import Iterator
from typing import NamedTuple

import _cs_edits as edits_mod
import _cs_guards as guards_mod

_DEFS = (ast.FunctionDef, ast.AsyncFunctionDef)
_OPS = {ast.Eq: "==", ast.NotEq: "!=", ast.Is: "is", ast.IsNot: "is not", ast.Lt: "<", ast.LtE: "<=",
        ast.Gt: ">", ast.GtE: ">=", ast.In: "in", ast.NotIn: "not in"}
_STRICT_OPS = frozenset({ast.Eq, ast.Is})
_STRICT_METHODS = frozenset({
    "assertEqual", "assertEquals", "assertIs", "assertIsNone", "assertDictEqual", "assertListEqual",
    "assertTupleEqual", "assertSetEqual", "assertSequenceEqual", "assertMultiLineEqual", "assertCountEqual",
    "assertAlmostEqual", "assert_called_with", "assert_called_once_with", "assert_awaited_with",
    "assert_awaited_once_with", "assert_has_calls"})
_FAIL_NAMES = frozenset({"fail", "raises", "warns", "deprecated_call"})
_DEFAULTS = {"rel": 1e-6, "abs": 1e-12}
_LITERAL_SUBJECT = "<literal>"
_TOLERANCE_INDEX = {"rel": 1, "abs": 2}
_OPERAND_SLOT = {
    "first": 0, "expr1": 0, "a": 0, "obj": 0, "member": 0, "expr": 0, "text": 0, "d1": 0, "list1": 0,
    "tuple1": 0, "set1": 0, "seq1": 0,
    "second": 1, "expr2": 1, "b": 1, "container": 1, "cls": 1, "expected_regex": 1, "expected_text": 1,
    "d2": 1, "list2": 1, "tuple2": 1, "set2": 1, "seq2": 1, "expected": 1}


class _Fact(NamedTuple):
    """One asserted comparison: the subject it is about, how it is spelled and whether it is strict."""

    subject: str
    form: str
    strict: bool


def _literal(node: ast.AST | None) -> bool:
    """True for a constant, a negated constant, or a tuple / list / set / dict of literals."""
    if isinstance(node, ast.Constant):
        return True
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        return _literal(node.operand)
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return all(_literal(e) for e in node.elts)
    if isinstance(node, ast.Dict):
        return all(k is not None and _literal(k) and _literal(v) for k, v in zip(node.keys, node.values, strict=True))
    return False


def _fixed(node: ast.AST) -> bool:
    """True for a literal or a ``pytest.approx(...)`` call (an expected value, never the subject)."""
    return _literal(node) or (isinstance(node, ast.Call) and _callee(node)[0] == "approx")


def _subject(left: ast.AST, right: ast.AST | None = None) -> str:
    """The source of the operand that is not a literal; both, order-independent, when neither is.

    Two literals compare nothing the code under test controls (``1 == 1``), so they share one subject
    and a changed literal pair (``1 == 1`` to ``2 == 2``) is not a lost comparison. Swapping two
    non-literal operands keeps the subject.
    """
    if right is None:
        return ast.unparse(left)
    left_lit, right_lit = _fixed(left), _fixed(right)
    if left_lit and right_lit:
        return _LITERAL_SUBJECT
    if left_lit or right_lit:
        return ast.unparse(right if left_lit else left)
    return " | ".join(sorted((ast.unparse(left), ast.unparse(right))))


def _body_nodes(func: ast.AST) -> Iterator[ast.AST]:
    """Every node of a function's body (decorators and signature excluded), nested blocks included."""
    for stmt in func.body:  # type: ignore[attr-defined]
        yield from ast.walk(stmt)


def _by_position(nodes: list[ast.AST]) -> list[ast.AST]:
    """*nodes* in source order."""
    return sorted(nodes, key=lambda n: (n.lineno, n.col_offset))  # type: ignore[attr-defined]


def _callee(call: ast.Call) -> tuple[str | None, bool]:
    """``(name, is_attribute)`` of a call's callee; the name is ``None`` for any other callee."""
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr, True
    if isinstance(func, ast.Name):
        return func.id, False
    return None, False


def _is_assertion_call(call: ast.Call) -> bool:
    """True for a call that counts as one assertion."""
    name, is_attr = _callee(call)
    if name is None:
        return False
    if name.startswith("assert"):
        return True
    if not is_attr:
        return name in _FAIL_NAMES
    owner = ast.unparse(call.func.value)  # type: ignore[attr-defined]
    return (owner == "self" and name == "fail") or (owner == "pytest" and name in _FAIL_NAMES)


def _clauses(test: ast.AST) -> int:
    """The number of and-chain clauses of an assert test (one for anything else)."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        return sum(_clauses(v) for v in test.values)
    return 1


def is_assertion_node(node: ast.AST) -> bool:
    """True for an assert statement or an assertion call."""
    return isinstance(node, ast.Assert) or (isinstance(node, ast.Call) and _is_assertion_call(node))


def count_assertions(func: ast.AST) -> int:
    """Assert statements (one per and-chain clause) plus assertion calls in the body of *func*."""
    return sum(_clauses(n.test) if isinstance(n, ast.Assert) else 1
               for n in _body_nodes(func) if is_assertion_node(n))


def _pairs(test: ast.AST) -> Iterator[tuple[ast.AST, ast.cmpop, ast.AST]]:
    """The ``(left, op, right)`` pairs of an assert test that is a comparison or an and-chain of them."""
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        for value in test.values:
            yield from _pairs(value)
    elif isinstance(test, ast.Compare):
        operands = [test.left, *test.comparators]
        yield from zip(operands, test.ops, operands[1:], strict=False)


def _pair_facts(test: ast.AST, strict_ok: bool = True) -> list[_Fact]:
    """The comparisons an assert test (or an ``assertTrue`` argument) makes."""
    return [_Fact(_subject(left, right), _OPS.get(type(op), type(op).__name__), strict_ok and type(op) in _STRICT_OPS)
            for left, op, right in _pairs(test)]


def _operands(call: ast.Call) -> list[ast.AST]:
    """The leading operands of an ``assert*`` call: positional ones, then keyword ones by unittest slot."""
    slots = dict(enumerate(call.args))
    for kw in call.keywords:
        index = _OPERAND_SLOT.get(kw.arg or "")
        if index is not None:
            slots.setdefault(index, kw.value)
    out: list[ast.AST] = []
    while len(out) in slots:
        out.append(slots[len(out)])
    return out


def _call_facts(call: ast.Call) -> list[_Fact]:
    """The comparisons one ``assert*`` method call makes (bare names and no operands make none)."""
    name, is_attr = _callee(call)
    if not is_attr or name is None or not name.startswith("assert"):
        return []
    strict = name in _STRICT_METHODS
    if "_" in name:
        return [_Fact(ast.unparse(call.func.value), name, strict)]  # type: ignore[attr-defined]
    args = _operands(call)
    if not args:
        return []
    if name in ("assertTrue", "assertFalse"):
        found = _pair_facts(args[0], name == "assertTrue")
        return found or [_Fact(ast.unparse(args[0]), f"{name}({ast.unparse(args[0])})", False)]
    return [_Fact(_subject(args[0], args[1] if len(args) > 1 else None), name, strict)]


def facts_of(func: ast.AST) -> list[_Fact]:
    """Every asserted comparison of *func* in source order."""
    nodes = _by_position([n for n in _body_nodes(func) if isinstance(n, (ast.Assert, ast.Call))])
    out: list[_Fact] = []
    for node in nodes:
        if isinstance(node, ast.Assert):
            out.extend(_pair_facts(node.test))
        else:
            out.extend(_call_facts(node))  # type: ignore[arg-type]
    return out


def comparison_detail(base: ast.AST, now: ast.AST) -> str | None:
    """The detail of rule (b): one fragment per strict comparison lost on a subject, or ``None``."""
    now_facts = facts_of(now)
    left = Counter(f.subject for f in now_facts if f.strict)
    fragments = []
    for fact in (f for f in facts_of(base) if f.strict):
        if left[fact.subject] > 0:
            left[fact.subject] -= 1
            continue
        became = next((f.form for f in now_facts if not f.strict and f.subject == fact.subject), None)
        fragments.append(f"{fact.form} became {became}" if became else f"{fact.form} removed")
    return ", ".join(fragments) or None


def _approx_calls(func: ast.AST) -> list[ast.Call]:
    """The ``pytest.approx`` / ``approx`` calls of *func* in source order."""
    found = [n for n in _body_nodes(func) if isinstance(n, ast.Call) and _callee(n)[0] == "approx"]
    return _by_position(found)  # type: ignore[return-value]


def _expected(call: ast.Call) -> str | None:
    """The source of an approx call's expected argument (first positional or ``expected=``)."""
    if call.args:
        return ast.unparse(call.args[0])
    return next((ast.unparse(k.value) for k in call.keywords if k.arg == "expected"), None)


def _tolerance(call: ast.Call, key: str) -> tuple[float | None, str]:
    """``(value, spelling)`` of the *key* tolerance of an approx call; the value is ``None`` for a non-literal."""
    index = _TOLERANCE_INDEX[key]
    node = next((k.value for k in call.keywords if k.arg == key), None)
    if node is None and len(call.args) > index:
        node = call.args[index]
    if node is None:
        return _DEFAULTS[key], "default"
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return float(node.value), ast.unparse(node)
    return None, ast.unparse(node)


def _widened_keys(old: ast.Call, new: ast.Call) -> list[str]:
    """``"<key> <before> to <after>"`` for each tolerance the *new* approx call widened over the *old* one.

    A literal (or default) that became a non-literal expression is unverifiable and counts as widened;
    a non-literal at the base leaves the key unjudged.
    """
    out = []
    for key in ("rel", "abs"):
        (before, before_src), (after, after_src) = _tolerance(old, key), _tolerance(new, key)
        if before is not None and (after is None or after > before):
            out.append(f"{key} {before_src} to {after_src}")
    return out


def tolerance_detail(base: ast.AST, now: ast.AST) -> str | None:
    """The detail of rule (c): each rel / abs value an approx pair now tolerates beyond the base, or ``None``."""
    unpaired = _approx_calls(now)
    fragments: list[str] = []
    for old in _approx_calls(base):
        expected = _expected(old)
        match = next((c for c in unpaired if expected is not None and _expected(c) == expected), None)
        if match is not None:
            unpaired.remove(match)
            fragments.extend(_widened_keys(old, match))
    return ", ".join(fragments) or None


def _items_for(edit: edits_mod.Edit) -> list[dict]:
    """The loosened items of one changed test (at most one per rule), in rule order."""
    base, now = edit.base, edit.now
    assert base is not None and now is not None  # noqa: S101 -- guarded by _in_scope
    found = []
    before, after = count_assertions(base), count_assertions(now)
    if after < before:
        found.append(("fewer assertions", f"{before} to {after}"))
    for what, detail in (("comparison loosened", comparison_detail(base, now)),
                         ("tolerance widened", tolerance_detail(base, now))):
        if detail:
            found.append((what, detail))
    found.extend(guards_mod.guard_items(base, now, is_assertion_node))
    return [{"file": edit.file, "test": edit.test, "what": what, "detail": detail} for what, detail in found]


def _in_scope(edit: edits_mod.Edit) -> bool:
    """True for a changed test (not fixture, helper, added or removed symbol) present as a function on both sides."""
    return (edit.kind == "changed" and edit.test.rsplit("::", 1)[-1].startswith("test")
            and isinstance(edit.base, _DEFS) and isinstance(edit.now, _DEFS))


def loosened_of(edits: list[edits_mod.Edit]) -> list[dict]:
    """The loosened items of every changed existing test, sorted by file, working-tree line, then rule."""
    scoped = [e for e in edits if _in_scope(e)]
    ordered = sorted(scoped, key=lambda e: (e.file, e.now.lineno))  # type: ignore[union-attr]
    items: list[dict] = []
    for edit in ordered:
        items.extend(_items_for(edit))
    return items
