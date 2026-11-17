"""ACD-2500b-4 -- docs/reference/test-intent.md (content checks).

The AC is ``test_required: false`` (documentation deliverable). Each test reads the delivered reference and
asserts one clause of the AC's criteria (and the it_requirements that shape it) is actually stated.
"""

from __future__ import annotations

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

PAGE = D.REPO / "docs" / "reference" / "test-intent.md"
SCHEMA_PAGE = D.REPO / "docs" / "reference" / "ac-schema.md"
GATES_PAGE = D.REPO / "docs" / "reference" / "ac-readiness-and-assignment-gates.md"


def test_ac4_test_intent_defined_and_not_a_test_contract():
    # covers: ACD-2500b-4
    # angle: criterion
    """Test intent is a per-outcome needs-test decision with a reason, and is stated not to be a test contract."""
    sec = D.section(D.read(PAGE), "What test intent is")
    D.assert_all(sec, ["per-outcome needs-test decision with a reason", "`needs_test`", "`reason`",
                       "is **not a test contract**", "A record with intent and no design has no test contract."],
                 "test-intent.md 'What test intent is'")


def test_ac4_states_who_writes_intent_and_who_writes_design():
    # covers: ACD-2500b-4
    # angle: criterion
    """The writer table names the technical planner for intent and the code-aware test-design step for design,
    and says only the code-aware step writes must_catch."""
    sec = D.flat(D.section(D.read(PAGE), "Who writes what"))
    assert "| `test_intent` | The technical planner (the IT PO) | The code-aware test-design step |" in sec
    assert "| `test_spec`, `test_design_authorship`, `test_design_opened_files` | The code-aware test-design step | The IT PO |" in sec
    assert "`must_catch` (an existing optional `test_spec` entry field, TQ-500f-2) | The code-aware test-design step only" in sec
    assert "test-angles.md" in sec, "the angle set must be linked, not restated"


def test_ac4_states_intent_without_design_cannot_be_approved_or_built():
    # covers: ACD-2500b-4
    # angle: criterion
    """The 'cannot be approved or built' section names the four points that hold it with 'test design pending'."""
    sec = D.flat(D.section(D.read(PAGE), "Intent with no design cannot be approved or built"))
    assert "`design_pending(record)` is true for a record with intent and no design" in sec
    for point in ("Approval", "Readiness gate", "Ticket generator", "Commit check"):
        assert f"| {point} |" in sec, f"hold point not stated: {point}"
    assert sec.count("`test design pending`") >= 1
    assert "TestDesignPendingError" in sec and "no ticket is written" in sec


def test_ac4_states_earlier_designs_are_kept_and_how_to_tell_them_apart():
    # covers: ACD-2500b-4
    # angle: criterion
    """Designs written before the change are kept (not deleted) and told apart by the missing authorship mark."""
    sec = D.flat(D.section(D.read(PAGE), "Designs written before the change"))
    assert "is kept, not deleted" in sec
    assert "missing `test_design_authorship` mark" in sec
    assert "`is_legacy_design(record)` is the only test" in sec


def test_ac4_ac_schema_carries_the_test_intent_field_row_and_hold_reason():
    # covers: ACD-2500b-4
    # angle: criterion
    """The normative home (ac-schema.md) has the test_intent field; the hold-reason vocabulary page it links
    carries 'test design pending'."""
    assert "`test_intent`" in D.read(SCHEMA_PAGE)
    assert "test design pending" in D.read(GATES_PAGE)
