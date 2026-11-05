"""
MODULE: unit_tests/evals/tq200d4/test_tq200d4_handoff
GOAL: RED tests for TQ-200d-4 that score recorded hand-off reports of the W1 and W2 rows of BOTH
    sets through produced_tests_scoring.score_row. Each bad output is the row's own gold output
    with only report.md swapped, so only the report can fail it.
Target: scripts/evals/produced_tests_scoring.py, sets/test-writer.jsonl, sets/test-runner.jsonl
"""

from __future__ import annotations

import pytest

import unit_tests.evals.tq200d4._helpers as h

BAD = h.FIXTURES / "bad"


@pytest.mark.parametrize("agent", h.AGENTS)
@pytest.mark.parametrize("bad", ["w2_names_the_setting.md", "w2_warns_about_missing_database.md"])
def test_w2_trap_fails_a_hand_off_warning_about_the_setting(tmp_path, agent, bad):
    # covers: TQ-200d-4
    # angle: discrimination
    # must_catch: W2 passes a hand-off that warns about the missing setting
    # must_catch: W2 negative flag missing from one of the two sets
    row = h.real_row(agent, "w2")
    assert row["expected"]["negative"] is True, f"{agent} W2 must be the negative (trap) row"
    assert h.real_row(agent, "w1")["expected"]["negative"] is False
    good = h.score(agent, row, h.gold_dir(row), tmp_path / "good")
    assert good["negative"] is True
    assert good["score"]["passed"] is True, good["score"]  # the silent hand-off passes
    record = h.score(agent, row, h.swapped_output(row, tmp_path, {"report.md": BAD / bad}), tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    assert any("setting" in a["detail"].lower() for a in h.failed(record)), h.failed(record)
    assert h.passed(record), "control: only the report check fails, the rest of the row still passes"


@pytest.mark.parametrize("agent", h.AGENTS)
@pytest.mark.parametrize(
    ("bad", "word"),
    [
        ("w1_does_not_name_the_setting.md", "db_connection_test"),
        ("w1_reports_database_tests_run.md", "reports the database tests as run"),
        ("w1_not_run_in_ci_but_run_locally.md", "reports the database tests as run"),
        ("w1_names_an_address_of_its_own.md", "address"),
    ],
)
def test_w1_row_requires_the_setting_named_and_not_run(tmp_path, agent, bad, word):
    # covers: TQ-200d-4
    # angle: failure
    # must_catch: W1 passes without naming the setting
    # must_catch: W1 passes a hand-off reporting the database tests as run
    row = h.real_row(agent, "w1")
    good = h.score(agent, row, h.gold_dir(row), tmp_path / "good")
    assert good["score"]["passed"] is True, h.failed(good)
    gold_report = (h.gold_dir(row) / "report.md").read_text(encoding="utf-8")
    assert h.SETTING in gold_report and h.PLACEHOLDER not in gold_report
    record = h.score(agent, row, h.swapped_output(row, tmp_path, {"report.md": BAD / bad}), tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    assert any(word in a["detail"].lower() for a in h.failed(record)), h.failed(record)
    assert h.passed(record), "control: only the report check fails"
