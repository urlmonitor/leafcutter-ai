"""
MODULE: unit_tests/evals/tq200d2/test_tq200d2_regression
GOAL: RED tests for TQ-200d-2 on the "stored-procedure regression" row: the wrong version is read from the
    to-run-later file the template mandates (never from report prose), and 'observed' is accepted only
    with a quoted verdict row.
Target: scripts/evals/produced_tests_scoring.py (and the sql-test-writer kinds it registers),
    scripts/evals/sets/sql-test-writer.jsonl
"""

from __future__ import annotations

import json

import pytest

import unit_tests.evals.tq200d2._helpers as h


def _row():
    row = h.real_row("reg")
    assert row["expected"]["negative"] is False
    assert h.AC_IDS["reg"] in row["input"], "the row asks for the test to be tagged with its requirement id"
    return row


def _label_text(name: str) -> str:
    return (h.LABELS / name).read_text(encoding="utf-8")


def _swap_label(tmp_path, row, label):
    """The gold output with the label of answer Q1 replaced; nothing else changes."""
    return h.with_report(row, tmp_path, h.relabel(h.report_of(row), 1, label))


def test_regression_row_gold_passes_with_a_to_run_later_wrong_version(tmp_path):
    # covers: TQ-200d-2
    # angle: criterion
    row = _row()
    gold = h.gold_dir(row)
    assert (gold / h.REG_TEST_FILE).is_file()
    later = json.loads((gold / h.TO_RUN_LATER).read_text(encoding="utf-8"))
    assert later["ac_id"] == h.AC_IDS["reg"]
    assert later["to_run_later"] and all({"test", "wrong_version", "reason"} <= set(e) for e in later["to_run_later"])
    assert any("fn_refresh_due" in e["test"] and e["wrong_version"].strip() for e in later["to_run_later"])
    report = h.report_of(row)
    assert "To run later" in report and "fn_refresh_due" in report and "[observed" not in report
    record = h.expect_passes(row, tmp_path, gold)
    assert {a["kind"] for a in record["score"]["assertions"]} >= h.ROW_KINDS["reg"]


@pytest.mark.parametrize(
    "case",
    [
        "good:quoted_caught.md", "good:quoted_survived.md",
        "bad_label:[observed: I watched the test fail]", "bad_label:[observed]",
        "bad_later:empty_list", "bad_later:blank_wrong_version",
    ],
)
def test_regression_row_accepts_observed_only_with_quoted_run(tmp_path, case):
    # covers: TQ-200d-2
    # angle: criterion
    # must_catch: 'observed' accepted without a quoted run
    # must_catch: wrong version read from report prose instead of the to-run-later file
    row = _row()
    kind, _, what = case.partition(":")
    if kind == "good":
        # Control: the same label with a verdict row quoted passes, so only the missing quote can fail the bad ones below.
        out = _swap_label(tmp_path / "good", row, _label_text(what))
        h.expect_passes(row, tmp_path / "good", out)
    elif kind == "bad_label":
        h.expect_passes(row, tmp_path / "control", h.gold_dir(row))
        out = _swap_label(tmp_path, row, what)
        h.expect_fails_only(row, tmp_path, out, h.K_QUOTED, "observed label", "quotes no verdict row")
    else:
        # The gold report still names fn_refresh_due in prose: only the to-run-later file can fail the row.
        assert "fn_refresh_due" in h.report_of(row) and "To run later" in h.report_of(row)
        entry = json.loads((h.gold_dir(row) / h.TO_RUN_LATER).read_text(encoding="utf-8"))["to_run_later"][0]
        entries = [] if what == "empty_list" else [{**entry, "wrong_version": "  "}]
        out = h.output_with(row, tmp_path, {h.TO_RUN_LATER: _later(entries)})
        h.expect_fails_only(row, tmp_path, out, h.K_TO_RUN_LATER, "names no wrong version of fn_refresh_due")


@pytest.mark.parametrize(
    "label",
    [
        "[observed]",
        "[observed: I watched the test fail]",
        "[observed: caught]",
        "[observed: " + h.VERDICT_QUOTE + "]",
    ],
    ids=["bare", "prose_only", "result_without_test", "test_without_result"],
)
def test_regression_row_fails_an_observed_label_without_a_quoted_run(tmp_path, label):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: 'observed' accepted without a quoted run
    row = _row()
    out = _swap_label(tmp_path, row, label)
    h.expect_fails_only(row, tmp_path, out, h.K_QUOTED, "observed label", "quotes no verdict row")


def test_regression_row_fails_one_unquoted_label_among_quoted_ones(tmp_path):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: only the first observed label of the report is checked
    row = _row()
    report = h.relabel(h.report_of(row), 1, _label_text("quoted_caught.md"))
    report = h.relabel(report, 2, "[observed: it failed]")
    out = h.with_report(row, tmp_path, report)
    h.expect_fails_only(row, tmp_path, out, h.K_QUOTED, "quotes no verdict row")


def _later(entries) -> str:
    return json.dumps({"ac_id": h.AC_IDS["reg"], "to_run_later": entries})


@pytest.mark.parametrize(
    ("how", "phrase"),
    [
        ("empty_list", "names no wrong version of fn_refresh_due"),
        ("file_missing", "holds no to-run-later file"),
        ("blank_wrong_version", "names no wrong version of fn_refresh_due"),
        ("other_function", "names no wrong version of fn_refresh_due"),
    ],
)
def test_regression_row_reads_the_wrong_version_from_the_to_run_later_file(tmp_path, how, phrase):
    # covers: TQ-200d-2
    # angle: criterion
    # must_catch: wrong version read from report prose instead of the to-run-later file
    row = _row()
    gold = h.gold_dir(row)
    entry = json.loads((gold / h.TO_RUN_LATER).read_text(encoding="utf-8"))["to_run_later"][0]
    swaps = {
        "empty_list": _later([]),
        "file_missing": None,
        "blank_wrong_version": _later([{**entry, "wrong_version": "  "}]),
        "other_function": _later([{**entry, "test": "unit_tests/sql_functions/test_fn_other.py::TestOther::test_x"}]),
    }
    if how == "empty_list":
        # The report prose still names the wrong version: only the file can fail the row.
        assert "To run later" in h.report_of(row) and "fn_refresh_due" in h.report_of(row)
    out = h.output_with(row, tmp_path, {h.TO_RUN_LATER: swaps[how]})
    h.expect_fails_only(row, tmp_path, out, h.K_TO_RUN_LATER, phrase)
