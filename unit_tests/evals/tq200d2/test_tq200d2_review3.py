"""
MODULE: unit_tests/evals/tq200d2/test_tq200d2_review3
GOAL: RED tests for the TQ-200d-2 review round 3 findings on the sql-test-writer kinds: a [reasoned]
    label does not hide a claimed run (H-1; conditional wording is what clears a hypothetical), a
    helper's parameter shadows outer names (H-2), and a helper is matched to its calls by receiver, not
    by a bare method name (H-3).
Target: scripts/evals/sql_test_writer_eval/report_kinds.py, sql_resolve.py, evidence_kinds.py
Each output is the REAL gold output of its row with ONE thing swapped, scored through the real scoring
path; a bad one fails exactly the named kind(s) with the rule's own wording.
"""

from __future__ import annotations

import pytest

import unit_tests.evals.tq200d2._helpers as h

SQL_GOOD = h.FIXTURES / "sql3_good"
SQL_BAD = h.FIXTURES / "sql3_bad"
HYPOTHETICAL = h.FIXTURES / "hypothetical"
BOTH_MISSING = "the SQL counts no processed rows and no non-NULL buy_volume values"
CLAIM = "claims an observed result"


def _trap():
    return h.real_row("trap")


def _set_answer(report: str, n: int, text: str) -> str:
    """*report* with the text of answer Q<n> replaced, keeping the line's own prefix."""
    line = h.answer_line(report, n)
    return report.replace(line, f"{line.split(f'Q{n}:')[0]}Q{n}: {text}", 1)


