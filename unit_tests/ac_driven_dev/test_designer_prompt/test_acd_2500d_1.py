"""
MODULE: unit_tests/ac_driven_dev/test_designer_prompt/test_acd_2500d_1.py
COVERS: ACD-2500d-1
GOAL: Red-first specification of ticket 35: the File Findings Procedure that ACD-2500d-1 writes into
    templates/agents/test-designer.md. The prompt tells the file-aware step to open each declared
    file, give it a verdict (`consistent`, `describes, does not implement` with the line range read,
    `absent, not to-be-created` naming the path), and list every file it opened.
BUSINESS CONTEXT: ADR-072. The planner cannot read source, so this step is the one place that
    confirms a declared file really holds the behaviour. A verdict on a file it never opened is the
    failure to prevent (an ungrounded finding), as is flagging a to-be-created file as absent.
HONEST LIMIT: a prompt change (`test_required: false`); what a prompt does happens in a model run.
    Proven here, in order of preference: STRUCTURE (the fenced example PARSES and validates against
    the real config/ac_store_schema.json file_findings properties); SEAM (the example merged into a
    record written by yaml.safe_dump is read by the real hold consumer; the real pre-pass output
    vocabulary is taught verbatim); REACHABILITY (the prompt as rendered by the real CLI); PRESENCE of
    each rule, paragraph-scoped and whitespace-normalised. Presence cannot prove the model obeys;
    ticket 39's rule family and the approval hold are the enforcement.
RED STATE (right reasons): the File Findings Procedure is still the ticket 27 skeleton ("procedure
    not yet written"), so every prose test fails on an ASSERTION about the current prompt. The two
    tests that need the schema property or scripts/ac_store/_file_findings.py go green only once
    ticket 39 lands (built in parallel); they are written now and fail first on the missing example.
INTERPRETATION (flagged in the hand-off): the verdict strings and the record shape come from the AC's
    delivers_to contract (the schema property is ticket 39's); `undecided_findings` is assumed to
    return the undecided findings (dicts, or their file names) and to ignore `consistent` ones
    (architect note section 3, conflict 8).
"""

from __future__ import annotations

import re
import sys

import jsonschema

from unit_tests.ac_driven_dev.test_designer_prompt import _file_findings_prompt_support as S

AC = "ACD-2500d-1"
TEMPLATE_NAME = "test-designer"
OPENED = "file_findings_opened_files"


def _text() -> str:
    return S.template(TEMPLATE_NAME)


def _example() -> dict:
    example = S.example_with(_text(), "file_findings")
    assert OPENED in example, f"the file-findings example must also show {OPENED}"
    return example


def test_ac1_skeleton_is_replaced_by_the_procedure():
    # covers: ACD-2500d-1
    # angle: criterion
    """Ticket 35: the File Findings Procedure is no longer the ticket 27 stub. The text that says the
    dispatch reports file_findings none because the procedure is 'not yet written' is gone, and the
    prompt teaches the first three verdict values."""
    text = S.flat(_text())

    assert "procedure not yet written" not in text and "Skeleton only" not in text
    for verdict in S.VERDICTS[:3]:
        assert verdict in text, f"verdict {verdict!r} is not taught"


def test_ac2_consistent_when_the_declared_file_holds_the_behaviour():
    # covers: ACD-2500d-1
    # angle: criterion
    """AC-2: a declared file that holds (defines, implements) the behaviour the requirement's criteria
    change gets the verdict `consistent`. The step judges only that: existence comes from the pre-pass."""
    paragraph = S.paragraph_with(_text(), "consistent", "criteria")

    assert re.search(r"(holds|implements|defines|contains)[^.]{0,80}behaviour", paragraph, re.I), paragraph
    assert re.search(r"(only|just)[^.]{0,60}(whether|judge)", S.flat(_text()), re.I)


def test_ac3_describes_does_not_implement_names_the_file_and_the_line_range_read():
    # covers: ACD-2500d-1
    # angle: criterion
    """AC-3: a declared file that only describes the behaviour (a reference document) gets the verdict
    `describes, does not implement`; the finding names the file and sets line_range to the lines the
    step read."""
    paragraph = S.paragraph_with(_text(), "describes, does not implement", "line_range")
    prose = S.flat(re.sub(r"```.*?```", " ", _text(), flags=re.DOTALL))

    assert re.search(r"describ", paragraph, re.I) and "file" in paragraph
    assert re.search(r"describes, does not implement.{0,300}?line_range[^.]{0,60}(read|opened)", prose, re.I), (
        "the describes verdict must say line_range is the lines read"
    )


