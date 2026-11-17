"""
MODULE: unit_tests/evals/tq200d2iii/test_tq200d2iii_filtered_count
GOAL: RED tests for TQ-200d-2-iii: the count check of the sql-test-writer "empty window, database shape"
    row reads a COUNT(*) or COUNT(1) filtered by "<column> IS NOT NULL" in the same statement as a
    non-NULL count, asserted with an equality, and never as the processed-row count too.
Target: scripts/evals/sql_test_writer_eval/evidence_kinds.py, sql_resolve.py
Each test opens with the filtered form passing (the control, red until the fix lands), then the
variants that must still fail, each built from the real kept re-run 1 output.
"""

from __future__ import annotations

import unit_tests.evals.tq200d2._helpers as h
import unit_tests.evals.tq200d2._probes as p
import unit_tests.evals.tq200d2iii._helpers as t

NOT_NULL = "WHERE symbol = ANY(%s) AND buy_volume IS NOT NULL"
ROWS_WORD, NON_NULL_WORD = "processed rows", "non-NULL buy_volume"
NAMED = "n = self.cur.fetchone()[0]\n        self.assertEqual(n, len(_SEEDED_ROWS))"


def test_where_filtered_count_star_counts_non_null(tmp_path):
    # covers: TQ-200d-2-iii
    # angle: criterion
    # must_catch: revert the fix
    # must_catch: alias-qualified predicate rejected
    # must_catch: COUNT(1) rejected
    cases = {
        "criteria_form": [t.ROWS, t.filtered(NOT_NULL)],
        "first_predicate": [t.ROWS, t.filtered("WHERE buy_volume IS NOT NULL")],
        "alias": [t.ROWS, (f"SELECT COUNT(*) FROM {t.VIEW} w WHERE w.buy_volume IS NOT NULL", t.EXACT)],
        "count_one": [t.ROWS, t.filtered(NOT_NULL, count="COUNT(1)")],
        "named_result": [t.ROWS, t.filtered(NOT_NULL, assertion=NAMED)],
        "bare_assert": [t.ROWS, t.filtered(NOT_NULL, assertion="assert self.cur.fetchone()[0] == len(_SEEDED_ROWS)")],
        "filtered_first": [t.filtered(NOT_NULL), t.ROWS],
    }
    for name, queries in cases.items():
        record = t.passes(queries, tmp_path, name)
        assert p.assertion(record, h.K_COUNTS)["passed"] is True, name


def test_earlier_non_null_forms_still_pass(tmp_path):
    # covers: TQ-200d-2-iii
    # angle: boundary
    # must_catch: an earlier form dropped when the filtered form was added
    earlier = {
        "count_column": t.filtered("WHERE symbol = ANY(%s)", count="COUNT(buy_volume)"),
        "filter": t.filtered("WHERE symbol = ANY(%s)", count="COUNT(*) FILTER (WHERE buy_volume IS NOT NULL)"),
        "case_when": t.filtered("WHERE symbol = ANY(%s)", count="SUM(CASE WHEN buy_volume IS NOT NULL THEN 1 ELSE 0 END)"),
    }
    # Control (red until the fix): the new form lands next to the old ones.
    t.passes([t.ROWS, t.filtered(NOT_NULL)], tmp_path, "new_form")
    for name, query in earlier.items():
        t.passes([t.ROWS, query], tmp_path, name)
    row = h.real_row("empty")
    h.expect_passes(row, tmp_path / "gold", h.gold_dir(row))
    probe = h.FIXTURES / "probes_counts" / "sql_aggregate.py.recorded"
    h.expect_passes(row, tmp_path / "agg", h.output_with(row, tmp_path / "agg", {h.EMPTY_TEST_FILE: probe}))


def test_filtered_count_star_false_greens_fail(tmp_path):
    # covers: TQ-200d-2-iii
    # angle: discrimination
    # must_catch: 'is not null' anywhere in the file accepted for an unfiltered COUNT(*)
    # must_catch: 'is null' accepted as a non-NULL filter
    # must_catch: another column's 'is not null' accepted
    # must_catch: a filtered count asserted with '>= 0' accepted
    # must_catch: the filtered COUNT(*) counted as the processed-row count too
    t.passes([t.ROWS, t.filtered(NOT_NULL)], tmp_path, "control")  # the same shape that must pass
    other_statement = [t.ROWS, t.filtered("WHERE symbol = ANY(%s)"), (f"SELECT buy_volume FROM {t.VIEW} WHERE buy_volume IS NOT NULL", "pass")]
    t.fails(other_statement, tmp_path, "other_statement", NON_NULL_WORD, absent=(ROWS_WORD,))
    t.fails([t.ROWS, t.filtered("WHERE symbol = ANY(%s) AND buy_volume IS NULL")], tmp_path, "is_null", NON_NULL_WORD, absent=(ROWS_WORD,))
    t.fails([t.ROWS, t.filtered("WHERE symbol = ANY(%s) AND symbol IS NOT NULL")], tmp_path, "other_column", NON_NULL_WORD, absent=(ROWS_WORD,))
    weak = {
        "ge_zero": "self.assertGreaterEqual(self.cur.fetchone()[0], 0)",
        "at_least_one": "self.assertTrue(self.cur.fetchone()[0] >= 1)",
        "assert_ge": "assert self.cur.fetchone()[0] >= 0",
    }
    for name, assertion in weak.items():
        t.fails([t.ROWS, t.filtered(NOT_NULL, assertion=assertion)], tmp_path, name, NON_NULL_WORD, absent=(ROWS_WORD,))
    # The filtered COUNT(*) is not also the processed-row count: with no other exact count the rows are missing.
    t.fails([t.filtered(NOT_NULL)], tmp_path, "only_filtered", ROWS_WORD, absent=(NON_NULL_WORD,))
    t.fails([t.filtered("WHERE buy_volume IS NOT NULL", count="COUNT(1)")], tmp_path, "only_filtered_one", ROWS_WORD, absent=(NON_NULL_WORD,))


def test_kept_rerun1_output_passes_and_predicate_removed_fails(tmp_path):
    # covers: TQ-200d-2-iii
    # angle: real_artifact
    # must_catch: the kept output without its predicate passes (false green)
    row = h.real_row("empty")
    assert t.PROBE.is_file() and (t.RERUN / "report.md").is_file(), "the kept re-run 1 output is committed as a fixture"
    text = t.PROBE.read_text(encoding="utf-8")
    assert "AND buy_volume IS NOT NULL" in text, "control: the kept output holds the predicate"
    kept = h.output_with(row, tmp_path / "kept", {h.EMPTY_TEST_FILE: t.PROBE, "report.md": t.RERUN / "report.md"})
    record = h.expect_passes(row, tmp_path / "kept", kept)
    assert p.assertion(record, h.K_COUNTS)["passed"] is True
    stripped = tmp_path / "stripped.py.recorded"
    stripped.write_text(text.replace(" AND buy_volume IS NOT NULL", ""), encoding="utf-8")
    assert "IS NOT NULL" not in stripped.read_text(encoding="utf-8")
    bad = h.output_with(row, tmp_path / "bad", {h.EMPTY_TEST_FILE: stripped})
    h.expect_fails_only(row, tmp_path / "bad", bad, h.K_COUNTS, NON_NULL_WORD, absent=(ROWS_WORD,))
