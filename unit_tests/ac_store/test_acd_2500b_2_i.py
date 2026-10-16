"""
MODULE: unit_tests/ac_store/test_acd_2500b_2_i.py
COVERS: ACD-2500b-2-i
GOAL: Red-first spec for "a requirement that reaches approved with its test design pending is
    still never built": the readiness gate (distinct reason, always held), the dispatch set of the
    real scan CLI, and the generator refusal on both paths. The commit-time record check is in
    unit_tests/commit_guardian/test_acd_2500b_2_i.py (the path the ticket names).
BUSINESS CONTEXT: ADR-071. An approved leaf code record that carries test intent and no test design
    must not reach a builder: the gate flags it "test design pending" (NOT "missing test contract"),
    the generator derives no Then-clause tests for it (an empty section would let test-writer
    self-skip), and it is held whatever enforce and schema_version say (note section 6, item 6).
ARCHITECTURE (what python-coder must build, note sections 1 and 6):
    * _impl_readiness_gate.py: HOLD_REASON_TEST_DESIGN_PENDING returned INSTEAD of "missing test
      contract" when design_pending(ac); is_held_back is True for it whatever enforce/schema_version.
    * _gtfa_tests_section.py: TestDesignPendingError(ValueError), raised by
      _build_test_requirements_section when design_pending(ac) and test_required is not false,
      before any derivation. _gtfa_cli.py: both the preview and the write path catch it, print
      `ERROR: generation refused - AC '<id>': test design pending` to stderr, exit 1, write nothing.
RED STATE: the gate reports "missing test contract" for an intent record (an assertion red) and
    holds nothing in advisory mode; TestDesignPendingError does not exist (an absence red); the
    generator happily derives a Then-clause test list for an intent record (an assertion red).
"""

from __future__ import annotations

import re
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
    legacy_leaf,
    reviewed_intent,
    run_generator,
    run_scan,
    valid_record,
)
from _rule_check_fixtures import intent_criteria, intent_entry  # noqa: E402

MISSING_CONTRACT = "missing test contract"


def _approved_intent(record_id: str, **overrides) -> dict:
    return reviewed_intent(record_id, readiness="approved", **overrides)


def test_gate_flags_intent_record_test_design_pending():
    # covers: ACD-2500b-2-i
    # angle: criterion
    """The gate flags an approved intent-without-design record "test design pending", distinct from
    "missing test contract", and the two never appear together for one record.

    Rows (reasons, exact): intent and no test_spec: [pending]; intent and an empty test_spec: [pending];
    intent with every needs_test false and no test_spec: [pending] (note conflict 11); intent and no
    file targets: [missing file targets, pending] in that order; a hand-set hold_reason equal to
    "test design pending" is reported once. Control rows: no intent and no test_spec is still
    ["missing test contract"] (the reason is NOT folded away); intent plus a design is ready.
    """
    from _impl_readiness_gate import implementation_readiness_reasons as reasons  # noqa: PLC0415

    all_false = [intent_entry(c, needs_test=False) for c in TWO]
    assert reasons(_approved_intent("ZZC-1a")) == [PENDING]
    assert reasons(_approved_intent("ZZC-1b", test_spec=[])) == [PENDING]
    assert reasons(_approved_intent("ZZC-1c", entries=all_false)) == [PENDING]
    assert reasons(_approved_intent("ZZC-1d", drop=("declared_files",))) == ["missing file targets", PENDING]
    assert reasons(_approved_intent("ZZC-1e", hold_reason=PENDING)) == [PENDING]

    assert reasons(valid_record("ZZC-1f", readiness="approved")) == [MISSING_CONTRACT]
    assert reasons(_approved_intent("ZZC-1g", spec=design_for(TWO))) == []


def test_test_design_pending_is_held_whatever_enforce_and_schema_version_say():
    # covers: ACD-2500b-2-i
    # angle: discrimination
    """"test design pending" is ALWAYS held; "missing test contract" stays advisory below schema 2.

    The wrong version this catches: the new reason is merely added to the advisory list, so an
    intent record without schema_version (every record written after this change) is reported but
    still dispatched. Rows: the intent record is held with enforce off and no schema_version, with
    schema_version 1, and with enforce on. Control: a no-intent no-spec record is NOT held with
    enforce off and schema_version 1 (ADR-026 rules 3-4 unchanged), and IS held with enforce on.
    """
    from _impl_readiness_gate import is_held_back  # noqa: PLC0415

    pending = _approved_intent("ZZC-2a")
    assert is_held_back(pending) is True
    assert is_held_back(dict(pending, schema_version=1)) is True
    assert is_held_back(pending, enforce=True) is True

    legacy_style = valid_record("ZZC-2b", readiness="approved", schema_version=1)
    assert is_held_back(legacy_style) is False
    assert is_held_back(legacy_style, enforce=True) is True