def test_ac4_absent_file_is_reported_from_the_pre_pass_state_naming_its_path():
    # covers: ACD-2500d-1
    # angle: criterion
    """AC-4: a declared file that is absent from the repository and not marked to-be-created gets the
    verdict `absent, not to-be-created`, naming its path in `file`. The step reads that fact from the
    pre-pass report (state `neither`) and does not probe the tree or open the file."""
    paragraph = S.paragraph_with(_text(), "absent, not to-be-created", "neither")

    prose = paragraph.replace("absent, not to-be-created", "")  # the verdict's own name contains 'not to-be-created'

    assert "pre-pass" in paragraph and re.search(r"path|file", paragraph), paragraph
    assert re.search(r"(never|not|do not)[^.]{0,60}(open|probe|search|check)", prose, re.I), prose


def test_a_to_be_created_file_is_never_reported_absent():
    # covers: ACD-2500d-1
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: every declared path that is not on disk is flagged `absent`, so a file
    the requirement marks to-be-created is reported as a defect. The prompt carves out state
    to_be_created: it gets no absent verdict (AC-4 says 'and not marked to-be-created')."""
    paragraph = S.paragraph_with(_text(), "to_be_created", "absent")
    prose = paragraph.replace("absent, not to-be-created", "")  # the verdict's own name contains 'not to-be-created'
    clauses = re.split(r"(?<=[.])\s+|\s+-\s+", prose)
    about = [c for c in clauses if re.search(r"to_be_created|to-be-created", c) and "absent" in c.lower()]

    assert about, "no sentence relates a to_be_created file to the absent verdict"
    assert all(re.search(r"\b(never|not|no|without)\b", c, re.I) for c in about), about


def test_ac5_every_opened_file_is_listed_and_no_verdict_is_given_on_an_unopened_file():
    # covers: ACD-2500d-1
    # angle: criterion
    """AC-5: the report names every file the step opened (file_findings_opened_files, repo-root-relative
    POSIX paths), and no verdict is given on a file that was not opened, except `absent` which the
    pre-pass state supports without opening."""
    paragraph = S.paragraph_with(_text(), OPENED, "opened")

    assert re.search(r"repo(sitory)?-root-relative", paragraph, re.I) and "POSIX" in paragraph, paragraph
    assert re.search(r"(every|each|all)[^.]{0,40}(file|path)[^.]{0,40}opened|opened[^.]{0,40}(every|each|all)", paragraph, re.I)
    assert re.search(
        r"(no|never)[^.]{0,40}verdict[^.]{0,60}(not opened|did not open|unopened|without open)", S.flat(_text()), re.I
    )


def test_ac5_example_gives_a_verdict_only_on_files_it_lists_as_opened():
    # covers: ACD-2500d-1
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: a finding written for a file that was never opened (an ungrounded
    verdict, judged from the file name). In the prompt's own example every `consistent` and
    `describes, does not implement` file is in file_findings_opened_files with a line_range, the
    `absent` file is NOT in the opened list (it cannot have been opened) and has line_range null, and
    all three verdicts are shown (control rows beside the negative one)."""
    example = _example()
    opened, findings = example[OPENED], example["file_findings"]
    by = {verdict: [f for f in findings if f["verdict"] == verdict] for verdict in S.VERDICTS[:3]}

    assert all(by.values()), f"the example must show consistent, describes and absent: {[v for v in by if not by[v]]}"
    for finding in by["consistent"] + by["describes, does not implement"]:
        assert finding["file"] in opened, f"verdict on a file never opened: {finding['file']}"
    for finding in by["describes, does not implement"]:
        assert re.fullmatch(r"\d+-\d+", str(finding["line_range"])), finding
    for finding in by["absent, not to-be-created"]:
        assert finding["file"] not in opened and finding.get("line_range") is None, finding
    assert all(not re.match(r"^([A-Za-z]:|/)", path) and "\\" not in path for path in opened), opened


def test_ac_example_is_valid_under_the_real_schema_properties():
    # covers: ACD-2500d-1
    # angle: real_artifact
    """Lockstep with ticket 39 (goes green only once 39 lands the file_findings schema properties): the
    fenced example parses and each of its fields validates against the matching property of the REAL
    config/ac_store_schema.json; every finding has a one-sentence reason and decision null (absent or
    null, never filled by this step)."""
    example = _example()

    jsonschema.validate(example["file_findings"], S.schema_property("file_findings"))
    jsonschema.validate(example[OPENED], S.schema_property(OPENED))
    for finding in example["file_findings"]:
        assert finding["reason"].strip() and finding["reason"].count(". ") == 0, finding
        assert finding.get("decision") is None, finding


