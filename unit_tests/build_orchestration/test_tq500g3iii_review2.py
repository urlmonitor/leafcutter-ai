"""
MODULE: unit_tests/build_orchestration/test_tq500g3iii_review2.py
GOAL: RED in-process review-fix tests for TQ-500g-3-iii: reordered assertions (M-1) and keyword-argument assertions (M-3).
BUSINESS CONTEXT: Reordering identical assertions that carry different guards is not a loosening, and the keyword
    form of a unittest assertion carries the same facts as the positional form. Run against _cs_asserts.loosened_of.
"""

from __future__ import annotations

import ast
import sys
import textwrap
from pathlib import Path

_SCRIPTS = str(Path(__file__).resolve().parents[2] / "scripts" / "build_orchestration")
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)

import _cs_asserts as asserts  # noqa: E402
import _cs_edits as edits_mod  # noqa: E402

COND = "assertion now conditional"
GUARDED = "if c:\n    assert f() == 1"
PLAIN = "assert f() == 1"


def _fn(body: str) -> ast.AST:
    src = "def test_x(self):\n" + textwrap.indent(textwrap.dedent(body).strip("\n"), "    ") + "\n"
    return ast.parse(src).body[0]


def _items(base: str, now: str) -> list[tuple[str, str]]:
    edit = edits_mod.Edit("test_f.py", "test_x", "changed", "fp", _fn(base), _fn(now))
    return [(i["what"], i["detail"]) for i in asserts.loosened_of([edit])]


def test_reordering_identical_assertions_with_different_guards_is_not_loosening():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: guard matching pairs assertions by position so a reorder looks like a newly guarded assertion
    assert _items(GUARDED + "\n" + PLAIN, PLAIN + "\n" + GUARDED) == []


def test_plain_assertion_made_guarded_is_still_reported_control():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: reorder tolerance that also hides a genuinely newly guarded assertion
    assert _items(PLAIN + "\n" + PLAIN, PLAIN + "\n" + GUARDED) == [(COND, "under if")]
    # a guarded site already in the base must not excuse a different plain site that became guarded
    assert _items(GUARDED + "\n" + PLAIN, GUARDED + "\n" + GUARDED) == [(COND, "under if")]


def test_keyword_form_of_unittest_assertion_equals_positional_form():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: facts read only positional args so the keyword form looks like a removed strict comparison
    assert _items("self.assertEqual(a, 1)", "self.assertEqual(first=a, second=1)") == []


def test_mixed_positional_and_keyword_assertion_carries_same_facts():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: facts read only positional args so a mixed call loses its second operand
    assert _items("self.assertEqual(a, b)", "self.assertEqual(a, second=b)") == []


def test_keyword_assertion_loosened_to_non_strict_is_reported_control():
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: keyword calls ignored entirely so a loosening in keyword form goes unreported
    found = _items("self.assertEqual(first=a, second=1)", "self.assertGreaterEqual(first=a, second=1)")
    assert [what for what, _ in found] == ["comparison loosened"]
