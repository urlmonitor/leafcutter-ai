"""
MODULE: test_bo_2200c_4
GOAL: RED test stubs for BO-2200c-4 — doc_links richness surfaced as existing
      docs to update / cross-link in the Agent Contracts block.

These tests are RED before the implementation of BO-2200c-4 because
_build_agent_contracts_section currently reduces doc_links to a bare path via
_extract_doc_path(), discarding relationship, status, and relevance metadata.

Target file to implement: scripts/ac_store/generate_ticket_from_ac.py
AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200c-4.yaml

Current broken behavior:
  _extract_doc_path() picks the FIRST doc_links entry's path and returns it
  as a bare string.  The resulting AC-N line is:
      - [ ] AC-1: [reference-doc] docs/reference/ac-schema.md — <constraint>
  The 'relationship', 'status', and 'relevance' fields of every entry are
  silently discarded; entries after the first are not rendered at all.

Required behavior (BO-2200c-4):
  All doc_links entries whose metadata is relevant must be surfaced in the
  documentation-expert subsection as 'existing docs to update / cross-link',
  with each entry's path, relationship, status, and relevance visible so the
  documentation-expert knows how each linked doc relates.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agent_contracts_section  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_doc_links_rich_ac() -> dict:
    """Return an AC dict whose doc_links entries carry relationship/status/relevance.

    Both entries have all three metadata fields populated.  The fixture criteria
    text deliberately avoids the literal strings 'relationship', 'status',
    'relevance', 'describes', 'exists', 'related', 'needs-update', and
    'primary reference' so that assertIn() cannot produce false positives by
    matching against the embedded gherkin block instead of the generated section.
    """
    return {
        "id": "BO-2200C4-TEST",
        "title": "doc_links richness surfaced in Agent Contracts",
        "component": "build-orchestration",
        "assigned_agent": "python-coder",
        "estimated_complexity": "M",
        "documentation_triggers": ["reference-doc"],
        "criteria": (
            "Given a documented AC whose doc_links carry structured metadata,\n"
            "When the generator writes the documentation-expert section,\n"
            "Then the existing-docs entries are shown with their metadata intact,\n"
            "And the metadata is not stripped to bare file paths."
        ),
        "doc_links": [
            {
                "path": "docs/reference/ac-schema.md",
                "relationship": "describes",
                "status": "exists",
                "relevance": "primary reference for the AC schema",
            },
            {
                "path": "docs/architecture/components/build-orchestration.md",
                "relationship": "related",
                "status": "needs-update",
                "relevance": "must be updated when new fields are added",
            },
        ],
    }


def _make_doc_agents_map() -> dict:
    """Return a pre-computed agents map that includes documentation-expert as needed."""
    return {
        "architect-review": "needed",
        "test-writer": "needed",
        "python-coder": "needed",
        "test-runner": "needed",
        "documentation-expert": "needed",
        "pr-reviewer": "needed",
        "commit": "needed",
        "pull-request": "needed",
    }


# ---------------------------------------------------------------------------
# TestDocLinksRelationshipStatusRelevancePreserved
# BO-2200c-4
# ---------------------------------------------------------------------------


class TestDocLinksRelationshipStatusRelevancePreserved(unittest.TestCase):
    """BO-2200c-4: doc_links entries with relationship/status/relevance are surfaced
    with those fields intact in the Agent Contracts block.

    RED before implementation: _build_agent_contracts_section calls _extract_doc_path()
    which returns only the first path as a bare string.  The resulting AC-N line
    carries no relationship, status, or relevance values — only:
        - [ ] AC-1: [reference-doc] docs/reference/ac-schema.md — <constraint>

    After the fix the documentation-expert subsection must render each doc_links
    entry as an 'existing docs to update / cross-link' entry that preserves all
    three metadata fields alongside its path.
    """

    def test_doc_links_relationship_status_relevance_preserved(self) -> None:
        # covers: BO-2200c-4
        """When a doc_links entry carries relationship, status, and relevance fields,
        all three must appear in the Agent Contracts section alongside the path.

        Failure: the current _extract_doc_path() discards relationship/status/relevance
        before returning, so these values will not be found in the rendered section.
        """
        ac = _make_doc_links_rich_ac()
        agents_map = _make_doc_agents_map()

        section = _build_agent_contracts_section(ac, "BO-2200C4-TEST", agents_map)

        # Precondition: the documentation-expert subsection must exist.
        self.assertIn(
            "### documentation-expert",
            section,
            "The '### documentation-expert' subsection must be present when "
            "documentation-expert is needed.\n"
            f"Actual section:\n{section}",
        )

        # Assertion 1: the 'relationship' value 'describes' (from the first doc_links
        # entry) must appear in the section.
        self.assertIn(
            "describes",
            section,
            "Expected the 'relationship' value 'describes' (from the first doc_links "
            "entry) to appear in the Agent Contracts section, but it was absent.\n\n"
            "Current broken behavior: _extract_doc_path() picks only the path and "
            "discards all metadata fields — the relationship value is never rendered.\n\n"
            "Fix: render each doc_links entry with its 'relationship' field visible in "
            "the documentation-expert subsection ('existing docs to update / cross-link').\n\n"
            f"Actual section:\n{section}",
        )

        # Assertion 2: the 'status' value 'exists' (from the first doc_links entry)
        # must appear in the section.
        self.assertIn(
            "exists",
            section,
            "Expected the 'status' value 'exists' (from the first doc_links entry) "
            "to appear in the Agent Contracts section, but it was absent.\n\n"
            "Fix: preserve the 'status' field of each doc_links entry when rendering "
            "the documentation-expert subsection.\n\n"
            f"Actual section:\n{section}",
        )

        # Assertion 3: the 'relevance' text 'primary reference' (from the first
        # doc_links entry) must appear in the section.
        self.assertIn(
            "primary reference",
            section,
            "Expected the 'relevance' text 'primary reference' (from the first "
            "doc_links entry) to appear in the Agent Contracts section, but it was absent.\n\n"
            "Fix: preserve the 'relevance' field of each doc_links entry when rendering "
            "the documentation-expert subsection.\n\n"
            f"Actual section:\n{section}",
        )


# ---------------------------------------------------------------------------
# TestDocLinksNotReducedToBarePaths
# BO-2200c-4
# ---------------------------------------------------------------------------


class TestDocLinksNotReducedToBarePaths(unittest.TestCase):
    """BO-2200c-4: The rendered existing-docs list preserves structured metadata
    rather than collapsing to bare files_touched paths.

    RED before implementation: _build_agent_contracts_section calls _extract_doc_path()
    which picks only the first doc_links path (bare string) for the AC-N line.
    Any subsequent doc_links entries and all metadata fields are dropped — the
    output looks identical to a bare files_touched listing.
    """

    def test_doc_links_not_reduced_to_bare_paths(self) -> None:
        # covers: BO-2200c-4
        """The Agent Contracts block must show ALL doc_links entries as a structured
        'existing docs to update / cross-link' list (path + relationship + status +
        relevance), NOT collapse them to a bare list of file paths.

        Two failure modes are tested simultaneously:

        1. Only the FIRST doc_links entry path appears (path-only collapse via
           _extract_doc_path's first-match behaviour) — the second entry
           'docs/architecture/components/build-orchestration.md' is absent.

        2. The 'relationship', 'status', and 'relevance' metadata fields for BOTH
           entries are absent from the section (bare-path anti-pattern).

        At least the second assertion (status 'needs-update' from the second entry)
        will be RED before any fix because _extract_doc_path never looks past the
        first entry.
        """
        ac = _make_doc_links_rich_ac()
        agents_map = _make_doc_agents_map()

        section = _build_agent_contracts_section(ac, "BO-2200C4-TEST", agents_map)

        # Precondition: the section must exist.
        self.assertIn(
            "### documentation-expert",
            section,
            "The '### documentation-expert' subsection must be present.\n"
            f"Actual section:\n{section}",
        )

        # Assertion 1a: the FIRST doc_links path must appear.
        self.assertIn(
            "docs/reference/ac-schema.md",
            section,
            "Expected the first doc_links path 'docs/reference/ac-schema.md' to "
            "appear in the Agent Contracts section.\n"
            f"Actual section:\n{section}",
        )

        # Assertion 1b: the SECOND doc_links path must also appear.
        # This fails before the fix because _extract_doc_path returns only the
        # FIRST matching path, so the second entry is completely dropped.
        self.assertIn(
            "docs/architecture/components/build-orchestration.md",
            section,
            "Expected the second doc_links path "
            "'docs/architecture/components/build-orchestration.md' to appear in the "
            "Agent Contracts section, but it was absent.\n\n"
            "Current broken behavior: _extract_doc_path() returns only the FIRST "
            "doc_links path and ignores all subsequent entries.  The second entry is "
            "never rendered, making the section an incomplete bare-path list.\n\n"
            "Fix: render ALL doc_links entries as 'existing docs to update / cross-link', "
            "not just the first one.\n\n"
            f"Actual section:\n{section}",
        )

        # Assertion 2: at least one metadata field from the SECOND entry must appear.
        # The 'status' value 'needs-update' appears only in the second entry, so its
        # presence proves that entry was rendered with structured metadata.
        self.assertIn(
            "needs-update",
            section,
            "Expected the 'status' value 'needs-update' (from the second doc_links "
            "entry) to appear in the Agent Contracts section, but it was absent.\n\n"
            "Fix: structured metadata (relationship/status/relevance) must be preserved "
            "for ALL doc_links entries, not just the first one.  The current reduction "
            "to bare paths (the files_touched anti-pattern) must be replaced with a "
            "per-entry structured rendering.\n\n"
            f"Actual section:\n{section}",
        )


if __name__ == "__main__":
    unittest.main()
