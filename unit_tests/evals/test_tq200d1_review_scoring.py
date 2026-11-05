"""
MODULE: unit_tests/evals/test_tq200d1_review_scoring
GOAL: RED review-fix tests (H-2..H-5) for TQ-200d-1: each swaps one file of a row's REAL gold
    output for a recorded bad one and asserts the row now FAILS, with the gold still passing.
Target: scripts/evals/produced_tests_scoring.py, scripts/evals/produced_tests_runs.py
"""

from __future__ import annotations

import shutil

import pytest

import unit_tests.evals._tq200d1_helpers as h

BAD_CASES = [
    ("trap", "trap_same_sign.py.recorded"),
    ("trap", "trap_zip_unused_constant.py.recorded"),
    ("trap", "trap_assert_true.py.recorded"),
    ("empty", "empty_window_len_literals.py.recorded"),
    ("presence", "presence_len_of_result.py.recorded"),
    ("presence", "presence_counter_equals_literal.py.recorded"),
    ("presence", "presence_variable_equals_itself.py.recorded"),
    ("newfn", "test_b_wrong_literal_first.py.recorded"),
    ("newfn", "test_b_pytest_fail.py.recorded"),
    ("newfn", "test_b_dict_keyerror.py.recorded"),
]
SKIP_VARIANTS = {
    "decorator": ("@pytest.mark.skip(reason='x')\n", ""),
    "xfail_norun": ("@pytest.mark.xfail(run=False, reason='x')\n", ""),
    "call": ("", '    pytest.skip("x")\n'),
}


@pytest.mark.parametrize(("key", "bad"), BAD_CASES, ids=[b.split(".")[0] for _, b in BAD_CASES])
def test_vacuous_produced_test_fails_its_row(tmp_path, key, bad):
    # covers: TQ-200d-1
    # angle: discrimination
    # Catches: trap row accepts same-sign distinct values / an unused distinct constant / assert True;
    # empty-window row accepts len() of literals; presence row accepts len(result) == 2, n == 1,
    # x == 2; test B accepted when it fails before reaching refresh_config (assert 1 == 2,
    # pytest.fail, a KeyError on a dict it built).
    row = h.real_row(key)
    good = h.score(row, h.gold_dir(row), tmp_path / "good")
    assert good["score"]["passed"] is True, h.failed_assertions(good)
    record = h.score(row, h.bad_output(key, bad, tmp_path), tmp_path / "bad")
    assert record["score"]["passed"] is False, record["score"]
    assert h.failed_assertions(record), "the row failed without a failed assertion naming why"
    assert h.passed_assertions(record), "control: the report check must still pass"


def _skipped_output(key: str, variant: str, tmp_path):
    """The row's gold output with its test file skipped by *variant*."""
    out = tmp_path / "skipped_output"
    shutil.copytree(h.gold_dir(h.real_row(key)), out)
    target = out / h.GOLD_TEST_FILE[key]
    decorator, body_line = SKIP_VARIANTS[variant]
    lines = ["import pytest"] + target.read_text(encoding="utf-8").splitlines()
    rebuilt = []
    for line in lines:
        if line.startswith("def test_"):
            rebuilt += [x.rstrip("\n") for x in (decorator, line, body_line) if x]
        else:
            rebuilt.append(line)
    target.write_bytes(("\n".join(rebuilt) + "\n").encode("utf-8"))
    return out


@pytest.mark.parametrize("variant", sorted(SKIP_VARIANTS))
@pytest.mark.parametrize("key", ["trap", "empty", "presence"])
def test_skipped_produced_test_is_not_green(tmp_path, key, variant):
    # covers: TQ-200d-1
    # angle: discrimination
    # Catches: produced_test_green counts a skipped / xfail(run=False) / pytest.skip() test as passed.
    row = h.real_row(key)
    assert h.score(row, h.gold_dir(row), tmp_path / "good")["score"]["passed"] is True
    record = h.score(row, _skipped_output(key, variant, tmp_path), tmp_path / "bad")
    green = [a for a in record["score"]["assertions"] if a["kind"] == "produced_test_green"]
    assert green, "the row has no produced_test_green assertion"
    assert green[0]["passed"] is False, green[0]
    assert record["score"]["passed"] is False
