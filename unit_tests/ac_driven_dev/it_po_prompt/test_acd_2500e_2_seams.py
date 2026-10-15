"""
MODULE: unit_tests/ac_driven_dev/it_po_prompt/test_acd_2500e_2_seams.py
COVERS: ACD-2500e-2 (also ACD-200b-1 and BO-2000d-3 where marked)
GOAL: Red-first specification of ticket 43 (seam half): what the slimmed templates/agents/it-po.md teaches is
    checked against the REAL consumers of that teaching: the rule-family strings and dispositions of
    scripts/ac_store/_rc_report.py, the hold vocabulary of _impl_readiness_gate.HOLD_REASONS, the
    hold oracle _approval_holds, the real config/ac_store_schema.json and the clause parser _test_intent;
    plus the prompt as rendered by the real scripts/render_effective_prompt.py CLI.
BUSINESS CONTEXT: A prompt that names a family string the script renamed, or teaches a record shape the
    schema rejects, fails silently in a model run. Structure tests (test_acd_2500e_2.py) cannot see that.
HONEST LIMIT: a prompt change. What is proven is the file; the planner's obedience is the rule check's
    job (ACD-2500a) and the approval hold's (ACD-2500b-2).
RED STATE (right reasons): the template has no S5b, no marker, a five-field example and a few-shot block
    that lacks components and test_intent, so each test fails on an assertion about the current template.
"""

from __future__ import annotations

import re

import jsonschema
import pytest

from unit_tests.ac_driven_dev.it_po_prompt import _slim_support as P

S = P.S
AC = "ACD-2500e-2"


# --------------------------------------------------------------------------
# AC-3 seam: the vocabulary the prompt points at is the real vocabulary
# --------------------------------------------------------------------------
def test_ac3_every_family_the_planner_acts_on_is_named_with_its_real_string():
    # covers: ACD-2500e-2
    # angle: seam
    """AC-3 seam (architect note D3): S5b names each rule-check family the planner acts on using the exact
    string of the real `_rc_report.FAMILY_*` constant, so a renamed family turns this red. Control: the
    nine constants are distinct non-empty strings, so a missing one cannot hide behind an empty needle."""
    families = [P.family(name) for name in P.ACTING_FAMILIES]
    body = S.flat(P.s5b())

    assert len(set(families)) == len(P.ACTING_FAMILIES) and all(families)
    assert [f for f in families if f not in body] == []


def test_ac3_s5b_dispositions_are_the_real_report_dispositions():
    # covers: ACD-2500e-2
    # angle: seam
    """AC-3 seam: S5b tells the planner what to do per disposition using the real `_rc_report.DISPOSITION_*`
    strings (fixed: never undo; needs a decision: yours; failed: stop and report it in `anomalies`)."""
    body = S.flat(P.s5b())
    dispositions = (P._rc_report.DISPOSITION_FIXED, P._rc_report.DISPOSITION_DECISION, P._rc_report.DISPOSITION_FAILED)

    assert [d for d in dispositions if d not in body] == []
    assert "anomalies" in body and re.search(r"(never|do not)[^.]{0,30}undo", body, re.I), body[:300]


def test_ac3_documentation_family_paragraph_tells_the_planner_to_add_the_missing_documentation_requirement():
    # covers: ACD-2500e-2
    # covers: ACD-200b-1
    # angle: seam
    """ACD-200b-1 clauses 2 and 3: the template names the requirement rule check as owner of the
    documentation-coverage check (real family string) and tells the planner that on a finding with no
    matching documentation requirement it ADDS one for the named specialist (the finding names it)."""
    paragraph = S.paragraph_with(P.s5b(), P.family("FAMILY_DOC_TRIGGERS"))

    assert re.search(r"add[^.]{0,80}documentation", paragraph, re.I), paragraph
    assert re.search(r"named specialist|specialist (named|the finding)", paragraph, re.I), paragraph


# --------------------------------------------------------------------------
# Marker seam (D1): the prompt's package-surface example against the real schema and hold oracle
# --------------------------------------------------------------------------
def test_marker_string_is_the_real_hold_reason_the_example_carries():
    # covers: ACD-2500e-2
    # covers: BO-2000d-3
    # angle: seam
    """The fenced package-surface example carries `hold_reason: reference file pending`, and that string is
    a member of the real `_impl_readiness_gate.HOLD_REASONS` (the store's one closed vocabulary)."""
    marker = P.package_surface_fragment().get("hold_reason")

    assert marker == P.MARKER, f"the example must carry the marker, found {marker!r}"
    assert marker in P._impl_readiness_gate.HOLD_REASONS


def test_marker_example_validates_and_holds_approval_and_the_marker_is_what_makes_it_legal(tmp_path):
    # covers: ACD-2500e-2
    # covers: BO-2000d-3
    # angle: seam
    """Seam, planner output to its consumers. The prompt's fenced example is merged into the REAL
    ACD-2500e-2 record (yaml.safe_dump to a tmp file, read back). It validates against the REAL schema and
    the REAL `_approval_holds.approval_hold_reason` holds it with 'reference file pending'. CONTROL ROW:
    the same record without the marker is rejected by the schema for the missing reference_file_path, so
    the marker (not anything else in the record) is what makes the four-field object legal."""
    import _approval_holds

    fragment = P.package_surface_fragment()
    held, real = S.merged_record(tmp_path, AC, fragment)
    (tmp_path / "control").mkdir()
    control, _ = S.merged_record(tmp_path / "control", AC, {k: v for k, v in fragment.items() if k != "hold_reason"})

    jsonschema.validate(held, S.schema())
    assert "reference_file_path" not in held["it_requirements"]
    assert _approval_holds.approval_hold_reason(held) == P.MARKER
    with pytest.raises(jsonschema.ValidationError, match="reference_file_path"):
        jsonschema.validate(control, S.schema())
    assert held["criteria"] == real["criteria"] and held["assigned_agent"] == real["assigned_agent"]


