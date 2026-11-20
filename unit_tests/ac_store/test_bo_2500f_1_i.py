"""
MODULE: unit_tests/ac_store/test_bo_2500f_1_i.py
GOAL: RED tests for BO-2500f-1-i (PR 1: validator only) -- the method-by-
    change_target restriction is one more problem kind of
    validate_verification_record (see test_bo_2500f_1.py for the API and the
    part-name vocabulary).

CONTRACT: an INSPECTION record whose ``change_target`` (scalar or list) holds any
    value outside {docs, prompt, config}, or whose change_target is absent / null
    / [] / '' , is refused with a problem on part ``change_target``. The message
    names the record id and the (first) ruling value; for a missing declaration it
    says the declaration is missing (contains the word "missing"). A check record
    is never subject to this restriction.

NOT COVERED (later PRs): the hook-level refusal specs and the derived-kind
    disagreement (BO-3500c-2, unbuilt).
"""
from __future__ import annotations

import sys as _sys
from pathlib import Path as _Path

_sys.path.insert(0, str(_Path(__file__).resolve().parent))

import pytest

from _bo_2500f_1_support import (  # noqa: E402
    RECORD_ID, assert_all_pass, check_form, inspection_form, parts, record,
    run_write_checks, validator,
)


def _change_target_problems(verdict: dict) -> list[dict]:
    return [p for p in verdict["problems"] if p["part"] == "change_target"]


def test_bo_2500f_1_i_writing_such_a_record_without_marking_it_done_is_not_refused(tmp_path):
    # covers: BO-2500f-1-i
    # angle: criterion
    """AC: an in_progress record with change_target code and an inspection record is not refused at write time.

    Runs the real check-ac-schema hook, validate_ac_schema.py, the precommit done
    check (no switch) and requirement_rule_check on it. Red today only because the
    store schema refuses ``verified_by`` as an additional property.
    """
    results = run_write_checks(
        tmp_path, {"change_target": "code", "verified_by": inspection_form()})
    assert_all_pass(pytest.fail, "change_target code + inspection, unfinished", results)


@pytest.mark.parametrize("target", [
    "docs", "prompt", "config", ["docs"], ["docs", "prompt"], ["config", "prompt", "docs"],
])
def test_bo_2500f_1_i_docs_prompt_and_config_targets_allow_inspection_and_other_values_do_not(target):
    # covers: BO-2500f-1-i
    # angle: boundary
    """AC: only docs/prompt/config targets may carry an inspection; any other value rules it out, named."""
    validate = validator()
    assert validate(record(inspection_form(), change_target=target)) == {
        "valid": True, "method": "inspection", "problems": []}, target
    for ruling in ("code", "schema", "pipeline", "ui", "infrastructure", "model", "dependency"):
        for shape in (ruling, [ruling], ["docs", ruling]):
            verdict = validate(record(inspection_form(), change_target=shape))
            assert verdict["valid"] is False, (shape, verdict)
            problems = _change_target_problems(verdict)
            assert len(problems) == 1, (shape, verdict)
            assert ruling in problems[0]["message"], (shape, problems)
            assert RECORD_ID in problems[0]["message"], problems
            assert parts(verdict) == ["change_target"], (shape, verdict)
    # malformed targets (non-string items, a mapping) are refused, never raised on.
    for shape in (["docs", ["x"]], [{"a": 1}], {"docs": 1}, ["docs", 3]):
        verdict = validate(record(inspection_form(), change_target=shape))
        assert verdict["valid"] is False, (shape, verdict)
        assert len(_change_target_problems(verdict)) == 1, (shape, verdict)
    # first ruling value is the one named when several rule it out.
    verdict = validate(record(inspection_form(), change_target=["docs", "schema", "code"]))
    assert "schema" in _change_target_problems(verdict)[0]["message"], verdict
    # control: a check record is never subject to the restriction.
    for ruling in ("code", "schema", ["docs", "pipeline"]):
        assert validate(record(check_form(), change_target=ruling))["valid"] is True, ruling


@pytest.mark.parametrize("missing", ["__omit__", None, [], ""])
def test_bo_2500f_1_i_absent_or_empty_change_target_rules_inspection_out(missing):
    # covers: BO-2500f-1-i
    # angle: failure
    """AC: no change_target (absent, null, [], '') rules inspection out; the problem says it is missing.

    Catches a lenient default that allows inspection when change_target is absent.
    """
    validate = validator()
    verdict = validate(record(inspection_form(), change_target=missing))
    assert verdict["valid"] is False, f"change_target={missing!r} must rule inspection out: {verdict}"
    assert verdict["method"] == "inspection", verdict
    problems = _change_target_problems(verdict)
    assert len(problems) == 1, (missing, verdict)
    assert "missing" in problems[0]["message"].lower(), problems
    assert RECORD_ID in problems[0]["message"], problems
    # control rows: a declared docs target is valid; a check record needs no change_target.
    assert validate(record(inspection_form(), change_target="docs"))["valid"] is True
    assert validate(record(check_form(), change_target=missing))["valid"] is True
