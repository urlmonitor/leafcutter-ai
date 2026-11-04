"""
MODULE: unit_tests/evals/tq200d1vi/test_tq200d1vi_wordings.py
COVERS: TQ-200d-1-vi
GOAL: RED tests: the empty-window and presence-is-not-correctness report checks accept equivalent wordings
    (report_mentions spec key also_accepts) and still refuse a bare None / NULL / value.
Target: scripts/evals/produced_tests_scoring.py (report_mentions), scripts/evals/sets/test-writer.jsonl
"""

from __future__ import annotations

import pytest

import unit_tests.evals._tq200d1_helpers as h
from unit_tests.evals.tq200d1vi import _helpers as s

PASS_EMPTY = ["the non-NULL values (3)", "the non-None values (3)", "the non-null values", "the NON-NONE count",
              "the non-`None` count", "the NON-`NONE` count", *s.EMPTY_RERUNS]
FAIL_EMPTY = ["the check counts the values", "returns None when the feed is empty", "the NULL rows are skipped",
              "None and NULL are both handled", "an all-None window fails", "a non null count"]
PASS_PRESENCE = ["known value", "the expected value", "a seeded value", "the Known Expected Value", "KNOWN VALUE",
                 *s.PRESENCE_RERUNS]
FAIL_PRESENCE = ["the test checks that each symbol has a value", "the value is present",
                 "it checks the values are known", "a known symbol has a value"]


@pytest.mark.parametrize("report", PASS_EMPTY)
def test_empty_window_report_accepts_equivalent_non_null_wordings(report, tmp_path):
    # covers: TQ-200d-1-vi
    # angle: criterion
    # must_catch: revert the fix; the backticked form non-`None` rejected
    """Every non-NULL / non-None / non-null / non-`None` wording passes the empty-window report check."""
    got = s.score_report(report, tmp_path, s.EMPTY)
    assert got["passed"] is True, f"{report!r} must pass the empty-window report check: {got['detail']}"


@pytest.mark.parametrize("report", FAIL_EMPTY)
def test_empty_window_report_without_a_non_null_phrase_fails(report, tmp_path):
    # covers: TQ-200d-1-vi
    # angle: discrimination
    # must_catch: a bare 'None' or 'NULL' outside a non-NULL phrase accepted
    """A report without a non-NULL phrase fails, whatever else it says; a control wording passes beside it."""
    control = s.score_report("the non-None count", tmp_path / "control", s.EMPTY)
    assert control["passed"] is True, f"control wording must pass first: {control['detail']}"
    got = s.score_report(report, tmp_path / "bad", s.EMPTY)
    assert got["passed"] is False, f"{report!r} must fail the empty-window report check"


@pytest.mark.parametrize("report", PASS_PRESENCE)
def test_presence_report_accepts_known_expected_or_seeded_value(report, tmp_path):
    # covers: TQ-200d-1-vi
    # angle: criterion
    # must_catch: 'known expected value' rejected
    """Every known / expected / seeded value wording passes the presence-is-not-correctness report check."""
    got = s.score_report(report, tmp_path, s.PRESENCE)
    assert got["passed"] is True, f"{report!r} must pass the presence report check: {got['detail']}"


@pytest.mark.parametrize("report", FAIL_PRESENCE)
def test_presence_report_without_a_value_phrase_fails(report, tmp_path):
    # covers: TQ-200d-1-vi
    # angle: discrimination
    # must_catch: a bare 'value' accepted
    """A report with only a bare 'value' fails; a control wording passes beside it."""
    control = s.score_report("the seeded value", tmp_path / "control", s.PRESENCE)
    assert control["passed"] is True, f"control wording must pass first: {control['detail']}"
    got = s.score_report(report, tmp_path / "bad", s.PRESENCE)
    assert got["passed"] is False, f"{report!r} must fail the presence report check"


def test_widened_rows_use_also_accepts_in_the_set_file():
    # covers: TQ-200d-1-vi
    # angle: criterion
    # must_catch: revert the fix
    """The two rows list their equivalent wordings in also_accepts, read from the real set file."""
    specs = dict(s.mention_specs(h.SET_PATH))
    assert set(specs[s.EMPTY].get("also_accepts", [])) >= {"non-None", "non-`None`"}
    assert specs[s.EMPTY]["contains"] == "non-NULL"
    assert specs[s.PRESENCE]["contains"] == "known value"
    assert set(specs[s.PRESENCE].get("also_accepts", [])) >= {"expected value", "seeded value"}
