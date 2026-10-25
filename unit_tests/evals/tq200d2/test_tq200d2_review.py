"""
MODULE: unit_tests/evals/tq200d2/test_tq200d2_review
GOAL: RED tests for the TQ-200d-2 review round 1 findings (H-1 .. H-7) on the sql-test-writer kinds:
    malformed output fails the row instead of crashing the run, more phrasings of a claimed run, the
    view and the execute call in the empty-window SQL, the to-run-later file's own content, the
    observed-label grammar, and report layouts the kinds must read.
Target: scripts/evals/sql_test_writer_eval/report_kinds.py, evidence_kinds.py, the set file
    (the new spec keys ``view`` and ``wrong_version_contains``)
Every bad output is the REAL gold output of its row with ONE thing swapped; each is scored through the
real scoring path, must not raise, and must fail exactly the named kind with that rule's own wording.
"""

from __future__ import annotations

import json

import pytest

import unit_tests.evals.tq200d2._helpers as h

CLAIMS = h.FIXTURES / "claims"
SQL_BAD = h.FIXTURES / "sql_bad"
SQL_GOOD = h.FIXTURES / "sql_good"
VIEW = "buy_volume_window"
KEYWORD = "fn_refresh_due"


def _spec(key: str, kind: str) -> dict:
    return next(a for a in h.real_row(key)["expected"]["assertions"] if a["kind"] == kind)


def _later_gold() -> dict:
    return json.loads((h.gold_dir(h.real_row("reg")) / h.TO_RUN_LATER).read_text(encoding="utf-8"))


def _later_with(tmp_path, **changes) -> object:
    """The regression gold output with the to-run-later file's first entry (or top level) changed."""
    row = h.real_row("reg")
    data = _later_gold()
    top = {k: changes.pop(k) for k in ("ac_id",) if k in changes}
    data["to_run_later"][0].update(changes)
    data.update(top)
    return row, h.output_with(row, tmp_path, {h.TO_RUN_LATER: json.dumps(data)})


def _verdict(result: str, test: str = h.VERDICT_QUOTE) -> str:
    return json.dumps({"test": test, "wrong_version": "the fix undone", "result": result, "detail": "d"})


def _q1_label(tmp_path, label: str, keep_reasoned: bool = False):
    """The regression gold output with the label of answer Q1 replaced by *label*."""
    row = h.real_row("reg")
    return row, h.with_report(row, tmp_path, h.relabel(h.report_of(row), 1, f"[reasoned] {label}" if keep_reasoned else label))


def test_review_new_spec_keys_are_in_the_real_rows():
    # covers: TQ-200d-2
    # angle: seam
    # must_catch: the empty-window SQL checked without naming the view
    # must_catch: the wrong version checked without a keyword
    assert _spec("empty", h.K_COUNTS).get("view") == VIEW, _spec("empty", h.K_COUNTS)
    spec = _spec("reg", h.K_TO_RUN_LATER)
    assert spec.get("wrong_version_contains") == KEYWORD, spec
    assert spec.get("ac_id") == h.AC_IDS["reg"] and spec.get("contains") == KEYWORD
    gold = _later_gold()["to_run_later"][0]
    assert KEYWORD in gold["wrong_version"] and "::" in gold["test"]


# ---------------------------------------------------------------------------------------- H-1


def test_review_h1_bom_in_the_to_run_later_file_is_read(tmp_path):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: a UTF-8 BOM in the to-run-later file crashes the run
    row = h.real_row("reg")
    raw = (h.gold_dir(row) / h.TO_RUN_LATER).read_bytes()
    out = h.output_with(row, tmp_path, {h.TO_RUN_LATER: b"\xef\xbb\xbf" + raw})
    h.expect_passes(row, tmp_path, out)


