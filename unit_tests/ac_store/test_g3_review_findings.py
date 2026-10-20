"""
MODULE: unit_tests/ac_store/test_g3_review_findings.py
GOAL: Red-first tests for two review findings on the G3 implementation (the third, M-1, is in
    test_outcome_clauses_scenarios.py).
    H-1 (covers ACD-2500b-2-i): the generator wrote a ticket WITHOUT a Test Requirements section for an
    intent-only record when no implementation file is in scope and no test_spec is authored, because
    _gtfa_body only calls the section builder `if implementation_in_scope or authored_spec`. test-writer
    then self-skips: the silent path the refusal exists to close. A record carrying test_intent and no
    design must be refused on BOTH generation paths whatever its files or agent.
    L-1 (covers ACD-2500b-2): `design_pending` is False when `test_required` is False even with
    test_intent present, so the approval step, the readiness gate and the generator agree that such a
    record is not pending and is not held.
RED STATE (before the fixes): H-1 fixtures exit 0 and write a ticket; L-1: design_pending is True for
    a test_required false record, approval holds it, the gate flags it.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _acd_2500b_approval_fixtures import (  # noqa: E402
    PENDING,
    TWO,
    build,
    goal,
    json_of,
    read_bytes,
    reviewed_intent,
    run_approve,
    run_generator,
)
from _rule_check_fixtures import intent_criteria, intent_entry  # noqa: E402

_REFUSAL = re.compile(r"ERROR: generation refused\s+\S+\s+AC '(?P<id>[^']+)': test design pending")


def _ac(assigned_agent: str, files: tuple[str, ...], **overrides) -> dict:
    """A generator-ready AC (TKT-500f fixture shape) with intent, no design, declared `files`."""
    from _tkt_500f_support import make_ac  # noqa: PLC0415

    ac = make_ac(assigned_agent=assigned_agent, files_touched=files)
    ac["criteria"] = intent_criteria(list(TWO))
    ac["test_intent"] = [intent_entry(c) for c in TWO]
    ac.update(overrides)
    return ac


def _both_paths(tmp_path: Path, ac_id: str, ac: dict):
    """Run the real generator CLI on the write path and the preview path; return both runs and the
    store file / tickets root so the caller can check that nothing was written."""
    from _tkt_500f_support import write_ac_store  # noqa: PLC0415

    ac_root = write_ac_store(tmp_path / "acs", ac_id, ac)
    tickets = tmp_path / "tickets"
    tickets.mkdir()
    base = ["--ac", ac_id, "--ac-root", str(ac_root)]
    write = run_generator([*base, "--tickets-root", str(tickets), "--location-kind", "standalone"])
    preview = run_generator([*base, "--dry-run"])
    return write, preview, next(ac_root.rglob(f"{ac_id}.yaml")), tickets


def _assert_refused(tmp_path: Path, ac_id: str, ac: dict) -> None:
    write, preview, ac_file, tickets = _both_paths(tmp_path, ac_id, ac)
    for label, run in (("write", write), ("preview", preview)):
        assert run.exit_code == 1, f"{label}: exit {run.exit_code}; stdout={run.stdout[:200]!r} stderr={run.stderr[-300:]!r}"
        match = _REFUSAL.search(run.stderr)
        assert match and match.group("id") == ac_id, f"{label}: {run.stderr[-300:]!r}"
    assert "## Test Requirements" not in preview.stdout and "---" not in preview.stdout
    assert list(tickets.rglob("*")) == [], "nothing may be written on refusal"
    assert "implemented_by" not in yaml.safe_load(ac_file.read_text(encoding="utf-8")), "no back-reference on refusal"


def test_h1_prompt_leaf_with_only_a_md_file_is_refused_on_both_paths(tmp_path):
    # covers: ACD-2500b-2-i
    # angle: failure
    """(a) llm-expert, change_target prompt, a `.md` declared file: no implementation file is in scope
    and no test_spec is authored, yet the record carries test_intent without a design.

    Both the write path and the preview path exit 1 with the "test design pending" refusal naming the
    AC, print no ticket, write no ticket and no implemented_by back-reference. Wrong version caught:
    the refusal lives only inside the branch that already builds the section, so this fixture
    generates a ticket with no Test Requirements.
    """
    ac = _ac("llm-expert", ("templates/agents/zz-fixture.md",), change_target="prompt")
    _assert_refused(tmp_path, "ZZH-1a", ac)


def test_h1_python_coder_with_only_a_docs_file_is_refused_on_both_paths(tmp_path):
    # covers: ACD-2500b-2-i
    # angle: failure
    """(b) python-coder whose only declared file is docs/zz.md: same refusal on both paths.

    The agent being a code agent does not matter; neither does the declared files list. The refusal
    follows the record (test_intent present, no design), not the surface the files imply.
    """
    _assert_refused(tmp_path, "ZZH-1b", _ac("python-coder", ("docs/zz.md",)))


def test_h1_control_test_required_false_without_intent_generates_normally(tmp_path):
    # covers: ACD-2500b-2-i
    # angle: discrimination
    """Control for both H-1 fixtures: the same AC with `test_required: false` and NO test_intent is
    generated on both paths (exit 0, one ticket written, a ticket printed by the preview).

    Catches the over-broad wrong version that refuses every record that reaches the body without a
    Test Requirements section; the refusal must be about intent without a design and nothing else.
    """
    from _tkt_500f_support import write_ac_store  # noqa: PLC0415

    for agent, files, ac_id in (
        ("llm-expert", ("templates/agents/zz-fixture.md",), "ZZH-1c"),
        ("python-coder", ("docs/zz.md",), "ZZH-1d"),
    ):
        ac = _ac(agent, files, test_required=False)
        del ac["test_intent"]
        root = tmp_path / ac_id
        ac_root = write_ac_store(root / "acs", ac_id, ac)
        tickets = root / "tickets"
        tickets.mkdir(parents=True)
        base = ["--ac", ac_id, "--ac-root", str(ac_root)]
        write = run_generator([*base, "--tickets-root", str(tickets), "--location-kind", "standalone"])
        preview = run_generator([*base, "--dry-run"])
        assert write.exit_code == 0, f"{agent} write: {write.stderr[-300:]!r}"
        assert len(list(tickets.rglob("*.md"))) == 1, agent
        assert preview.exit_code == 0 and "---" in preview.stdout, f"{agent} preview: {preview.stderr[-300:]!r}"


# ---------------------------------------------------------------------------
# L-1: test_required false is not pending
# ---------------------------------------------------------------------------
def _no_test_intent_record(record_id: str, **overrides) -> dict:
    """A reviewed prompt leaf carrying test_intent AND `test_required: false`."""
    fields = {"change_target": "prompt", "assigned_agent": "llm-expert", "test_required": False}
    fields.update(overrides)
    return reviewed_intent(record_id, **fields)


def test_l1_design_pending_is_false_when_test_required_is_false():
    # covers: ACD-2500b-2
    # angle: boundary
    """design_pending is False for intent + `test_required: false`, and still True for every other
    value of the field (absent, None, True), so the exception is exactly `is False`.

    Exact rows (record -> pending): required false: False; absent: True; None: True; True: True.
    """
    from _test_intent import design_pending  # noqa: PLC0415

    base = reviewed_intent("ZZH-2a")
    rows = {
        "false": (dict(base, test_required=False), False),
        "absent": (base, True),
        "none": (dict(base, test_required=None), True),
        "true": (dict(base, test_required=True), True),
    }
    got = {label: design_pending(record) for label, (record, _) in rows.items()}
    assert got == {label: want for label, (_, want) in rows.items()}, got


def test_l1_gate_approval_and_generator_agree_on_test_required_false():
    # covers: ACD-2500b-2
    # angle: seam
    """The three consumers read one predicate, so they agree: for intent + `test_required: false` the
    approval check does not hold it, the readiness gate does not flag "test design pending" (and, the
    contract being an explicit test_required false, flags nothing), and the generator's section builder
    returns "" instead of refusing. Control: the same record without test_required IS held, flagged
    pending, and refused, so the agreement is not "nothing fires".
    """
    from _approval_holds import approval_hold_reason  # noqa: PLC0415
    from _gtfa_tests_section import TestDesignPendingError, _build_test_requirements_section  # noqa: PLC0415
    from _impl_readiness_gate import implementation_readiness_reasons  # noqa: PLC0415

    exempt = _no_test_intent_record("ZZH-3a", readiness="approved")
    assert approval_hold_reason(exempt) is None
    assert PENDING not in implementation_readiness_reasons(exempt)
    assert implementation_readiness_reasons(exempt) == []

    ac = _ac("llm-expert", ("templates/agents/zz-fixture.md",), change_target="prompt", test_required=False)
    assert _build_test_requirements_section(ac, "ZZH-3a") == ""

    pending = reviewed_intent("ZZH-3b", readiness="approved", change_target="prompt", assigned_agent="llm-expert")
    assert approval_hold_reason(pending) == PENDING
    assert implementation_readiness_reasons(pending) == [PENDING]
    import pytest  # noqa: PLC0415

    with pytest.raises(TestDesignPendingError):
        _build_test_requirements_section(dict(ac, test_required=None), "ZZH-3b")


def test_l1_real_approval_cli_promotes_intent_with_test_required_false(tmp_path):
    # covers: ACD-2500b-2
    # angle: reachability
    """Entry point: `python scripts/ac_store/approve_acs.py --goal <id> --json` (CLI via subprocess).

    A reviewed leaf carrying test_intent and `test_required: false` is promoted to approved (it is in
    the approved list, not the held list, and its file changed); the control leaf (same intent, no
    test_required) is held "test design pending" with its bytes unchanged.
    """
    records = [
        goal("ZZH-4", ["ZZH-4a-1", "ZZH-4a-2"]),
        _no_test_intent_record("ZZH-4a-1"),
        reviewed_intent("ZZH-4a-2", change_target="prompt", assigned_agent="llm-expert"),
    ]
    store = build(tmp_path, records)
    held_before = read_bytes(store, "ZZH-4a-2")

    report = json_of(run_approve(store, "--goal", "ZZH-4", "--json"))

    assert report["approved"] == ["ZZH-4a-1"], report
    assert [(h["id"], h["reason"]) for h in report["held"]] == [("ZZH-4a-2", PENDING)], report
    assert store.read("ZZH-4a-1")["readiness"] == "approved"
    assert read_bytes(store, "ZZH-4a-2") == held_before
