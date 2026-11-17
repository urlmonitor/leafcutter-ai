"""ACD-2500a-5-i, -ii and -iii -- ADR-075, the ADR-072 amendment notes and the rule check reference (content checks).

All three ACs are ``test_required: false`` (documentation deliverables). Each test reads the delivered page and
asserts one clause of the AC's criteria is actually stated there, so a deleted section or a dropped clause turns
it red. Where a clause names a fact the code owns (the protected field list, the per-stage owner map, the rule
families), the expected value is read from the real ``scripts/ac_store`` modules, never retyped.
"""

from __future__ import annotations

import re
import sys

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

ADRS = D.REPO / "docs" / "architecture" / "adrs"
ADR_075 = ADRS / "ADR-075-requirement-rule-check.md"
ADR_072 = ADRS / "ADR-072-code-aware-test-designer-may-read-source.md"
REFERENCE = D.REPO / "docs" / "reference" / "requirement-rule-check.md"

sys.path.insert(0, str(D.REPO / "scripts" / "ac_store"))
import _rc_protected_fields  # noqa: E402
import _rc_report  # noqa: E402
import requirement_rule_check  # noqa: E402

# Decision heading (ADR-075 section 3) -> the rejected alternative it is paired with (section 5).
DECISIONS = {
    1: ("### 1. One rule check made of rule families", "Keep the rules as instructions the authoring agents must remember"),
    2: ("### 2. A fail-closed gate after every authoring stage", "Let the stage agent run the check and report the result"),
    3: ("### 3. Repair only where one answer exists, through a guarded writer, with a before-state",
        "Repair every violation the check can name, or repair without a before-state"),
    4: ("### 4. `--changed-since` finds the records itself", "Check the ids the stage agent says it wrote"),
    5: ("### 5. `config/surface_craft_map.yaml` is the one surface-to-specialist authority",
        "Give the rule check its own file-type-to-specialist table"),
    6: ("### 6. `HOLD_REASONS` is the one hold-reason vocabulary",
        "Let each gate keep its own hold-reason list, or report holds as rule-check findings"),
    7: ("### 7. The protected-field family is the backstop for fields a stage does not own",
        "Rely on the prose in `test-designer.md` and the commit-time governance hook"),
}
NUMBER_WORDS = {10: "Ten", 11: "Eleven", 12: "Twelve", 13: "Thirteen"}


# ---------------------------------------------------------------- ACD-2500a-5-i (ADR-075)
def test_adr_075_is_numbered_in_the_decision_folder_and_indexed():
    # covers: ACD-2500a-5-i
    # angle: criterion
    """It is numbered ADR-075, sits in docs/architecture/adrs/, and the index lists it by link."""
    text = D.read(ADR_075)
    assert re.search(r'^title: "ADR-075: ', text, re.M), "frontmatter title must carry the number ADR-075"
    assert "\n# ADR-075: " in text
    index_rows = [ln for ln in D.read(ADRS / "README.md").splitlines() if ln.startswith("| [ADR-075]")]
    assert index_rows == ["| [ADR-075](ADR-075-requirement-rule-check.md) | Active | Mechanical Requirement Rules "
                          "Are Checked by One Fail-Closed Rule Check | 2026-10-21 |"], index_rows


def test_adr_075_records_each_decision_with_its_rejected_alternative():
    # covers: ACD-2500a-5-i
    # angle: criterion
    """Each of the seven decisions the AC lists is a Decision subsection, and the Alternatives section pairs
    each with a rejected alternative naming that decision's number."""
    text = D.read(ADR_075)
    decision = D.section(text, "## Decision")
    alternatives = D.flat(D.section(text, "## Alternatives"))
    for number, (heading, rejected) in DECISIONS.items():
        assert heading in decision, f"decision {number} missing: {heading}"
        match = re.search(re.escape(rejected) + r"\*\* \((?:for )?decision (\d)\)\. Rejected\.", alternatives)
        assert match and int(match.group(1)) == number, f"decision {number} has no rejected alternative: {rejected}"


