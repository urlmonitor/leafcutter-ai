"""
MODULE: unit_tests/build_orchestration/test_tq500g3iii_rules.py
GOAL: RED tests for TQ-500g-3-iii: the pinned matching rule (assertion count, strict comparisons per
    subject, pytest.approx tolerance) as seen in the ``loosened`` list of consumer_sweep.py check.
BUSINESS CONTEXT: Each scenario is a real scratch git repo; the real record step lists every changed
    test as strengthened and the real check CLI is read back. Today ``loosened`` is [].
"""

from __future__ import annotations

from pathlib import Path

import unit_tests.build_orchestration._tq500g3iii_fixtures as fx3

R = fx3.RETRY
CLASS_HEAD = "class TestUnit(unittest.TestCase):\n"


def _go(tmp: Path, base: str, now: str, listed: tuple[str, ...]) -> dict[str, list[tuple[str, str]]]:
    return fx3.brief(fx3.loosened_of(fx3.scenario(tmp, base, now, listed)))


def test_fewer_assertions_reported_with_counts(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: criterion
    # must_catch: only assert statements counted, so a removed pytest.raises or self.assert* call is missed
    # must_catch: count compared per file, so an assertion added in one test hides one removed in another
    f, l_ = "test_backoff_caps_at_five", "test_rejects_negative_delay"
    base = (fx3.body(R, (f, l_), 0)
            + "\n\n" + CLASS_HEAD + "    def test_u(self):\n        with self.assertRaises(ValueError):\n"
            "            compute_delay(-1)\n        self.assertEqual(1, 1)\n"
            "\n\ndef test_m():\n    m = mock.Mock()\n    m()\n    m.assert_called_once()\n"
            "\n\ndef test_removes():\n    x = 1\n    assert x == 1\n    assert x in (1, 2)\n"
            "\n\ndef test_adds():\n    x = 1\n    assert x == 1\n")
    now = (fx3.body(R, (f, l_), 1)
           + "\n\n" + CLASS_HEAD + "    def test_u(self):\n        compute_delay(1)\n        self.assertEqual(1, 1)\n"
           "\n\ndef test_m():\n    m = mock.Mock()\n    m()\n"
           "\n\ndef test_removes():\n    x = 1\n    assert x == 1\n"
           "\n\ndef test_adds():\n    x = 1\n    assert x == 1\n    assert x in (1, 2)\n")
    listed = (f, l_, "TestUnit::test_u", "test_m", "test_removes", "test_adds")
    got = _go(tmp_path, base, now, listed)
    fewer = "fewer assertions"
    assert got == {f: [(fewer, "3 to 2")], l_: [(fewer, "1 to 0")], "TestUnit::test_u": [(fewer, "2 to 1")],
                   "test_m": [(fewer, "1 to 0")], "test_removes": [(fewer, "2 to 1")]}, got


def test_strict_comparison_loosened_reported_with_operators(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: criterion
    # must_catch: bare truthiness replacing == not seen as loosening because the assertion count is unchanged
    # must_catch: only assert statements classified, unittest strict methods ignored
    # must_catch: detail omits the base or the new operator
    names = ("test_first_delay", "test_no_result", "test_ok_status")
    base = (fx3.body(R, names, 0) + "\n\n" + CLASS_HEAD
            + "    def test_u1(self):\n        delay = 1\n        self.assertEqual(delay, 1)\n"
            "\n    def test_u2(self):\n        result = None\n        self.assertIsNone(result)\n")
    now = (fx3.body(R, names, 1) + "\n\n" + CLASS_HEAD
           + "    def test_u1(self):\n        delay = 1\n        self.assertGreaterEqual(delay, 1)\n"
           "\n    def test_u2(self):\n        result = None\n        self.assertIn(result, (None, ''))\n")
    got = _go(tmp_path, base, now, (*names, "TestUnit::test_u1", "TestUnit::test_u2"))
    loose = "comparison loosened"
    assert got == {"test_first_delay": [(loose, "== became >=")], "test_no_result": [(loose, "is became in")],
                   "test_ok_status": [(loose, "== removed")],
                   "TestUnit::test_u1": [(loose, "assertEqual became assertGreaterEqual")],
                   "TestUnit::test_u2": [(loose, "assertIsNone became assertIn")]}, got


def test_operator_swap_with_equal_counts_is_caught(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: boundary
    # must_catch: strict comparisons compared as a per-test count or operator multiset instead of per subject
    base = "def test_swap():\n    a, b = 1, 2\n    assert a == 1\n    assert b >= 2\n"
    now = "def test_swap():\n    a, b = 1, 2\n    assert a >= 1\n    assert b == 2\n"
    got = _go(tmp_path, base, now, ("test_swap",))
    assert got == {"test_swap": [("comparison loosened", "== became >=")]}, got


_APPROX_CASES = {  # name: (base approx call, now approx call); the first four and test_literal_to_name are judged (M-5), the rest must not be
    "test_i": ("(0.5, rel=0.01)", "(0.5, rel=0.1)"),
    "test_added_rel": ("(0.5)", "(0.5, rel=0.01)"),
    "test_positional": ("(0.5, 0.01)", "(0.5, 0.1)"),
    "test_both_keys": ("(0.5, rel=0.01, abs=0.001)", "(0.5, rel=0.1, abs=0.01)"),
    "test_narrowed_abs": ("(0.5, abs=0.1)", "(0.5, abs=0.01)"),
    "test_name_both": ("(0.5, rel=TOL)", "(0.5, rel=TOL2)"),
    "test_literal_to_name": ("(0.5, rel=0.01)", "(0.5, rel=TOL2)"),
}


def _approx_test(name: str, call: str) -> str:
    return f"def {name}():\n    x = 0.5\n    assert x == pytest.approx{call}\n"


def test_approx_tolerance_widened(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: criterion
    # must_catch: approx calls paired by position, so an inserted approx mis-pairs
    # must_catch: pytest default ignored when the base gave no rel or abs
    # must_catch: non-literal tolerance crashes the check or is read as widened
    base = "\n\n".join(_approx_test(n, b) for n, (b, _) in _APPROX_CASES.items())
    now = "\n\n".join(_approx_test(n, a) for n, (_, a) in _APPROX_CASES.items())
    first = "def test_inserted_first():\n    j, k = 0.5, 0.9\n"
    base += "\n\n" + first + "    assert j == pytest.approx(0.5, rel=0.01)\n"
    now += ("\n\n" + first + "    assert k == pytest.approx(0.9, rel=0.5)\n"
            "    assert j == pytest.approx(0.5, rel=0.01)\n")
    got = _go(tmp_path, base, now, (*_APPROX_CASES, "test_inserted_first"))
    wide = "tolerance widened"
    assert got == {"test_i": [(wide, "rel 0.01 to 0.1")], "test_added_rel": [(wide, "rel default to 0.01")],
                   "test_positional": [(wide, "rel 0.01 to 0.1")],
                   "test_both_keys": [(wide, "rel 0.01 to 0.1, abs 0.001 to 0.01")],
                   "test_literal_to_name": [(wide, "rel 0.01 to TOL2")]}, got


def test_added_assertion_beside_strict_one_passes(tmp_path: Path):
    # covers: TQ-500g-3-iii
    # angle: discrimination
    # must_catch: any changed test reported as loosened
    # must_catch: assertions matched by position, so an inserted assertion shifts the strict one
    # must_catch: pytest.approx counted as an assertion, so replacing it by an exact == reads as fewer assertions
    f = "test_backoff_caps_at_five"  # the negative row: a genuine weakening beside the controls
    j = "test_retry_header"
    base = (fx3.body(R, (f, j), 0)
            + "\n\ndef test_ins_before():\n    x = 5\n    assert x == 5\n"
            "\n\ndef test_approx_to_exact():\n    y = 1.0\n    assert y == pytest.approx(1.0)\n"
            "\n\n" + CLASS_HEAD + "    def test_c(self):\n        delay = 1\n        assert delay == 1\n"
            "\n    def test_added(self):\n        self.assertEqual(1, 1)\n")
    now = (fx3.body(R, (f, j), 1)
           + "\n\ndef test_ins_before():\n    x = 5\n    assert x >= 0\n    assert x == 5\n"
           "\n\ndef test_approx_to_exact():\n    y = 1.0\n    assert y == 1.0\n"
           "\n\n" + CLASS_HEAD + "    def test_c(self):\n        delay = 1\n        self.assertEqual(delay, 1)\n"
           "\n    def test_added(self):\n        self.assertEqual(1, 1)\n        self.assertIn(1, [1])\n")
    listed = (f, j, "test_ins_before", "test_approx_to_exact", "TestUnit::test_c", "TestUnit::test_added")
    got = _go(tmp_path, base, now, listed)
    assert got == {f: [("fewer assertions", "3 to 2")]}, got