def test_ac_pre_pass_state_vocabulary_from_the_real_producer_is_taught(tmp_path):
    # covers: ACD-2500d-1
    # angle: seam
    """Seam, producer to consumer: the REAL pre-pass CLI (scripts/ac_store/design_prepass.py) is run over
    a tmp store and repo (record written by yaml.safe_dump) with an existing, a missing and a
    to-be-created declared file. Every `state` value it actually emits is named in the prompt's
    findings paragraph, and `exists` is tied to opening the file."""
    report = S.prepass_report(
        tmp_path,
        [{"path": "scripts/a/real.py", "state": "existing"}, {"path": "missing/x.py", "state": "existing"},
         {"path": "scripts/a/new.py", "state": "to_be_created"}],
        {"_create": ["scripts/a/real.py"]},
    )
    states = {entry["state"] for entry in report["declared_files"]}
    paragraph = S.paragraph_with(_text(), "pre-pass", "state")

    assert states == {"exists", "neither", "to_be_created"}
    assert "absent, not to-be-created" in S.flat(_text()), "the neither state must lead to the absent verdict"
    assert [state for state in states if state not in paragraph] == [], paragraph
    assert re.search(r"exists[^.]{0,80}(open|read)", paragraph, re.I), paragraph


def test_ac_example_merged_into_a_real_record_reads_as_undecided_findings(tmp_path):
    # covers: ACD-2500d-1
    # angle: seam
    """Seam, producer to the hold's consumer (goes green only once 39 lands): the prompt's example is
    merged into the REAL ACD-2500d-1 record (yaml.safe_dump to a tmp file, read back). The merged
    record validates as a whole against the real schema and the REAL scripts/ac_store/_file_findings.py
    reports exactly the non-`consistent` findings as undecided (the consistent one needs no decision),
    while the record's protected fields are unchanged by the merge."""
    example = _example()
    loaded, real = S.merged_record(tmp_path, AC, {key: example[key] for key in ("file_findings", OPENED)})
    jsonschema.validate(loaded, S.schema())
    sys.path.insert(0, str(S.REPO / "scripts" / "ac_store"))
    import _file_findings

    undecided = _file_findings.undecided_findings(loaded)
    names = {item["file"] if isinstance(item, dict) else str(item) for item in undecided}
    expected = {f["file"] for f in example["file_findings"] if f["verdict"] != "consistent"}

    assert len(undecided) == len(expected) >= 2 and names == expected
    assert all(loaded[field] == real[field] for field in ("criteria", "assigned_agent", "delivers_to", "expects_from"))


def test_ac_findings_are_written_by_field_targeted_edits_and_group_one_is_left_alone():
    # covers: ACD-2500d-1
    # angle: criterion
    """it_requirements 2 and ACD-2500d-5 clause 4: the findings are separate from the test design.
    The File Findings Procedure writes file_findings and file_findings_opened_files by field-targeted
    Edit (never a whole-record Write) and leaves test_spec, test_design_authorship and
    test_design_opened_files untouched."""
    paragraph = S.paragraph_with(_text(), "file_findings", "Edit", "untouched")

    assert re.search(r"field-targeted", paragraph, re.I) and re.search(r"test_spec|test design", paragraph, re.I), paragraph
    assert re.search(r"never[^.]{0,30}Write[^.]{0,40}record", paragraph, re.I), paragraph


def test_ac_findings_never_edit_declared_files_criteria_or_contracts():
    # covers: ACD-2500d-1
    # angle: criterion
    """it_requirements 6: the step never edits the declared files, the criteria, the contracts
    (delivers_to, expects_from) or any it_requirements key except reference_file_path (ticket 36),
    which it fills field-targeted."""
    paragraph = S.paragraph_with(
        _text(), "declared_files", "criteria", "delivers_to", "expects_from", "reference_file_path", "never"
    )

    assert re.search(r"it_requirements", paragraph) and re.search(r"except|other than|only", paragraph, re.I), paragraph


def test_ac_existence_facts_come_from_the_pre_pass_report_and_the_step_judges_content_only():
    # covers: ACD-2500d-1
    # angle: criterion
    """it_requirements 3 and 4: existence and to-be-created facts come from the pre-pass report, never
    re-derived; the step judges only whether the file holds the behaviour; a file it opened is listed."""
    paragraph = S.paragraph_with(_text(), "findings", "pre-pass")

    assert re.search(r"(never|not|rather than)[^.]{0,40}re-?deriv", paragraph, re.I), paragraph
    assert re.search(r"(only|just)[^.]{0,60}(whether|judge)|judge[^.]{0,40}only", paragraph, re.I), paragraph


def test_acd_2500d_1_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500d-1
    # angle: reachability
    """Entry point resolved (CLI script with main under scripts/): `python
    scripts/render_effective_prompt.py --agent test-designer --ac ACD-2500d-1`, run as a subprocess.
    The prompt the designer receives at spawn time carries, verbatim, the paragraphs that teach the
    describes verdict, the absent verdict and the opened-files rule (nothing rewrites or drops them)."""
    rendered = set(S.rendered_prompt_paragraphs(TEMPLATE_NAME, AC, tmp_path))

    for needles in (
        ("describes, does not implement", "line_range"), ("absent, not to-be-created", "neither"), (OPENED, "opened"),
    ):
        S.assert_rendered(rendered, _text(), *needles)
