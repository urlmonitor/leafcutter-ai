"""
MODULE: unit_tests/evals/tq200d1ii/test_tq200d1ii_index.py
GOAL: RED test for TQ-200d-1-ii: docs/reference/README.md lists the hub exactly once (under "Testing,
    Proof & False-Green Discipline", no family page listed) and each family page links back to the hub.
Target: docs/reference/README.md, docs/reference/produced-tests-eval-assertion-kinds*.md
"""

from __future__ import annotations

import re

import unit_tests.evals.tq200d1ii._helpers as h
import unit_tests.evals.tq200d1ii._pageset as ps

INDEX = h.REPO_ROOT / "docs" / "reference" / "README.md"
HUB_ROW = f"| [{h.HUB}]({h.HUB}) | What an assertion kind is, and the four family pages that hold one entry per kind. |"
HUB_TARGET = re.compile(r"\]\([^)\s]*" + re.escape(h.HUB) + r"[^)\s]*\)")


def gold_index() -> str:
    """The real index with one hub row after the wrong-version-runs row (unchanged when it lists the hub already)."""
    text = INDEX.read_text(encoding="utf-8")
    if h.HUB in text:
        return text
    return re.sub(r"^(\| \[wrong-version-runs\.md\].*)$", lambda m: m.group(1) + "\n" + HUB_ROW, text, count=1, flags=re.M)


def in_testing_section(index: str) -> bool:
    """The hub is linked under the 'Testing, Proof & False-Green Discipline' heading."""
    return any(h.resolves_to(t, h.REF_DIR, f"{h.REF_DIR}/{h.HUB}") for t in h.links_in(h.section(index, "Testing, Proof")))


def test_reference_index_lists_the_hub_once():
    # covers: TQ-200d-1-ii
    # angle: real_artifact
    # must_catch: hub missing from the reference index; hub listed twice; a family page listed instead of the hub; a family page without a link back
    """The REAL index lists the hub once and every real family page links back; each break is caught by name."""
    real_index = INDEX.read_text(encoding="utf-8")
    assert h.check_index(real_index, h.read_real_pages()) == set(), "the real index and family pages must satisfy the rules"
    assert in_testing_section(real_index)
    pages = ps.gold_pages()
    gold = gold_index()
    assert h.check_index(gold, pages) == set() and in_testing_section(gold)
    row = next(ln for ln in gold.splitlines() if h.HUB in ln)
    assert h.check_index(gold.replace(row + "\n", ""), pages) == {("hub_lines:0", "")}
    assert h.check_index(gold.replace(row, row + "\n" + row), pages) == {("hub_lines:2", "")}
    fam = h.FAMILY_PAGE["test-writer"]
    instead = gold.replace(row, row.replace(h.HUB, fam))
    assert h.check_index(instead, pages) == {("hub_lines:0", ""), ("family_in_index", fam)}
    # the hub row filed under another section of the index
    moved = gold.replace(row + "\n", "") + "\n## Elsewhere\n\n" + row + "\n"
    assert not in_testing_section(moved)
    # a family page that does not link back to the hub
    name = h.FAMILY_PAGE["sql-test-writer"]
    unlinked = {**pages, name: HUB_TARGET.sub("](#top)", pages[name])}
    assert h.check_index(gold, unlinked) == {("no_back_link", name)}
    # control: a ./ prefix and a fragment still resolve to the hub
    dotted = HUB_TARGET.sub(f"](./{h.HUB}#top)", gold)
    assert h.check_index(dotted, pages) == set() and in_testing_section(dotted)
