"""
Unit tests for validate_test_contract in _ac_schema_validators.

The AC is the source of truth for tests: an approved leaf code AC must declare a
test contract (a non-empty test_spec or an explicit test_required: false). These
tests pin the forward-ratchet gate and the contradiction check.
"""
from __future__ import annotations

import sys
from pathlib import Path

_VALIDATORS_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
)
sys.path.insert(0, str(_VALIDATORS_DIR))

from _ac_schema_validators import validate_test_contract  # noqa: E402

_P = Path("docs/acceptance-criteria/x/ZZ-100a-1.yaml")


def _ac(**overrides):
    base = {
        "id": "ZZ-100a-1",
        "readiness": "approved",
        "work_status": "todo",
        "assigned_agent": "python-coder",
        "level": "L2",
    }
    base.update(overrides)
    return base


def test_approved_code_ac_without_contract_is_blocked():
    errors = validate_test_contract(_P, _ac())
    assert errors and "test contract" in errors[0]


def test_test_spec_satisfies_contract():
    assert validate_test_contract(
        _P, _ac(test_spec=[{"name": "t", "target_dir": "d"}])
    ) == []


def test_test_required_false_satisfies_contract():
    assert validate_test_contract(_P, _ac(test_required=False)) == []


def test_contradiction_spec_and_required_false():
    errors = validate_test_contract(
        _P, _ac(test_spec=[{"name": "t", "target_dir": "d"}], test_required=False)
    )
    assert errors and "test_required is false" in errors[0]


def test_composite_ac_is_exempt():
    assert validate_test_contract(
        _P, _ac(level="L1", assigned_agent=None, covered_by=["ZZ-100a-1a"])
    ) == []


def test_done_ac_is_grandfathered():
    assert validate_test_contract(_P, _ac(work_status="done")) == []


def test_draft_ac_is_exempt():
    assert validate_test_contract(_P, _ac(readiness="draft")) == []


def test_change_target_code_triggers_gate_without_coder_agent():
    errors = validate_test_contract(
        _P, _ac(assigned_agent=None, change_target="code")
    )
    assert errors and "test contract" in errors[0]


def test_non_code_ac_is_exempt():
    assert validate_test_contract(
        _P, _ac(assigned_agent="documentation-expert", change_target="docs")
    ) == []
