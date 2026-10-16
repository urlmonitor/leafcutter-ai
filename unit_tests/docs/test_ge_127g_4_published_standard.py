"""
MODULE: unit_tests/docs/test_ge_127g_4_published_standard.py
COVERS: GE-127g-4 -- an author can find out before committing whether their
    document is judged for length, and on what stated ground it would not be.

GOAL: Regression guard on the PUBLISHED page. GE-127g-4 is test_required: false
    and was verified at delivery by an independent review that ran the gate;
    this test only stops the page from later losing the statements the record
    requires. It reads the published prose and nothing else.

DELIBERATELY NOT A PARITY CHECK: it never reads commit_guardian.json and never
    compares the page with the configuration. GE-127g-4's it_requirements fence
    that off explicitly (a document-side published-versus-configured gate belongs
    under GE-127d), so the locations below are the ones GE-127g-4 itself requires
    the page to list, not ones read from the declaration.

What it catches: the page or its pointer removed; a declared location dropped
    from the listing; the ground restated as a generator name only (no earning
    property); the above-bound outcome inverted into a refusal; the mandatory
    report size or the no-edit property dropped; the judged-document limit
    dropped.

DECISION HISTORY
- 2026-10-14 [GE-127g-4]: Initial authoring.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PAGE = _REPO_ROOT / "docs" / "reference" / "document-length-standard.md"
_HOOKS_PAGE = _REPO_ROOT / "docs" / "pre-commit-hooks.md"

# The three locations GE-127g-4's it_requirements require the page to list.
_REQUIRED_LOCATIONS = ("docs/agents/cards/", "docs/roadmap.md", "docs/INDEX.md")


def _page_text() -> str:
    return _PAGE.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """Body of the `## heading` section, up to the next `## ` heading."""
    match = re.search(rf"^## {re.escape(heading)}\s*$(.*?)(?=^## |\Z)", text, re.M | re.S)
    assert match, f"published page has no '## {heading}' section"
    return match.group(1)


def test_published_standard_is_reachable_from_the_hooks_page():
    # covers: GE-127g-4
    """The page exists and the hooks reference an author already reads points at it."""
    assert _PAGE.is_file(), f"{_PAGE.relative_to(_REPO_ROOT)} is missing"
    assert "reference/document-length-standard.md" in _HOOKS_PAGE.read_text(encoding="utf-8")


def test_every_set_aside_location_is_listed_with_its_earning_property():
    # covers: GE-127g-4
    """Arm 1: each location is listed, and the ground is the property that earns
    the exemption (regenerated whole, no human author) -- not only a generator name."""
    section = _section(_page_text(), "Set-aside locations")
    missing = [loc for loc in _REQUIRED_LOCATIONS if f"`{loc}`" not in section]
    assert not missing, f"set-aside locations not listed: {missing}"
    lowered = section.lower()
    assert "regenerated whole" in lowered and "no human author" in lowered
    assert "needs no change to the declaration" in lowered


def test_the_bound_is_stated_as_reported_never_refused_and_mandatory():
    # covers: GE-127g-4
    """Arm 2: a bound applies per location; standing above it is reported and the
    commit still completes; declaring a location requires declaring that size."""
    text = _page_text()
    bound = _section(text, "The bound on a set-aside location")
    above_row = next(
        (line for line in bound.splitlines() if line.startswith("| A document above the bound")),
        "",
    )
    assert above_row, "the bound table has no row for a document above the bound"
    assert "Reported" in above_row and "never refuses" in above_row, above_row
    assert "per entry, not globally" in bound
    declaring = _section(text, "Declaring a location").lower()
    assert "only together with both its ground and its report size" in declaring


def test_a_document_in_no_declared_location_is_stated_as_judged_with_its_limit():
    # covers: GE-127g-4
    """Arm 3: an author outside every declared location learns it is judged and the limit."""
    section = _section(_page_text(), "A document in no declared location")
    assert "is judged" in section
    assert "300 lines" in section and "400" in section and "25 sections" in section
