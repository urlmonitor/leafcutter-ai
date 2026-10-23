"""
MODULE: unit_tests/ac_driven_dev/it_po_prompt/test_acd_2500e_2.py
COVERS: ACD-2500e-2 (also ACD-200b-1 and BO-2000d-3 where marked)
GOAL: Red-first specification of ticket 43 (structure half): templates/agents/it-po.md holds only the duties
    the technical planner keeps. Removed duties are checked by distinctive tokens and structure (a heading,
    a table row, an S8 item, a fenced example), never by loose prose; the kept duties are guards.
    The seams (real rule-check vocabulary, real schema and hold oracle, few-shot, render CLI) are in
    test_acd_2500e_2_seams.py.
BUSINESS CONTEXT: ACD-2500a/b/d moved the planner's checks into the requirement rule check and the test
    designer. Left in the prompt, the old procedures make the planner redo (or contradict) the script.
    Design: architect note G5, D1 to D3, in the Comments of ticket 41.
HONEST LIMIT: a prompt change (`test_required: false`). A unit test cannot prove a model obeys a prompt; it
    proves what is mechanically decidable about the file. GUARD tests (marked) pin kept duties and PASS on
    today's template by design: they fail only if the slimming deletes a duty it must keep.
RED STATE (right reasons): every other test fails on an ASSERTION about the current template (S2.8 and S7b
    still there, five-field example, no S5b, no marker, tools comment unchanged, ...).
"""

from __future__ import annotations

import re

from unit_tests.ac_driven_dev.it_po_prompt import _slim_support as P

S = P.S
DOC_SENTENCE = "Batches without documentation coverage for triggered categories MUST NOT receive readiness: reviewed."
# Distinctive tokens of the removed S2.8 / S3 step 6 / S5 presence step / S7 components / S7b / BO-2000d text.
REMOVED_TOKENS = (
    "BP-1100f-3", "Technology-surface compatibility", "Cannot act on", "42 underscore ids",
    "Apply parent covered_by update", "Verify both sides have matching contracts", "component_membership",
    "Documentation Gate", "checks at authoring time",
)
TRIGGERS = ("how-to", "reference-doc", "sequence-diagram", "state-diagram", "component-diagram")


# --------------------------------------------------------------------------
# AC-1: what the planner keeps
# --------------------------------------------------------------------------
def test_ac1_guard_routing_splitting_sizing_and_requirements_survive():
    # covers: ACD-2500e-2
    # angle: criterion
    """GUARD (green today): routing (one agent), splitting, sizing and it_requirements stay."""
    text = P.planner()

    assert "ONE agent" in S.section_titled(text, "2.1 —", "Never leave `assigned_agent` null")
    assert "superseded_by" in S.section_titled(text, "Splitting Protocol", "Split procedure")
    assert all(f"`{size}`" in S.section_titled(text, "estimated_complexity") for size in "SML")
    assert "policy-level" in S.section_titled(text, "it_requirements", "GOOD (policy-level)")


def test_ac1_contracts_include_judging_agreement_in_meaning():
    # covers: ACD-2500e-2
    # angle: criterion
    """AC-1: the planner keeps producer/consumer contracts INCLUDING judging whether both sides agree in
    meaning. A paragraph about the contract says the two descriptions must agree in meaning."""
    paragraph = S.paragraph_with(P.planner(), "agree in meaning")

    assert re.search(r"contract|delivers_to|expects_from", paragraph, re.I), paragraph


def test_ac1_guard_test_intent_file_findings_and_knowledge_loop_survive():
    # covers: ACD-2500e-2
    # angle: criterion
    """GUARD (green today): test intent (2.7), the handed-back file findings (S3b) and the knowledge loop
    (S9) stay."""
    text = P.planner()

    assert "needs_test" in S.section_titled(text, "test_intent", "one `test_intent` entry per outcome clause")
    assert "decision" in S.section_titled(text, "Handed-Back", "file_findings")
    assert re.search(r"^## S9 Knowledge Loop", text, re.MULTILINE)


