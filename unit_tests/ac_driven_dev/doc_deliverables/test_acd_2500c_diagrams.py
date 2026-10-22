"""ACD-2500c-4 and ACD-2500c-5 -- the test-design sequence diagram and the part-owners component diagram.

Both ACs are ``test_required: false`` (documentation deliverables). Each test parses the delivered mermaid
block (order of steps, nodes, who-writes-what edges) rather than checking that the file exists.
"""

from __future__ import annotations

import re

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

SEQUENCE = D.FLOWS / "c3-032-code-aware-test-design-sequence.md"
OWNERS = D.FLOWS / "c3-033-requirement-part-owners-components.md"


def _positions(block: str, markers: list[str]) -> list[int]:
    out = []
    for m in markers:
        i = block.find(m)
        assert i >= 0, f"sequence diagram lost step: {m}"
        out.append(i)
    return out


def test_ac4_sequence_shows_the_steps_in_order():
    # covers: ACD-2500c-4
    # angle: criterion
    """planner records test intent -> rule check -> (pre-pass) -> code-aware step writes design -> rule check
    -> hand-back commit, round and itpo-handback check -> approval gate -> approve_acs.py dry run, then apply
    for the released ids (ACD-300c-4) -> final commit -> build -> test writer consumes the design, in order."""
    block = D.mermaid(D.read(SEQUENCE))
    order = _positions(block, [
        "records with it_requirements and test_intent (no test_spec)",
        "RC: rule-check-itpo",
        "PF->>PP: design-prepass",
        "PF->>TD: stage-test-design-author",
        "PF->>RC: rule-check-test-design --before-ref HEAD",
        "PF->>HR: approval-holds (all ids)",
        "PF->>PF: commit test-design-handback",
        "PF->>ITPO: it-po-findings-round-N",
        "PF->>RC: rule-check-itpo-handback --stage itpo-handback",
        "PF->>User: final-gate",
        "PF->>AA: approval-holds: approve_acs.py --ids (all ids) --dry-run --json",
        "PF->>AA: approval-apply: approve_acs.py --ids (released ids only) --priority p --json",
        "PF->>PF: commit plan-feature(TEST-DESIGN, final)",
        "Note over PF,TW: build",
        "TW->>TW: reads test_spec",
    ])
    assert order == sorted(order), f"steps out of order: {order}"
    assert "participant AA as approve_acs.py" in block
    assert "apply-approval" not in block and "status-checker" not in block, "the retired agent edit is still drawn"


def test_ac4_sequence_shows_pending_branch_at_gate_and_at_test_writer():
    # covers: ACD-2500c-4
    # angle: criterion
    """'test design pending' is shown at the approval gate (held reasons) and at the test writer (halts)."""
    block = D.mermaid(D.read(SEQUENCE))
    gate_at = block.index("PF->>User: final-gate")
    tw_alt = block.index("alt record has test_intent and no test_spec")
    gate_note = block.index("held reasons, first match wins: test design pending")
    assert gate_at < gate_note < tw_alt
    tw_branch = block[tw_alt:]
    assert "halts with test design pending (status blocker)" in tw_branch
    assert "writes no test" in tw_branch


def test_ac4_sequence_shows_file_aware_checks_in_the_same_pre_approval_step():
    # covers: ACD-2500c-4
    # angle: criterion
    """File findings and the reference-file choice run in the same test-designer dispatch; findings are
    handed back to the planner; the approval gate is reached only after the decisions; the pre-pass is its
    own step before the agent; the page is linked next to c3-008."""
    text = D.read(SEQUENCE)
    block = D.mermaid(text)
    assert "Group 2 file findings (verdict per declared file, reference-file choice" in block
    assert "PF->>ITPO: it-po-findings-round-N" in block
    assert block.index("it-po-findings-round-N") < block.index("PF->>User: final-gate")
    assert block.index("participant PP as design_prepass.py") < block.index("participant TD as test-designer")
    assert block.index("PF->>PP: design-prepass") < block.index("PF->>TD: stage-test-design-author")
    comp = D.read(D.COMPONENT_DOC)
    assert comp.index("c3-008-plan-feature-decision-gate-sequence.md)") < comp.index("c3-032-code-aware-test-design-sequence.md)")


def _boundary(block: str, title: str) -> str:
    m = re.search(r'Container_Boundary\(\w+, "' + re.escape(title) + r'"\) \{(.*?)\n    \}', block, re.DOTALL)
    assert m, f"no boundary {title!r}"
    return m.group(1)


def test_ac5_owners_diagram_shows_each_part_and_its_single_writer():
    # covers: ACD-2500c-5
    # angle: criterion
    """Each of the seven requirement parts is one node, written by exactly one owner."""
    block = D.mermaid(D.read(OWNERS))
    expected = {"crit": {"pb"}, "route": {"itpo"}, "tech": {"itpo"}, "intent": {"itpo"},
                "design": {"td"}, "find": {"td"}, "rcf": {"rc"}}
    titles = {"crit": "Criteria", "route": "Routing and contracts", "tech": "Technical requirements",
              "intent": "Test intent and finding decisions", "design": "Test design",
              "find": "File findings and reference file", "rcf": "Rule-checked fields"}
    for part, owners in expected.items():
        assert f'ComponentDb({part}, "{titles[part]}"' in block, f"part node missing: {titles[part]}"
        writers = set(re.findall(rf"Rel\((\w+), {part}, \"(?:writes|repairs[^\"]*)\"\)", block))
        assert writers == owners, f"{titles[part]} written by {writers}, expected exactly {owners}"


def test_ac5_owners_diagram_shows_who_may_read_source_and_who_may_not():
    # covers: ACD-2500c-5
    # angle: criterion
    """test-designer and test-writer sit in the 'may read source' boundary; planner, rule check and pre-pass
    in the 'may not' boundary; the page is linked from the component doc."""
    block = D.mermaid(D.read(OWNERS))
    yes = _boundary(block, "May read source code")
    no = _boundary(block, "May not read source code")
    for node in ("td", "tw"):
        assert f"Component({node}," in yes and f"Component({node}," not in no
    for node in ("pb", "itpo", "rc", "pp"):
        assert f"Component({node}," in no and f"Component({node}," not in yes
    assert "ADR-009" in no
    assert "c3-033-requirement-part-owners-components.md" in D.read(D.COMPONENT_DOC)
