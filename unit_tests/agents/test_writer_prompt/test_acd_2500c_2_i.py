"""
MODULE: unit_tests/agents/test_writer_prompt/test_acd_2500c_2_i.py
COVERS: ACD-2500c-2-i
GOAL: Red-first specification of ticket 32: the build-time rule that ACD-2500c-2-i writes into
    templates/agents/test-writer.md. For a requirement carrying a code-aware test design, the test
    writer writes exactly the tests the design lists (the entry's `name` as the test name, its
    `target_dir` as the directory, each tagged with the requirement id through `# covers:`) and never
    adds, removes or edits an entry or writes to an AC record. For a requirement with test intent and
    no test design it writes no test, derives nothing from the Then clauses, and stops with the reason
    "test design pending" naming the requirement. Legacy designs behave as before.
BUSINESS CONTEXT: ADR-071/-072, user decision 1: the test writer consumes the design at build time and
    does not author it. The halt is the build-time twin of the approval gate: a record can reach the
    test writer by a path other than the queue (fast lane, quick-fix). The existing template still
    tells the writer to derive tests from the Then clauses of the AC when the Test Requirements block
    is empty; left unconditional, that fallback would silently re-author the design.
HONEST LIMIT: a prompt change (`test_required: false`); what the model does is not reproducible in a
    unit test. Proven here: the paragraphs that carry each rule, the carve-out of the two existing
    criteria-derivation fallbacks (DISCRIMINATION), the vocabulary of the real consumers
    (scripts/ac_store/_test_intent.py, _impl_readiness_gate.py) taught verbatim for each state the real
    classifier distinguishes (SEAM, records written by yaml.safe_dump), and the prompt as rendered by the
    real CLI (REACHABILITY). Not pinned: the number of extra tests the existing mandates may add
    beside the design's entries.
RED STATE (right reasons): the template has no build-from-design section and its criteria fallbacks
    are unconditional, so each test fails on an ASSERTION about the current prompt.
INTERPRETATION (flagged in the hand-off): the section is found by a level 2-4 heading whose title
    contains "design" and whose body names test_spec and target_dir; the halt is reported as a
    `(status: blocker)` (the template's existing stop idiom), which the AC does not name.
"""

from __future__ import annotations

import re
import sys

from unit_tests.ac_driven_dev.test_designer_prompt import _file_findings_prompt_support as S

AC = "ACD-2500c-2-i"
AGENT = "test-writer"
PENDING = "test design pending"


def _text() -> str:
    return S.template(AGENT)


def _section() -> str:
    return S.section_titled(_text(), "design", "test_spec", "target_dir")


def test_ac1_each_design_entry_becomes_one_test_with_its_name_in_its_directory():
    # covers: ACD-2500c-2-i
    # angle: criterion
    """AC-1: for a requirement at readiness approved whose design has 3 entries the test writer writes
    tests whose names and directories match the 3 entries: one test per test_spec entry, the test
    function named exactly by the entry's `name`, placed in the entry's `target_dir`."""
    paragraph = S.paragraph_with(_section(), "test_spec", "name", "target_dir")

    assert re.search(r"(one|each|every)[^.]{0,60}entry", paragraph, re.I), paragraph
    assert re.search(r"exactly|verbatim|as named|the entry's", paragraph, re.I), paragraph


def test_ac1_each_test_is_tagged_with_the_requirement_id():
    # covers: ACD-2500c-2-i
    # angle: criterion
    """AC-1: each test is tagged with the requirement id, through the existing `# covers:` convention."""
    paragraph = S.paragraph_with(_section(), "# covers:", "requirement")

    assert re.search(r"(requirement|AC) id", paragraph, re.I), paragraph


def test_ac2_the_design_is_never_added_to_removed_from_or_edited_and_no_ac_record_is_written():
    # covers: ACD-2500c-2-i
    # angle: criterion
    """AC-2 and it_requirements 5: the test writer adds no entry to, removes no entry from and edits no
    entry of the requirement's test design, and never writes to an AC record (reads only)."""
    paragraph = S.paragraph_with(_section(), "test_spec", "never", "AC record")

    for verb in ("add", "remov", "edit"):
        assert verb in paragraph.lower(), f"the paragraph never says it does not {verb}: {paragraph}"


def test_ac3_without_a_design_the_writer_writes_no_test_and_stops_naming_the_requirement():
    # covers: ACD-2500c-2-i
    # angle: criterion
    """AC-3: a requirement carrying test intent (test_intent) but no test design reaches the test writer:
    it writes no test, derives nothing from the Then clauses, and stops with the reason
    "test design pending" naming the requirement (reported as a blocker)."""
    paragraph = S.paragraph_with(_section(), "test_intent", PENDING)

    assert re.search(r"(no|zero|not write any|writes? nothing)[^.]{0,40}test", paragraph, re.I), paragraph
    assert re.search(r"(never|not|nothing)[^.]{0,60}(deriv|from)[^.]{0,40}Then", paragraph, re.I), paragraph
    assert re.search(r"stop", paragraph, re.I) and re.search(r"(requirement|AC) id|naming", paragraph, re.I), paragraph
    assert "blocker" in paragraph, paragraph