# --------------------------------------------------------------------------
# AC-2: what the planner no longer carries
# --------------------------------------------------------------------------
def test_ac2_no_s2_8_and_no_s7b_section_heading():
    # covers: ACD-2500e-2
    # angle: criterion
    """AC-2: no file-type compatibility section (S2.8) and no documentation gate section (S7b) remain.
    Checked by heading, the structure, not by prose. The new S5b heading must not trip the check."""
    titles = [match.group(2) for match in S.HEADING.finditer(P.planner())]

    assert [t for t in titles if "S2.8" in t or re.search(r"\bS7b\b", t)] == []
    assert any("S5b" in t for t in titles), "the new S5b heading must exist (control for the heading scan)"


def test_ac2_removed_procedures_leave_no_distinctive_token():
    # covers: ACD-2500e-2
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the headings are renamed or the sections shortened but their text lives
    on (a planner told to run both the old procedure and the script). None of the tokens unique to the
    removed text survives anywhere in the template: the S2.8 table and BP id, the parent covered_by step,
    the presence-only contract step, the S7 components bullet, the S7b gate and the authoring-time check."""
    flat = S.flat(P.planner())

    assert [token for token in REMOVED_TOKENS if token in flat] == []


def test_ac2_no_trigger_to_specialist_table_or_mapping_of_its_own():
    # covers: ACD-2500e-2
    # covers: ACD-200b
    # covers: ACD-200b-1
    # angle: discrimination
    """ACD-200b-1 clause 1 and the architect note (conflict table): no table row pairs `sequence-diagram`
    with `architecture-diagram-author`, and no line anywhere pairs any of the five triggers with its
    specialist. The prompt carries no copy of the five-entry mapping; the finding names the specialist."""
    lines = P.planner().splitlines()
    table_rows = [ln for ln in lines if ln.lstrip().startswith("|")]

    assert [r for r in table_rows if "sequence-diagram" in r and "architecture-diagram-author" in r] == []
    specialists = ("documentation-expert", "architecture-diagram-author")
    copied = [ln for ln in lines if any(t in ln for t in TRIGGERS) and any(s in ln for s in specialists)]
    assert copied == [], copied


def test_ac2_s8_keeps_only_items_that_need_judgment():
    # covers: ACD-2500e-2
    # angle: boundary
    """AC-2 clause 4: the checklist drops what the rule check decides: contract presence (family
    producer/consumer), the documentation gate, the components list, and the duplicate non-null
    assigned_agent item. Exact count: 16 items today, minus 4, plus the one new package-surface item = 13."""
    items = P.s8_items()
    joined = " ".join(items)

    assert not any("components:" in item or "component_membership" in item for item in items), "components item"
    assert not any(re.search(r"documentation gate|S7b", item, re.I) for item in items), "documentation gate item"
    assert not re.search(r"matching delivers_to/expects_from", joined), "contract presence item"
    assert not any(re.search(r"non-null assigned_agent", item) for item in items), "duplicate assigned_agent item"
    assert len(items) == 13, f"expected 13 judgment items, found {len(items)}"


def test_ac2_s8_keeps_registry_membership_and_the_pattern_and_contract_judgment_items():
    # covers: ACD-2500e-2
    # angle: criterion
    """GUARD (green today): the items no rule-check family owns stay: registry membership of
    assigned_agent (no family checks it), criteria unchanged, pattern fields preserved, specific
    contracts, split ordering."""
    joined = " ".join(P.s8_items())

    assert P.missing_from(joined, (
        "config/agent_registry.json", "criteria field is UNCHANGED", "implements_pattern",
        "Contract descriptions are specific", "superseded_by",
    )) == []


def test_ac2_s8_readiness_item_is_trimmed_to_reviewed_never_approved():
    # covers: ACD-2500e-2
    # angle: criterion
    """Architect note D2: item 12 keeps only 'readiness is reviewed, never approved' (the draft case is
    dropped). approve_acs.py skips every record that is not reviewed, so the rule must stay."""
    item = next((i for i in P.s8_items() if "readiness" in i), "")

    assert "reviewed" in item and re.search(r"never approved", item), item
    assert "draft" not in item, item


def test_ac2_s8_has_one_item_for_package_surface_records():
    # covers: ACD-2500e-2
    # covers: BO-2000d-3
    # angle: criterion
    """Architect note D2: one new S8 item says package-surface records carry four it_requirements fields and
    the reference-file-pending marker, and no reference_file_path."""
    item = next((i for i in P.s8_items() if "package-surface" in i), "")

    assert all(token in item for token in ("reference_file_path", P.MARKER, "four")), item


def test_ac2_package_surface_example_has_exactly_four_keys_and_no_reference_file_path():
    # covers: ACD-2500e-2
    # covers: BO-2000d-3
    # angle: real_artifact
    """AC-2 (no reference-file choice) / BO-2000d-3: the fenced package-surface `it_requirements` example
    parses to EXACTLY the four planner-owned keys, and none of them is reference_file_path. Exact set, not
    a subset, so a fifth key (or the old five-field example) turns it red."""
    requirements = P.package_surface_fragment()["it_requirements"]

    assert set(requirements) == P.FOUR_FIELDS, sorted(requirements)
    assert requirements["required_skills"] and isinstance(requirements["post_write_commands"], list)


def test_ac2_no_instruction_to_choose_or_block_on_a_reference_file():
    # covers: ACD-2500e-2
    # covers: BO-2000d-3
    # angle: failure
    """The stale S2.3 instruction 'if you cannot supply a real reference_file_path ... raise a blocker' must
    go (left in, the planner blocks on every package-surface record), as must the claim that validate_ac.py
    checks the path 'at authoring time' (ACD-2500d-2-i moved that check after the file-aware step)."""
    text = P.planner()
    blocking = [p for p in S.paragraphs(text) if "reference_file_path" in p and re.search(r"blocker|blocked", p, re.I)]

    assert blocking == [], blocking[0][:160]
    assert not re.search(r"validate_ac\.py[^.]{0,80}authoring time", S.flat(text))


def test_ac2_splitting_protocol_has_no_covered_by_edit_step_and_points_to_the_family():
    # covers: ACD-2500e-2
    # angle: criterion
    """AC-2 (no parent back-link procedure) and AC-3 (pointer): split steps 1-5 stay (superseded_by on the
    original), step 6 is gone, and one sentence names the rule check family that appends each child to its
    parent's covered_by."""
    section = S.section_titled(P.planner(), "Splitting Protocol", "Split procedure")
    flat = S.flat(section)

    assert "superseded_by" in flat and "Preserve the original criteria verbatim" in flat
    assert not re.search(r"modifies ONLY covered_by|Use an Edit call", flat), "step 6 is still there"
    assert P.family("FAMILY_BACKLINKS") in flat and re.search(r"you do not edit the parent", flat, re.I), flat