# --------------------------------------------------------------------------
# Few-shot example (D2.2): validates against the real schema, intent matches the real clause parser
# --------------------------------------------------------------------------
def test_few_shot_before_and_after_validate_against_the_real_schema():
    # covers: ACD-2500e-2
    # angle: real_artifact
    """D2.2: both few-shot blocks carry a non-empty `components` list (the schema requires it) and validate
    against the REAL config/ac_store_schema.json. Today neither does."""
    for which in ("Before", "After"):
        record = P.few_shot(which)
        errors = [e.message for e in jsonschema.Draft7Validator(S.schema()).iter_errors(record)]
        assert errors == [], f"{which} block: {errors}"
        assert record["components"], which


def test_few_shot_after_test_intent_has_one_entry_per_clause_matching_the_real_parser():
    # covers: ACD-2500e-2
    # angle: seam
    """D2.2: the 'After' block carries `test_intent` with exactly three entries (one per Then/And clause of
    its criteria), clause text equal to `_test_intent.normalise_clause` of each clause from the REAL
    `_test_intent.outcome_clauses`, exactly the keys {clause, needs_test, reason}, at least one
    needs_test true. The second clause holds a colon and quotes, so it is a quoted YAML scalar."""
    after = P.few_shot("After")
    expected = [P._test_intent.normalise_clause(c) for c in P._test_intent.outcome_clauses(after["criteria"])]
    entries = after.get("test_intent") or []

    assert len(expected) == 3 and len(entries) == 3, (len(expected), len(entries))
    assert [P._test_intent.normalise_clause(e["clause"]) for e in entries] == expected
    assert all(set(e) == {"clause", "needs_test", "reason"} for e in entries)
    assert any(e["needs_test"] is True for e in entries)


def test_few_shot_after_has_no_test_design_hold_or_reference_file_and_is_reviewed():
    # covers: ACD-2500e-2
    # angle: discrimination
    """D2.2. WRONG VERSION THIS CATCHES: the example still teaches a test design, a hold or a chosen
    reference file (a planner copies the example). The 'After' record has `readiness: reviewed` and no
    test_spec, no hold_reason, no reference_file_path anywhere in it_requirements."""
    after = P.few_shot("After")

    assert after.get("readiness") == "reviewed", after.get("readiness")
    assert not {"test_spec", "hold_reason"} & set(after)
    assert "reference_file_path" not in str(after.get("it_requirements"))
    assert after.get("test_intent"), "the After block must teach test_intent"


def test_few_shot_criteria_are_byte_identical_between_before_and_after():
    # covers: ACD-2500e-2
    # angle: boundary
    """D2.2 / TKT-300a-4: criteria stay byte-identical between the Before and After blocks, and the Before
    block (BA output) carries no test_intent (the planner adds it). Needs the After test_intent, so a
    green criteria comparison alone cannot satisfy it."""
    before, after = P.few_shot("Before"), P.few_shot("After")

    assert before["criteria"] == after["criteria"]
    assert "test_intent" not in before and after.get("test_intent")


def test_few_shot_what_changed_lists_intent_readiness_and_the_three_absences():
    # covers: ACD-2500e-2
    # angle: criterion
    """D2.2: 'What changed' gains the test_intent and readiness lines and one line 'no test_spec, no
    hold_reason, no reference_file_path'."""
    section = S.flat(S.section_titled(P.planner(), "Few-Shot Example"))
    changed = section[section.index("What changed"):]

    assert "test_intent" in changed and "readiness" in changed
    assert re.search(r"no test_spec, no hold_reason,? (and )?no reference_file_path", changed), changed[-300:]


# --------------------------------------------------------------------------
# Reachability: the prompt as the planner receives it
# --------------------------------------------------------------------------
def test_acd_2500e_2_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500e-2
    # angle: reachability
    """Entry point resolved (CLI script with main under scripts/): `python scripts/render_effective_prompt.py
    --agent it-po --ac ACD-2500e-2`, run as a subprocess against a tmp repo root holding a verbatim copy of
    the TEMPLATE (the CLI prefers the stale deployed copy). The prompt the planner receives carries every
    paragraph of S5b verbatim and no S2.8 / S7b section or compatibility table."""
    rendered_list = S.rendered_prompt_paragraphs("it-po", AC, tmp_path)
    rendered = set(rendered_list)

    S.assert_rendered(rendered, P.s5b(), "requirement_rule_check.py")
    S.assert_rendered(rendered, P.s5b(), P.family("FAMILY_CONTRACTS"))
    headings = [p for p in rendered_list if p.startswith("#") and re.search(r"S2\.8|\bS7b\b", p)]
    assert headings == [], headings
    assert not any("Technology-surface compatibility" in p for p in rendered_list)


def test_rendered_prompt_still_carries_the_kept_duties(tmp_path):
    # covers: ACD-2500e-2
    # angle: reachability
    """GUARD for the entry point (green today): the rendered prompt keeps the paragraph that carries the
    Splitting Protocol and the test_intent rule, so the render path drops no kept duty."""
    rendered = set(S.rendered_prompt_paragraphs("it-po", AC, tmp_path))

    S.assert_rendered(rendered, P.planner(), "Assign exactly ONE agent")
    S.assert_rendered(rendered, S.section_titled(P.planner(), "test_intent"), "test_spec", "never")
