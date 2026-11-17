"""
MODULE: unit_tests/ac_driven_dev/test_designer_prompt/test_acd_2500d_2.py
COVERS: ACD-2500d-2
GOAL: Red-first specification of ticket 36: the reference-file procedure that ACD-2500d-2 writes into
    templates/agents/test-designer.md. For a package-surface record carrying the marker
    `hold_reason: reference file pending`, the step chooses ONE reference file among the pre-pass
    candidates (exists, same type, same area), opens it, fills it_requirements.reference_file_path
    (field-targeted, no other it_requirements key touched), records its one-sentence reason as a
    `consistent` finding on that file, and clears the marker.
BUSINESS CONTEXT: ADR-072, G4 architect note sections 1, 3 and 5. The planner cannot read source, so it
    cannot honestly name a reference file; it leaves the marker (G5 ticket 43) and this step, which
    can read, names the file. A reference file that was not opened, or that does not qualify, or a
    marker cleared without a file named, would let a package-surface record through unreferenced.
HONEST LIMIT: a prompt change (`test_required: false`). Proven here: the paragraphs that carry each
    rule (paragraph-scoped, whitespace-normalised), the fenced example (parsed; its findings validated
    against the real schema property, which lands with ticket 39), the real pre-pass CLI's output
    vocabulary taught verbatim (SEAM), and the prompt as rendered by the real CLI (REACHABILITY).
RED STATE (right reasons): the prompt has no reference-file procedure yet (only a mention of
    reference_file_path among the output fields), so each test fails on an ASSERTION about the
    current prompt. The schema-property test goes green only once ticket 39 lands.
INTERPRETATION (flagged in the hand-off): with no qualifying candidate the step leaves the marker and
    reports why (architect note: the marker is "cleared when it fills"); candidates exist only for
    records that carry the marker (section 3, conflict 6), and the prompt must say so.
"""

from __future__ import annotations

import re

import jsonschema
import yaml

from unit_tests.ac_driven_dev.test_designer_prompt import _file_findings_prompt_support as S

AC = "ACD-2500d-2"
TEMPLATE_NAME = "test-designer"
MARKER = "reference file pending"
CANDIDATE_KEYS = ("path", "exists", "same_type", "same_area")


def _text() -> str:
    return S.template(TEMPLATE_NAME)


def _reference_example() -> tuple[str, dict, list[dict], list[str]]:
    """(reference path, filled it_requirements, file_findings, opened files) from the prompt's fenced
    YAML. The it_requirements mapping and the findings may sit in one block or in separate ones."""
    filled: dict = {}
    for block in S.YAML_FENCE.findall(_text()):
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict) and isinstance(parsed.get("it_requirements"), dict):
            filled.update(parsed["it_requirements"])
    assert filled.get("reference_file_path"), "the prompt needs a fenced yaml example filling it_requirements.reference_file_path"
    findings, opened = [], []
    for block in S.YAML_FENCE.findall(_text()):
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict) and isinstance(parsed.get("file_findings"), list):
            findings += parsed["file_findings"]
            opened += parsed.get("file_findings_opened_files", [])
    return filled["reference_file_path"], filled, findings, opened


def test_ac1_the_reference_file_is_chosen_among_pre_pass_candidates_that_exist():
    # covers: ACD-2500d-2
    # angle: criterion
    """AC-1: the requirement names a reference file that exists at that moment. The step chooses only
    among the pre-pass report's reference_files candidates whose `exists` is true."""
    paragraph = S.paragraph_with(_text(), "reference_files", "exists", "candidate")

    assert re.search(r"(only|never)[^.]{0,80}(among|from|outside)[^.]{0,60}candidate|candidate[^.]{0,60}only", paragraph, re.I), paragraph
    assert re.search(r"exists[^.]{0,20}true", paragraph, re.I), paragraph


