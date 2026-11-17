"""
MODULE: unit_tests/evals/tq200d2/test_tq200d2_python_counts
GOAL: RED tests for TQ-200d-2-ii: the count check of the sql-test-writer "empty window, database
    shape" row also accepts the Python-side form (rows fetched from the view, an equality assertion on
    their number and an equality assertion on the number of non-None values), and still refuses
    '>= 0', 'at least one row' and a single count.
Target: scripts/evals/sql_test_writer_eval/evidence_kinds.py, sql_resolve.py,
    docs/reference/produced-tests-eval-assertion-kinds-sql-test-writer.md
Every probe is a recorded produced test (unit_tests/evals/fixtures/tq200d2/probes_counts/; the live one
is the kept output of the 2026-10-25 before-score session, only its sandbox path shortened) laid over
the REAL gold output of the row, so a probe can only fail for the reason it carries.
"""

from __future__ import annotations

import unit_tests.evals.tq200d1ii._helpers as ref
import unit_tests.evals.tq200d2._helpers as h
import unit_tests.evals.tq200d2._probes as p

PROBES = h.FIXTURES / "probes_counts"
PLAIN = h.FIXTURES / "probes_counts_plain"
ROWS_WORD, NON_NULL_WORD = "processed rows", "non-NULL buy_volume"
REMEDY = "assert an exact count of processed rows plus a non-NULL count"


def _stems(files: list[str]) -> set[str]:
    """The probe names of repo-relative probe paths."""
    return {f.rsplit("/", 1)[-1].removesuffix(".py.recorded") for f in files}


def _out(tmp_path, name: str, folder=PROBES):
    """The empty-window gold output with only the produced test replaced by the probe *name* of *folder*."""
    return h.output_with(h.real_row("empty"), tmp_path / name, {h.EMPTY_TEST_FILE: folder / f"{name}.py.recorded"})


def test_python_side_counts_on_fetched_rows_pass(tmp_path):
    # covers: TQ-200d-2-ii
    # angle: discrimination
    # must_catch: revert the fix
    # must_catch: only SQL aggregates accepted as counts
    row = h.real_row("empty")
    for name in ("live_python_side", "ki_shape_fetchall", "bare_asserts", "values_list_style", "sum_of_booleans_style"):
        record = h.expect_passes(row, tmp_path / name, _out(tmp_path, name))
        assert p.assertion(record, h.K_COUNTS)["passed"] is True, name
    live = (PROBES / "live_python_side.py.recorded").read_text(encoding="utf-8")
    assert "cur.execute(" in live and "select count" not in live.lower(), "control: the live test counts in Python, not in SQL"


def test_sql_aggregate_counts_still_pass(tmp_path):
    # covers: TQ-200d-2-ii
    # angle: boundary
    # must_catch: SQL aggregate form dropped when the Python form was added
    row = h.real_row("empty")
    probe = (PROBES / "sql_aggregate.py.recorded").read_text(encoding="utf-8")
    assert "select count(*), count(buy_volume) from buy_volume_window" in probe
    h.expect_passes(row, tmp_path / "gold", h.gold_dir(row))
    record = h.expect_passes(row, tmp_path / "aggregate", _out(tmp_path, "sql_aggregate"))
    assert p.assertion(record, h.K_COUNTS)["passed"] is True
    # the aggregate forms the kind accepted before (filter / case-when) are still counts
    for name in ("empty_filter_form", "empty_sum_case_form"):
        out = h.output_with(row, tmp_path / name, {h.EMPTY_TEST_FILE: h.FIXTURES / "good" / f"{name}.py.recorded"})
        h.expect_passes(row, tmp_path / name, out)


