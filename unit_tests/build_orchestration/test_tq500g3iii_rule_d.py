"""
MODULE: unit_tests/build_orchestration/test_tq500g3iii_rule_d.py
GOAL: RED in-process tests for TQ-500g-3-iii rule (d): an assertion made conditional, or cut off by an early exit.
BUSINESS CONTEXT: Moving an unchanged assertion under a condition, or returning/skipping above it, weakens a
    passing test without touching the assertion text. Run against _cs_asserts.loosened_of (pure AST rules).
"""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path

import pytest

_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "build_orchestration")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import _cs_asserts as asserts  # noqa: E402
import _cs_edits as edits_mod  # noqa: E402

COND = "assertion now conditional"
RET, SKIP, XFAIL = "assertion after an early return", "assertion after an early skip", "assertion after an early xfail"
HDR = "assert header == 'Retry-After: 5'"
M_BASE = "header = 'Retry-After: 5'\n" + HDR
M_NOW = "header = 'Retry-After: 5'\nif header:\n    " + HDR
TWO = "assert delay == 1\nassert attempts == 0"
LEAD_RET = "if not retried:\n    return\n"


def _fn(body: str) -> ast.AST:
    src = "def test_x(self):\n" + textwrap.indent(textwrap.dedent(body).strip("\n"), "    ") + "\n"
    return ast.parse(src).body[0]


def _items(base: str, now: str) -> list[tuple[str, str]]:
    edit = edits_mod.Edit("test_f.py", "test_x", "changed", "fp", _fn(base), _fn(now))
    return [(i["what"], i["detail"]) for i in asserts.loosened_of([edit])]


def _under(guard_open: str, inner: str = "assert x == 1", tail: str = "") -> str:
    return guard_open + "\n    " + inner + tail


GUARDS = [
    ("if", _under("if c:")),
    ("if", "if c:\n    pass\nelif d:\n    assert x == 1"),
    ("if", "if c:\n    pass\nelse:\n    assert x == 1"),
    ("while", _under("while c:")),
    ("for", _under("for i in items:")),
    ("for", _under("async for i in items:")),
    ("match", "match c:\n    case 1:\n        assert x == 1"),
    ("try", _under("try:", tail="\nexcept ValueError:\n    pass")),
    ("try", "try:\n    pass\nexcept ValueError:\n    assert x == 1"),
    ("try", "try:\n    pass\nexcept ValueError:\n    pass\nelse:\n    assert x == 1"),
    ("try", "try:\n    pass\nfinally:\n    assert x == 1"),
    ("try", "try:\n    assert x == 1\nexcept AssertionError:\n    pass"),
    ("try", "try:\n    assert x == 1\nexcept Exception:\n    pass"),
    ("function", _under("def helper():")),
    ("function", _under("async def helper():")),
    ("lambda", "check = lambda: self.assertEqual(x, 1)"),
    ("class", _under("class Inner:")),
]


def test_assertion_moved_under_condition_reported():
    # covers: TQ-500g-3-iii
    # angle: criterion
    # must_catch: assertion moved under a condition not reported
    # must_catch: detail does not name the guard
    assert _items(M_BASE, M_NOW) == [(COND, "under if")]


@pytest.mark.parametrize(("kind", "now"), GUARDS)
def test_assertion_moved_under_every_guard_kind_names_it(kind: str, now: str):
    # covers: TQ-500g-3-iii
    # angle: criterion
    # must_catch: only if guards recognised, so while, for, match, try, nested def, lambda or class pass unnoticed
    # must_catch: swallowed failure (except AssertionError: pass) treated as safe
    base = "self.assertEqual(x, 1)" if kind == "lambda" else "assert x == 1"
    got = _items(base, now)
    assert got == [(COND, f"under {kind}")], got


@pytest.mark.skipif(sys.version_info < (3, 11), reason="try/except* needs Python 3.11")
def test_assertion_moved_under_try_star_reported():
    # covers: TQ-500g-3-iii
    # angle: boundary
    got = _items("assert x == 1", "try:\n    assert x == 1\nexcept* ValueError:\n    pass")
    assert got == [(COND, "under try")], got


def test_nearest_guard_is_named_not_the_outer_one():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: outermost guard named instead of the nearest
    got = _items("assert x == 1", "if c:\n    for i in items:\n        assert x == 1")
    assert got == [(COND, "under for")], got
    got = _items("assert x == 1", "while c:\n    if d:\n        assert x == 1")
    assert got == [(COND, "under if")], got


def test_two_guards_give_one_item_with_joined_detail():
    # covers: TQ-500g-3-iii
    # angle: boundary
    # must_catch: one item per assertion instead of one per (test, what)
    # must_catch: repeated guard kind listed twice
    base = "assert a == 1\nassert b == 2"
    got = _items(base, "if c:\n    assert a == 1\ntry:\n    assert b == 2\nexcept ValueError:\n    pass")
    assert got == [(COND, "under if, under try")], got
    got = _items(base, "if c:\n    assert a == 1\nif d:\n    assert b == 2")
    assert got == [(COND, "under if")], got


