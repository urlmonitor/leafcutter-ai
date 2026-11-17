"""
MODULE: unit_tests/ac_driven_dev/test_designer_prompt/test_acd_2500d_1_i.py
COVERS: ACD-2500d-1-i
GOAL: Red-first specification of ticket 40: the `behaviour found elsewhere` case that ACD-2500d-1-i adds
    to the File Findings Procedure of templates/agents/test-designer.md. When none of the declared
    files holds the behaviour and it is found in another file, the step reports a surface mismatch:
    each declared file that does not hold it gets the verdict `behaviour found elsewhere` with
    `found_in` naming the file where it was found; the declared files are not changed or extended; the
    requirement is not offered for approval until the mismatch is resolved.
BUSINESS CONTEXT: ADR-072, G4 architect note sections 1, 3 and 5. Quietly adding the third file to the
    requirement's declared files would hide a planner mistake and defeat the approval hold; the finding
    must stay with `decision: null` so the deterministic hold (ticket 39) holds the record.
HONEST LIMIT: a prompt change (`test_required: false`); the hold itself is enforced deterministically
    by ticket 39 (_file_findings.undecided_findings, _approval_holds), not by prose. Proven here: the
    paragraphs carrying each rule, the fenced example (parsed, validated against the real schema
    property that lands with ticket 39), the example merged into a record written by yaml.safe_dump and
    read by the REAL hold oracle (SEAM), and the rendered prompt (REACHABILITY).
RED STATE (right reasons): the prompt has no `behaviour found elsewhere` text, so each prose test fails
    on an ASSERTION about the current prompt. The schema and hold-oracle tests go green only once
    ticket 39 lands; they fail first on the missing example.
INTERPRETATION (flagged in the hand-off): the AC's "reports a surface mismatch naming the 2 declared
    files and the third file" is read as one finding per declared file that does not hold the
    behaviour, each with `found_in` naming the third file (the contract has no mismatch record of its
    own); the example must show at least two such findings sharing one found_in.
"""

from __future__ import annotations

import re
import sys

import jsonschema

from unit_tests.ac_driven_dev.test_designer_prompt import _file_findings_prompt_support as S

AC = "ACD-2500d-1-i"
TEMPLATE_NAME = "test-designer"
OPENED = "file_findings_opened_files"
ELSEWHERE = "behaviour found elsewhere"


def _text() -> str:
    return S.template(TEMPLATE_NAME)


def _example() -> dict:
    example = S.example_with(_text(), "file_findings")
    assert OPENED in example, f"the file-findings example must also show {OPENED}"
    return example


def _elsewhere(example: dict) -> list[dict]:
    found = [f for f in example["file_findings"] if f["verdict"] == ELSEWHERE]
    assert len(found) >= 2, f"the example must show a surface mismatch: at least 2 declared files with {ELSEWHERE!r}"
    return found


def test_ac1_a_surface_mismatch_names_each_declared_file_and_the_file_where_it_was_found():
    # covers: ACD-2500d-1-i
    # angle: criterion
    """AC-1: when no declared file holds the behaviour and it is found in a third file, the step reports
    a surface mismatch: each declared file that does not hold the behaviour gets the verdict
    `behaviour found elsewhere`, and `found_in` names the third file."""
    paragraph = S.paragraph_with(_text(), ELSEWHERE, "found_in")

    assert re.search(r"(each|every)[^.]{0,60}declared file", paragraph, re.I), paragraph
    assert re.search(r"(third|other|another|different)[^.]{0,40}file|outside[^.]{0,40}declared", paragraph, re.I), paragraph
    assert re.search(r"mismatch", S.flat(_text()), re.I)


def test_ac1_example_shows_two_declared_files_pointing_at_one_third_file_it_opened():
    # covers: ACD-2500d-1-i
    # angle: boundary
    """Boundary (the AC's count: 2 declared files, 1 third file): the prompt's example shows at least two
    `behaviour found elsewhere` findings, each with a non-null `found_in`, all naming the same third
    file; the third file is in file_findings_opened_files (it was read to be found) and is not itself a
    finding's `file`. Control row: a finding with another verdict has found_in null."""
    example = _example()
    elsewhere = _elsewhere(example)
    third = {f["found_in"] for f in elsewhere}

    assert len(third) == 1 and None not in third, third
    (path,) = third
    assert path in example[OPENED], f"{path} is named in found_in but never listed as opened"
    assert path not in {f["file"] for f in example["file_findings"]}, "the third file must not become a finding of its own"
    others = [f for f in example["file_findings"] if f["verdict"] != ELSEWHERE]
    assert others and all(f.get("found_in") is None for f in others), "control rows: found_in only on the elsewhere verdict"


def test_ac_example_is_valid_under_the_real_schema_properties():
    # covers: ACD-2500d-1-i
    # angle: real_artifact
    """Lockstep with ticket 39 (goes green only once 39 lands the file_findings properties): the fenced
    example parses and validates against the REAL config/ac_store_schema.json properties, with
    decision null on every finding and a one-sentence reason."""
    example = _example()

    jsonschema.validate(example["file_findings"], S.schema_property("file_findings"))
    jsonschema.validate(example[OPENED], S.schema_property(OPENED))
    assert all(f.get("decision") is None and f["reason"].strip() for f in example["file_findings"])