def test_weak_python_side_checks_fail(tmp_path):
    # covers: TQ-200d-2-ii
    # angle: discrimination
    # must_catch: '>= 0' over fetched values accepted as a count
    # must_catch: 'at least one row' accepted as an exact count
    # must_catch: row count accepted without a non-None count
    # must_catch: non-None count accepted without an exact row count
    row = h.real_row("empty")
    h.expect_passes(row, tmp_path / "control", _out(tmp_path, "ki_shape_fetchall"))  # the same shape with both equalities
    both = ((ROWS_WORD, NON_NULL_WORD), ())
    only_non_null_missing = ((NON_NULL_WORD,), (ROWS_WORD,))
    only_rows_missing = ((ROWS_WORD,), ("non-NULL",))
    cases = {
        "only_ge_zero": both,
        "at_least_one_row": both,
        "at_least_one_row_and_non_none_count": only_rows_missing,  # the good shape with its exact row count swapped for "at least one row"
        "row_count_only": only_non_null_missing,
        "non_none_count_only": only_rows_missing,
        "counts_not_equalities": both,
        "counts_on_another_table": both,
        "counts_in_comments_only": both,
        "row_count_twice": only_non_null_missing,  # the second equality counts the values, None included
    }
    for name, (words, absent) in cases.items():
        h.expect_fails_only(row, tmp_path / name, _out(tmp_path, name), h.K_COUNTS, *words, absent=absent)
    # the same weak checks written as plain ``assert`` statements (a different path from assertGreater / assertGreaterEqual calls)
    plain = {
        "plain_rows_gt_zero": only_rows_missing,
        "plain_rows_ge_one": only_rows_missing,
        "plain_sum_non_none_ge_zero": only_non_null_missing,
        "plain_non_null_list_ge_zero": only_non_null_missing,
        "plain_both_weak": both,
    }
    for name, (words, absent) in plain.items():
        out = _out(tmp_path, name, PLAIN)
        h.expect_fails_only(row, tmp_path / name, out, h.K_COUNTS, *words, absent=absent)


def test_sql_test_writer_gold_still_passes_after_count_change(tmp_path):
    # covers: TQ-200d-2-ii
    # angle: reachability
    proc, payload = h.score_gold_cli(tmp_path)
    assert payload is not None, f"stdout={proc.stdout[-500:]} stderr={proc.stderr[-500:]}"
    assert proc.returncode == 0, f"stdout={proc.stdout[-600:]} stderr={proc.stderr[-600:]}"
    rows = {r["id"]: r for r in payload["rows"]}
    assert sorted(rows) == sorted(h.ROW_IDS.values())
    empty = {a["kind"]: a for a in rows[h.ROW_IDS["empty"]]["score"]["assertions"]}
    assert empty[h.K_COUNTS]["passed"] is True, empty[h.K_COUNTS]
    assert [i for i, r in rows.items() if not r["score"]["passed"]] == []


def test_count_entry_examples_score_as_stated_and_remedy_unchanged(tmp_path):
    # covers: TQ-200d-2-ii
    # angle: real_artifact
    entry = p.entry_of(h.K_COUNTS)
    text = p.text_of(entry)
    for phrase in ("at least one row", ">= 0", "fetch", "none"):
        assert phrase in text, f"the {h.K_COUNTS} entry must state {phrase!r}"
    passing, failing = p.probe_files(entry, "Passing example"), p.probe_files(entry, "Failing example")
    assert {"sql_aggregate", "live_python_side"} <= _stems(passing), f"one example per accepted form: {passing}"
    assert {"only_ge_zero", "at_least_one_row", "row_count_only", "non_none_count_only"} <= _stems(failing), f"the four failing forms: {failing}"
    row = h.real_row("empty")
    for verdict, files in ((True, passing), (False, failing)):
        for n, named in enumerate(files):
            assert named.endswith(".py.recorded"), f"a count example is a recorded test file: {named}"
            out = h.output_with(row, tmp_path / f"{verdict}{n}", {h.EMPTY_TEST_FILE: p.REPO_ROOT / named})
            record = h.score(row, out, tmp_path / f"{verdict}{n}" / "work")
            assert p.assertion(record, h.K_COUNTS)["passed"] is verdict, f"{named} must {'pass' if verdict else 'fail'} as the entry says"
    template = ref.norm((p.REPO_ROOT / "templates/agents/sql-test-writer.md").read_text(encoding="utf-8"))
    assert REMEDY in template
    assert any(REMEDY in quote for quote, _path in ref.quotes_of(entry)), "the entry quotes the template remedy"