def test_adr_075_decisions_state_the_clauses_the_ac_names():
    # covers: ACD-2500a-5-i
    # angle: criterion
    """The decision text states the AC's specific clauses: fail-closed gate with no completion on a failed or
    empty check, the guarded re-evaluating writer, repair only with a before-state, the changed-since scope, and
    the protected-field family as the deterministic backstop."""
    D.assert_all(
        D.section(D.read(ADR_075), "## Decision"),
        ["A stage MUST NOT be reported complete unless the exit code is `0`, the verdict is `passed` and "
         "`records_checked` is above zero.",
         "`scripts/ac_store/_rc_edit.py` MUST be the only writer.",
         "The orchestrator MUST evaluate again after it repairs",
         "Repairs MUST be applied only when the run has a usable before-state",
         "`--changed-since REV` checks every record file under the store",
         "MUST be read only from `config/surface_craft_map.yaml`",
         "MUST be the only list of reasons a record can be held from approval or dispatch",
         "for every record that existed at stage start"],
        "ADR-075 Decision",
    )


def test_adr_075_links_adr_072_and_the_reference_instead_of_restating_them():
    # covers: ACD-2500a-5-i
    # angle: discrimination
    """It links ADR-072 and the reference doc, says it does not repeat the reference, and carries no copy of
    the report format (no JSON report example, no family-by-family table)."""
    text = D.read(ADR_075)
    assert "(ADR-072-code-aware-test-designer-may-read-source.md)" in text
    assert "(../../reference/requirement-rule-check.md)" in text
    assert "does not repeat that reference" in D.flat(text)
    assert "```json" not in text, "the JSON report format belongs to the reference, not the ADR"
    assert "| Rule family" not in text and "| # |" not in text, "the family table belongs to the reference"


# ---------------------------------------------------------------- ACD-2500a-5-ii (ADR-072 amendment)
def test_adr_072_section_2_backstop_names_the_protected_field_family():
    # covers: ACD-2500a-5-ii
    # angle: criterion
    """Section 2's backstop sentence names the protected-field rule family (and ADR-075)."""
    sec = D.flat(D.section(D.read(ADR_072), "### 2. Two output groups"))
    assert re.search(r"The rule check's `protected fields` rule family \(ACD-2500a-2-vi, \[ADR-075\][^)]*\)"
                     r"[^.]*is the deterministic backstop\.", sec), sec


def test_adr_072_consequences_carry_dated_closing_notes_above_the_original_text():
    # covers: ACD-2500a-5-ii
    # angle: criterion
    """Each of the two Consequences bullets carries a dated amendment note naming its closing record, and the
    original sentence stays readable beneath the note."""
    negative = D.flat(D.section(D.read(ADR_072), "### Negative"))
    for record, original in (("ACD-300c-4", "**The M-5 bypass stays open.**"),
                             ("ACD-2500a-2-vi", "not by a dedicated rule family.")):
        note = f"*Amended 2026-10-21: closed by {record}."
        assert note in negative, f"no dated amendment note naming {record}"
        tail = negative[negative.index(note):]
        assert "Original text:" in tail and original in tail, f"original sentence lost beneath the {record} note"
        assert tail.index("Original text:") < tail.index(original)


def test_adr_072_section_4_amendment_and_original_order_unchanged():
    # covers: ACD-2500a-5-ii
    # angle: criterion
    """Section 4 gains the dated ACD-2500a-2-ix sentence (test-design output committed before the hand-back
    round, so the hand-back before-state is the post-design batch) and keeps its original stage list."""
    sec = D.flat(D.section(D.read(ADR_072), "### 4. Stage order in /plan-feature"))
    D.assert_all(sec, ["*Amended 2026-10-21 (ACD-2500a-2-ix):* /plan-feature commits the test-design output",
                       "before the IT PO's first hand-back round",
                       "the hand-back rule check's before-state is the post-design batch"], "ADR-072 section 4")
    for original in ("1. `it-po` authors (stage `itpo`);", "2. `rule-check-itpo`;", "5. `test-designer`;",
                     "6. `rule-check-test-design` (`--changed-since HEAD --before-ref HEAD`);",
                     "An `edit` retry re-dispatches `test-designer`, never `it-po`."):
        assert original in sec, f"section 4 original text changed: {original}"


