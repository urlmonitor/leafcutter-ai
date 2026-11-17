"""
MODULE: unit_tests/evals/tq200d1iv/test_tq200d1iv_counts
GOAL: RED tests for TQ-200d-1-iv: counts_rows_and_non_null reads unittest assertion calls and
    exact counts against a non-literal integer expression, without opening a false green.
Target: scripts/evals/produced_tests_scoring.py
"""

from __future__ import annotations

import pytest

from unit_tests.evals.tq200d1iv import _static as s

PROC_NN_UT = ["self.assertEqual(len(volumes), len(window))", "self.assertEqual(sum(v is not None for v in volumes), len(window))"]


def _count(source, tmp_path):
    return s.score_source(s.COUNT, source, tmp_path)


def test_unittest_counts_against_the_seed_length_pass(tmp_path):
    # covers: TQ-200d-1-iv
    # angle: criterion
    got = _count(s.unittest_body(*PROC_NN_UT), tmp_path)
    assert got["passed"] is True, got["detail"]


def test_bare_assert_and_assert_true_forms_still_pass(tmp_path):
    # covers: TQ-200d-1-iv
    # angle: boundary
    bare = _count(s.bare_body("assert len(volumes) == 3", "assert sum(v is not None for v in volumes) == 3"), tmp_path / "a")
    assert bare["passed"] is True, bare["detail"]
    true_form = _count(s.unittest_body("self.assertTrue(len(volumes) == 3)", "self.assertTrue(sum(v is not None for v in volumes) == 3)"), tmp_path / "b")
    assert true_form["passed"] is True, true_form["detail"]
    mixed = _count(s.unittest_body("self.assertTrue(len(volumes) == 3)", "assert sum(v is not None for v in volumes) == 3"), tmp_path / "c")
    assert mixed["passed"] is True, mixed["detail"]


@pytest.mark.parametrize(("bound_line", "ok"), [
    ("self.assertGreater(non_null, 0)", True),
    ("self.assertGreaterEqual(non_null, 1)", True),
    ("self.assertGreaterEqual(non_null, 0)", False),
])
def test_unittest_bounds_follow_the_assert_bounds(tmp_path, bound_line, ok):
    # covers: TQ-200d-1-iv
    # angle: boundary
    src = s.unittest_body("self.assertEqual(len(volumes), len(window))", bound_line)
    got = _count(src, tmp_path)
    assert got["passed"] is ok, got["detail"]


@pytest.mark.parametrize("lines", [
    ["self.assertEqual(len(volumes), len(window))", "self.assertGreaterEqual(non_null, 0)"],
    ["self.assertTrue(len(volumes))", "self.assertEqual(sum(v is not None for v in volumes), len(window))"],
    ["self.assertIsNotNone(volumes)", "self.assertGreater(non_null, 0)"],
    ["self.assertEqual(len(volumes), len(window))", "self.assertIsNotNone(volumes)"],
    ["self.assertEqual(len(volumes), len(volumes))", "self.assertEqual(sum(v is not None for v in volumes), len(window))"],
    ["self.assertEqual(len(volumes), len(window))"],
    ["self.assertEqual(len(volumes), 3)"],
])
def test_weak_or_self_comparing_counts_fail(tmp_path, lines):
    # covers: TQ-200d-1-iv
    # angle: discrimination
    got = _count(s.unittest_body(*lines), tmp_path)
    assert got["passed"] is False, f"false green for {lines}"
    assert got["detail"].startswith("the test asserts no"), got["detail"]


def test_bare_assert_forms_of_the_weak_counts_still_fail(tmp_path):
    # covers: TQ-200d-1-iv
    # angle: discrimination
    for i, lines in enumerate([["assert len(volumes) == 3"], ["assert len(volumes) == len(volumes)", "assert non_null == 3"]]):
        got = _count(s.bare_body(*lines), tmp_path / str(i))
        assert got["passed"] is False, lines


def test_unittest_equal_with_count_on_either_side_passes(tmp_path):
    # covers: TQ-200d-1-iv
    # angle: boundary
    src = s.unittest_body("self.assertEqual(len(window), len(volumes))", "self.assertEqual(len(window), sum(v is not None for v in volumes))")
    got = _count(src, tmp_path)
    assert got["passed"] is True, got["detail"]