def test_ac2_the_reference_file_has_the_deliverable_s_type_and_lives_in_the_same_area():
    # covers: ACD-2500d-2
    # angle: criterion
    """AC-2: the reference file is of the same file type as the deliverable and lives in the same area.
    The pre-pass report decides both (same_type, same_area): the step takes only candidates where each
    is true and never re-derives either."""
    paragraph = S.paragraph_with(_text(), "same_type", "same_area")

    assert len(re.findall(r"true", paragraph, re.I)) >= 2 or re.search(r"(both|all)[^.]{0,40}true", paragraph, re.I), paragraph
    assert re.search(r"(never|not|rather than)[^.]{0,40}re-?deriv|(never|not)[^.]{0,40}(judge|decide)", paragraph, re.I), paragraph


def test_ac1_the_step_opens_the_file_it_names_and_lists_it_as_opened():
    # covers: ACD-2500d-2
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the reference file is picked from the candidate list by its name and
    never read, so 'a step that opened it' (the AC title) is false. The prompt says to open the chosen
    file before naming it and to list it in file_findings_opened_files."""
    paragraph = S.paragraph_with(_text(), "reference_file_path", "opened")

    assert re.search(r"open[^.]{0,60}(before|first)|(before|first)[^.]{0,60}open", paragraph, re.I), paragraph
    assert "file_findings_opened_files" in paragraph, paragraph


def test_ac3_one_sentence_reason_is_stored_as_a_consistent_finding_on_the_reference_file():
    # covers: ACD-2500d-2
    # angle: criterion
    """AC-3 and architect note section 3: the step states in one sentence why it chose that file; the
    sentence is the `reason` of a `consistent` finding whose `file` is the reference file (so the
    approval hold, which ignores consistent findings, is not blocked by it)."""
    paragraph = S.paragraph_with(_text(), "reference", "one sentence", "consistent", "reason")

    assert re.search(r"finding", paragraph, re.I) and "file_findings" in paragraph, paragraph


def test_ac3_example_records_the_reference_choice_as_a_grounded_consistent_finding():
    # covers: ACD-2500d-2
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the reference path is written into it_requirements but there is no
    finding with the reason (or the finding names another file, or the file was never opened). In the
    prompt's example the chosen path has exactly one finding, verdict `consistent`, a one-sentence
    reason, decision null, and is in file_findings_opened_files."""
    path, _, findings, opened = _reference_example()
    about = [f for f in findings if f["file"] == path]

    assert len(about) == 1, f"expected exactly one finding on {path}, got {len(about)}"
    assert about[0]["verdict"] == "consistent" and about[0].get("decision") is None, about[0]
    assert about[0]["reason"].strip() and about[0]["reason"].count(". ") == 0, about[0]
    assert path in opened, f"{path} is chosen but never listed as opened"


def test_ac_example_findings_are_valid_under_the_real_schema_property():
    # covers: ACD-2500d-2
    # angle: real_artifact
    """Lockstep with ticket 39 (goes green only once 39 lands the file_findings property): the
    reference-file example's findings and opened files validate against the REAL
    config/ac_store_schema.json properties, and the filled it_requirements has only the one key the
    step may write (reference_file_path) beyond what the planner wrote."""
    path, filled, findings, opened = _reference_example()

    jsonschema.validate(findings, S.schema_property("file_findings"))
    jsonschema.validate(opened, S.schema_property("file_findings_opened_files"))
    assert set(filled) <= {"reference_file_path"}, f"the step may fill only reference_file_path, example shows {sorted(filled)}"


def test_ac4_only_reference_file_path_is_written_by_a_field_targeted_edit():
    # covers: ACD-2500d-2
    # angle: criterion
    """AC-4 and it_requirements 1: the reference file goes into the reference_file_path key of the
    structured it_requirements object only, by a field-targeted Edit; the planner's other four keys
    stay as written (the planner's output names no reference file; ACD-2500e-2 owns that side)."""
    paragraph = S.paragraph_with(_text(), "reference_file_path", "it_requirements", "field-targeted")

    assert re.search(r"other (four )?keys|four other|remaining", paragraph, re.I), paragraph
    assert re.search(r"as written|unchanged|untouched|byte-identical", paragraph, re.I), paragraph