# --------------------------------------------------------------------------
# AC-3: pointers to the new owners (prose half; the family-string seam is in the seams file)
# --------------------------------------------------------------------------
def test_ac3_s5b_names_the_script_the_stage_and_the_reference_doc():
    # covers: ACD-2500e-2
    # angle: criterion
    """AC-3: a section 'S5b What the rule check owns' gives the CLI entry point, the stage flag and the
    reference doc that lists every family, and says the planner never runs the script (it repairs fields)."""
    body = S.flat(P.s5b())

    assert P.missing_from(body, (
        "requirement_rule_check.py", "--stage itpo", "docs/reference/requirement-rule-check.md",
    )) == []
    assert re.search(r"(never|do not|don't)[^.]{0,40}run", body, re.I), body[:300]


def test_ac3_documentation_sentence_is_verbatim_inside_s5b():
    # covers: ACD-2500e-2
    # covers: ACD-200b
    # covers: ACD-200b-1
    # angle: criterion
    """ACD-200b-1 clause 5: the template states, verbatim, 'Batches without documentation coverage for
    triggered categories MUST NOT receive readiness: reviewed.' It must live in S5b (the old S7b copy goes
    with S7b), so a sentence left behind in a half-deleted gate does not satisfy it."""
    assert DOC_SENTENCE in S.flat(P.s5b())


