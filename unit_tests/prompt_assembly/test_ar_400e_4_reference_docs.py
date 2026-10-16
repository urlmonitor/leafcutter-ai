"""AR-400e-4 -- the registry and frontmatter references name ONE derived abilities list
(TDD red phase). The AC is ``test_required: false`` (documentation), so this is a single
content check over the reference tree; the second clause is, per the AC's own notes, "checkable
by a search over the reference docs". Historical records (ADRs, changelogs, AC notes,
known-issues) are out of scope: only ``docs/reference/**`` is read.

The ``{{my_skills_used}}`` template token is a different, retired injection token (not the
registry field) and is removed from the text before the search.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
REFERENCE = REPO_ROOT / "docs" / "reference"
FRONTMATTER_PAGE = REFERENCE / "agent-template-frontmatter.md"
FIELD = re.compile(r"(?<![A-Za-z_])skills_used")


def _blocks(text: str) -> list[str]:
    """Paragraphs; each table row is its own block (a row must stand on its own)."""
    out: list[str] = []
    for para in re.split(r"\n\s*\n", text):
        rows = [ln for ln in para.splitlines() if ln.lstrip().startswith("|")]
        out += rows if rows and len(rows) == len(para.splitlines()) else [para]
    return out


def test_references_state_one_derived_field_and_skills_used_retired_and_refused():
    # covers: AR-400e-4
    # angle: criterion
    """Every block under docs/reference/** that mentions the registry field skills_used says it
    is retired or refused (none presents it as current, an alias, or readable); the frontmatter
    reference states that `skills:` derives the one field skills_invoked and that skills_used is
    retired and refused by the registry validator; its derivation diagram has ONE arrow to ONE
    field. Control: the scan reads a populated reference tree (more than ten pages)."""
    pages = sorted(REFERENCE.rglob("*.md"))
    assert len(pages) > 10, f"control: only {len(pages)} reference pages scanned"
    assert FRONTMATTER_PAGE.is_file()
    offenders: list[str] = []
    for page in pages:
        text = page.read_text(encoding="utf-8").replace("{{my_skills_used}}", "").replace("my_skills_used", "")
        for block in _blocks(text):
            if FIELD.search(block) and not re.search(r"retired|refus", block, re.I):
                offenders.append(f"{page.relative_to(REPO_ROOT)}: {block.strip().splitlines()[0][:110]}")
    page_text = FRONTMATTER_PAGE.read_text(encoding="utf-8")
    stated = [b for b in _blocks(page_text)
              if FIELD.search(b) and "skills_invoked" in b and re.search(r"retired", b, re.I)
              and re.search(r"refus", b, re.I) and re.search(r"validator", b, re.I)]
    arrows = [ln for ln in page_text.splitlines() if ln.startswith("skills:") and "derives" in ln]
    arrow_problems = [ln for ln in arrows
                      if "skills_invoked" not in ln.split("derives")[-1] or FIELD.search(ln.split("derives")[-1])
                      or "/" in ln.split("derives")[-1]]
    assert arrows, "the derivation diagram line was not found"
    assert not offenders, f"{len(offenders)} block(s) present skills_used as current:\n" + "\n".join(offenders)
    assert stated, "frontmatter reference does not state skills_used is retired and refused by the validator"
    assert not arrow_problems, f"derivation diagram must show one arrow to skills_invoked: {arrow_problems}"
