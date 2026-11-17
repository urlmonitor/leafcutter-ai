"""TKT-600a-4 -- the ADR-010 amendment (declared_files -> files_touched; doc_links the labelled legacy path).

The AC is ``test_required: false`` (an ADR amendment). Each test reads ADR-010 and asserts one clause of the
AC's criteria is actually stated; the link test resolves every link of the amendment against the tree.
"""

from __future__ import annotations

import re

from unit_tests.ac_driven_dev.doc_deliverables import _doc_support as D

ADR = D.REPO / "docs" / "architecture" / "adrs" / "ADR-010-ac-store-as-authoritative-backlog.md"
HEADING = "Amendment 1 — 2026-10-12"


def _amendment() -> str:
    return D.section(D.read(ADR), HEADING)


def test_declared_list_is_the_files_touched_list_in_order_and_nothing_else():
    # covers: TKT-600a-4
    # angle: criterion
    """For a record that declares its files, files_touched is that list in declared order, with no
    doc_links path, no technical-requirement prose path and no reference file path; the R example is named."""
    sec = D.flat(_amendment())
    assert "`files_touched` MUST be exactly that list's paths, in declared order, and nothing else" in sec
    assert "MUST NOT add a `doc_links` path, a path named in `it_requirements` prose, or `reference_file_path`" in sec
    assert sec.index("`scripts/ac_store/scan_ac_store.py` (`existing`)") < sec.index(
        "`unit_tests/ac_store/test_hold_reasons.py` (`to_be_created`)")


def test_doc_links_derivation_is_the_labelled_legacy_path_for_no_declared_files_only():
    # covers: TKT-600a-4
    # angle: criterion
    """The documentation-link derivation is named the legacy path, run only for 'no declared files', and
    labelled 'derived, not declared'; an example L is given."""
    sec = D.flat(_amendment())
    assert "is the legacy path" in sec
    assert 'It MUST run only for a record in the "no declared files" state' in sec
    assert 'labelled "derived, not declared"' in sec
    assert "`scripts/build.py` as `modifies` gets `scripts/build.py`, labelled derived" in sec


def test_no_unqualified_doc_links_maps_to_files_touched_sentence_remains():
    # covers: TKT-600a-4
    # angle: criterion
    """Both original statements (Context and Consequences / Positive) still exist and each carries the
    'no declared files' qualification or points to the amendment."""
    text = D.read(ADR)
    # Context: "`doc_links` (maps to `files_touched`"; Consequences: "`doc_links → files_touched`"
    pattern = re.compile(r"`doc_links(?:`\s*\(maps to\s*`|\s*(?:→|->)\s*)files_touched")
    hits = [m.start() for m in pattern.finditer(text)]
    original = [h for h in hits if h < text.index(f"## {HEADING}")]
    assert len(original) == 2, f"expected the Context and Consequences statements, found {len(original)}"
    for h in original:
        window = D.flat(text[h:h + 400])
        assert 'only for a record in the "no declared files" state' in window, window[:120]
        assert "Amendment 1" in window


def test_known_issue_named_and_stays_open():
    # covers: TKT-600a-4
    # angle: criterion
    """KI-ACS-002 is named as the issue the legacy derivation still carries and stays open."""
    sec = D.flat(_amendment())
    assert "KI-ACS-002 is the known issue it still carries, and that issue stays open" in sec
    assert 'for every record in the "no declared files" state' in sec


def test_deciding_records_are_links_that_resolve_to_existing_files():
    # covers: TKT-600a-4
    # angle: criterion
    """ACD-1600c-4, TKT-600a-3, TKT-600a-3-i and KI-ACS-002 are each a relative link that resolves from the
    ADR's directory to an existing file, and each is also in the frontmatter related_docs."""
    sec = _amendment()
    links = dict(re.findall(r"\[([A-Za-z0-9-]+)\]\((\.\./[^)]+)\)", sec))
    text = D.read(ADR)
    for name in ("ACD-1600c-4", "TKT-600a-3", "TKT-600a-3-i", "KI-ACS-002"):
        assert name in links, f"amendment does not link {name}"
        target = (ADR.parent / links[name]).resolve()
        assert target.is_file(), f"{name} link does not resolve: {links[name]}"
    related = text.split("---", 2)[1]
    for fname in ("ACD-1600c-4.yaml", "TKT-600a-3.yaml", "TKT-600a-3-i.yaml", "open-high-ki-acs-002.md"):
        assert fname in related, f"frontmatter related_docs lacks {fname}"


def test_amendment_is_a_dated_separate_section_and_original_decision_is_preserved():
    # covers: TKT-600a-4
    # angle: criterion
    """The amendment is its own dated level-2 section; the 2026-06 Context, Decision, Consequences and
    Alternatives sections are all still present and readable."""
    text = D.read(ADR)
    assert re.search(r"^## Amendment 1 — 2026-10-12 — ", text, re.MULTILINE)
    for heading in ("## Status", "## Context", "## Decision", "## Consequences", "## Alternatives"):
        assert re.search(rf"^{re.escape(heading)}$", text, re.MULTILINE), f"original section gone: {heading}"
    assert text.index("## Decision") < text.index(f"## {HEADING}")
    assert "`doc_links` (maps to `files_touched`;" in text, "the 2026-06 wording must stay readable"