def test_ac2_the_declared_files_are_reported_on_never_changed_or_extended():
    # covers: ACD-2500d-1-i
    # angle: discrimination
    """WRONG VERSION THIS CATCHES (the quiet add): the step finds the behaviour in a third file and
    appends that file to the requirement's declared_files, so the mismatch disappears. The prompt says
    to report it and never add the found file to, remove a file from or edit declared_files, and the
    third file never appears in the example as a declared-style finding of its own."""
    paragraph = S.paragraph_with(_text(), ELSEWHERE, "declared_files")

    assert re.search(r"(never|not|do not)[^.]{0,60}(add|append|extend)[^.]{0,80}declared_files", paragraph, re.I), paragraph
    assert re.search(r"report", paragraph, re.I) and re.search(r"(unchanged|byte-identical|never[^.]{0,30}(edit|change|remove))", paragraph, re.I)


def test_ac3_a_mismatch_finding_keeps_decision_null_so_the_approval_hold_applies():
    # covers: ACD-2500d-1-i
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the step fills `decision` itself on the mismatch findings (to make the
    mismatch look resolved), so the deterministic hold (ticket 39) never holds the requirement. The
    prompt says the decision stays null for the technical planner, and in its own example every
    `behaviour found elsewhere` finding has decision null (the hold is the workflow's, not this step's)."""
    paragraph = S.paragraph_with(_text(), "decision", "null", "planner")

    assert re.search(r"(never|not|do not)[^.]{0,60}(record|write|fill|set)[^.]{0,40}decision|only[^.]{0,60}planner", paragraph, re.I), paragraph
    assert all(f.get("decision") is None for f in _elsewhere(_example())), "a mismatch finding must keep decision null"


def test_the_third_file_is_found_from_candidate_paths_or_delegated_research_never_a_search():
    # covers: ACD-2500d-1-i
    # angle: criterion
    """it_requirements (ADR-033 section 2.6): no Grep, Glob or shell search. The file where the behaviour
    lives is located from candidate paths in the pre-pass report or from research the depth-0 workflow
    delegates, and `found_in` names only a file the step opened."""
    paragraph = S.paragraph_with(_text(), "found_in", "opened", "candidate")

    assert re.search(r"(never|not|no)[^.]{0,40}(search|grep|glob|find)", paragraph, re.I), paragraph
    assert re.search(r"pre-pass|workflow|research", paragraph, re.I), paragraph


def test_ac_mismatch_example_merged_into_a_real_record_is_held_by_the_real_oracle(tmp_path):
    # covers: ACD-2500d-1-i
    # angle: seam
    """Seam, producer to the hold's consumer (goes green only once 39 lands): the prompt's example is
    merged into the REAL ACD-2500d-1-i record (yaml.safe_dump to a tmp file, read back). The merged
    record validates as a whole, the REAL scripts/ac_store/_file_findings.undecided_findings reports
    every mismatch finding, and the REAL scripts/ac_store/_approval_holds.approval_hold_reason holds
    the record with `file finding undecided`: the requirement is not offered for approval."""
    example = _example()
    elsewhere = _elsewhere(example)
    loaded, real = S.merged_record(tmp_path, AC, {key: example[key] for key in ("file_findings", OPENED)})
    jsonschema.validate(loaded, S.schema())
    sys.path.insert(0, str(S.REPO / "scripts" / "ac_store"))
    import _approval_holds
    import _file_findings

    undecided = _file_findings.undecided_findings(loaded)
    names = {item["file"] if isinstance(item, dict) else str(item) for item in undecided}

    assert {f["file"] for f in elsewhere} <= names
    assert _approval_holds.approval_hold_reason(loaded) == "file finding undecided"
    assert loaded["covered_by"] == real["covered_by"] and loaded["criteria"] == real["criteria"]


def test_acd_2500d_1_i_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500d-1-i
    # angle: reachability
    """Entry point resolved (CLI script with main under scripts/): `python
    scripts/render_effective_prompt.py --agent test-designer --ac ACD-2500d-1-i`, run as a subprocess.
    The prompt the designer receives at spawn time carries, verbatim, the paragraphs that teach the
    `behaviour found elsewhere` verdict and the never-add-to-declared_files rule."""
    rendered = set(S.rendered_prompt_paragraphs(TEMPLATE_NAME, AC, tmp_path))

    for needles in ((ELSEWHERE, "found_in"), (ELSEWHERE, "declared_files"), (ELSEWHERE, "decision")):
        S.assert_rendered(rendered, _text(), *needles)


def test_the_third_file_is_reached_by_following_a_reference_in_an_opened_file_not_by_search():
    # covers: ACD-2500d-1-i
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the step finds the third file by a repository search (or guesses a
    path). The prompt says it is reached by following a reference (an import, a call or a path) that
    appears in a file the step has already opened, and that search stays banned."""
    paragraph = S.paragraph_with(_text(), "third file", "import")

    assert re.search(r"(follow|following)[^.]{0,80}(import|call|path|reference)", paragraph, re.I), paragraph
    assert re.search(r"(already|previously)?[^.]{0,40}opened", paragraph, re.I) and re.search(r"already", paragraph, re.I), paragraph
    assert re.search(r"never[^.]{0,80}search", paragraph, re.I), paragraph
