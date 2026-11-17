"""
MODULE: unit_tests/evals/tq200d2/test_tq200d2_empty_window
GOAL: RED tests for TQ-200d-2 on the "empty window, database shape" row: the produced SQL must count the
    processed rows and the non-NULL buy_volume values, checked structurally on the SQL string literals of
    the produced test (no database is available to the eval, OQ-9).
Target: scripts/evals/produced_tests_scoring.py (and the sql-test-writer kinds it registers),
    scripts/evals/sets/sql-test-writer.jsonl
"""

from __future__ import annotations

import pytest

import unit_tests.evals.tq200d2._helpers as h


def _row():
    row = h.real_row("empty")
    assert row["expected"]["negative"] is False
    return row


def _with_test(tmp_path, row, path):
    """The gold output of the row with only the produced test file swapped."""
    return h.output_with(row, tmp_path, {h.EMPTY_TEST_FILE: path})


def test_empty_window_gold_passes_and_counts_both(tmp_path):
    # covers: TQ-200d-2
    # angle: criterion
    row = _row()
    text = (h.gold_dir(row) / h.EMPTY_TEST_FILE).read_text(encoding="utf-8").lower()
    assert "buy_volume" in text and "count(" in text
    record = h.expect_passes(row, tmp_path, h.gold_dir(row))
    assert {a["kind"] for a in record["score"]["assertions"]} >= h.ROW_KINDS["empty"]


@pytest.mark.parametrize("good", ["empty_filter_form.py.recorded", "empty_sum_case_form.py.recorded"])
def test_empty_window_accepts_other_forms_of_the_non_null_count(tmp_path, good):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: only count(buy_volume) accepted as a non-NULL count
    row = _row()
    h.expect_passes(row, tmp_path, _with_test(tmp_path, row, h.FIXTURES / "good" / good))


@pytest.mark.parametrize(
    ("bad", "both_missing"),
    [
        ("empty_one_sided_check.py.recorded", True),
        ("empty_counts_only_in_prose.py.recorded", True),
        ("empty_row_count_only.py.recorded", False),
        ("empty_alias_lies.py.recorded", False),
    ],
)
def test_empty_window_db_row_requires_row_and_non_null_counts(tmp_path, bad, both_missing):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: empty-window query accepted with only a one-sided buy_volume >= 0 check
    # must_catch: non-NULL count satisfied by a row count alone
    # must_catch: counts read from prose or an alias instead of the SQL
    row = _row()
    h.expect_passes(row, tmp_path / "control", h.gold_dir(row))
    out = _with_test(tmp_path, row, h.BAD / bad)
    # The detail names the missing half(ves) in the rule's own words: a row count alone leaves only the non-NULL half missing.
    if both_missing:
        h.expect_fails_only(row, tmp_path, out, h.K_COUNTS, "the SQL counts no processed rows and no non-NULL buy_volume values")
    else:
        h.expect_fails_only(row, tmp_path, out, h.K_COUNTS, "the SQL counts no non-NULL buy_volume values", absent=("processed rows",))
