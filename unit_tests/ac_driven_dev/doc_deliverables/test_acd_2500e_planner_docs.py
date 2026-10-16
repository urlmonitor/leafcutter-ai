"""ACD-2500e-4, ACD-2500e (parent) and ACD-2500e-3 -- the technical planner's reference doc and prompt.

ACD-2500e-4 is ``test_required: false`` (documentation): its tests read docs/reference/technical-planner-role.md.

ACD-2500e (composite parent) closes through its children; the one check here reads the planner's real
template and asserts the parent's own three claims together (profile truthful, kept duties present, relocated
duties gone). ACD-2500e-1 alone cannot prove the parent because it covers only the profile.

ACD-2500e-3 is ``test_required: false`` because its behaviour is a live LLM run, which no unit test can
reproduce; it was proved operationally by ticket 44. The tests tagged for it are HONEST ABOUT THAT LIMIT: they
check only (a) the static precondition, that the real it-po prompt instructs each behaviour the live run
demonstrated, and (b) that the operational proof (verifier PASS 11/11 and rule check passed) is recorded in
ticket 44. They do not, and cannot, show a model obeys the prompt.
"""

from __future__ import annotations

import re

import yaml

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

ROLE = D.REPO / "docs" / "reference" / "technical-planner-role.md"
TEMPLATE = D.REPO / "templates" / "agents" / "it-po.md"
TICKETS = D.REPO / "tickets"


def _frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    assert m, "template has no frontmatter"
    return yaml.safe_load(m.group(1))


# ---------------------------------------------------------------- ACD-2500e-4
def test_ac4_role_doc_lists_kept_duties_and_owner_of_each_relocated_duty():
    # covers: ACD-2500e-4
    # angle: criterion
    """The kept-duties table names routing/splitting, sizing, it_requirements, contracts, test intent; the
    relocated table maps each relocated duty to the rule check, the test-designer or its output groups."""
    text = D.read(ROLE)
    kept = D.flat(D.section(text, "Duties the planner keeps"))
    for duty in ("Routing and splitting", "Sizing", "`it_requirements`", "Contracts", "Test intent"):
        assert f"| {duty} |" in kept, f"kept duty not listed: {duty}"
    moved = D.flat(D.section(text, "Relocated duty to owner"))
    for row in ("| Parent-to-child back-links | Rule check family 1 |",
                "| Contract presence and symmetry | Rule check family 3 |",
                "| Test design (`test_spec`) | `test-designer`, code-aware output group |",
                "| Reference-file choice (`reference_file_path`) | `test-designer`, file-aware output group |",
                "| File findings (`file_findings`) | `test-designer`, file-aware output group |"):
        assert row in moved, f"relocated duty row missing: {row}"


def test_ac4_role_doc_states_intent_not_design_and_names_the_one_agent():
    # covers: ACD-2500e-4
    # angle: criterion
    """It states the planner records test intent and never test design, and that both steps are one agent."""
    text = D.flat(D.read(ROLE))
    assert "Records test intent, never test design." in text
    assert "The planner never writes `test_spec`" in text
    assert "two output groups of one registered agent, `test-designer`" in text


def test_ac4_role_doc_states_no_source_access_and_why_it_is_no_longer_a_gap():
    # covers: ACD-2500e-4
    # angle: criterion
    """It states the planner does not read source (ADR-009) and why that is no longer a gap."""
    sec = D.flat(D.section(D.read(ROLE), "Source access"))
    assert "The planner does not read source code or test files (ADR-009)." in sec
    assert "This is no longer a gap" in sec
    assert "the `test-designer` reads the files it needs" in sec


# ---------------------------------------------------------------- ACD-2500e (parent)
def test_parent_planner_profile_truthful_kept_duties_present_relocated_duties_gone():
    # covers: ACD-2500e
    # angle: criterion
    """Parent criteria, read from the real it-po template: the profile says it mutates the requirement
    store and produces requirement records (not 'none' / 'analysis'); the kept duties (routing and
    splitting, technical requirements, contracts) are sections of the prompt; the relocated duties' distinctive
    text is gone from the instructions."""
    text = D.read(TEMPLATE)
    fm = _frontmatter(text)
    mutates = fm["mutates"]
    assert isinstance(mutates, list) and mutates, "profile must declare what it mutates"
    assert any("docs/acceptance-criteria" in str(m.get("surface", "")) for m in mutates)
    assert fm["produces"] == "requirement_records"
    for heading in ("### 2.1 — assigned_agent", "### 2.3 — it_requirements", "### 2.4 — delivers_to",
                    "### 2.5 — expects_from", "## S3 Splitting Protocol"):
        assert heading in text, f"kept duty section gone: {heading}"
    for relocated in ("Documentation Gate", "Technology-surface compatibility", "Cannot act on",
                      "component_membership", "Apply parent covered_by update"):
        assert relocated not in text, f"relocated duty text still in the planner's instructions: {relocated}"
    assert "test design pending" not in fm["description"]


# ---------------------------------------------------------------- ACD-2500e-3
def test_ac3_static_precondition_prompt_instructs_the_behaviour_the_live_run_showed():
    # covers: ACD-2500e-3
    # angle: criterion
    """STATIC PRECONDITION ONLY (not the live behaviour): the real it-po prompt instructs each clause of the
    criteria: test intent and never test design, no reference-file choice, no readiness above reviewed,
    criteria and pattern fields left byte-identical."""
    text = D.flat(D.read(TEMPLATE))
    for instruction in (
        "Never write `test_spec`",
        "never raise `readiness` above `reviewed`",
        "Write no `reference_file_path`",
        "The criteria stay byte-identical.",
        "`implements_pattern` | Read-only — copy verbatim from the BA output, never clear or change",
        "`pattern_bindings` | Read-only — copy verbatim from the BA output, never clear or change",
    ):
        assert instruction in text, f"it-po prompt no longer instructs: {instruction}"
    assert "It writes no test design." in text


def test_ac3_recorded_proof_ticket_44_holds_the_verifier_result():
    # covers: ACD-2500e-3
    # angle: criterion
    """RECORDED PROOF ONLY (not a re-run): the operational proof is recorded in ticket 44 -- the real prompt
    on a 3-record scratch batch, verifier PASS 11/11 and the rule check (stage itpo) verdict passed, exit 0."""
    found = sorted(TICKETS.rglob("*TICKET-*-ACD-2500e-3.md"))
    assert found, "ticket 44 (ACD-2500e-3) not found under tickets/"
    body = D.flat(found[0].read_text(encoding="utf-8"))
    assert "Operational proof (ACD-2500e-3)" in body
    assert "three BA-shaped leaves (code, prompt-only, documentation" in body
    assert "OVERALL: PASS (11/11)" in body
    assert "--stage itpo verdict passed, exit 0" in body