@pytest.mark.parametrize(
    ("content", "phrase"),
    [("{bad", "not valid JSON"), ('{"to_run_later": null}', f"names no wrong version of {KEYWORD}"), ('{"to_run_later": "x"}', f"names no wrong version of {KEYWORD}")],
    ids=["malformed_json", "null_list", "list_is_a_string"],
)
def test_review_h1_malformed_to_run_later_fails_the_row_without_raising(tmp_path, content, phrase):
    # covers: TQ-200d-2
    # angle: failure
    # must_catch: a malformed to-run-later file crashes the run instead of failing the row
    row = h.real_row("reg")
    h.expect_passes(row, tmp_path / "control", h.gold_dir(row))
    out = h.output_with(row, tmp_path, {h.TO_RUN_LATER: content})
    h.expect_fails_only(row, tmp_path, out, h.K_TO_RUN_LATER, phrase)


def test_review_h1_unparsable_test_file_fails_the_counts_kind_without_raising(tmp_path):
    # covers: TQ-200d-2
    # angle: failure
    # must_catch: a produced test that does not parse crashes the empty-window kind
    row = h.real_row("empty")
    out = h.output_with(row, tmp_path, {h.EMPTY_TEST_FILE: "def (:\n"})
    record = h.score(row, out, tmp_path / "bad")
    assert record["score"]["passed"] is False
    # db_test_uses_setting cannot read the file either; the counts kind fails in its own words.
    assert sorted(a["kind"] for a in h.failed(record)) == sorted(["db_test_uses_setting", h.K_COUNTS]), h.failed(record)
    detail = next(a["detail"] for a in h.failed(record) if a["kind"] == h.K_COUNTS)
    assert "does not parse" in detail, detail
    assert any(a["kind"] == "test_files_present" for a in h.passed(record)), "control: the file is present"


# ---------------------------------------------------------------------------------------- H-2


@pytest.mark.parametrize(
    "phrase",
    ["went_red_then_green", "failed_as_expected", "verified_fails", "all_green", "wrong_version_caught", "red_without_fix", "failed_no_surprises"],
)
def test_review_h2_trap_fails_more_phrasings_of_a_claimed_run(tmp_path, phrase):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: a claimed run phrased as red/green, failed as expected, verified, all green or caught passes the trap
    # must_catch: "no surprises" read as a negation of the claim
    row = h.real_row("trap")
    h.expect_passes(row, tmp_path / "control", h.gold_dir(row))
    added = (CLAIMS / f"{phrase}.md").read_text(encoding="utf-8")
    out = h.with_report(row, tmp_path, h.report_of(row).rstrip("\n") + "\n\n" + added)
    h.expect_fails_only(row, tmp_path, out, h.K_NO_OBSERVED, "claims an observed result")


def test_review_h2_trap_fails_an_answer_ending_observed_in_parentheses(tmp_path):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: a Q answer ending (observed) passes the trap
    row = h.real_row("trap")
    gold = h.report_of(row)
    line = h.answer_line(gold, 1)
    out = h.with_report(row, tmp_path, gold.replace(line, line + " (observed)", 1))
    h.expect_fails_only(row, tmp_path, out, h.K_NO_OBSERVED, "claims an observed result")


def test_review_h2_trap_accepts_a_passed_syntax_check(tmp_path):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: "syntax check passed" read as a claimed test run
    row = h.real_row("trap")
    added = (CLAIMS / "good_syntax_check_passed.md").read_text(encoding="utf-8")
    out = h.with_report(row, tmp_path, h.report_of(row).rstrip("\n") + "\n\n" + added)
    h.expect_passes(row, tmp_path, out)


# ---------------------------------------------------------------------------------------- H-3


def _with_sql(tmp_path, folder, name):
    row = h.real_row("empty")
    return row, h.output_with(row, tmp_path, {h.EMPTY_TEST_FILE: folder / f"{name}.py.recorded"})


