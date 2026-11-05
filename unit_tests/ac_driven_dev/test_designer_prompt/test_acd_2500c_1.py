"""
MODULE: unit_tests/ac_driven_dev/test_designer_prompt/test_acd_2500c_1.py
COVERS: ACD-2500c-1
GOAL: Red-first specification of ticket 29: the test-design procedure that ACD-2500c-1 writes into
    templates/agents/test-designer.md (the agent ticket 27 creates). The prompt tells the
    code-aware step to open the files, write one `test_spec` entry per needs-test clause carrying
    the ACD-2500c-3 keys (proves_clause, code_file, to_be_created, convention_test_file), set the
    authorship mark and the opened-files list, use must_catch and angle `discrimination` for
    bug-fix and gate records, and never touch a field it does not own.
BUSINESS CONTEXT: The planner cannot read code (ADR-009), so the design is written here, grounded
    in files this step opened (ADR-071/-072). The prompt IS the deliverable: ACD-2500c-1-i (ticket
    30) is the deterministic check of what the model produced.
HONEST LIMIT: ACD-2500c-1 is a prompt change, `test_required: false` on its record, and no coder
    agent is needed. What a prompt "does" happens in a model run that a unit test cannot reproduce.
    These tests prove only what is mechanically decidable, in this order of preference:
      1. STRUCTURE: the test-design section exists and its fenced YAML example is PARSED and
         validated against the REAL config/ac_store_schema.json; the example is internally
         grounded (every file it names is in its own opened-files list);
      2. SEAM: the example, merged into a record written through yaml.safe_dump from the real
         ACD-2500c-1 record, is schema-valid and read as a code-aware (not legacy) design by the
         real consumer scripts/ac_store/_test_intent.py;
      3. REACHABILITY: the prompt as the agent receives it (scripts/render_effective_prompt.py on
         a tmp copy) carries the same section;
      4. PRESENCE of the specific rules (architect note G4 section 1), paragraph-scoped and
         whitespace-normalised, never a whole-file grep.
    Presence checks cannot prove the model obeys; the grounding rule check (ticket 30) is the
    enforcement. No test asserts on the file-findings procedures (tickets 35, 36, 38, 40) or on the
    file-findings constants of ticket 39 (_file_findings.py does not exist yet): only this ticket's
    own section is pinned.
INTERPRETATION (flagged in the hand-off): the section is found by a heading whose title contains
    "test design" and whose body names test_spec, level 2 to 4, up to the next heading of the same
    or a higher level. The skeleton's exact heading text is ticket 27's, so only that much is pinned.
RED STATE: templates/agents/test-designer.md does not exist, so every test fails on an explicit
    existence assertion (an absence red); once ticket 27 lands, each fails on an assertion about the
    missing test-design procedure.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

REPO = Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "templates" / "agents" / "test-designer.md"
SCHEMA_FILE = REPO / "config" / "ac_store_schema.json"
RENDER_CLI = REPO / "scripts" / "render_effective_prompt.py"
AC_FILE = (
    REPO / "docs" / "acceptance-criteria" / "ac-driven-dev"
    / "ACD-2500-right-job-right-agent" / "ACD-2500c-1.yaml"
)
YAML_FENCE = re.compile(r"```ya?ml\n(.*?)```", re.DOTALL)
HEADING = re.compile(r"^(#{2,4}) (.*)$", re.MULTILINE)
G3_ENTRY_KEYS = ("proves_clause", "code_file", "to_be_created", "convention_test_file")
PROTECTED = (
    "criteria", "test_intent", "assigned_agent", "implements_pattern", "pattern_bindings",
    "declared_files", "covered_by", "delivers_to", "expects_from", "it_requirements",
)


def _flat(text: str) -> str:
    """Prose view: emphasis dropped, whitespace collapsed (a wrapped line is one line)."""
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def _template(path: Path | None = None) -> str:
    path = TEMPLATE if path is None else path
    assert path.is_file(), f"{path.relative_to(REPO).as_posix()} does not exist yet (ticket 27 creates it)"
    return path.read_text(encoding="utf-8")


def _design_section(text: str | None = None) -> str:
    """The test-design section: a heading titled 'test design' whose body names test_spec."""
    text = _template() if text is None else text
    headings = list(HEADING.finditer(text))
    for index, heading in enumerate(headings):
        if "test design" not in heading.group(2).lower():
            continue
        end = next(
            (nxt.start() for nxt in headings[index + 1:] if len(nxt.group(1)) <= len(heading.group(1))),
            len(text),
        )
        section = text[heading.start():end]
        if "test_spec" in section:
            return section
    pytest.fail("no heading titled 'test design' with a body naming test_spec (ACD-2500c-1 procedure)")


def _paragraphs(text: str) -> list[str]:
    return [_flat(block) for block in re.split(r"\n\s*\n", text) if block.strip()]


def _paragraph_with(text: str, *needles: str) -> str:
    """The flattened paragraph containing every needle (case-insensitive)."""
    for paragraph in _paragraphs(text):
        if all(needle.lower() in paragraph.lower() for needle in needles):
            return paragraph
    pytest.fail(f"no paragraph of the test-design section mentions all of {needles!r}")


def _example(section: str) -> dict:
    """Every fenced YAML mapping of the section merged into one record fragment, parsed."""
    merged: dict = {}
    for block in YAML_FENCE.findall(section):
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict):
            merged.update(parsed)
    assert isinstance(merged.get("test_spec"), list), "the section needs a fenced yaml example with a test_spec list"
    return merged


def _schema() -> dict:
    return json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# AC-1 .. AC-3: which clauses get entries
# --------------------------------------------------------------------------
def test_ac1_one_entry_per_needs_test_clause_naming_the_clause_it_proves():
    # covers: ACD-2500c-1, ACD-2500c
    # angle: criterion
    """AC-1 and AC-2: the record carries at least one test_spec entry per needs_test: true clause,
    and each entry names the outcome clause it proves in `proves_clause`, copied verbatim from
    test_intent.clause (not reworded, so it matches under normalise_clause)."""
    section = _flat(_design_section())

    assert re.search(r"at least one[^.]{0,60}(entry|test_spec)[^.]{0,80}needs_test: true", section, re.I), section
    paragraph = _paragraph_with(_design_section(), "proves_clause", "verbatim")
    assert "test_intent" in paragraph and "clause" in paragraph, paragraph
    assert re.search(r"(never|not|do not)[^.]{0,40}(reword|trim|paraphras)", paragraph, re.I), paragraph


def test_ac3_no_entry_is_written_for_a_needs_test_false_clause():
    # covers: ACD-2500c-1
    # angle: criterion
    """AC-3: no entry names a clause whose intent says needs_test: false. The section says the step
    designs only needs_test: true clauses and writes no entry for a needs_test: false one."""
    section = _flat(_design_section())

    assert re.search(r"(only|just)[^.]{0,40}needs_test: true", section, re.I), section
    assert re.search(r"no (test_spec )?entry[^.]{0,60}needs_test: false", section, re.I), section


def test_ac3_an_all_false_intent_is_reported_pending_and_test_required_is_never_edited():
    # covers: ACD-2500c-1
    # angle: boundary
    """Boundary (zero needs-test clauses, architect note section 1): an intent whose every clause is
    needs_test: false is a planner defect (the planner must use test_required: false). The step
    reports test_design "pending" with that reason and never edits test_required."""
    paragraph = _paragraph_with(_design_section(), "needs_test: false", "pending")

    assert re.search(r"(every|all)[^.]{0,40}needs_test: false", paragraph, re.I), paragraph
    assert "test_required" in paragraph, paragraph
    assert re.search(r"(never|not|must not|do not)[^.]{0,30}(edit|change|set|write)[^.]{0,20}test_required", paragraph, re.I), (
        paragraph
    )


# --------------------------------------------------------------------------
# AC-2, AC-4, AC-5, AC-6: the entry shape, the facts, the convention file
# --------------------------------------------------------------------------
def test_ac2_prompt_example_is_valid_under_the_real_schema_with_the_g3_keys():
    # covers: ACD-2500c-1
    # angle: real_artifact
    """AC-2 / AC-4 / AC-6, lockstep with ticket 22 (the schema keys already exist): the fenced example
    in the section parses, its test_spec validates against the test_spec property of the REAL
    config/ac_store_schema.json, every entry names target_dir, proves_clause and code_file, it shows
    BOTH an entry for existing code and a to_be_created: true entry that cites a convention_test_file,
    and its authorship mark and opened-files list validate against their own schema properties."""
    example = _example(_design_section())
    schema = _schema()["properties"]
    spec = example["test_spec"]

    jsonschema.validate(spec, schema["test_spec"])
    jsonschema.validate(example["test_design_authorship"], schema["test_design_authorship"])
    jsonschema.validate(example["test_design_opened_files"], schema["test_design_opened_files"])
    for entry in spec:
        assert entry["target_dir"].endswith("/") and entry["proves_clause"].strip() and entry["code_file"].strip(), entry
        assert "convention_test_file" in entry or entry.get("to_be_created") is not True, entry
    created = [entry for entry in spec if entry.get("to_be_created") is True]
    existing = [entry for entry in spec if entry.get("to_be_created") in (None, False)]
    assert created and existing, "show a to_be_created: true and an existing-code entry"
    assert all(str(entry.get("convention_test_file", "")).strip() for entry in created)
    assert example["test_design_authorship"]["step"] == "test-designer"


def test_ac2_every_g3_key_the_consumers_read_is_taught_verbatim():
    # covers: ACD-2500c-1
    # angle: real_artifact
    """Lockstep with the real consumer module: each key constant of scripts/ac_store/_test_intent.py
    (ENTRY_CLAUSE_KEY, ENTRY_CODE_FILE_KEY, ENTRY_TO_BE_CREATED_KEY, ENTRY_CONVENTION_KEY,
    AUTHORSHIP_KEY, OPENED_FILES_KEY) appears verbatim in the section, so a renamed key on either
    side is caught. The constants are IMPORTED, not hand-typed here. (The file-findings constants
    of ticket 39 are deliberately not asserted: _file_findings.py does not exist yet.)"""
    sys.path.insert(0, str(REPO / "scripts" / "ac_store"))
    import _test_intent

    constants = [
        _test_intent.ENTRY_CLAUSE_KEY, _test_intent.ENTRY_CODE_FILE_KEY,
        _test_intent.ENTRY_TO_BE_CREATED_KEY, _test_intent.ENTRY_CONVENTION_KEY,
        _test_intent.AUTHORSHIP_KEY, _test_intent.OPENED_FILES_KEY,
    ]
    section = _design_section()

    assert tuple(constants[:4]) == G3_ENTRY_KEYS
    assert [key for key in constants if key not in section] == []


def test_ac4_ac5_test_dirs_and_file_existence_come_from_the_pre_pass_report():
    # covers: ACD-2500c-1
    # angle: criterion
    """AC-4 and AC-5: each entry names a target test directory that exists and a code file that exists
    at design time. The section takes existence, to_be_created and test-directory facts from the
    pre-pass report (ticket 28) rather than re-deriving them, and names its fields (declared_files
    state, test_dirs)."""
    paragraph = _paragraph_with(_design_section(), "pre-pass", "test_dirs")

    assert re.search(r"(rather than|never|not)[^.]{0,40}re-?deriv", paragraph, re.I), paragraph
    assert re.search(r"declared_files|state", paragraph), paragraph
    assert re.search(r"to_be_created|to-be-created", paragraph, re.I), paragraph
    assert re.search(r"target_dir", _flat(_design_section()))


def test_ac6_a_to_be_created_entry_cites_a_neighbouring_test_file_it_read():
    # covers: ACD-2500c-1
    # angle: criterion
    """AC-6: for a clause about code that does not exist yet the entry sets to_be_created: true and
    cites an existing neighbouring test file in convention_test_file, one the step opened and read as
    the convention the new test follows."""
    paragraph = _paragraph_with(_design_section(), "to_be_created", "convention_test_file")

    assert re.search(r"to_be_created: true", paragraph), paragraph
    assert re.search(r"(existing|neighbouring|neighboring)[^.]{0,40}test file", paragraph, re.I), paragraph
    assert re.search(r"(opened|read)", paragraph, re.I), paragraph


# --------------------------------------------------------------------------
# AC-7: authorship mark and the opened-files list, and the grounding rule
# --------------------------------------------------------------------------
def test_ac7_authorship_mark_and_opened_files_list_are_written():
    # covers: ACD-2500c-1
    # angle: criterion
    """AC-7: the design carries the step's authorship mark (test_design_authorship: step test-designer,
    date from `date +%F`) and the list of repository files the step opened (test_design_opened_files,
    repo-root-relative POSIX paths, non-empty)."""
    section = _design_section()
    authorship = _paragraph_with(section, "test_design_authorship", "date")
    opened = _paragraph_with(section, "test_design_opened_files")

    assert "test-designer" in authorship and "date +%F" in authorship, authorship
    assert re.search(r"repo(sitory)?-root-relative", opened, re.I) and "POSIX" in opened, opened
    assert re.search(r"non-empty|at least one|never (leave )?empty", opened, re.I), opened


def test_ac7_example_names_only_files_it_lists_as_opened_and_names_the_files_it_read():
    # covers: ACD-2500c-1
    # angle: discrimination
    """WRONG VERSION THIS CATCHES (the named alteration of the AC): an entry designed from the
    criteria text alone, without opening the file, so the opened-files list is empty or lacks the
    named files and ACD-2500c-1-i rejects the ungrounded path. In the prompt's own example every
    code_file and every convention_test_file is a member of test_design_opened_files, the list is
    non-empty, and the paths are repo-root-relative POSIX (no drive, no backslash, no leading slash);
    the prose states a file that was not opened must not be named."""
    section = _design_section()
    example = _example(section)
    opened = example["test_design_opened_files"]
    named = {entry["code_file"] for entry in example["test_spec"]}
    named |= {entry["convention_test_file"] for entry in example["test_spec"] if "convention_test_file" in entry}

    assert opened, "the example's opened-files list is empty (an ungrounded design)"
    assert named <= set(opened), f"named but never opened: {sorted(named - set(opened))}"
    for path in opened:
        assert not re.match(r"^([A-Za-z]:|/)", path) and "\\" not in path, path
    assert re.search(r"(never|not|only)[^.]{0,80}(name|cite)[^.]{0,80}(not opened|did not open|opened)", _flat(section), re.I)


# --------------------------------------------------------------------------
# AC-8: the fields the step must not touch, and how it writes
# --------------------------------------------------------------------------
def test_ac8_protected_fields_stay_byte_identical_and_writes_are_field_targeted_edits():
    # covers: ACD-2500c-1
    # angle: criterion
    """AC-8: criteria, test_intent, assigned_agent, implements_pattern and pattern_bindings are
    byte-identical before and after the step (TKT-300a-4, ACS-500c-2), and so are declared_files,
    covered_by, delivers_to, expects_from and the other it_requirements keys. Every write is a
    field-targeted Edit of the AC YAML: never Write a whole record, never a YAML load/dump rewrite,
    read and write with the file's own line endings."""
    section = _design_section()
    protected = _paragraph_with(section, "criteria", "pattern_bindings", "byte-identical")
    writing = _paragraph_with(section, "field-targeted")

    for field in PROTECTED:
        assert field in protected, f"{field!r} missing from the never-touch paragraph: {protected}"
    assert re.search(r"(never|do not|must not)[^.]{0,30}touch|byte-identical", protected, re.I)
    assert re.search(r"never[^.]{0,30}Write[^.]{0,40}(whole )?record", writing, re.I), writing
    assert re.search(r"(load|dump|rewrite|re-?serial)", writing, re.I), writing
    assert re.search(r"line ending", writing, re.I), writing