def test_adr_072_status_unchanged_and_links_adr_075():
    # covers: ACD-2500a-5-ii
    # angle: criterion
    """ADR-072's status stays Proposed and it links ADR-075."""
    text = D.read(ADR_072)
    assert "| **Status** | Proposed |" in D.section(text, "## Status")
    assert "(ADR-075-requirement-rule-check.md)" in text


# ---------------------------------------------------------------- ACD-2500a-5-iii (reference doc)
def test_reference_lists_protected_fields_with_disposition_field_list_and_owner_map():
    # covers: ACD-2500a-5-iii
    # angle: real_artifact
    """The protected fields family is listed as 'needs a decision'; its fixed field list and per-stage owner map
    equal the real _rc_protected_fields constants; the hand-back pass may change the assignment and a finding's
    decision."""
    text = D.read(REFERENCE)
    assert "| 11 | `protected fields` | `needs a decision`, `not evaluated` | none |" in text
    sec = D.flat(D.section(text, "### 11. protected fields"))
    fields = _rc_protected_fields.PROTECTED_FIELDS
    listed = ", ".join(f"`{f}`" for f in fields[:-1]) + f" and `{fields[-1]}`"
    assert f"a fixed list of {NUMBER_WORDS.get(len(fields), len(fields)).lower()}, {listed}" in sec, sec
    for stage, owned in _rc_protected_fields.OWNER_MAP.items():
        row = re.search(r"\| `" + re.escape(stage) + r"` \| ([^|]+)\|", sec)
        assert row, f"owner map row missing for {stage}"
        assert re.findall(r"`([^`]+)`", row.group(1))[:len(owned)] == list(owned), (stage, row.group(1))
    assert "the planner's hand-back pass may change the assignment and a file finding's decision" in sec


def test_reference_states_repairs_need_a_before_state_and_what_a_run_without_one_reports():
    # covers: ACD-2500a-5-iii
    # angle: criterion
    """It states a run repairs only with a before-state, names the two ways to give one, and what a run
    without one reports ('not evaluated: no before-state', nothing repaired)."""
    D.assert_all(
        D.section(D.read(REFERENCE), "### Before-state"),
        ["A run repairs a record only when it has a usable before-state",
         "There are two ways to give one: `--before-ref REV` or `--before-snapshot FILE`.",
         "nothing is written: no record file is changed;", "every repair becomes `needs a decision`",
         "`not evaluated: no before-state`"],
        "requirement-rule-check.md Before-state",
    )


def test_reference_every_example_command_passes_a_before_state():
    # covers: ACD-2500a-5-iii
    # angle: boundary
    """Every fenced example command that runs the rule check passes --before-ref or --before-snapshot."""
    blocks = re.findall(r"```(?:bash|sh)?\n(.*?)```", D.read(REFERENCE), re.DOTALL)
    commands = [ln for block in blocks for ln in block.splitlines() if "requirement_rule_check.py" in ln]
    assert len(commands) >= 4, "control: the reference shows its example commands"
    missing = [c for c in commands if "--before-ref" not in c and "--before-snapshot" not in c]
    assert missing == [], missing


def test_reference_family_count_and_list_agree_with_the_check():
    # covers: ACD-2500a-5-iii
    # angle: real_artifact
    """The numbered family table and the numbered family sections list exactly the families the check runs,
    in its FAMILIES order (the pass-through record schema, evaluated first, aside), numbered 1..n, and the
    stated count matches. The doc says families are 'evaluated in the order listed', so order is compared."""
    names = [getattr(family, "NAME") for family in requirement_rule_check.FAMILIES]
    numbered = [n for n in names if n != _rc_report.FAMILY_RECORD_SCHEMA]
    text = D.read(REFERENCE)
    rows = re.findall(r"^\| (\d+) \| `([^`]+)` \|", D.section(text, "## Rule families"), re.M)
    assert [name for _, name in rows] == numbered
    headings = re.findall(r"^### (\d+)\. (.+)$", D.section(text, "## Rule families"), re.M)
    assert [name for _, name in headings] == numbered
    assert [int(n) for n, _ in rows] == list(range(1, len(numbered) + 1))
    assert f"| Rule families | {len(numbered)} rule families plus the pass-through" in text
    assert f"{NUMBER_WORDS[len(numbered)]} rule families, evaluated in the order listed" in text