def test_ac3_no_criteria_fallback_survives_beside_the_halt():
    # covers: ACD-2500c-2-i
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the new halt is added but the two existing paths that derive tests from
    the AC's criteria (the 'Code ticket ... Then-clauses' fallback of the Skip rule, and 'use the AC's
    test_spec (preferred) or criteria field' of the AC Store pre-flight) stay unconditional, so a record
    with intent and no design is still silently re-authored from its Then clauses. Each of the two
    paragraphs must carry the carve-out (it names the test design / the halt)."""
    text = _text()
    skip_rule = S.paragraph_with(text, "Then-clauses", "derive", "reachability")
    preflight = S.paragraph_with(text, "authoritative source", "criteria", "test_spec")

    assert "test design" in skip_rule.lower(), f"Skip-rule fallback has no carve-out: {skip_rule[:200]}"
    assert "test design" in preflight.lower(), f"AC Store pre-flight has no carve-out: {preflight[:200]}"


def test_legacy_designs_keep_the_existing_behaviour():
    # covers: ACD-2500c-2-i
    # angle: boundary
    """Boundary (it_requirements 4, ACD-2500b-3): a record whose test_spec carries no authorship mark
    (test_design_authorship) is a legacy design; the test writer's behaviour for it is unchanged."""
    paragraph = S.paragraph_with(_section(), "legacy", "test_design_authorship")

    assert re.search(r"unchanged|as before|existing behaviour|no change", paragraph, re.I), paragraph


def test_ac_each_state_the_real_classifier_distinguishes_has_its_rule_in_the_prompt(tmp_path):
    # covers: ACD-2500c-2-i
    # angle: seam
    """Seam, real consumers to the prompt: three records are built on the REAL ACD-2500c-2-i record and
    written through yaml.safe_dump (a code-aware design, intent with no design, a legacy design). The
    REAL scripts/ac_store/_test_intent.py classifies each; for each state the prompt's section carries
    the vocabulary of the real module: the authorship key for the code-aware design, the halt reason
    constant HOLD_REASON_TEST_DESIGN_PENDING of _impl_readiness_gate.py for the pending one, the word
    legacy for the legacy one. The entry keys the writer reads (name, target_dir) are checked against
    the real schema's test_spec property."""
    sys.path.insert(0, str(S.REPO / "scripts" / "ac_store"))
    import _impl_readiness_gate as gate
    import _test_intent as intent

    intent_entries = [{"clause": "it writes the tests", "needs_test": True, "reason": "behaviour"}]
    spec = [{"name": "test_a", "target_dir": "unit_tests/x/", "proves_clause": "it writes the tests", "code_file": "x.py"}]
    states = {}
    for label, fragment in (
        ("design", {"test_intent": intent_entries, "test_spec": spec, intent.AUTHORSHIP_KEY: {"step": "test-designer", "date": "2026-10-14"}}),
        ("pending", {"test_intent": intent_entries}),
        ("legacy", {"test_spec": [{"name": "test_a", "target_dir": "unit_tests/x/"}]}),
    ):
        (tmp_path / label).mkdir()
        record, _ = S.merged_record(tmp_path / label, AC, fragment)
        record.pop("test_required", None)
        states[label] = (intent.design_pending(record), intent.is_legacy_design(record))
    section = S.flat(_section())
    spec_property = S.schema_property("test_spec")
    array_form = next(v for v in spec_property.get("oneOf", [spec_property]) if v.get("type") == "array")
    properties = array_form["items"]["properties"]

    assert states == {"design": (False, False), "pending": (True, False), "legacy": (False, True)}
    assert gate.HOLD_REASON_TEST_DESIGN_PENDING == PENDING and PENDING in section
    assert intent.AUTHORSHIP_KEY in section and "legacy" in section.lower()
    assert {"name", "target_dir"} <= set(properties)


def test_acd_2500c_2_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500c-2-i
    # angle: reachability
    """Entry point resolved (CLI script with main under scripts/): `python
    scripts/render_effective_prompt.py --agent test-writer --ac ACD-2500c-2-i`, run as a subprocess.
    The prompt the test writer receives at spawn time carries, verbatim, the paragraph that halts on a
    missing design and the paragraph that builds one test per design entry."""
    rendered = set(S.rendered_prompt_paragraphs(AGENT, AC, tmp_path))

    S.assert_rendered(rendered, _section(), "test_intent", PENDING)
    S.assert_rendered(rendered, _section(), "test_spec", "name", "target_dir")


def test_design_lists_every_test_so_the_writer_adds_no_standing_mandate_test():
    # covers: ACD-2500c-2-i
    # angle: criterion
    """User decision 2026-10-14: when a code-aware design exists the test writer writes exactly the tests
    it lists and adds no reachability, bug-fix or real-artifact test of its own."""
    paragraph = S.paragraph_with(_section(), "reachability", "bug-fix", "real-artifact")

    assert re.search(r"(no|not|never)[^.]{0,60}(add|write)", paragraph, re.I), paragraph
    assert re.search(r"exactly", paragraph, re.I) or "exactly" in S.flat(_section()).lower(), paragraph


def test_the_three_standing_mandates_apply_only_to_legacy_designs_and_records_with_no_design():
    # covers: ACD-2500c-2-i
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the new section forbids the extra tests but the Bug-Fix, Real-Artifact
    and Reachability sections stay unconditional, so the template contradicts itself and the writer
    still adds the tests. Each of the three carries the carve-out: it applies only to legacy designs
    and records with no design."""
    text = _text()
    for title in ("Bug-Fix", "Real-Artifact", "Reachability"):
        body = S.flat(S.section_titled(text, title)).lower()
        assert "legacy" in body and re.search(r"(no|without)[^.]{0,30}design", body), f"{title} section has no carve-out"
        assert re.search(r"(only|just)[^.]{0,120}legacy|legacy[^.]{0,120}(only)", body), f"{title}: 'only' missing"
