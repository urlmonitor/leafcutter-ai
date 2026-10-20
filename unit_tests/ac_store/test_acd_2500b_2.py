"""
MODULE: unit_tests/ac_store/test_acd_2500b_2.py
COVERS: ACD-2500b-2
GOAL: Red-first spec for "a requirement with test intent but no test design cannot be approved":
    the AC's R1 / R2 / R3 scenario through the real approval step, plus the never-accepted-as-a-
    contract proof and the closed hold-reason membership check.
BUSINESS CONTEXT: ADR-071. R1 carries intent (2 clauses needing a test) and no design; R2 carries
    intent and a design covering both clauses (linked by the per-entry clause key, ticket 22);
    R3 is a prompt leaf recorded as requiring no tests. The approval step must hold R1 at
    "reviewed" and report it with the reason "test design pending", approve R2 and R3, and never
    accept intent as the test contract.
ARCHITECTURE (what python-coder must build, note sections 1 and 6):
    * scripts/ac_store/_approval_holds.py: approval_hold_reason(record), APPROVAL_HOLD_CHECKS,
      build_report(approved, held).
    * approve_acs.py: `--json` prints exactly {"approved": [id], "held": [{"id","file","reason"}]};
      a held record is never written; `file` is the repo-relative POSIX path of the AC yaml.
    * _impl_readiness_gate.py: HOLD_REASON_TEST_DESIGN_PENDING; ValueError for a hold_reason
      outside HOLD_REASONS.
    The sibling file test_acd_2500b_2_holds.py holds the boundary, vocabulary and text-mode tests.
RED STATE: every test is red today. `--json` is an unknown argument of approve_acs.py (the CLI exits
    2 and prints nothing on stdout: an assertion red), _approval_holds does not exist (an absence
    red), and the gate does not yet reject an unknown hold_reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500b_approval_fixtures import (  # noqa: E402
    PENDING,
    TWO,
    build,
    design_for,
    goal,
    holds_module,
    json_of,
    read_bytes,
    reviewed_intent,
    reviewed_no_tests,
    run_approve,
    valid_record,
)

_TEMPLATES = Path(__file__).resolve().parents[2] / "templates" / "scripts" / "commit_guardian"


def _ac_scenario(tmp_path):
    """The AC's Given: R1 (intent, no design), R2 (intent + design for both clauses), R3 (no tests)."""
    records = [
        goal("ZZB-1", ["ZZB-1a-1", "ZZB-1a-2", "ZZB-1a-3"]),
        reviewed_intent("ZZB-1a-1"),
        reviewed_intent("ZZB-1a-2", spec=design_for(TWO)),
        reviewed_no_tests("ZZB-1a-3"),
    ]
    return build(tmp_path, records)


def test_intent_without_design_held_with_reason(tmp_path):
    # covers: ACD-2500b-2
    # angle: criterion
    """R1 stays "reviewed" and the report names R1 with exactly the reason "test design pending".

    Wrong versions caught: the reason reads "missing test contract" (the pre-G3 literal), R1 is
    reported held but its file was rewritten (promoted anyway), `file` is absolute or uses
    backslashes, or a record other than R1 is held. Control row: R2 and R3 are not held.
    """
    store = _ac_scenario(tmp_path)
    before = read_bytes(store, "ZZB-1a-1")

    run = run_approve(store, "--goal", "ZZB-1", "--json")
    report = json_of(run)

    assert set(report) == {"approved", "held"}, report
    assert report["held"] == [
        {"id": "ZZB-1a-1", "file": store.rel("ZZB-1a-1"), "reason": PENDING}
    ], report
    assert read_bytes(store, "ZZB-1a-1") == before, "a held record must stay byte-identical"
    assert store.read("ZZB-1a-1")["readiness"] == "reviewed"


def test_designed_and_no_test_records_approved(tmp_path):
    # covers: ACD-2500b-2
    # angle: criterion
    """R2 (design covers both needs-test clauses) and R3 (no tests required) move to "approved".

    Exactly one amended_by entry is appended per promoted record and no other field changes; the
    held R1 is NOT in the approved list. Exact counts: 2 approved, 1 held.
    """
    store = _ac_scenario(tmp_path)
    originals = {rid: store.read(rid) for rid in ("ZZB-1a-2", "ZZB-1a-3")}

    report = json_of(run_approve(store, "--goal", "ZZB-1", "--json"))

    assert sorted(report["approved"]) == ["ZZB-1a-2", "ZZB-1a-3"], report
    assert len(report["held"]) == 1, report
    for rid, original in originals.items():
        after = store.read(rid)
        assert after["readiness"] == "approved", rid
        assert len(after["amended_by"]) == 1 and after["amended_by"][0]["agent"] == "approve_acs", rid
        untouched = {k: v for k, v in after.items() if k not in ("readiness", "amended_by")}
        expected = {k: v for k, v in original.items() if k not in ("readiness", "amended_by")}
        assert untouched == expected, f"{rid}: only readiness and amended_by may change"