def test_ac8_the_other_output_group_is_not_written_by_the_test_design_procedure():
    # covers: ACD-2500c-1
    # angle: criterion
    """AC-8 / ACD-2500d-5 clause 4: the test design is kept separate from the file findings. Wherever
    the test-design section mentions file_findings it is to say the field is left untouched."""
    mentions = [paragraph for paragraph in _paragraphs(_design_section()) if "file_findings" in paragraph]

    assert mentions, "the section must say it leaves file_findings untouched"
    assert all(re.search(r"untouched|never|not write|do not|leave", paragraph, re.I) for paragraph in mentions), mentions


# --------------------------------------------------------------------------
# bug-fix and gate records
# --------------------------------------------------------------------------
def test_must_catch_and_discrimination_are_written_for_bug_fix_and_gate_records_only():
    # covers: ACD-2500c-1
    # angle: criterion
    """it_requirements: the step MAY write the existing optional test_spec[].must_catch (a non-empty
    list of non-blank strings: the wrong versions the test must go red under) and angle
    `discrimination` on an entry for a bug-fix or gate/guard record; their presence is the
    declaration (no separate key, no other undeclared key); the step is the only writer of must_catch
    and uses no Opus sub-call (Sonnet-only, user decision 2026-09-28)."""
    paragraph = _paragraph_with(_design_section(), "must_catch", "discrimination")

    assert re.search(r"bug-?fix", paragraph, re.I) and re.search(r"gate|guard", paragraph, re.I), paragraph
    assert re.search(r"(only|just|when)[^.]{0,80}(bug-?fix|gate)", paragraph, re.I), paragraph
    assert re.search(r"no (separate|other|extra)[^.]{0,40}key|no undeclared key", _flat(_design_section()), re.I)
    assert re.search(r"(only writer|only step|only this step|only you)", _flat(_design_section()), re.I)
    assert re.search(r"no Opus|without an Opus|Sonnet-only|never[^.]{0,30}Opus", _flat(_design_section()), re.I)