def _fails_exactly(row, tmp_path, out, kinds):
    """Score *out*: the failed kinds are exactly *kinds*; return the detail of the claim kind if it failed."""
    record = h.score(row, out, tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    assert sorted(a["kind"] for a in h.failed(record)) == sorted(kinds), h.failed(record)
    assert h.passed(record), "control: some other assertion of the row still passes"
    return {a["kind"]: a["detail"] for a in h.failed(record)}


# ---------------------------------------------------------------------------------------- H-1


def test_review3_h1_a_reasoned_label_does_not_hide_a_run_claimed_in_an_answer(tmp_path):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: a line carrying [reasoned] exempted from the prose rules
    row = _trap()
    h.expect_passes(row, tmp_path / "control", h.gold_dir(row))
    for n, text in ((1, "I ran it and it failed before the fix [reasoned]"), (1, "the test was seen to fail on the old code. [reasoned]")):
        sub = tmp_path / text[:12].replace(" ", "_")
        out = h.with_report(row, sub, _set_answer(h.report_of(row), n, text))
        details = _fails_exactly(row, sub, out, [h.K_NO_OBSERVED])
        assert CLAIM in details[h.K_NO_OBSERVED]


def test_review3_h1_a_reasoned_label_does_not_hide_a_claimed_run_paragraph(tmp_path):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: a paragraph ending [reasoned] exempted from the prose rules
    row = _trap()
    out = h.with_report(row, tmp_path, h.report_of(row).rstrip("\n") + "\n\nI ran the tests and they passed. [reasoned]\n")
    details = _fails_exactly(row, tmp_path, out, [h.K_NO_OBSERVED])
    assert CLAIM in details[h.K_NO_OBSERVED]


def test_review3_h1_a_run_line_reporting_a_result_fails_both_the_claim_and_the_not_run_rule(tmp_path):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: a "- Pre-fix run: failed [reasoned]" line read as neither a claim nor a missing "not run"
    row = _trap()
    gold = h.report_of(row)
    out = h.with_report(row, tmp_path, gold.replace(h.run_line(gold, "Pre-fix"), "- Pre-fix run: failed [reasoned]", 1))
    details = _fails_exactly(row, tmp_path, out, [h.K_NO_OBSERVED, h.K_NOT_RUN])
    assert CLAIM in details[h.K_NO_OBSERVED]
    assert "does not say both runs were not run" in details[h.K_NOT_RUN]


@pytest.mark.parametrize(
    ("n", "text"),
    [
        (2, "the result that shows it can fail is a retry_due-false row, so the test is red then. [reasoned]"),
        (1, "the test is written so that it goes red when retry_due is dropped. [reasoned]"),
        (3, "the control row is green on both versions [reasoned]"),
        (1, "the test would fail if retry_due were dropped. [reasoned]"),
        (1, "the test is expected to fail without the fix. [reasoned]"),
        (2, "when retry_due is false the test fails. [reasoned]"),
    ],
    ids=["red_then", "so_that_when", "control_row_green", "would_if", "expected_to", "when_it_fails"],
)
def test_review3_h1_conditional_wording_clears_a_hypothetical_without_a_line_exemption(tmp_path, n, text):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: hypotheticals failing once the [reasoned] line exemption is removed
    row = _trap()
    out = h.with_report(row, tmp_path, _set_answer(h.report_of(row), n, text))
    h.expect_passes(row, tmp_path, out)


@pytest.mark.parametrize("name", ["would_fail_if", "expected_to_turn_red", "when_false_it_fails", "written_so_that"])
def test_review3_h1_conditional_wording_clears_a_hypothetical_paragraph_with_no_label(tmp_path, name):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: a conditional sentence outside any [reasoned] line read as a claimed run
    row = _trap()
    text = (HYPOTHETICAL / f"{name}.md").read_text(encoding="utf-8")
    out = h.with_report(row, tmp_path, h.report_of(row).rstrip("\n") + "\n\n" + text)
    h.expect_passes(row, tmp_path, out)


def test_review3_h1_the_real_gold_report_passes_with_no_help_from_its_labels(tmp_path):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: gold [reasoned] lines that pass only because the label exempts them
    row = _trap()
    gold = h.report_of(row)
    assert gold.count("[reasoned]") >= 4, "the gold report's own [reasoned] lines are what this test strips"
    h.expect_passes(row, tmp_path / "whole", h.gold_dir(row))
    out = h.with_report(row, tmp_path / "stripped", gold.replace("[reasoned]", ""))
    record = h.score(row, out, tmp_path / "stripped_score")
    claim = next(a for a in record["score"]["assertions"] if a["kind"] == h.K_NO_OBSERVED)
    assert claim["passed"] is True, claim


# ---------------------------------------------------------------------------------------- H-2 / H-3


def _sql_row(tmp_path, folder, name):
    row = h.real_row("empty")
    return row, h.output_with(row, tmp_path, {h.EMPTY_TEST_FILE: folder / f"{name}.py.recorded"})


@pytest.mark.parametrize("name", ["helper_parameter_shadows_module_sql", "helper_parameter_shadows_class_attribute"])
def test_review3_h2_a_helper_parameter_shadows_outer_names(tmp_path, name):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: a helper's parameter named sql resolved to a module-level or class-level sql string
    row = h.real_row("empty")
    h.expect_passes(row, tmp_path / "control", h.gold_dir(row))
    _, out = _sql_row(tmp_path, SQL_BAD, name)
    h.expect_fails_only(row, tmp_path, out, h.K_COUNTS, BOTH_MISSING)


def test_review3_h2_the_call_site_argument_still_counts_when_the_outer_name_is_unrelated(tmp_path):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: a parameter shadow that also hides the helper's call-site argument
    row, out = _sql_row(tmp_path, SQL_GOOD, "helper_parameter_with_unrelated_module_sql")
    h.expect_passes(row, tmp_path, out)


def test_review3_h3_a_bare_call_does_not_match_a_method_of_the_same_name(tmp_path):
    # covers: TQ-200d-2
    # angle: discrimination
    # must_catch: run("<counting query>") taken as a call of the method Log.run(self, msg) because the names match
    row = h.real_row("empty")
    _, out = _sql_row(tmp_path, SQL_BAD, "bare_run_is_not_the_logging_method")
    h.expect_fails_only(row, tmp_path, out, h.K_COUNTS, BOTH_MISSING)


def test_review3_h3_a_module_helper_called_by_its_bare_name_and_the_method_helper_still_count(tmp_path):
    # covers: TQ-200d-2
    # angle: boundary
    # must_catch: receiver matching that drops a real module helper or the self._q method helper
    row, out = _sql_row(tmp_path, SQL_GOOD, "module_helper_called_by_bare_name")
    h.expect_passes(row, tmp_path / "module", out)
    row, out = _sql_row(tmp_path / "method", h.FIXTURES / "sql2_good", "helper_method_q")
    h.expect_passes(row, tmp_path / "method", out)
