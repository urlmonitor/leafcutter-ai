"""AR-400b-5 -- the reference states the own-grant comparison (content checks).

The AC is a documentation deliverable. Each test reads the delivered section of
docs/reference/specialist-ability-references.md and asserts that one clause of the
AC's criteria is stated there. The worked example's finding line is also checked
against the real gate's wording (the kind phrase the gate prints).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PAGE = REPO / "docs" / "reference" / "specialist-ability-references.md"
MAIN = REPO / "docs" / "reference" / "agent-template-frontmatter.md"


def _section(heading: str) -> str:
    text = PAGE.read_text(encoding="utf-8")
    start = text.index(heading)
    nxt = re.search(r"\n## ", text[start + len(heading):])
    end = start + len(heading) + nxt.start() if nxt else len(text)
    return re.sub(r"\s+", " ", text[start:end])


def test_reference_states_grant_is_own_declaration_not_registry():
    # covers: AR-400b-5
    # angle: criterion
    """The grant compared is the specialist's own skills:, and editing the registry neither causes nor clears it."""
    sec = _section("## Comparing an instruction with the grant")
    assert "the `skills:` declaration in the specialist's own definition" in sec
    assert "editing the registry neither causes nor clears a \"not granted\" finding" in sec


def test_reference_states_skill_tool_is_required_for_a_grant():
    # covers: AR-400b-5
    # angle: criterion
    """A non-empty grant also needs the Skill tool among the permitted tools."""
    sec = _section("## Comparing an instruction with the grant")
    assert "A non-empty grant also needs `Skill` among the specialist's `tools:`" in sec


def test_reference_gives_both_worked_fixes():
    # covers: AR-400b-5
    # angle: criterion
    """One worked fix adds the grant, one corrects the instruction; the quoted finding uses the gate's phrase."""
    sec = _section("## Comparing an instruction with the grant")
    assert "### Worked example: fix by adding the grant" in sec
    assert "### Worked example: fix by correcting the instruction" in sec
    assert "ability exists but is not granted" in sec


def test_main_frontmatter_reference_links_the_page():
    # covers: AR-400b-5
    # angle: reachability
    """The frontmatter reference an author reads first links to the detailed page."""
    assert "specialist-ability-references.md" in MAIN.read_text(encoding="utf-8")