def test_with_block_is_not_a_guard_and_pairing_is_by_text():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: with block treated as a condition
    # must_catch: assertions paired by position, so an inserted statement mis-pairs
    # must_catch: k-th occurrence of a repeated text paired with the wrong one
    assert _items(M_BASE, M_NOW) == [(COND, "under if")]  # companion: the rule fires at all
    assert _items("assert x == 1", "with ctx():\n    assert x == 1") == []
    assert _items("assert x == 1", "async with ctx():\n    assert x == 1") == []
    got = _items("assert a == 1\nassert b == 2", "assert z == 9\nassert a == 1\nif c:\n    assert b == 2")
    assert got == [(COND, "under if")], got
    got = _items("assert x == 1\nassert x == 1", "assert x == 1\nif c:\n    assert x == 1")
    assert got == [(COND, "under if")], got
    # leftovers pair k-th to k-th (first free base site first), not from the end
    got = _items("assert f() == 1\nif c:\n    assert f() == 1",
                 "for x in y:\n    assert f() == 1\nwhile z:\n    assert f() == 1")
    assert got == [(COND, "under for")], got


EXITS = [
    ("return", RET, "return"),
    ("pytest.skip('slow')", SKIP, "pytest.skip(...)"),
    ("self.skipTest('slow')", SKIP, "self.skipTest(...)"),
    ("raise SkipTest", SKIP, "raise SkipTest"),
    ("raise SkipTest('slow')", SKIP, "raise SkipTest"),
    ("raise unittest.SkipTest", SKIP, "raise unittest.SkipTest"),
    ("raise unittest.SkipTest('slow')", SKIP, "raise unittest.SkipTest"),
    ("pytest.xfail('known')", XFAIL, "pytest.xfail(...)"),
]


def test_assertion_after_early_exit_reported():
    # covers: TQ-500g-3-iii
    # angle: criterion
    # must_catch: assertion after an early return not reported
    # must_catch: both cut-off assertions given as two items instead of one
    got = _items(TWO, LEAD_RET + TWO)
    assert got == [(RET, "return")], got


@pytest.mark.parametrize(("exit_src", "what", "detail"), EXITS)
def test_every_exit_kind_is_reported_with_its_own_what_and_detail(exit_src: str, what: str, detail: str):
    # covers: TQ-500g-3-iii
    # angle: criterion
    # must_catch: skip or xfail not reported, or reported under the wrong what
    # must_catch: detail names a different exit than the one inserted
    got = _items(TWO, f"{exit_src}\n{TWO}")
    assert got == [(what, detail)], got


ENCLOSING = [
    (LEAD_RET + "with ctx():\n    assert delay == 1\n    assert attempts == 0", [(RET, "return")]),
    ("for i in items:\n    return\n" + TWO, [(RET, "return")]),
    ("return\nif ok:\n    assert delay == 1\n    assert attempts == 0", [(COND, "under if"), (RET, "return")]),
]


@pytest.mark.parametrize(("now", "expected"), ENCLOSING)
def test_exit_in_an_enclosing_or_preceding_block_counts(now: str, expected: list[tuple[str, str]]):
    # covers: TQ-500g-3-iii
    # angle: boundary
    # must_catch: exit nested in a preceding block not seen because only same-level statements are scanned
    # must_catch: assertion inside a with or if block not seen as cut off by an exit before that block
    got = _items(TWO, now)
    assert got == expected, got


def test_first_exit_names_the_kind_and_both_rules_can_fire():
    # covers: TQ-500g-3-iii
    # angle: boundary
    # must_catch: the conditional and early-exit rules suppress each other when both fire for one test
    # must_catch: a later exit named instead of the first exit before the assertion
    got = _items(TWO, LEAD_RET + "if ready:\n    assert delay == 1\nassert attempts == 0")
    assert got == [(COND, "under if"), (RET, "return")], got
    got = _items(TWO, "pytest.skip('a')\nreturn\n" + TWO)
    assert got == [(SKIP, "pytest.skip(...)")], got
    got = _items(TWO, "pytest.xfail('a')\n" + TWO)
    assert got == [(XFAIL, "pytest.xfail(...)")], got


def test_exits_that_cannot_cut_the_assertion_off_give_no_item():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: return inside a nested helper def treated as an exit of the test
    # must_catch: exit after the last assertion treated as cutting it off
    # must_catch: exit already before the assertion at the base reported as new
    assert _items(TWO, LEAD_RET + TWO) == [(RET, "return")]  # companion: the rule fires at all
    assert _items(TWO, "def helper():\n    return 1\n" + TWO) == []
    assert _items(TWO, "pick = lambda: 1\n" + TWO) == []
    assert _items(TWO, TWO + "\nif not retried:\n    return") == []
    assert _items(TWO, TWO + "\npytest.skip('late')") == []
    before = LEAD_RET + TWO
    assert _items(before, "tidy = 1\n" + before) == []
    assert _items("pytest.skip('x')\n" + TWO, "pytest.skip('y')\n" + TWO) == []


def test_conditional_controls_not_reported():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: already-conditional assertion reported
    # must_catch: added conditional assertion beside an unconditional one reported
    assert _items(M_BASE, M_NOW) == [(COND, "under if")]  # companion: the rule fires at all
    p_base = "raw, parsed = '5', '5'\nif raw:\n    assert parsed == '5'"
    p_now = "raw, parsed = 'Retry-After: 5', '5'\nif raw:\n    assert parsed == '5'"
    assert _items(p_base, p_now) == []
    q_base = "attempts, log = 3, make()\nassert attempts == 3"
    q_now = q_base + "\nif log.called:\n    assert log.call_count == 1"
    assert _items(q_base, q_now) == []