def test_intent_alone_never_accepted_as_contract():
    # covers: ACD-2500b-2
    # angle: failure
    """Test intent on its own is never the test contract an approved leaf code record must carry.

    Three layers agree on one approved leaf code record carrying only test_intent: the approval
    check holds it with "test design pending"; the readiness gate reports it not implementation-
    ready with that reason (and NOT "missing test contract"); the commit-time record check rejects
    it. Control: the same record with a design covering both clauses is held by none of the three.
    """
    from _impl_readiness_gate import implementation_readiness_reasons  # noqa: PLC0415

    sys.path.insert(0, str(_TEMPLATES))
    from _ac_schema_validators import validate_test_contract  # noqa: PLC0415

    holds = holds_module()
    intent_only = reviewed_intent("ZZB-2a-1", readiness="approved", assigned_agent="python-coder", change_target="code")
    designed = dict(intent_only, test_spec=design_for(TWO))

    assert holds.approval_hold_reason(intent_only) == PENDING
    assert implementation_readiness_reasons(intent_only) == [PENDING]
    errors = validate_test_contract(Path("docs/acceptance-criteria/x/ZZB-2a-1.yaml"), intent_only)
    assert errors, "the commit-time record check must reject an approved leaf code record with intent only"

    assert holds.approval_hold_reason(designed) is None
    assert implementation_readiness_reasons(designed) == []
    assert validate_test_contract(Path("docs/acceptance-criteria/x/ZZB-2a-1.yaml"), designed) == []


def test_unknown_hold_reason_rejected():
    # covers: ACD-2500b-2
    # angle: boundary
    """A hold_reason outside the closed vocabulary is a ValueError (G1 follow-up F2).

    Every one of the five vocabulary values is accepted (control row: the check must not reject the
    closed list itself), and the rejection names the offending value.
    """
    import _impl_readiness_gate as gate  # noqa: PLC0415

    base = valid_record("ZZB-3a-1", readiness="approved", test_required=False)
    for reason in gate.HOLD_REASONS:
        assert reason in gate.implementation_readiness_reasons(dict(base, hold_reason=reason))
    with pytest.raises(ValueError, match="made-up reason"):
        gate.implementation_readiness_reasons(dict(base, hold_reason="made-up reason"))


def test_acd_2500b_2_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500b-2
    # angle: reachability
    """The AC scenario through the real approval CLI, as a subprocess, with its result consumed.

    Entry point: `python scripts/ac_store/approve_acs.py --goal ZZB-1 --json` (CLI). The report is
    consumed in control flow: the file on disk of R1 is unchanged and R2 / R3 are promoted; a second
    run is idempotent (R1 still held, R2 / R3 not promoted again), and `--ac <R1>` mode holds too.
    """
    store = _ac_scenario(tmp_path)
    run_approve(store, "--goal", "ZZB-1", "--json")
    assert store.read("ZZB-1a-1")["readiness"] == "reviewed"
    assert store.read("ZZB-1a-2")["readiness"] == store.read("ZZB-1a-3")["readiness"] == "approved"
    approved_bytes = read_bytes(store, "ZZB-1a-2")

    again = json_of(run_approve(store, "--goal", "ZZB-1", "--json"))
    assert [h["id"] for h in again["held"]] == ["ZZB-1a-1"], again
    assert read_bytes(store, "ZZB-1a-2") == approved_bytes, "an approved record is never rewritten"
    assert len(yaml.safe_load(approved_bytes)["amended_by"]) == 1

    single = json_of(run_approve(store, "--ac", "ZZB-1a-1", "--json"))
    assert single["held"] == [{"id": "ZZB-1a-1", "file": store.rel("ZZB-1a-1"), "reason": PENDING}]
    assert store.read("ZZB-1a-1")["readiness"] == "reviewed"
