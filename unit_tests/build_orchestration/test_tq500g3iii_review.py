"""
MODULE: unit_tests/build_orchestration/test_tq500g3iii_review.py
GOAL: Review-fix tests for TQ-500g-3-iii, run in-process against _cs_asserts (pure AST rules).
BUSINESS CONTEXT: Operand swaps, and-chain merges and assertTrue(<comparison>) are not loosenings;
    a tolerance moving from a literal to a name is unverifiable and is reported.
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


def _fn(body: str) -> ast.AST:
    src = "def test_x(self):\n" + textwrap.indent(textwrap.dedent(body).strip("\n"), "    ") + "\n"
    return ast.parse(src).body[0]


def _items(base: str, now: str) -> list[tuple[str, str]]:
    edit = edits_mod.Edit("test_f.py", "test_x", "changed", "fp", _fn(base), _fn(now))
    return [(i["what"], i["detail"]) for i in asserts.loosened_of([edit])]


SWAPS = [
    ("assert f() == expected", "assert expected == f()"),
    ("self.assertEqual(expected, actual)", "self.assertEqual(actual, expected)"),
    ("assert f() == g()", "assert g() == f()"),
]


@pytest.mark.parametrize(("base", "now"), SWAPS)
def test_h1_operand_swap_of_non_literals_is_not_loosened(base: str, now: str):
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: subject taken as the left operand, so swapping two non-literal operands reads as a lost subject
    assert _items(base, now) == []


def test_h1_control_comparison_still_reported():
    # covers: TQ-500g-3-iii
    # angle: boundary
    got = _items("assert f() == expected", "assert f() >= expected")
    assert [w for w, _ in got] == ["comparison loosened"], got


def test_h2_merging_asserts_into_and_chain_is_not_fewer():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: count_assertions counting statements only, so a merged and-chain reads as one fewer
    assert _items("assert x == 1\nassert y == 2", "assert x == 1 and y == 2") == []


def test_h2_control_removing_one_assert_is_fewer():
    # covers: TQ-500g-3-iii
    # angle: boundary
    assert ("fewer assertions", "2 to 1") in _items("assert x == 1\nassert y == 2", "assert x == 1")


def test_m4_asserttrue_with_comparison_losing_it_is_loosened():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: assertTrue(x == 1) treated as a non-strict fact on subject "x == 1", so dropping the comparison is invisible
    got = _items("self.assertTrue(x == 1)", "self.assertTrue(x)")
    assert [w for w, _ in got] == ["comparison loosened"], got
    assert "x" in got[0][1]


def test_m4_assertequal_to_asserttrue_comparison_is_not_loosened():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    assert _items("self.assertEqual(x, 1)", "self.assertTrue(x == 1)") == []


def test_m5_tolerance_literal_to_name_is_reported():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: a non-literal tolerance skipped as unparseable, so any widening hides behind a name
    got = _items("assert v == pytest.approx(0.5, rel=0.01)", "assert v == pytest.approx(0.5, rel=TOL)")
    assert len(got) == 1, got
    assert "TOL" in got[0][1], got


@pytest.mark.parametrize(("base", "now"), [
    ("assert v == pytest.approx(0.5, rel=TOL)", "assert v == pytest.approx(0.5, rel=TOL)"),
    ("assert v == pytest.approx(0.5, rel=0.01)", "assert v == pytest.approx(0.5, rel=0.001)"),
])
def test_m5_controls_unchanged_or_tightened_tolerance_is_not_reported(base: str, now: str):
    # covers: TQ-500g-3-iii
    # angle: boundary
    assert _items(base, now) == []


@pytest.mark.parametrize(("base", "now"), [
    ("assert x == 1\nassert y == 2", "assert y == 2\nassert x == 1"),
    ("assert x == 1 and y == 2", "assert x == 1\nassert y == 2"),
    ("assert x == 1", "self.assertEqual(x, 1)"),
    ("assert x == 1", "assert (x ==   1)"),
])
def test_confirmed_ok_cases_stay_ok(base: str, now: str):
    # covers: TQ-500g-3-iii
    # angle: boundary
    assert _items(base, now) == []
