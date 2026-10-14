"""
MODULE: unit_tests/ac_driven_dev/it_po_prompt/test_acd_2500d_3.py
COVERS: ACD-2500d-3
GOAL: Red-first specification of ticket 38: how the technical planner (the IT PO) decides on the file
    findings it is handed back, and what the file-aware step (test-designer) must leave alone.
    templates/agents/it-po.md gains a next-pass rule: for each undecided non-`consistent` finding
    record `decision: {choice: reassign | split | assignment stands, reason: <one sentence>, by:
    it-po}`; reassign changes assigned_agent, split follows the Splitting Protocol; nothing else is
    touched. templates/agents/test-designer.md states that the step reports findings with decision
    null and changes no routing field.
BUSINESS CONTEXT: ADR-072, user decision 2: the IT PO keeps routing and splitting (TKT-300a-1,
    TKT-300a-3); the file-aware step only informs it. Approval is held while a finding has no decision
    (ticket 39 enforces that deterministically, so the prompt must make the planner record one per
    finding, and the designer must never record it for the planner).
HONEST LIMIT: a prompt change (`test_required: false`); the hold and the workflow hand-back are
    ticket 39's code. Proven here: the paragraphs carrying each rule, the fenced example (parsed and
    validated against the real schema property that lands with ticket 39), the example merged into a
    record written by yaml.safe_dump and read by the REAL hold oracle (SEAM, with a control row), and
    both prompts as rendered by the real CLI (REACHABILITY). No assertion touches the G5-owned it-po.md
    sections (S2.8, S5, S7, S7b, the BO-2000d block, the S8 items G5 removes).
RED STATE (right reasons): neither prompt carries the rule, so each prose test fails on an ASSERTION
    about the current prompt. The schema and hold-oracle tests go green only once ticket 39 lands.
INTERPRETATION (flagged in the hand-off): the it-po rule is found by a level 2-4 heading whose title
    contains "finding" and whose body names file_findings and decision (the architect note does not fix
    the heading); the stop of the planner after round 2 is the workflow's, not pinned here.
"""

from __future__ import annotations

import copy
import re
import sys

import jsonschema

from unit_tests.ac_driven_dev.test_designer_prompt import _file_findings_prompt_support as S

AC = "ACD-2500d-3"
DESIGNER = "test-designer"
PLANNER = "it-po"


def _section() -> str:
    return S.section_titled(S.template(PLANNER), "finding", "file_findings", "decision")


def _example() -> dict:
    example = S.example_with(_section(), "file_findings")
    assert any(f.get("decision") for f in example["file_findings"]), "the example must show a recorded decision"
    return example


def test_ac1_the_file_aware_step_changes_no_routing_field():
    # covers: ACD-2500d-3
    # angle: criterion
    """AC-1: the requirement's assigned specialist, split, technical requirements, contracts and criteria
    are unchanged by the step. The designer prompt names assigned_agent, the split, delivers_to,
    expects_from, criteria and the it_requirements keys as fields a finding never changes."""
    paragraph = S.paragraph_with(
        S.template(DESIGNER), "assigned_agent", "split", "delivers_to", "expects_from", "criteria", "findings", "never"
    )

    assert re.search(r"it_requirements", paragraph) and re.search(r"(route|routing|specialist)", paragraph, re.I), paragraph


def test_ac2_the_step_leaves_decision_null_for_the_technical_planner():
    # covers: ACD-2500d-3
    # angle: criterion
    """AC-2: the finding reaches the technical planner, whose next pass records the decision. The
    designer writes every finding with decision null and never records one: the decision belongs to
    the technical planner (IT PO)."""
    paragraph = S.paragraph_with(S.template(DESIGNER), "decision", "null", "technical planner")

    assert re.search(r"(never|not|do not)[^.]{0,60}(record|write|fill|set)[^.]{0,40}decision|only[^.]{0,60}planner", paragraph, re.I), paragraph


