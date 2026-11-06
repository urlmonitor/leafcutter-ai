"""
MODULE: unit_tests/commit_guardian/test_bo_2500f_1_write_checks.py
GOAL: RED integration test for BO-2500f-1 -- an UNFINISHED test-free record with
    a missing, incomplete, unknown-method or non-mapping ``verified_by`` passes
    every write-time check, each run as its real CLI:
        - the check-ac-schema hook script (templates/scripts/commit_guardian/check_ac_schema.py)
        - scripts/ac_store/validate_ac_schema.py
        - check_done_proof.py --mode precommit (no switch)
        - scripts/ac_store/requirement_rule_check.py

    Today the shapes carrying a ``verified_by`` key fail because config/
    ac_store_schema.json does not declare ``verified_by`` (top-level
    additionalProperties false), so the hook, validate_ac_schema.py and the rule
    check's record-schema family refuse the record; check_done_proof precommit
    already passes (an in_progress record is not a done record). The "missing"
    shape (no key at all) is the control that already passes.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ac_store"))

import pytest  # noqa: E402

from _bo_2500f_1_support import INVALID_SHAPES, run_write_checks  # noqa: E402


def test_bo_2500f_1_unfinished_record_with_invalid_verification_record_passes_every_write_check(tmp_path):
    # covers: BO-2500f-1
    # angle: criterion
    """AC: writing/checking an unfinished record never refuses on verified_by grounds."""
    failures: dict[str, dict] = {}
    for label, shape in INVALID_SHAPES.items():
        overrides = {} if shape == "__omit__" else {"verified_by": shape}
        results = run_write_checks(tmp_path / label, overrides)
        bad = {name: out for name, (code, out) in results.items() if code != 0}
        if bad:
            failures[label] = bad
    if failures:
        pytest.fail(f"write-time checks refused an unfinished record: {failures}")
    # exactly the four real CLIs ran for the last shape (no check silently dropped).
    assert set(results) == {
        "check-ac-schema hook", "validate_ac_schema.py",
        "check_done_proof precommit", "requirement_rule_check",
    }
