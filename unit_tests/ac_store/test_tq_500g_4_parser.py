"""
MODULE: unit_tests/ac_store/test_tq_500g_4_parser.py
GOAL: TQ-500g-4 -- a SUBFAILED line is attributed to the test's FULL node id,
    even when a parametrize id contains a space, so the failure lands on the
    test it belongs to and never on a truncated phantom key.
BUSINESS CONTEXT: pr-review of the TQ-500g-4 parser (2026-10-07) ran real
    pytest 9.1.1 over test_x[a b] and saw the SUBFAILED node id captured up to
    the first space ("test_x[a"). With a parent line that reads PASSED, the
    real test would keep PASSED while the phantom key absorbed the FAILED, and
    the exit-1 contradiction rule would not fire. The lines below are the shape
    that run printed; the PASSED parent models the fail-open case.
"""

from __future__ import annotations

import sys
from pathlib import Path

_AC_STORE_DIR = Path(__file__).resolve().parents[2] / "scripts" / "ac_store"
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))

from pytest_outcome_reader import parse_pytest_outcomes  # noqa: E402


def test_subfailed_nodeid_with_space_keeps_full_id():
    # covers: TQ-500g-4
    # Wrong version caught: node id captured up to the first space, leaving
    # "test_sf.py::test_x[a" FAILED and the real test_x[a b] PASSED.
    output = (
        "test_sf.py::test_x[a b] PASSED\n"
        "SUBFAILED[inner case] test_sf.py::test_x[a b] - AssertionError: boom\n"
    )
    outcomes = parse_pytest_outcomes(output, returncode=1)
    assert dict(outcomes) == {"test_sf.py::test_x[a b]": "FAILED"}
    assert outcomes.subfailed == {"test_sf.py::test_x[a b]": ["inner case"]}


def test_subfailed_line_without_message_tail_keeps_full_id():
    # covers: TQ-500g-4
    # Same rule when the SUBFAILED line ends at the node id (no " - " tail).
    output = (
        "test_sf.py::test_x[a b] PASSED\n"
        "SUBFAILED(i=1) test_sf.py::test_x[a b]\n"
    )
    outcomes = parse_pytest_outcomes(output, returncode=1)
    assert dict(outcomes) == {"test_sf.py::test_x[a b]": "FAILED"}
    assert outcomes.subfailed == {"test_sf.py::test_x[a b]": ["i=1"]}
