"""ACD-2500a-4 and ACD-2500a-5 -- the requirement rule check's component diagram and reference doc.

Both ACs are ``test_required: false`` (documentation deliverables). Each test reads the delivered page and
asserts one clause of the AC's criteria is actually stated; the family names are read from the real
``_rc_report`` module, so a family added to the check but missing from the doc turns the reference test red.
"""

from __future__ import annotations

import re
import sys

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

DIAGRAM = D.FLOWS / "c3-030-requirement-rule-check-components.md"
REFERENCE = D.REPO / "docs" / "reference" / "requirement-rule-check.md"

sys.path.insert(0, str(D.REPO / "scripts" / "ac_store"))
import _rc_report  # noqa: E402

FAMILIES = [v for k, v in vars(_rc_report).items() if k.startswith("FAMILY_") and isinstance(v, str)]


def test_ac_a4_diagram_shows_stages_check_rule_source_map_and_store_checks():
    # covers: ACD-2500a-4
    # angle: criterion
    """The diagram has a node for each: authoring stages, the check, the rule source (one node), the
    surface-to-specialist map (one node) and the existing store check it extends; it is linked from the
    component doc."""
    block = D.mermaid(D.read(DIAGRAM))
    for node in ('Component(stages, "Authoring stage loop"', 'Component(rrc, "runRuleCheck"',
                 'Component(cli, "requirement_rule_check.py"', 'ComponentDb(rules, "Rule source"',
                 'ComponentDb(smap, "Surface-to-specialist map"', 'Component(vas, "validate_ac_schema.py"'):
        assert node in block, f"diagram lost node {node}"
    assert len(re.findall(r"ComponentDb\(rules,", block)) == 1, "rule source must be exactly one node"
    assert len(re.findall(r"ComponentDb\(smap,", block)) == 1, "surface map must be exactly one node"
    assert "c3-030-requirement-rule-check-components.md" in D.read(D.COMPONENT_DOC)


def test_ac_a4_diagram_marks_which_families_repair_and_which_only_report():
    # covers: ACD-2500a-4
    # angle: criterion
    """The repairing and report-only family nodes are labelled as such, and the repairing node names the
    three repairing modules while the report-only node names the others."""
    text = D.read(DIAGRAM)
    block = D.mermaid(text)
    repair = re.search(r'Component\(repair, "Repairing families - REPAIRS", "([^"]+)"', block)
    report = re.search(r'Component\(report, "Report-only families - REPORT ONLY", "([^"]+)"', block)
    assert repair and report, "repair / report-only nodes missing"
    for mod in ("_rc_backlinks", "_rc_components", "_rc_readiness"):
        assert mod in repair.group(1)
    for mod in ("_rc_record_schema", "_rc_contracts", "_rc_doc_triggers", "_rc_declared"):
        assert mod in report.group(1)
    assert "**Repairs.**" in text and "**Report only.**" in text


def test_ac_a4_diagram_shows_failed_check_keeps_stage_open():
    # covers: ACD-2500a-4
    # angle: criterion
    """A not-passed result loops back to the stage (retry or error) and the commit is reachable only when
    passed."""
    text = D.read(DIAGRAM)
    block = D.mermaid(text)
    assert 'Rel(rrc, stages, "10. not passed:' in block
    assert "status error with failed_check" in block
    assert 'Rel(stages, commit, "11. only when passed' in block
    assert "A failed check keeps the stage open" in text


def test_ac_a5_reference_lists_every_rule_family_with_its_disposition():
    # covers: ACD-2500a-5
    # angle: criterion
    """Every rule family the check really has (read from _rc_report) appears in the family table, and the
    table states the 'fixed' and 'needs a decision' dispositions."""
    assert len(FAMILIES) >= 10, "control: _rc_report should expose the check's families"
    sec = D.section(D.read(REFERENCE), "Rule families")
    for fam in FAMILIES:
        assert f"`{fam}`" in sec, f"requirement-rule-check.md does not list family {fam!r}"
    assert "`fixed`" in sec and "`needs a decision`" in sec


def test_ac_a5_reference_states_finding_format_and_cli_report_shape():
    # covers: ACD-2500a-5
    # angle: criterion
    """It states the finding format (file, record id, rule family, disposition), the CLI and the JSON shape."""
    text = D.read(REFERENCE)
    D.assert_all(text, ["states **file, record id, rule family, disposition**",
                        "python scripts/ac_store/requirement_rule_check.py --stage",
                        '"verdict"', '"records_checked"', '"findings"', "Exit codes"], "requirement-rule-check.md")


def test_ac_a5_reference_states_zero_records_and_unreadable_record_outcomes():
    # covers: ACD-2500a-5
    # angle: criterion
    """The fail-closed table states both outcomes: zero records checked and an unreadable record."""
    sec = D.flat(D.section(D.read(REFERENCE), "Fail-closed paths"))
    assert "Zero records checked | `record readable`" in sec
    assert "no requirement records found at" in sec
    assert "Unreadable record (YAML error, bad encoding, no top-level `id`) | `record readable`" in sec
    assert "The file still counts in `records_checked`" in sec


def test_ac_a5_reference_names_owner_of_each_shared_rule_and_planner_keeps_contract_judgement():
    # covers: ACD-2500a-5
    # angle: criterion
    """The ownership table names the existing store check per shared rule, and the doc states that judging
    whether two contract descriptions agree stays with the technical planner."""
    text = D.read(REFERENCE)
    owners = D.flat(D.section(text, "Which store check owns a shared rule"))
    for owner in ("validate_ac_schema._validate_file", "check_ac_parent_covered_by",
                  "assignment_quality.resolve_craft_in", "declared_files.get_declared_files", "check_ac_governance"):
        assert owner in owners, f"ownership table lost {owner}"
    assert "Judging whether two contract descriptions agree stays with the technical planner." in D.flat(text)