def test_ac3_surface_pointer_in_2_1_names_the_craft_map_and_says_planner_does_not_read_it():
    # covers: ACD-2500e-2
    # angle: criterion
    """AC-3 / ADR-009: section 2.1 says which specialist fits a file is judged by the surface-to-specialist
    map `config/surface_craft_map.yaml` and checked by the rule check family `specialist versus surface`;
    the planner judges from the criteria only and does not read the map. The signal table stays."""
    section = S.section_titled(P.planner(), "2.1 —", "Signal")
    flat = S.flat(section)

    assert "config/surface_craft_map.yaml" in flat and P.family("FAMILY_SURFACE") in flat
    assert re.search(r"(do not|don't|never)[^.]{0,30}read", flat, re.I), flat[-300:]


# --------------------------------------------------------------------------
# Marker (BO-2000d-3), readiness, S7, tools line
# --------------------------------------------------------------------------
def test_marker_paragraph_sets_hold_reason_only_when_reference_file_path_is_absent():
    # covers: ACD-2500e-2
    # covers: BO-2000d-3
    # angle: criterion
    """D1: one paragraph says the planner sets `hold_reason: reference file pending` on a package-surface
    record, only when reference_file_path is absent (a record the test designer already completed is left
    alone), and sets no other hold_reason value."""
    paragraph = S.paragraph_with(P.planner(), "hold_reason", P.MARKER, "reference_file_path")

    assert re.search(r"only when[^.]{0,80}(absent|missing)", paragraph, re.I), paragraph
    assert re.search(r"no other|any other|other than", paragraph, re.I), paragraph


def test_marker_names_the_test_designer_as_owner_of_reference_file_path():
    # covers: ACD-2500e-2
    # covers: BO-2000d-3
    # angle: criterion
    """BO-2000d-3 / ACD-2500d-2: the planner does not choose reference_file_path; a paragraph names the
    `test-designer` agent (the file-aware step) as the one that does."""
    paragraph = S.paragraph_with(P.planner(), "reference_file_path", "test-designer")

    assert re.search(r"(chosen|choose|names?|supplies|fills?|sets?|owns?)[^.]{0,60}test-designer|test-designer[^.]{0,60}(chooses|names|supplies|fills|sets|owns)", paragraph, re.I), paragraph


def test_readiness_guard_s7_sets_reviewed_and_never_approved():
    # covers: ACD-2500e-2
    # angle: criterion
    """GUARD (green today): S7 still says to set `readiness: reviewed` and never `approved` (approve_acs.py
    skips every record that is not reviewed; with no such rule the planner's records stay draft)."""
    section = S.flat(S.section_titled(P.planner(), "S7 Write"))

    assert "readiness: reviewed" in section and re.search(r"(do not|never)[^.]{0,20}readiness: approved", section, re.I)


def test_s7_write_rules_carry_the_new_fields_and_preserve_the_designers_output():
    # covers: ACD-2500e-2
    # angle: criterion
    """D2 (S7): the add list gains test_intent / test_required and the marker; the preserve list names the
    test designer's output groups and any existing decision; the components bullet is gone."""
    section = S.flat(S.section_titled(P.planner(), "S7 Write"))
    needed = ("test_intent", "test_required", P.MARKER, "test_spec", "test_design_authorship",
              "test_design_opened_files", "file_findings", "file_findings_opened_files", "decision")

    assert P.missing_from(section, needed) == []
    assert "components" not in section, "the S7 components bullet must go (rule check family owns it)"