def test_intent_record_excluded_from_dispatch_set(tmp_path):
    # covers: ACD-2500b-2-i
    # angle: reachability
    """The real scan CLI (subprocess) leaves the intent record out of the set dispatched to builders.

    Entry point: `python scripts/ac_store/scan_ac_store.py --json --ac-root <store>` (CLI), once with
    the default advisory gate and once with --enforce-impl-readiness. The report is consumed: the
    record is absent from `ready` and listed with reasons == ["test design pending"] and held_back
    true. Control rows in the same store: a designed intent record and a legacy-designed record
    are ready; a no-intent no-spec record is flagged "missing test contract" but (advisory) NOT held.
    """
    records = [
        _approved_intent("ZZC-3a"),
        _approved_intent("ZZC-3b", spec=design_for(TWO)),
        valid_record("ZZC-3c", readiness="approved"),
        legacy_leaf("ZZC-3d"),
    ]
    store = build(tmp_path, records)

    import json  # noqa: PLC0415

    def ids(out, key):
        return {item["ac_id"] for item in out[key]}

    advisory = json.loads(run_scan(store).stdout or "{}")
    assert ids(advisory, "ready") == {"ZZC-3b", "ZZC-3c", "ZZC-3d"}, advisory
    flagged = {item["ac_id"]: item for item in advisory["not_implementation_ready"]}
    assert set(flagged) == {"ZZC-3a", "ZZC-3c"}, flagged
    assert flagged["ZZC-3a"]["reasons"] == [PENDING] and flagged["ZZC-3a"]["held_back"] is True
    assert flagged["ZZC-3c"]["reasons"] == [MISSING_CONTRACT] and flagged["ZZC-3c"]["held_back"] is False

    enforced = json.loads(run_scan(store, "--enforce-impl-readiness").stdout or "{}")
    assert ids(enforced, "ready") == {"ZZC-3b", "ZZC-3d"}, enforced
    assert {i["ac_id"]: i["reasons"] for i in enforced["not_implementation_ready"]} == {
        "ZZC-3a": [PENDING], "ZZC-3c": [MISSING_CONTRACT],
    }


def _ac_with_intent(**overrides) -> dict:
    """A generator-ready AC (the TKT-500f fixture shape) carrying test intent and no design."""
    from _tkt_500f_support import make_ac  # noqa: PLC0415

    ac = make_ac(assigned_agent="python-coder")
    ac["criteria"] = intent_criteria(list(TWO))
    ac["test_intent"] = [intent_entry(c) for c in TWO]
    ac.update(overrides)
    return ac


def test_generator_derives_no_tests_for_intent_record():
    # covers: ACD-2500b-2-i
    # angle: seam
    """The ticket generator derives no Then-clause test list for a record carrying test_intent.

    The seam is the generator's section builder, fed the real record shape the store holds: it
    refuses with TestDesignPendingError (a ValueError) instead of falling back to the per-clause
    derivation, BEFORE any derivation. Control rows: with a design the section is built from it;
    with no intent and no design the Then-clause fallback still applies (the refusal is not a
    blanket "no test_spec"); test_required false with intent builds the empty section.
    """
    import _gtfa_tests_section as section  # noqa: PLC0415

    error = section.TestDesignPendingError
    assert issubclass(error, ValueError)
    with pytest.raises(error):
        section._build_test_requirements_section(_ac_with_intent(), "ZZC-4a")

    designed = _ac_with_intent(test_spec=design_for(TWO))
    assert "test_proves_1" in section._build_test_requirements_section(designed, "ZZC-4a")

    no_intent = _ac_with_intent()
    del no_intent["test_intent"]
    derived = section._build_test_requirements_section(no_intent, "ZZC-4a")
    assert "## Test Requirements" in derived and "name:" in derived

    assert section._build_test_requirements_section(_ac_with_intent(test_required=False), "ZZC-4a") == ""


def test_generator_cli_refuses_on_both_paths_and_writes_nothing(tmp_path):
    # covers: ACD-2500b-2-i
    # angle: failure
    """The real generator CLI refuses an intent record on the write path AND the preview path.

    Both exit 1 and print `ERROR: generation refused - AC '<id>': test design pending` to stderr (the
    separator may be the existing em dash); nothing is written: the tickets root stays empty and the
    AC file is byte-identical (no implemented_by back-reference). Control: the same AC with a design
    generates a ticket (exit 0), so the refusal is about the missing design and nothing else.
    """
    from _tkt_500f_support import write_ac_store  # noqa: PLC0415

    ac_root = write_ac_store(tmp_path / "acs", "ZZC-5a", _ac_with_intent())
    ac_file = next(ac_root.rglob("ZZC-5a.yaml"))
    before = ac_file.read_bytes()
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    base = ["--ac", "ZZC-5a", "--ac-root", str(ac_root)]
    refusal = re.compile(r"ERROR: generation refused\s+\S+\s+AC 'ZZC-5a': test design pending")

    write = run_generator([*base, "--tickets-root", str(tickets), "--location-kind", "standalone"])
    preview = run_generator([*base, "--dry-run"])

    for label, run in (("write", write), ("preview", preview)):
        assert run.exit_code == 1, f"{label}: {run.stderr[-400:]}"
        assert refusal.search(run.stderr), f"{label}: {run.stderr[-400:]}"
    assert "---" not in preview.stdout, "the preview must not print a ticket"
    assert list(tickets.rglob("*")) == [], "nothing may be written on refusal"
    assert ac_file.read_bytes() == before

    designed = dict(yaml.safe_load(before), test_spec=design_for(TWO))
    ac_file.write_text(yaml.dump(designed, allow_unicode=True), encoding="utf-8")
    ok = run_generator([*base, "--tickets-root", str(tickets), "--location-kind", "standalone"])
    assert ok.exit_code == 0, ok.stderr[-400:]
    assert len(list(tickets.rglob("*.md"))) == 1
