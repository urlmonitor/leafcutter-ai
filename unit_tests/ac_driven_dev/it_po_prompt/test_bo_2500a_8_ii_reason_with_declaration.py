"""
MODULE: unit_tests/ac_driven_dev/it_po_prompt/test_bo_2500a_8_ii_reason_with_declaration.py
GOAL: BO-2500a-8-ii - the technical planner's instructions (templates/agents/it-po.md) direct it to write
    `test_required: false` together with a `test_rationale`, as one declaration, never the first alone.
BUSINESS CONTEXT: The planner is the author of test-free declarations. Instructions that describe the
    flag alone produce the reasonless records the commit-time check (BO-2500a-8-i) now refuses.
ARCHITECTURE: Template structure is read through the paragraph helpers of the sibling prompt tests; the
    rendered prompt comes from the real scripts/render_effective_prompt.py CLI. The live-model half of the
    proof lives in test_bo_2500a_8_ii_live_model.py (marker live_model, deselected by default).
"""

from __future__ import annotations

import re
from pathlib import Path

from unit_tests.ac_driven_dev.test_designer_prompt import _file_findings_prompt_support as S

FALSE_DECLARATION = re.compile(r"test_required\W{0,3}false", re.IGNORECASE)
ITEM_START = re.compile(r"^\s*(?:[-*]\s|\d+\.\s|\[ \]\s*\d+\.\s)")
RECORD = "ACD-2500e-2"


def items(text: str) -> list[str]:
    """Every paragraph, list item and checklist item of `text`, flattened."""
    found: list[str] = []
    for block in re.split(r"\n\s*\n", text):
        current: list[str] = []
        for line in block.splitlines():
            if ITEM_START.match(line) and current:
                found.append(S.flat(" ".join(current)))
                current = []
            current.append(line)
        if current and any(part.strip() for part in current):
            found.append(S.flat(" ".join(current)))
    return found


def declaring(text: str) -> list[str]:
    return [item for item in items(text) if FALSE_DECLARATION.search(item)]


def test_every_passage_declaring_test_required_false_presents_it_with_a_test_rationale() -> None:
    # covers: BO-2500a-8-ii
    # angle: criterion
    """Section 2.7, the S7 write rule and S8 checklist item 12 each pair test_required false with test_rationale."""
    body = S.template("it-po")
    passages = {
        "2.7 paragraph": [i for i in declaring(body) if "genuinely produces no executable behaviour" in i],
        "S7 write rule": [i for i in declaring(body) if "see 2.7" in i],
        "S8 item 12": [i for i in declaring(body) if i.startswith("[ ] 12.")],
    }
    missing = {name: len(found) for name, found in passages.items() if len(found) != 1}
    assert not missing, f"expected exactly one passage each, found: {missing}"
    lacking = [name for name, (item,) in passages.items() if "test_rationale" not in item]
    assert not lacking, f"passage(s) describe test_required: false without test_rationale: {lacking}"
    (section,) = passages["2.7 paragraph"]
    assert re.search(r"together|one declaration|as a pair|alongside", section, re.IGNORECASE), (
        "section 2.7 must present the two fields as one declaration, not as separate settings")


def test_no_passage_anywhere_in_the_template_describes_test_required_false_as_complete_alone() -> None:
    # covers: BO-2500a-8-ii
    # angle: boundary
    """Every passage of the whole template that mentions test_required false also carries test_rationale."""
    found = declaring(S.template("it-po"))
    assert found, "the template no longer mentions test_required: false at all"
    alone = [item[:140] for item in found if "test_rationale" not in item]
    assert not alone, f"{len(alone)} of {len(found)} passage(s) lack test_rationale: {alone}"


def test_rendered_planner_prompt_carries_the_declaration_instruction(tmp_path: Path) -> None:
    # covers: BO-2500a-8-ii
    # angle: reachability
    """The prompt the planner receives (real render CLI) pairs every test_required false passage with test_rationale."""
    rendered = S.rendered_prompt_paragraphs("it-po", RECORD, tmp_path)
    mentioning = [p for p in rendered if FALSE_DECLARATION.search(p)]
    assert mentioning, "the rendered it-po prompt never mentions test_required: false"
    alone = [p[:140] for p in mentioning if "test_rationale" not in p]
    assert not alone, f"{len(alone)} of {len(mentioning)} rendered paragraph(s) lack test_rationale: {alone}"
