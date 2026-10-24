"""
MODULE: unit_tests/evals/test_tq200d1_scoring
GOAL: RED tests for TQ-200d-1 that score recorded outputs through produced_tests_scoring.score_row
    against the REAL rows of scripts/evals/sets/test-writer.jsonl: the trap, the gold outputs of the
    positive rows, and test B. Each bad output is the row's own gold output with one recorded file
    swapped, so the report and every other file stay good and only the swapped file can fail it.
Target: scripts/evals/produced_tests_scoring.py, scripts/evals/sets/test-writer.jsonl
"""

from __future__ import annotations

import pytest

import unit_tests.evals._tq200d1_helpers as h


def _control_still_passes(record: dict) -> None:
    """Q3: a bad output fails on the swapped file, not on everything (the report check still passes)."""
    assert h.passed_assertions(record), f"nothing passed, so the failure proves nothing: {record['score']}"


@pytest.mark.parametrize("bad", ["trap_only_cvd.py.recorded", "trap_equal_values.py.recorded"])
def test_trap_row_fails_fixture_seeding_only_old_column(tmp_path, bad):
    # covers: TQ-200d-1
    # angle: discrimination
    # Catches: trap scored on report wording only; fixture check accepts cvd-only seeding;
    # fixture check accepts cvd_delta_30 seeded equal to cvd.
    row = h.real_row("trap")
    assert row["expected"]["negative"] is True
    good = h.score(row, h.gold_dir(row), tmp_path / "good")
    assert good["negative"] is True
    assert good["score"]["passed"] is True, good["score"]
    record = h.score(row, h.bad_output("trap", bad, tmp_path), tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    assert h.failed_assertions(record), "the row failed without a failed assertion naming why"
    _control_still_passes(record)


def test_gold_outputs_pass_each_positive_row(tmp_path):
    # covers: TQ-200d-1
    # angle: criterion
    for key in ("newfn", "empty", "presence"):
        row = h.real_row(key)
        record = h.score(row, h.gold_dir(row), tmp_path / key)
        assert record["id"] == h.ROW_IDS[key]
        assert record["negative"] is False
        assert record["score"]["passed"] is True, (key, h.failed_assertions(record))
        assert len(record["score"]["assertions"]) >= 2, f"{key}: a test check and a report check are both required"


@pytest.mark.parametrize(
    ("key", "bad"),
    [("empty", "empty_window_null_skipping.py.recorded"), ("presence", "presence_without_known_value.py.recorded")],
)
def test_vacuous_checks_fail_their_rows(tmp_path, key, bad):
    # covers: TQ-200d-1
    # angle: discrimination
    # Catches: empty-window row passes a NULL-skipping check; presence row passes a test that
    # asserts no seeded known value.
    row = h.real_row(key)
    assert h.score(row, h.gold_dir(row), tmp_path / "good")["score"]["passed"] is True
    record = h.score(row, h.bad_output(key, bad, tmp_path), tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    assert h.failed_assertions(record)
    _control_still_passes(record)


def test_test_b_failing_only_at_import_fails_the_row(tmp_path):
    # covers: TQ-200d-1
    # angle: discrimination
    # Catches: test B accepted when it fails only at import.
    row = h.real_row("newfn")
    good = h.score(row, h.gold_dir(row), tmp_path / "good")
    assert good["score"]["passed"] is True, h.failed_assertions(good)
    record = h.score(row, h.bad_output("newfn", "test_b_import_only.py.recorded", tmp_path), tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    failed = h.failed_assertions(record)
    assert failed, "the row failed without a failed assertion naming why"
    assert any("import" in a["detail"].lower() or "absence" in a["detail"].lower() for a in failed), failed
    _control_still_passes(record)