@pytest.mark.parametrize(
    ("name", "words", "absent"),
    [
        ("filter_only", ("the SQL counts no processed rows",), ("non-NULL",)),
        ("other_table", ("the SQL counts no processed rows and no non-NULL buy_volume values",), ()),
        ("assigned_never_executed", ("the SQL counts no processed rows and no non-NULL buy_volume values",), ()),
        ("counts_in_assert_message", ("the SQL counts no processed rows and no non-NULL buy_volume values",), ()),
    ],
)
def test_review_h3_empty_window_sql_must_count_the_view_and_run_the_query(tmp_path, name, words, absent):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: a filtered count taken as the separate row count
    # must_catch: counts over a table other than the view accepted
    # must_catch: SQL assigned but never passed to execute accepted
    # must_catch: counts read from an assertion message
    row = h.real_row("empty")
    h.expect_passes(row, tmp_path / "control", h.gold_dir(row))
    _, out = _with_sql(tmp_path, SQL_BAD, name)
    h.expect_fails_only(row, tmp_path, out, h.K_COUNTS, *words, absent=absent)


@pytest.mark.parametrize(
    "name",
    ["fstring_hole", "plus_concatenation", "module_constant_columns", "aliased_column", "quoted_column", "assigned_then_executed"],
)
def test_review_h3_empty_window_sql_accepts_the_ways_an_agent_writes_the_query(tmp_path, name):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: an f-string with a hole, a + concatenation or a module constant column list not read
    # must_catch: count(w.buy_volume) or count("buy_volume") not read as the non-NULL count
    row, out = _with_sql(tmp_path, SQL_GOOD, name)
    h.expect_passes(row, tmp_path, out)


# ---------------------------------------------------------------------------------------- H-4


@pytest.mark.parametrize(
    ("changes", "words"),
    [
        ({"wrong_version": "n/a"}, (f"names no wrong version of {KEYWORD}",)),
        ({"wrong_version": "unrelated change to other_fn"}, (f"names no wrong version of {KEYWORD}",)),
        ({"wrong_version": "the fix undone"}, (f"names no wrong version of {KEYWORD}",)),
        ({"test": f"unit_tests/sql_functions/test_{KEYWORD}.py"}, (f"names no wrong version of {KEYWORD}",)),
        ({"ac_id": "TQ-9999"}, ("TQ-9999", "TQ-9501")),
    ],
    ids=["n_a", "unrelated_function", "the_fix_undone", "test_without_node_id", "other_ac_id"],
)
def test_review_h4_to_run_later_entry_must_name_a_real_wrong_version(tmp_path, changes, words):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: a placeholder wrong_version ("n/a", "the fix undone") accepted
    # must_catch: a wrong version that names neither fn_refresh_due nor the spec keyword accepted
    # must_catch: a file written for another requirement id accepted
    # must_catch: a test field with no :: node id accepted
    row = h.real_row("reg")
    h.expect_passes(row, tmp_path / "control", h.gold_dir(row))
    _, out = _later_with(tmp_path, **changes)
    h.expect_fails_only(row, tmp_path, out, h.K_TO_RUN_LATER, *words)


# ---------------------------------------------------------------------------------------- H-5 / H-7


@pytest.mark.parametrize("result", ["not_run", "invalid", "not_in_scope"])
def test_review_h5_only_caught_and_survived_count_as_observations(tmp_path, result):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: an observed label quoting a not_run, invalid or not_in_scope row accepted
    row, out = _q1_label(tmp_path, f"[observed: {_verdict(result)}]")
    h.expect_fails_only(row, tmp_path, out, h.K_QUOTED, "quotes no verdict row", "caught or survived")


@pytest.mark.parametrize(
    "label",
    ["[observed: a.py::T::t caught", "(observed: a.py::T::t caught)"],
    ids=["unclosed", "parentheses"],
)
def test_review_h5_a_malformed_observed_label_fails(tmp_path, label):
    # covers: TQ-200d-2
    # angle: failure
    # must_catch: an unclosed [observed: label ignored
    # must_catch: an (observed: ...) label ignored
    row, out = _q1_label(tmp_path, label, keep_reasoned=True)
    h.expect_fails_only(row, tmp_path, out, h.K_QUOTED, "malformed observed label")