def test_the_pending_marker_is_cleared_only_after_the_reference_file_is_filled():
    # covers: ACD-2500d-2
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the marker `hold_reason: reference file pending` is cleared
    unconditionally, so a package-surface record with no reference file is released. The prompt clears
    it only after it_requirements.reference_file_path is filled (architect note section 5)."""
    paragraph = S.paragraph_with(_text(), "hold_reason", MARKER)

    assert re.search(r"(clear|remove)", paragraph, re.I), paragraph
    assert re.search(
        r"(clear|remove)[^.]{0,100}(only|after|once|when)|(only|after|once|when)[^.]{0,100}(clear|remove)", paragraph, re.I
    ), paragraph
    assert "reference_file_path" in paragraph, paragraph


def test_with_no_qualifying_candidate_the_marker_stays_and_the_reason_is_reported():
    # covers: ACD-2500d-2
    # angle: boundary
    """Boundary (zero qualifying candidates): the step fills nothing, leaves the marker in place so the
    record stays held (`reference file pending`), and reports why in the dispatch reason; it never
    names a file from outside the candidate list to make the hold go away."""
    paragraph = S.paragraph_with(_text(), MARKER, "no candidate")

    assert re.search(r"(leave|keep|stays|remain)[^.]{0,60}(marker|hold_reason|pending)", paragraph, re.I), paragraph
    assert re.search(r"report|reason|anomal", paragraph, re.I), paragraph


def test_the_pre_pass_candidate_vocabulary_from_the_real_producer_is_taught(tmp_path):
    # covers: ACD-2500d-2
    # angle: seam
    """Seam, producer to consumer: the REAL pre-pass CLI is run over a tmp store and repo (record written
    by yaml.safe_dump) for a package-surface record that carries the marker. Every key its
    reference_files entries actually carry is named in the paragraph that teaches the choice. Control
    row: the same record WITHOUT the marker gets no candidates from the real producer, and the prompt
    says candidates come only for records carrying the marker."""
    declared = [{"path": "scripts/a/new_tool.py", "state": "to_be_created"}]
    create = ["scripts/a/sibling.py", "scripts/a/other.py"]
    with_marker = S.prepass_report(
        tmp_path / "m", declared, {"package_surface": True, "hold_reason": MARKER, "_create": create}
    )
    without = S.prepass_report(tmp_path / "n", declared, {"package_surface": True, "_create": create})
    paragraph = S.paragraph_with(_text(), "reference_files", "same_type")

    assert with_marker["reference_files"], "the real pre-pass produced no candidates for the marked record"
    assert set(with_marker["reference_files"][0]) == set(CANDIDATE_KEYS)
    assert [key for key in CANDIDATE_KEYS if key != "path" and key not in paragraph] == [], paragraph
    assert without["reference_files"] == []
    assert re.search(r"(only|just)[^.]{0,60}(marker|pending)|(marker|pending)[^.]{0,60}only", S.flat(_text()), re.I)


def test_acd_2500d_2_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500d-2
    # angle: reachability
    """Entry point resolved (CLI script with main under scripts/): `python
    scripts/render_effective_prompt.py --agent test-designer --ac ACD-2500d-2`, run as a subprocess.
    The prompt the designer receives at spawn time carries, verbatim, the paragraphs that teach the
    choice among candidates and the clearing of the marker."""
    rendered = set(S.rendered_prompt_paragraphs(TEMPLATE_NAME, AC, tmp_path))

    for needles in (("reference_files", "same_type", "same_area"), ("hold_reason", MARKER, "reference_file_path")):
        S.assert_rendered(rendered, _text(), *needles)
