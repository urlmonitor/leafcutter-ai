"""
Tests for BO-2200c-2: Each contract line names a genre, a target doc path,
and a content constraint.

These tests are RED before the implementation of BO-2200c-2 because
_build_agent_contracts_section currently emits only '- [ ] AC-1: {title}' --
no Diataxis genre, no target documentation path, and no content constraint
derived from the leaf AC criteria.

Target file to implement: scripts/ac_store/generate_ticket_from_ac.py
AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200c-2.yaml
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_agent_contracts_section  # noqa: E402


# ---------------------------------------------------------------------------
# Valid genre vocabulary (documentation_triggers enum + 'explanation')
# ---------------------------------------------------------------------------

#: Valid Diataxis genre values per BO-2200c-2.
#: Source: config/ac_store_schema.json documentation_triggers enum plus
#: 'explanation' (the sixth value permitted by BO-2200c-2 but not in the
#: schema enum because it is not a trigger type, only a valid genre label).
_VALID_GENRES: frozenset[str] = frozenset({
    "how-to",
    "reference-doc",
    "sequence-diagram",
    "state-diagram",
    "component-diagram",
    "explanation",
})


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_documented_ac() -> dict:
    """Return a minimal AC dict for a ticket that carries documentation_triggers.

    The AC is designed so that:
    - The 'title' field contains a unique string ('UNIQUE-TITLE-TEXT') that
      does NOT appear in the criteria and is NOT a valid genre keyword.  This
      lets tests distinguish between the old behaviour (uses the title) and the
      new behaviour (uses genre + path + criteria-derived constraint).
    - The 'documentation_triggers' field carries a single genre ('how-to').
    - The 'doc_links' field carries an edit-surface path under docs/how-to/.
    - The 'criteria' field contains Then/And clauses from which a content
      constraint should be derived.

    IMPORTANT: The criteria text must NOT contain the string 'UNIQUE-TITLE-TEXT'
    so that 'assertNotIn' checks can reliably detect whether the AC-N line was
    populated from the title vs. from the criteria.
    """
    return {
        "id": "BO-2200C2-TEST",
        "title": "UNIQUE-TITLE-TEXT",
        "component": "build-orchestration",
        "assigned_agent": "python-coder",
        "estimated_complexity": "M",
        "documentation_triggers": ["how-to"],
        "criteria": (
            "Given a documented AC is being generated,\n"
            "When the generator builds the documentation-expert contract block,\n"
            "Then the contract line names the Diataxis genre required,\n"
            "And the contract line names a documentation path with slash separator,\n"
            "And the contract line names a content constraint derived from AC criteria."
        ),
        "doc_links": [
            {
                "path": "docs/how-to/ac-coverage-guide.md",
                "relationship": "creates",
                "status": "missing",
            }
        ],
    }


def _make_doc_agents_map() -> dict:
    """Return a pre-computed agents map with documentation-expert as needed."""
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
# TestContractLineNamesGenrePathAndConstraint
# BO-2200c-2
# ---------------------------------------------------------------------------


class TestContractLineNamesGenrePathAndConstraint(unittest.TestCase):
    """BO-2200c-2: A generated AC-N line carries a Diataxis genre, a target
    documentation path, and a content constraint derived from the AC criteria.

    RED before implementation: _build_agent_contracts_section currently emits
    only '- [ ] AC-1: {title}'.  The title is not a valid genre keyword, does
    not contain a '/' path separator, and is not derived from the criteria.
    """

    def test_contract_line_names_genre_path_and_constraint(self) -> None:
        # covers: BO-2200c-2
        """A generated AC-N line in the documentation-expert subsection must contain
        all three of the following parts:

        1. A Diataxis genre keyword from the valid vocabulary:
           how-to, reference-doc, sequence-diagram, state-diagram,
           component-diagram, or explanation.

        2. A target documentation path (a string containing a '/' separator).

        3. A content constraint derived from the leaf AC's criteria (not merely
           the AC title repeated verbatim).

        This test is RED before the fix because _build_agent_contracts_section
        currently emits:
            - [ ] AC-1: UNIQUE-TITLE-TEXT
        which contains no genre keyword, no path separator, and no criteria-
        derived content.

        Implementation note: the generator must read 'documentation_triggers'
        for the genre, extract a doc path from 'doc_links' or a computed
        default, and derive the content constraint from the AC's Then/And clauses.
        """
        ac = _make_documented_ac()
        agents_map = _make_doc_agents_map()

        section = _build_agent_contracts_section(ac, "BO-2200C2-TEST", agents_map)

        # Require the section to exist
        self.assertIn(
            "### documentation-expert",
            section,
            "The '### documentation-expert' subsection must be present when "
            "documentation-expert is needed.\n"
            f"Actual section:\n{section}",
        )

        # Extract the AC-N line
        ac_n_match = re.search(r"^- \[ \] AC-\d+:(.+)$", section, re.MULTILINE)
        self.assertIsNotNone(
            ac_n_match,
            "Expected at least one '- [ ] AC-N: ...' checklist line in the "
            "documentation-expert subsection, but none were found.\n\n"
            f"Actual section:\n{section}",
        )

        ac_n_line: str = ac_n_match.group(0)  # type: ignore[union-attr]

        # Assertion 1: line must name a recognised Diataxis genre keyword.
        has_genre = any(genre in ac_n_line for genre in _VALID_GENRES)
        self.assertTrue(
            has_genre,
            f"The AC-N line must name a Diataxis genre (one of "
            f"{sorted(_VALID_GENRES)}), but none was found.\n\n"
            f"Actual AC-N line: {ac_n_line!r}\n\n"
            "Fix: read 'documentation_triggers' from the AC and include the genre "
            "value in the '- [ ] AC-N:' line.\n\n"
            f"Full section:\n{section}",
        )

        # Assertion 2: line must contain a target documentation path.
        # A path contains at least one '/' separator.
        has_path = "/" in ac_n_line
        self.assertTrue(
            has_path,
            "The AC-N line must name a target documentation path (containing a "
            "'/' separator), but no path-like string was found.\n\n"
            f"Actual AC-N line: {ac_n_line!r}\n\n"
            "Fix: include the target doc path (from doc_links or a computed default) "
            "in the '- [ ] AC-N:' line.\n\n"
            f"Full section:\n{section}",
        )

        # Assertion 3: line must NOT simply repeat the AC title verbatim.
        # The AC title is 'UNIQUE-TITLE-TEXT' -- if that string appears as the
        # sole payload, the implementation is using the old title-only approach.
        self.assertNotIn(
            "UNIQUE-TITLE-TEXT",
            ac_n_line,
            "The AC-N line must carry a content constraint derived from the AC "
            "criteria rather than repeating the AC title verbatim.\n\n"
            f"Actual AC-N line: {ac_n_line!r}\n\n"
            "Fix: derive the content constraint from the AC's Then/And criteria "
            "clauses instead of using ac.get('title') as the line payload.\n\n"
            f"Full section:\n{section}",
        )


# ---------------------------------------------------------------------------
# TestGenreVocabularyMatchesEnumPlusExplanation
# BO-2200c-2
# ---------------------------------------------------------------------------


class TestGenreVocabularyMatchesEnumPlusExplanation(unittest.TestCase):
    """BO-2200c-2: The genre named on a contract line must be one of the
    documentation_triggers enum values or 'explanation'.

    RED before implementation: the current AC-N line is '- [ ] AC-1: UNIQUE-TITLE-TEXT'.
    No valid genre keyword is present, so the genre-vocabulary check fails.
    """

    def test_genre_vocabulary_matches_enum_plus_explanation(self) -> None:
        # covers: BO-2200c-2
        """The genre named on a contract line in the '### documentation-expert'
        subsection must be one of the six valid genre keywords:

            how-to, reference-doc, sequence-diagram, state-diagram,
            component-diagram, explanation

        This test verifies two things:

        A) At least one valid genre keyword appears in the AC-N line.
        B) The specific genre matches what the AC declared in
           'documentation_triggers'.  The fixture AC declares
           documentation_triggers: ['how-to'], so 'how-to' must be named.

        This test is RED before the fix because _build_agent_contracts_section
        currently emits '- [ ] AC-1: UNIQUE-TITLE-TEXT' -- the title contains
        no valid genre keyword, so assertion A fails immediately.

        Implementation note: read 'documentation_triggers' to pick the genre.
        When the field is absent or empty, use 'explanation' as the default.
        Never emit a genre value that is not a member of _VALID_GENRES.
        """
        ac = _make_documented_ac()  # documentation_triggers: ["how-to"]
        agents_map = _make_doc_agents_map()

        section = _build_agent_contracts_section(ac, "BO-2200C2-TEST", agents_map)

        # Extract the AC-N line
        ac_n_match = re.search(r"^- \[ \] AC-\d+:(.+)$", section, re.MULTILINE)
        self.assertIsNotNone(
            ac_n_match,
            "Expected at least one '- [ ] AC-N: ...' checklist line in the "
            "documentation-expert subsection, but none were found.\n\n"
            f"Actual section:\n{section}",
        )

        ac_n_line: str = ac_n_match.group(0)  # type: ignore[union-attr]

        # Assertion A: at least one valid genre keyword must appear.
        genres_found = [genre for genre in _VALID_GENRES if genre in ac_n_line]
        self.assertGreaterEqual(
            len(genres_found),
            1,
            f"The AC-N line must name a genre from the vocabulary "
            f"{sorted(_VALID_GENRES)}, but none was found.\n\n"
            f"Actual AC-N line: {ac_n_line!r}\n\n"
            "Fix: include the genre from 'documentation_triggers' (or 'explanation' "
            "as a default) in the contract line.\n\n"
            f"Full section:\n{section}",
        )

        # Assertion B: the declared genre ('how-to') must be the one named.
        # The AC declares documentation_triggers: ['how-to'] so the implementation
        # must honour that declaration and emit 'how-to' in the contract line.
        self.assertIn(
            "how-to",
            ac_n_line,
            "The AC declares documentation_triggers: ['how-to'], so 'how-to' must "
            "appear as the genre in the contract line.\n\n"
            f"Actual AC-N line: {ac_n_line!r}\n\n"
            "Fix: read ac.get('documentation_triggers') and use its first (or only) "
            "value as the genre label in the '- [ ] AC-N:' line.\n\n"
            f"Full section:\n{section}",
        )


if __name__ == "__main__":
    unittest.main()