@pytest.mark.parametrize(
    "label",
    [
        '[observed: {"test": "a.py::T::test[1]", "result": "caught"}]',
        '[observed: {"test": "", "wrong_version": "the fix undone", "result": "survived", "detail": "group row"}]',
    ],
    ids=["param_id_with_brackets", "group_row_without_test"],
)
def test_review_h5_h7_a_label_with_brackets_or_a_group_row_passes(tmp_path, label):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: a bracketed param id cuts the label short
    # must_catch: a group row with an empty test rejected
    row, out = _q1_label(tmp_path, label)
    h.expect_passes(row, tmp_path, out)


# ---------------------------------------------------------------------------------------- H-6


def _run_forms(report: str, form: str) -> str:
    for which in ("Pre-fix", "Post-fix"):
        report = report.replace(h.run_line(report, which), form.format(w=which), 1)
    return report


@pytest.mark.parametrize(
    "form",
    ["**{w} run:** not run: x", "- {w} run: `not run`: x", '**{w} run**: "not run: x"', "{w} run - not run: x"],
    ids=["bold_colon_inside", "bullet_backticked", "quoted_value", "dash_separator"],
)
def test_review_h6_not_run_lines_in_other_layouts_pass(tmp_path, form):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: a run line with the colon inside the bold, a bullet, backticks, quotes or a dash is not read
    row = h.real_row("trap")
    gold = h.report_of(row)
    assert h.SETTING in gold.replace(h.run_line(gold, "Pre-fix"), "").replace(h.run_line(gold, "Post-fix"), "")
    out = h.with_report(row, tmp_path, _run_forms(gold, form))
    h.expect_passes(row, tmp_path, out)


def _rewrite_answers(report: str, rewrite) -> str:
    lines = {n: h.answer_line(report, n) for n in (1, 2, 3)}
    for n, line in lines.items():
        report = report.replace(line, rewrite(n, line), 1)
    return report


@pytest.mark.parametrize(
    "how",
    ["wrapped_label_on_second_line", "bold_question_ids", "dotted_question_ids", "parenthesised_reasoned", "backticked_reasoned"],
)
def test_review_h6_answers_in_other_layouts_are_read_as_labelled(tmp_path, how):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: an answer wrapped over two lines read as unlabelled
    # must_catch: **Q1**: or Q1. prefixes not read as answers
    # must_catch: (reasoned) or backticked reasoned not read as a label
    rewrites = {
        "wrapped_label_on_second_line": lambda n, ln: ln.replace(" [reasoned]", "\n    [reasoned]"),
        "bold_question_ids": lambda n, ln: ln.replace(f"Q{n}:", f"**Q{n}**:"),
        "dotted_question_ids": lambda n, ln: ln.replace(f"Q{n}:", f"Q{n}."),
        "parenthesised_reasoned": lambda n, ln: ln.replace("[reasoned]", "(reasoned)"),
        "backticked_reasoned": lambda n, ln: ln.replace("[reasoned]", "`reasoned`"),
    }
    row = h.real_row("trap")
    out = h.with_report(row, tmp_path, _rewrite_answers(h.report_of(row), rewrites[how]))
    h.expect_passes(row, tmp_path, out)


def test_review_h6_a_second_guarding_test_with_unlabelled_answers_fails(tmp_path):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: only the first test's three answers are checked
    row = h.real_row("trap")
    gold = h.report_of(row)
    q3 = h.answer_line(gold, 3)
    out = h.with_report(row, tmp_path, gold.replace(q3, q3 + "\n- second_test - Q1: x\n  Q2: y\n  Q3: z", 1))
    h.expect_fails_only(row, tmp_path, out, h.K_LABELLED, "Q1", "label")