# --------------------------------------------------------------------------
# seam: the example through the real consumers
# --------------------------------------------------------------------------
def test_ac7_prompt_example_merged_into_a_real_record_is_valid_and_read_as_code_aware(tmp_path):
    # covers: ACD-2500c-1
    # angle: seam
    """Seam, producer to consumers: the prompt's example fields are merged into the REAL ACD-2500c-1
    record, written through yaml.safe_dump to a tmp file and read back (not a hand-typed record). The
    merged record validates against the REAL schema (jsonschema, whole record) and the REAL consumer
    scripts/ac_store/_test_intent.py answers is_legacy_design -> False (the authorship mark is
    recognised) while the record's protected fields are unchanged by the merge."""
    sys.path.insert(0, str(REPO / "scripts" / "ac_store"))
    import _test_intent

    real = yaml.safe_load(AC_FILE.read_text(encoding="utf-8"))
    example = _example(_design_section())
    merged = {**real, **{key: example[key] for key in ("test_spec", "test_design_authorship", "test_design_opened_files")}}
    merged.pop("test_required", None)
    path = tmp_path / "ACD-2500c-1.yaml"
    path.write_text(yaml.safe_dump(merged, sort_keys=False), encoding="utf-8")
    loaded = yaml.safe_load(path.read_text(encoding="utf-8"))

    jsonschema.validate(loaded, _schema())
    assert _test_intent.is_legacy_design(loaded) is False
    assert not _test_intent.design_pending(loaded)
    assert all(loaded[field] == real[field] for field in PROTECTED if field in real)


