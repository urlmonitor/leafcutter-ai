"""
MODULE: unit_tests/evals/tq200d1iv/test_tq200d1iv_seeded
GOAL: RED tests for TQ-200d-1-iv: asserts_known_seeded_value reads unittest equality calls with the
    seeded value on either side, and keeps presence and unseeded numbers failing.
Target: scripts/evals/produced_tests_scoring.py
"""

from __future__ import annotations

import pytest

from unit_tests.evals.tq200d1iv import _static as s


@pytest.mark.parametrize("line", [
    'self.assertEqual(result["AAPL"], 190.12)',
    'self.assertEqual(190.12, result["AAPL"])',
    'self.assertEquals(result["AAPL"], 190.12)',
])
def test_unittest_seeded_value_assertions_pass(tmp_path, line):
    # covers: TQ-200d-1-iv
    # angle: criterion
    got = s.score_source(s.SEED, s.seed_body(line), tmp_path)
    assert got["passed"] is True, got["detail"]


@pytest.mark.parametrize("line", [
    'self.assertIsNotNone(result["AAPL"])',
    'self.assertEqual(result["AAPL"], 9.0)',
    'self.assertEqual(result["AAPL"], 9.0)\n        self.assertEqual(9.0, result["MSFT"])',
    'self.assertTrue(result["AAPL"])',
])
def test_presence_and_unseeded_values_fail_in_unittest_form(tmp_path, line):
    # covers: TQ-200d-1-iv
    # angle: discrimination
    got = s.score_source(s.SEED, s.seed_body(line), tmp_path)
    assert got["passed"] is False, f"false green for {line!r}"


def test_number_only_inside_assertion_calls_is_not_a_seed(tmp_path):
    # covers: TQ-200d-1-iv
    # angle: discrimination
    src = ('import unittest\n\n\nclass T(unittest.TestCase):\n    def test_x(self):\n'
           '        feed = {"AAPL": 190.12}\n        result = dict(feed)\n'
           '        self.assertEqual(result["AAPL"], 7.5)\n        self.assertEqual(7.5, result["MSFT"])\n')
    got = s.score_source(s.SEED, src, tmp_path)
    assert got["passed"] is False, got["detail"]


def test_bare_assert_seeded_value_still_passes(tmp_path):
    # covers: TQ-200d-1-iv
    # angle: boundary
    got = s.score_source(s.SEED, s.seed_body('assert result["AAPL"] == 190.12', unittest_form=False), tmp_path)
    assert got["passed"] is True, got["detail"]
