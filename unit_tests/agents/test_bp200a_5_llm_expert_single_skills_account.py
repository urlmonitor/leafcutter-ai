"""BP-200a-5 is SUPERSEDED by AR-300c-1 / AR-300a-4 (BrainCandy, 2026-10-09).

BP-200a-5 required a hand-written "## Skills" table in llm-expert's template
body. AR-300a-4 forbids two competing accounts of what an agent may use, and
AR-300c-1 declares abilities once, in the template frontmatter `skills:`, with
one delivered "## Your Available Skills" section. This file pins the intent of
BP-200a-5 (llm-expert knows exactly these three skills and when each applies)
through that mechanism. Moved out of test_llm_expert_artifacts.py (size ratchet).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]
_LLM_EXPERT_TEMPLATE = _ROOT / "templates" / "agents" / "llm-expert.md"


def test_bp200a_5_skills_table_lists_exactly_three():
    # covers: AR-300a-4
    # covers: BP-200a-5
    # angle: seam
    """llm-expert declares exactly three skills in frontmatter; the REAL compiler
    delivers exactly ONE skills section naming each; signoff is `always`, the
    other two `conditional` with a non-empty condition; the template body carries
    no hand-written skills section. No SKILL.md path column is asserted."""
    sys.path.insert(0, str(_ROOT / "unit_tests" / "prompt_assembly"))
    import _ar_300ad_support as support  # reuses the compile + account helpers

    expected = {"add-agent-to-package", "add-skill-to-package", "signoff"}
    template = _LLM_EXPERT_TEMPLATE  # module global read at call time (probe seam)

    # (1) frontmatter declares exactly the three skills, once each.
    entries = support.declared_entries(support.template_frontmatter(template))
    ids = [e["skill_id"] for e in entries]
    assert sorted(ids) == sorted(expected), f"frontmatter skills: must be exactly {sorted(expected)}, got {ids}"

    # (2) compiled prompt (real compiler, in-process) has exactly ONE account naming all three.
    installed = support.installed_skill_ids(_ROOT)
    compiled = support.compile_with(template, agents=None, skills_root=_ROOT / "templates" / "skills")
    accts = support.accounts(compiled, installed)
    assert len(accts) == 1, f"expected exactly 1 skills section in compiled prompt, got {[a['heading'] for a in accts]}"
    assert len(support.abilities_heading_lines(compiled)) == 1
    assert sorted(accts[0]["ids"]) == sorted(expected), f"compiled section names {accts[0]['ids']}"

    # (3) each row says WHEN it applies (cells split on unescaped pipes).
    rows = support.ability_rows(compiled, installed)
    for skill in expected:
        assert len(rows.get(skill, [])) == 1, f"{skill}: expected one compiled row, got {rows.get(skill)}"
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", rows[skill][0])[1:-1]]
        assert cells[0] == skill and len(cells) >= 3, f"{skill}: row is not Skill|Mode|Description: {cells}"
        mode = cells[1]
        if skill == "signoff":
            assert mode == "always", f"signoff must be `always`, got {mode!r}"
        else:
            head, _, cond = mode.partition(":")
            assert head.strip() == "conditional", f"{skill} must be conditional, got {mode!r}"
            assert cond.strip(), f"{skill}: conditional row carries no condition text"

    # (4) no second, hand-written account in the template body.
    _, body = support.parse_frontmatter(template.read_text(encoding="utf-8"))
    assert support.accounts(body, installed) == [], "template body still hand-writes a skills table"
    assert support.abilities_heading_lines(body) == [], "template body still has a skills/abilities heading"