# --------------------------------------------------------------------------
# reachability: the prompt as the agent receives it
# --------------------------------------------------------------------------
def test_acd_2500c_1_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500c-1
    # angle: reachability
    """Entry point resolved (Step 1.1, CLI script with main under scripts/):
    `python scripts/render_effective_prompt.py --agent test-designer --ac ACD-2500c-1`, run as a
    subprocess. It renders the prompt the test designer receives at spawn time; its test-design
    section must be the template's section (nothing rewrites or drops it) and must teach
    proves_clause. The CLI prefers the DEPLOYED copy under .claude/agents (build output, stale until
    the build runs), so it is pointed at a tmp repo root holding a verbatim copy of the TEMPLATE and
    of the AC record; the build is not run here."""
    root = tmp_path / "repo"
    (root / "templates" / "agents").mkdir(parents=True)
    _template()
    shutil.copyfile(TEMPLATE, root / "templates" / "agents" / "test-designer.md")
    ac_folder = root / "docs" / "acceptance-criteria" / "ac-driven-dev"
    ac_folder.mkdir(parents=True)
    shutil.copyfile(AC_FILE, ac_folder / "ACD-2500c-1.yaml")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    proc = subprocess.run(
        [sys.executable, str(RENDER_CLI), "--agent", "test-designer", "--ac", "ACD-2500c-1",
         "--repo-root", str(root), "--out-dir", str(out_dir), "--quiet"],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env, cwd=str(REPO),
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    rendered = (out_dir / "effective_prompt_test-designer_ACD-2500c-1.md").read_text(encoding="utf-8")
    rendered_section = _design_section(rendered)
    assert rendered_section == _design_section()
    assert "proves_clause" in rendered_section


# --------------------------------------------------------------------------
# user decision 2026-10-14 "Design lists them all": the standing test mandates live in the design
# --------------------------------------------------------------------------
def test_every_code_record_design_carries_a_reachability_entry_through_the_real_entry_point():
    # covers: ACD-2500c-1
    # angle: criterion
    """The design is the whole list: for every code record test_spec carries a test with angle
    `reachability` that invokes the real production entry point (CLI, hook runner, slash command,
    workflow dispatch or main() with real argv). The rule is mandatory, not optional."""
    paragraph = _paragraph_with(_design_section(), "reachability", "entry point")

    assert re.search(r"(every|each|all)[^.]{0,40}(code )?record", paragraph, re.I), paragraph
    assert re.search(r"(must|always|at least one|requires?|carry|carries)", paragraph, re.I), paragraph
    assert not re.search(r"\bmay\b[^.]{0,40}reachability", paragraph, re.I), paragraph


def test_reachability_is_not_left_optional_or_to_the_test_writer():
    # covers: ACD-2500c-1
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: the designer writes only criterion entries and leaves the
    reachability test to the test writer's old standing mandate (so the design no longer 'lists them
    all'). The section states that the design lists it, so the test writer adds nothing of its own."""
    section = _flat(_design_section())

    assert re.search(r"(test writer|test-writer)[^.]{0,80}(adds? no|nothing|does not add|never add)", section, re.I), section


def test_bug_fix_and_real_artifact_entries_are_designed_where_they_apply():
    # covers: ACD-2500c-1
    # angle: criterion
    """Where they apply the design also carries a bug-fix discrimination entry (must_catch with angle
    discrimination, the rule already stated) and a real-artifact entry (angle real_artifact: the code
    runs, writes to a real location and the artifact is read back) for a record with a durable side
    effect."""
    section = _design_section()
    real = _paragraph_with(section, "real_artifact")

    assert re.search(r"(durable|side[- ]effect|writes? (a|an|to)|artifact)", real, re.I), real
    assert re.search(r"(where|when|only)[^.]{0,80}(appl|side[- ]effect|durable)", real, re.I), real
    assert "discrimination" in _flat(section) and "must_catch" in _flat(section)


def test_example_shows_a_reachability_entry_valid_under_the_real_schema():
    # covers: ACD-2500c-1
    # angle: real_artifact
    """The fenced example shows a `reachability` entry (angle reachability) next to the others; its
    test_spec still validates against the REAL config/ac_store_schema.json, and the reachability entry
    names a code_file that is in test_design_opened_files (grounded like every other entry)."""
    example = _example(_design_section())
    entries = [e for e in example["test_spec"] if e.get("angle") == "reachability"]

    assert entries, "the example needs an entry with angle: reachability"
    jsonschema.validate(example["test_spec"], _schema()["properties"]["test_spec"])
    assert all(e["code_file"] in example["test_design_opened_files"] for e in entries), entries