def test_ac2_example_findings_of_the_step_all_carry_decision_null():
    # covers: ACD-2500d-3
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the file-aware step fills `decision` itself (to make a finding look
    resolved), which would defeat the approval hold. Every finding in the designer prompt's own example
    has decision null or absent."""
    example = S.example_with(S.template(DESIGNER), "file_findings")

    assert example["file_findings"] and all(f.get("decision") is None for f in example["file_findings"])


def test_ac2_the_planner_prompt_has_a_next_pass_rule_for_file_findings():
    # covers: ACD-2500d-3
    # angle: criterion
    """AC-2: templates/agents/it-po.md gains a section about file findings that says what the next pass
    does: it reads the findings the code-aware step wrote on the record and records a decision on each
    one that needs it."""
    paragraph = S.paragraph_with(_section(), "next pass", "file_findings")

    assert re.search(r"(record|write|set)[^.]{0,60}decision", paragraph, re.I), paragraph


def test_ac2_a_decision_is_one_of_three_choices_with_a_one_sentence_reason_by_it_po():
    # covers: ACD-2500d-3
    # angle: criterion
    """AC-2: the planner either reassigns, splits, or states why the assignment stands. The decision is
    `{choice, reason, by}` with choice exactly reassign, split or assignment stands, a one-sentence
    reason, and by: it-po."""
    paragraph = S.paragraph_with(_section(), "reassign", "split", "assignment stands", "reason")

    assert "one sentence" in paragraph or "one-sentence" in paragraph, paragraph
    assert re.search(r"by: it-po|by it-po", paragraph, re.I), paragraph


def test_ac2_consistent_findings_need_no_decision_every_other_finding_gets_one():
    # covers: ACD-2500d-3
    # angle: boundary
    """Boundary (architect note conflict 8): a `consistent` finding needs no decision and keeps
    decision null; every finding with another verdict that still has decision null gets one, so none
    is left undecided (an undecided finding keeps the requirement out of approval)."""
    paragraph = S.paragraph_with(_section(), "consistent", "decision")

    assert re.search(r"consistent[^.]{0,80}(no decision|needs no|does not need|without|null)", paragraph, re.I), paragraph
    assert re.search(r"(every|each|all)[^.]{0,80}(other|remaining|non-consistent|undecided)", paragraph, re.I), paragraph


def test_ac2_reassign_changes_assigned_agent_and_split_follows_the_splitting_protocol():
    # covers: ACD-2500d-3
    # angle: criterion
    """AC-2 / ticket 38 note: `reassign` makes the assignment change (assigned_agent, by the same rule
    as the assignment step); `split` follows the Splitting Protocol of this prompt; `assignment stands`
    changes nothing but the decision. TKT-300a-1 (one agent) and TKT-300a-3 (contracts) stay with the
    planner."""
    section = _section()
    reassign = S.paragraph_with(section, "reassign", "assigned_agent")
    split = S.paragraph_with(section, "split", "Splitting Protocol")
    stands = S.paragraph_with(section, "assignment stands", "nothing")

    assert reassign and split and re.search(r"(only|just)[^.]{0,40}decision|nothing (else|but)|no (other )?change", stands, re.I), stands


def test_ac2_the_planner_touches_nothing_but_the_decision_and_the_routing_change():
    # covers: ACD-2500d-3
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the planner rewrites the designer's verdict, reason, line_range or
    found_in (or the opened-files list) so a finding no longer needs a decision. The prompt says the
    planner records `decision` only on the finding and touches nothing else of the file-aware step's
    output."""
    paragraph = S.paragraph_with(_section(), "verdict", "decision", "file_findings_opened_files")

    assert re.search(r"(never|not|do not)[^.]{0,80}(edit|change|rewrite|alter)", paragraph, re.I), paragraph
    assert all(field in paragraph for field in ("reason", "line_range", "found_in")), paragraph


def test_ac3_an_undecided_finding_keeps_the_requirement_out_of_approval():
    # covers: ACD-2500d-3
    # angle: criterion
    """AC-3 (prose half; the deterministic hold is ticket 39): the planner prompt states that a finding
    with no recorded decision keeps the requirement from being offered for approval, which is why every
    finding that needs one gets one. The planner never approves or sets readiness itself."""
    paragraph = S.paragraph_with(_section(), "decision", "approval")

    assert re.search(r"(not offered|held|hold|cannot be approved|kept out)", paragraph, re.I), paragraph


def test_ac_example_is_valid_under_the_real_schema_properties():
    # covers: ACD-2500d-3
    # angle: real_artifact
    """Lockstep with ticket 39 (goes green only once 39 lands the file_findings property): the planner
    prompt's fenced example parses and validates against the REAL config/ac_store_schema.json property;
    each decision uses a valid choice with by: it-po, and the example shows one `consistent` finding
    left at decision null beside a decided non-consistent one (control row)."""
    findings = _example()["file_findings"]

    jsonschema.validate(findings, S.schema_property("file_findings"))
    decided = [f for f in findings if f.get("decision")]
    assert all(f["decision"]["by"] == "it-po" and f["decision"]["choice"] in S.CHOICES for f in decided)
    assert any(f["verdict"] == "consistent" and f.get("decision") is None for f in findings)
    assert all(f["verdict"] != "consistent" for f in decided)


def test_ac_the_planner_example_releases_the_real_hold_and_stripping_it_restores_the_hold(tmp_path):
    # covers: ACD-2500d-3
    # angle: seam
    """Seam, planner output to the hold's consumer (goes green only once 39 lands): the planner prompt's
    example is merged into the REAL ACD-2500d-3 record (yaml.safe_dump to a tmp file, read back). The
    REAL scripts/ac_store/_approval_holds.approval_hold_reason releases it (None). Control row: the SAME
    findings with every decision set back to null are held with `file finding undecided`, so the
    release is caused by the recorded decisions and not by anything else in the record."""
    example = _example()
    fragment = {key: example[key] for key in ("file_findings", "file_findings_opened_files") if key in example}
    decided, real = S.merged_record(tmp_path, AC, fragment)
    stripped_findings = copy.deepcopy(fragment["file_findings"])
    for finding in stripped_findings:
        finding["decision"] = None
    (tmp_path / "control").mkdir()
    undecided, _ = S.merged_record(tmp_path / "control", AC, {**fragment, "file_findings": stripped_findings})
    jsonschema.validate(decided, S.schema())
    sys.path.insert(0, str(S.REPO / "scripts" / "ac_store"))
    import _approval_holds

    assert _approval_holds.approval_hold_reason(decided) is None
    assert _approval_holds.approval_hold_reason(undecided) == "file finding undecided"
    assert decided["criteria"] == real["criteria"] and decided["assigned_agent"] == real["assigned_agent"]


def test_acd_2500d_3_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500d-3
    # angle: reachability
    """Entry point resolved (CLI script with main under scripts/): `python
    scripts/render_effective_prompt.py --agent it-po --ac ACD-2500d-3` and the same for test-designer,
    each run as a subprocess. Each prompt as its agent receives it carries, verbatim, the paragraph
    that carries this ticket's rule (the planner's decision choices; the designer's decision-null rule)."""
    planner = set(S.rendered_prompt_paragraphs(PLANNER, AC, tmp_path / "planner"))
    designer = set(S.rendered_prompt_paragraphs(DESIGNER, AC, tmp_path / "designer"))

    S.assert_rendered(planner, _section(), "reassign", "split", "assignment stands", "reason")
    S.assert_rendered(designer, S.template(DESIGNER), "decision", "null", "technical planner")
