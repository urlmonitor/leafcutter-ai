"""
MODULE: unit_tests/ac_driven_dev/it_po_prompt/test_acd_2500b_1.py
COVERS: ACD-2500b-1
GOAL: Red-first specification of ACD-2500b-1 (ticket 20): the IT PO prompt
    (templates/agents/it-po.md) tells the technical planner to record, per outcome clause,
    whether a test is needed and why (`test_intent`), to write NO test design, and to keep
    `test_required: false` for prompt- or docs-only work. Section 2.7 is rewritten IN PLACE:
    the old "MANDATORY test_spec" paragraph and its YAML example are gone.
BUSINESS CONTEXT: The planner cannot read code (ADR-009), so a test design it writes is not
    grounded (ADR-071). The prompt is the only place that behaviour is enforced upstream of
    the rule check, so the prompt content is itself the deliverable of this ticket.
HONEST LIMIT (read this before editing): ACD-2500b-1 is a prompt change. Its record authors NO
    test_spec and sets test_required: false. What a prompt "does" happens in a model run, which a
    unit test cannot reproduce. The tests below therefore prove only what is mechanically
    decidable about the file, in this order of preference:
      1. STRUCTURE: section headings, the number of 2.7 sections, fenced YAML examples that are
         PARSED and validated (against the schema for test_intent; no `test_spec` example left);
      2. REAL ARTIFACT / REACHABILITY: the prompt as the agent receives it, rendered by the real
         CLI `scripts/render_effective_prompt.py`, carries the same section;
      3. PRESENCE of the specific rules named in architect note G3 section 4 (clause rule,
         one entry per clause, forbidden content, test_required: false, never write test_spec).
    Presence checks (3) are paragraph-scoped and whitespace-normalised, never a whole-file grep,
    and none asserts on the G5-owned parts (S2.8, S5, S7, S7b, the BO-2000d block, the S8 items
    ACD-2500e-2 removes). They cannot prove the model obeys the rule; the rule-check family
    (ticket 21) and the approval hold (ticket 23) are the enforcement.

RED STATE: the file still carries the old test_spec / test_required section 2.7; every test
    fails on an ASSERTION about the current prompt text.
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

REPO_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE = REPO_ROOT / "templates" / "agents" / "it-po.md"
SCHEMA_FILE = REPO_ROOT / "config" / "ac_store_schema.json"
RENDER_CLI = REPO_ROOT / "scripts" / "render_effective_prompt.py"
AC_FILE = (
    REPO_ROOT / "docs" / "acceptance-criteria" / "ac-driven-dev"
    / "ACD-2500-right-job-right-agent" / "ACD-2500b-1.yaml"
)

INTENT_KEYS = {"clause", "needs_test", "reason"}
SECTION_27 = re.compile(r"^### 2\.7 [^\n]*\n.*?(?=^#{2,3} (?!#))", re.DOTALL | re.MULTILINE)
SECTION_S8 = re.compile(r"^## S8 Self-Review Checklist.*?(?=^## S9)", re.DOTALL | re.MULTILINE)
SECTION_DOES_NOT = re.compile(r"^## What the IT PO Does NOT Do.*?(?=^## Sign-Off)", re.DOTALL | re.MULTILINE)
YAML_FENCE = re.compile(r"```ya?ml\n(.*?)```", re.DOTALL)
OLD_MANDATORY_FRAGMENTS = (
    "test_merged_output_has_seven_entries",
    "Rules for `test_spec`",
    "One descriptor per distinct `Then`",
    "You MUST set",
)


def _flat(text: str) -> str:
    """Prose view: markdown emphasis dropped, whitespace collapsed (a wrapped line is one line)."""
    return re.sub(r"\s+", " ", text.replace("`", "").replace("**", "")).strip()


def _template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def _section(pattern: re.Pattern[str], text: str | None = None) -> str:
    match = pattern.search(_template() if text is None else text)
    assert match is not None, f"section {pattern.pattern[:40]!r} not found"
    return match.group(0)


def _paragraphs(text: str) -> list[str]:
    return [_flat(block) for block in re.split(r"\n\s*\n", text) if block.strip()]


def _paragraph_with(text: str, needle: str) -> str:
    """The flattened paragraph of `text` containing `needle` (case-insensitive)."""
    for paragraph in _paragraphs(text):
        if needle.lower() in paragraph.lower():
            return paragraph
    pytest.fail(f"no paragraph of section 2.7 mentions {needle!r}")


def _intent_examples(section: str) -> list[list]:
    """Every fenced YAML block of `section` that has a top-level `test_intent` list, parsed."""
    found = []
    for block in YAML_FENCE.findall(section):
        parsed = yaml.safe_load(block)
        if isinstance(parsed, dict) and isinstance(parsed.get("test_intent"), list):
            found.append(parsed["test_intent"])
    return found


# --------------------------------------------------------------------------
# AC-1 .. AC-5
# --------------------------------------------------------------------------
def test_ac1_one_entry_per_outcome_clause_including_needs_test_false():
    # covers: ACD-2500b-1
    # angle: criterion
    """AC-1: the record carries one test-intent entry per outcome clause. Section 2.7 states the
    one-entry-per-clause rule for the Then AND And clauses, that an entry is written also when the
    clause needs no test, and that a code leaf needs at least one needs_test: true clause."""
    section = _flat(_section(SECTION_27))

    assert re.search(r"one (test_intent )?entry per (Then/And )?(outcome )?clause", section, re.I), section
    assert "Then" in section and "And" in section
    assert re.search(r"needs_test: false[^.]{0,120}(reason|entry)", section), section
    assert re.search(r"at least one[^.]{0,80}needs_test: true", section), section


def test_ac1_clause_rule_matches_the_normaliser():
    # covers: ACD-2500b-1
    # angle: criterion
    """AC-1 (clause text): the prompt states the clause rule the rule check applies (architect note
    section 4b): the text after the keyword of each Then and And line after the first Then,
    continuation lines joined, whitespace collapsed, a trailing , ; or . dropped, so an entry matches
    its clause under normalise_clause (ticket 21)."""
    section = _flat(_section(SECTION_27))
    lowered = section.lower()

    assert "continuation" in lowered, section
    assert "whitespace" in lowered, section
    after_trailing = section[lowered.index("trailing"):][:140] if "trailing" in lowered else ""
    assert after_trailing, "the prompt must say a trailing , ; or . is dropped from the clause text"
    assert all(mark in after_trailing for mark in (",", ";", ".")), after_trailing


def test_ac2_entry_shape_clause_needs_test_reason_with_a_valid_example():
    # covers: ACD-2500b-1
    # covers: ACD-2500b
    # angle: criterion
    """AC-2: each entry names its clause, states needs-test yes or no, and gives a one-sentence
    reason. The section names exactly these three keys and shows the shape as a fenced YAML
    example that parses: a `test_intent` list whose entries have exactly {clause, needs_test,
    reason}, needs_test a boolean, clause and reason non-empty strings, with both a needs_test
    true and a needs_test false entry shown."""
    raw = _section(SECTION_27)
    flat = _flat(raw)

    for key in sorted(INTENT_KEYS):
        assert key in flat, f"section 2.7 must name the key {key!r}"
    examples = _intent_examples(raw)
    assert examples, "section 2.7 must show a fenced yaml example with a top-level test_intent list"
    entries = [entry for example in examples for entry in example]
    for entry in entries:
        assert set(entry) == INTENT_KEYS, entry
        assert isinstance(entry["needs_test"], bool), entry
        assert isinstance(entry["clause"], str) and entry["clause"].strip(), entry
        assert isinstance(entry["reason"], str) and entry["reason"].strip(), entry
    assert {entry["needs_test"] for entry in entries} == {True, False}, "show a true and a false entry"


def test_ac2_prompt_example_is_valid_under_the_real_schema():
    # covers: ACD-2500b-1
    # angle: real_artifact
    """AC-2, lockstep with ticket 21 (they ship together): the example in the prompt validates against
    the test_intent property of the REAL config/ac_store_schema.json, and every key the schema
    requires appears in section 2.7. A prompt that teaches a shape the schema rejects is the exact
    failure the SHIP-TOGETHER rule exists for."""
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    assert "test_intent" in schema["properties"], "ticket 21 declares test_intent in the schema"
    prop = schema["properties"]["test_intent"]
    required = set(prop["items"]["required"])
    raw = _section(SECTION_27)

    assert required == INTENT_KEYS
    assert all(key in _flat(raw) for key in required)
    examples = _intent_examples(raw)
    assert examples, "section 2.7 must show a fenced yaml example with a top-level test_intent list"
    for example in examples:
        jsonschema.validate(example, prop)


def test_ac3_no_test_design_in_the_planner_instructions():
    # covers: ACD-2500b-1
    # covers: ACD-2500b
    # angle: criterion
    """AC-3: the record carries no test design written by the planner. Section 2.7 forbids, in one
    place, test names, directories, frameworks, types, angles, strategy, isolation level and
    must_catch; says the planner NEVER writes test_spec; and shows no `test_spec` YAML example."""
    raw = _section(SECTION_27)
    forbidden = _paragraph_with(raw, "test names")
    for token in (r"director", r"framework", r"types?\b", r"angle", r"strategy", r"isolation", r"must_catch"):
        assert re.search(token, forbidden, re.I), f"forbidden-content list lacks {token!r}: {forbidden}"
    assert re.search(r"(never|must not|do not)[^.]{0,60}(write|author|set)[^.]{0,40}test_spec", _flat(raw), re.I)
    for block in YAML_FENCE.findall(raw):
        parsed = yaml.safe_load(block)
        assert not (isinstance(parsed, dict) and "test_spec" in parsed), "a test_spec example is left in 2.7"


def test_ac3_planner_never_sets_hold_reason_or_raises_readiness():
    # covers: ACD-2500b-1
    # angle: criterion
    """ADR-071 section 2 (and note 4b): the IT PO writes test_intent and MUST NOT write test_spec, set
    hold_reason, or raise readiness. The section says so."""
    flat = _flat(_section(SECTION_27))

    assert re.search(r"(never|must not|do not)[^.]{0,60}hold_reason", flat, re.I), flat
    assert re.search(r"(never|must not|do not)[^.]{0,80}readiness", flat, re.I), flat


def test_ac3_existing_planner_test_spec_is_left_untouched():
    # covers: ACD-2500b-1
    # angle: criterion
    """A record that already carries a planner-written test_spec is left untouched and gets no
    test_intent (ACD-2500b-3 protects legacy designs)."""
    paragraph = _paragraph_with(_section(SECTION_27), "already")

    assert "test_spec" in paragraph and "test_intent" in paragraph, paragraph
    assert re.search(r"untouched|unchanged|left alone|leave it|do not (add|write)|no test_intent", paragraph, re.I), (
        paragraph
    )


def test_ac4_criteria_stay_byte_identical_is_restated_in_the_section():
    # covers: ACD-2500b-1
    # angle: criterion
    """AC-4: the criteria text is byte-identical before and after enrichment. The new section restates
    it (the planner reads the clauses, it must never fix their wording to make an entry match)."""
    flat = _flat(_section(SECTION_27))

    assert re.search(r"criteria[^.]{0,80}byte-identical|byte-identical[^.]{0,80}criteria", flat, re.I), flat


def test_ac5_prompt_or_docs_only_work_keeps_test_required_false_and_no_intent():
    # covers: ACD-2500b-1
    # angle: criterion
    """AC-5: for a requirement with no executable behaviour (prompt- or docs-only) the planner may
    instead record that no tests are required, as today: `test_required: false`, and no test_intent."""
    paragraph = _paragraph_with(_section(SECTION_27), "test_required: false")

    assert re.search(r"prompt", paragraph, re.I) and re.search(r"docs", paragraph, re.I), paragraph
    assert "test_intent" in paragraph, paragraph
    assert re.search(
        r"no test_intent|not (write|carry|add)[^.]{0,30}test_intent|without[^.]{0,30}test_intent",
        paragraph, re.I,
    ), paragraph


# --------------------------------------------------------------------------
# replaced in place, not appended
# --------------------------------------------------------------------------
def test_section_2_7_is_rewritten_in_place_and_the_mandatory_test_spec_paragraph_is_gone():
    # covers: ACD-2500b-1
    # angle: discrimination
    """WRONG VERSION THIS CATCHES: new test_intent text APPENDED next to the old section, leaving the
    "MANDATORY test_spec" instruction alive (a planner told to do both writes both). There is exactly
    one section 2.7, retitled with test_intent and test_required, no longer titled around
    test_spec / MANDATORY, and none of the old paragraph's own sentences or its YAML example remain
    anywhere in the file."""
    text = _template()
    heading = re.search(r"^### 2\.7 [^\n]*$", text, re.MULTILINE)

    assert heading is not None
    assert len(re.findall(r"^### 2\.7 ", text, re.MULTILINE)) == 1
    assert "test_intent" in heading.group(0) and "test_required" in heading.group(0), heading.group(0)
    assert "MANDATORY" not in heading.group(0), heading.group(0)
    assert "test_spec / test_required" not in heading.group(0), heading.group(0)
    leftovers = [fragment for fragment in OLD_MANDATORY_FRAGMENTS if fragment in text]
    assert leftovers == [], f"old test_spec paragraph still present: {leftovers}"


def test_frontmatter_description_names_test_intent_not_the_test_contract():
    # covers: ACD-2500b-1
    # angle: criterion
    """Architect note 4a: the description line 'the test contract (test_spec / test_required)' becomes
    the test-intent wording. The frontmatter is parsed as YAML (not grepped)."""
    text = _template()
    frontmatter = yaml.safe_load(text.split("---", 2)[1])
    description = _flat(frontmatter["description"])

    assert "test_spec" not in description, description
    assert re.search(r"test[ _-]intent", description, re.I), description


def test_checklist_and_does_not_list_carry_the_new_rule():
    # covers: ACD-2500b-1
    # angle: criterion
    """Architect note 4c and 4d: one new S8 checklist item about test_intent (one entry per clause,
    nothing forbidden), and one bullet in 'What the IT PO Does NOT Do' about test_spec. Only the PRESENCE
    of the new line is asserted: no numbering, no count (ACD-2500e-2 edits the other S8 items)."""
    checklist = _flat(_section(SECTION_S8))
    does_not = _flat(_section(SECTION_DOES_NOT))

    assert "test_intent" in checklist, "S8 needs an item about test_intent"
    assert re.search(r"Never[^.]{0,80}test_spec", does_not), "the Does-NOT list needs a 'never write test_spec' bullet"


# --------------------------------------------------------------------------
# reachability: the prompt as the agent receives it
# --------------------------------------------------------------------------
def test_acd_2500b_1_reachable_from_entry_point(tmp_path):
    # covers: ACD-2500b-1
    # angle: reachability
    """Entry point resolved (Step 1.1, a CLI script with main under scripts/): `python
    scripts/render_effective_prompt.py --agent it-po --ac ACD-2500b-1`, run as a subprocess. It
    renders the prompt the IT PO receives at spawn time. Its section 2.7 must be the template's
    section 2.7 (same text, so nothing rewrites or drops it), must teach test_intent, and must not
    carry the old MANDATORY test_spec paragraph.

    The CLI prefers the DEPLOYED copy under .claude/agents (build output, untracked, stale until the
    build runs), so it is pointed at a tmp repo root holding a verbatim copy of the TEMPLATE and of
    the AC record; the build is not run here and the result does not depend on it."""
    root = tmp_path / "repo"
    (root / "templates" / "agents").mkdir(parents=True)
    shutil.copyfile(TEMPLATE, root / "templates" / "agents" / "it-po.md")
    ac_folder = root / "docs" / "acceptance-criteria" / "ac-driven-dev"
    ac_folder.mkdir(parents=True)
    shutil.copyfile(AC_FILE, ac_folder / "ACD-2500b-1.yaml")
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}

    proc = subprocess.run(
        [sys.executable, str(RENDER_CLI), "--agent", "it-po", "--ac", "ACD-2500b-1",
         "--repo-root", str(root), "--out-dir", str(out_dir), "--quiet"],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=env, cwd=str(REPO_ROOT),
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    rendered = (out_dir / "effective_prompt_it-po_ACD-2500b-1.md").read_text(encoding="utf-8")
    rendered_27 = _section(SECTION_27, rendered)
    assert rendered_27 == _section(SECTION_27)
    assert "test_intent" in rendered_27
    assert not [fragment for fragment in OLD_MANDATORY_FRAGMENTS if fragment in rendered]