def test_tools_comment_names_the_real_reasons_for_edit_and_keeps_no_source_access():
    # covers: ACD-2500e-2
    # angle: criterion
    """D2 (frontmatter line `tools:`): the comment no longer blames 'the covered_by update protocol'; it
    names the field-targeted Edits that remain (superseded_by, finding decisions)."""
    line = next(ln for ln in (S.AGENTS_DIR / "it-po.md").read_text(encoding="utf-8").splitlines() if ln.startswith("tools:"))

    assert "covered_by" not in line, line
    assert "superseded_by" in line and "decision" in line, line


def test_tools_line_guard_keeps_edit_and_the_no_source_code_access_words():
    # covers: ACD-2500e-2
    # angle: criterion
    """GUARD (green today; unit_tests/agents/test_acd_2500d_5.py pins the words): the tool list keeps Edit
    and the comment keeps 'No source code access'."""
    line = next(ln for ln in (S.AGENTS_DIR / "it-po.md").read_text(encoding="utf-8").splitlines() if ln.startswith("tools:"))
    tools = [t.strip() for t in line.split("#")[0].removeprefix("tools:").split(",")]

    assert "Edit" in tools and "Write" in tools and "No source code access" in line


# --------------------------------------------------------------------------
# Stays true (TKT-300a-1..4, ACS-500c-2)
# --------------------------------------------------------------------------
def test_stays_true_one_agent_per_ac_and_never_null():
    # covers: ACD-2500e-2
    # angle: criterion
    """GUARD (green today), TKT-300a-1: exactly one agent per AC, never null, an agent in the registry."""
    text = S.flat(P.planner())

    assert "Assign exactly ONE agent" in text and "Never leave assigned_agent null" in text
    assert re.search(r"No AC has multiple agents assigned|multiple agents[^.]{0,40}split", text, re.I) or "split instead" in text


def test_stays_true_policy_level_good_and_bad_requirement_lists():
    # covers: ACD-2500e-2
    # angle: criterion
    """GUARD (green today), TKT-300a-2: GOOD (policy-level) and BAD (implementation prescription) lists
    stay in 2.3, with the BAD list naming exception types and exit codes."""
    section = S.section_titled(P.planner(), "it_requirements", "GOOD (policy-level)", "BAD (implementation prescription)")

    assert "CyclicDependencyError" in section and "exit with code 1" in section


def test_stays_true_both_sides_of_a_contract_are_written():
    # covers: ACD-2500e-2
    # angle: discrimination
    """TKT-300a-3. WRONG VERSION THIS CATCHES: S5 is trimmed to 'verify both sides exist' (a presence
    check the rule check now makes) and the planner stops WRITING the delivers_to / expects_from pair.
    A paragraph tells the planner to write both sides when it wires a pair."""
    paragraph = S.paragraph_with(P.planner(), "delivers_to", "expects_from")

    assert re.search(r"(write|wire)[^.]{0,50}both sides", S.flat(P.planner()), re.I), paragraph[:200]


def test_stays_true_criteria_and_pattern_fields_are_copied_verbatim():
    # covers: ACD-2500e-2
    # angle: criterion
    """GUARD (green today), TKT-300a-4 and ACS-500c-2: criteria stay byte-identical (caveat, never reword),
    implements_pattern and pattern_bindings are copied verbatim, pattern behaviour is not restated."""
    text = P.planner()
    section = S.flat(S.section_titled(text, "Pattern-linked AC preservation"))

    assert "implements_pattern" in section and "pattern_bindings" in section and "exactly as-is" in section
    assert re.search(r"never modifies the criteria field", S.flat(text), re.I) and "byte-identical" in S.flat(text)
