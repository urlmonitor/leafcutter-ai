"""
Tests for BO-2200c-1: The generated ticket carries an Agent Contracts
documentation-expert section in a fixed position.

These tests are RED before the implementation of BO-2200c-1 because
_build_ticket_body currently does not emit an '## Agent Contracts' section.

Target file to implement: scripts/ac_store/generate_ticket_from_ac.py
AC source: docs/acceptance-criteria/build-orchestration/
           BO-2200-documentation-coverage-guarantee/BO-2200c-1.yaml
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts" / "ac_store"
sys.path.insert(0, str(_SCRIPTS_DIR))

from generate_ticket_from_ac import _build_ticket_body  # noqa: E402


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _make_doc_required_ac() -> dict:
    """Return a minimal AC dict for a ticket that requires documentation.

    'Requires documentation' is defined as: documentation-expert appears
    in the computed agents map with status 'needed'.  This AC record is used
    in conjunction with an explicit agents_map that includes documentation-expert
    so the test controls the exact scenario without depending on guardrail config.

    IMPORTANT: The criteria text must NOT contain the literal strings
    '## Agent Contracts' or '### documentation-expert', otherwise assertIn()
    checks on the body will find those strings in the embedded gherkin block
    (a false pass) rather than in the actual generated section.
    """
    return {
        "id": "BO-2200C1-TEST",
        "title": "Ticket body emits the agent-contracts doc-expert block",
        "component": "build-orchestration",
        "assigned_agent": "python-coder",
        "estimated_complexity": "M",
        "criteria": (
            "Given a ticket requires documentation review,\n"
            "When the generator builds the ticket body,\n"
            "Then the body includes an agent-contracts block for the doc reviewer,\n"
            "And that block is positioned between acceptance-criteria and sign-offs,\n"
            "And each item is globally numbered with an AC-N prefix."
        ),
        "doc_links": [],
    }


def _make_doc_agents_map() -> dict:
    """Return a pre-computed agents map that includes documentation-expert as needed.

    Passing this map directly to _build_ticket_body (via agents_map=) ensures the
    test exercises the documentation-required branch without requiring a specific
    guardrail config to be present.
    """
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
# test_agent_contracts_documentation_expert_section_present
# BO-2200c-1
# ---------------------------------------------------------------------------


class TestAgentContractsDocExpertSectionPresent(unittest.TestCase):
    """BO-2200c-1: A generated doc-required ticket body contains '## Agent Contracts'
    with a '### documentation-expert' subsection.

    RED before implementation: _build_ticket_body does not emit ## Agent Contracts.
    """

    def test_agent_contracts_documentation_expert_section_present(self) -> None:
        # covers: BO-2200c-1
        """A generated ticket whose agents map includes documentation-expert:needed must
        contain an '## Agent Contracts' section with a '### documentation-expert' subsection.

        Implementation requirement: _build_ticket_body must detect when
        documentation-expert is in the agents map as 'needed' and emit the
        '## Agent Contracts' -> '### documentation-expert' block.

        This test is RED before the fix because _build_ticket_body currently emits
        no '## Agent Contracts' section at all.

        NOTE: assertions use line-anchored regex (^## heading$) to avoid false positives
        from the same strings appearing inside embedded gherkin criteria blocks.
        """
        ac = _make_doc_required_ac()
        agents_map = _make_doc_agents_map()

        body = _build_ticket_body(ac, "BO-2200C1-TEST", agents_map=agents_map)

        has_agent_contracts_heading = bool(
            re.search(r"^## Agent Contracts\s*$", body, re.MULTILINE)
        )
        self.assertTrue(
            has_agent_contracts_heading,
            "Expected '## Agent Contracts' section heading (on its own line) in ticket "
            "body when documentation-expert is a needed agent, but it was not found.\n\n"
            "Fix: _build_ticket_body must emit '## Agent Contracts' when "
            "documentation-expert appears in the agents map as 'needed'.\n\n"
            f"Actual body:\n{body}",
        )

        has_doc_expert_subsection = bool(
            re.search(r"^### documentation-expert\s*$", body, re.MULTILINE)
        )
        self.assertTrue(
            has_doc_expert_subsection,
            "Expected '### documentation-expert' subsection heading (on its own line) "
            "inside '## Agent Contracts', but it was not found.\n\n"
            "Fix: emit the '### documentation-expert' heading inside the "
            "'## Agent Contracts' block.\n\n"
            f"Actual body:\n{body}",
        )


# ---------------------------------------------------------------------------
# test_agent_contracts_positioned_after_ac_before_signoffs
# BO-2200c-1
# ---------------------------------------------------------------------------


class TestAgentContractsPositioning(unittest.TestCase):
    """BO-2200c-1: The '## Agent Contracts' section must appear AFTER
    '## Acceptance Criteria' and BEFORE '## Sign-offs'.

    RED before implementation: the section is absent, so positions cannot be compared.
    """

    def test_agent_contracts_positioned_after_ac_before_signoffs(self) -> None:
        # covers: BO-2200c-1
        """The '## Agent Contracts' section must appear after '## Acceptance Criteria'
        and before '## Sign-offs' in the generated ticket body.

        This is the location rule from BO-2200c-1 n_location_rule='1': the block is
        a fixed-position section between the two already-existing anchors.

        This test is RED before the fix because the '## Agent Contracts' section
        is entirely absent from the output of _build_ticket_body, making the
        position assertion fail with an AssertionError (section not found).

        NOTE: positions are found using regex search for headings on their own line
        (^## heading$) to avoid false matches inside embedded gherkin blocks.
        """
        ac = _make_doc_required_ac()
        agents_map = _make_doc_agents_map()

        body = _build_ticket_body(ac, "BO-2200C1-TEST", agents_map=agents_map)

        # Locate heading positions via regex to avoid false matches in criteria text
        ac_match = re.search(r"^## Acceptance Criteria\s*$", body, re.MULTILINE)
        contracts_match = re.search(r"^## Agent Contracts\s*$", body, re.MULTILINE)
        signoffs_match = re.search(r"^## Sign-offs\s*$", body, re.MULTILINE)

        self.assertIsNotNone(
            ac_match,
            "'## Acceptance Criteria' heading must be present (on its own line) in body",
        )
        self.assertIsNotNone(
            contracts_match,
            "'## Agent Contracts' heading (on its own line) must be present when "
            "documentation-expert is needed.\n"
            "Fix: emit the '## Agent Contracts' block in _build_ticket_body.\n"
            f"Actual body:\n{body}",
        )
        self.assertIsNotNone(
            signoffs_match,
            "'## Sign-offs' heading must be present (on its own line) in body",
        )

        ac_pos = ac_match.start()  # type: ignore[union-attr]
        contracts_pos = contracts_match.start()  # type: ignore[union-attr]
        signoffs_pos = signoffs_match.start()  # type: ignore[union-attr]

        self.assertGreater(
            contracts_pos,
            ac_pos,
            f"'## Agent Contracts' (pos {contracts_pos}) must appear AFTER "
            f"'## Acceptance Criteria' (pos {ac_pos}) in the ticket body.\n\n"
            f"Fix: place the Agent Contracts block after the Acceptance Criteria "
            f"section in _build_ticket_body's output.\n\n"
            f"Actual body:\n{body}",
        )

        self.assertLess(
            contracts_pos,
            signoffs_pos,
            f"'## Agent Contracts' (pos {contracts_pos}) must appear BEFORE "
            f"'## Sign-offs' (pos {signoffs_pos}) in the ticket body.\n\n"
            f"Fix: place the Agent Contracts block before the Sign-offs section "
            f"in _build_ticket_body's output.\n\n"
            f"Actual body:\n{body}",
        )


# ---------------------------------------------------------------------------
# test_contract_lines_globally_numbered
# BO-2200c-1
# ---------------------------------------------------------------------------


class TestContractLinesGloballyNumbered(unittest.TestCase):
    """BO-2200c-1: The '### documentation-expert' subsection lists one '- [ ] AC-N:'
    checklist item per documented AC, numbered globally across the whole ticket.

    RED before implementation: the section is absent, so no such lines exist.
    """

    def test_contract_lines_globally_numbered(self) -> None:
        # covers: BO-2200c-1
        """The '### documentation-expert' subsection must contain checklist items
        in the globally-numbered '- [ ] AC-N:' format.

        Requirements:
        - At least one '- [ ] AC-N:' line must appear (one per documented AC).
        - Numbering starts at AC-1 (not AC-0 and not restarting per subsection).
        - Lines match the exact format '- [ ] AC-<integer>:' (square brackets, space inside).

        'Globally numbered' means: if the full ticket has a `### test-writer` section
        with items AC-1 and AC-2, then the `### documentation-expert` section continues
        with AC-3, AC-4, etc. — it does NOT restart at AC-1.

        This test is RED before the fix because '## Agent Contracts' is absent from
        the body entirely, so no '- [ ] AC-N:' lines can be found.
        """
        ac = _make_doc_required_ac()
        agents_map = _make_doc_agents_map()

        body = _build_ticket_body(ac, "BO-2200C1-TEST", agents_map=agents_map)

        # Require the section to exist before checking line format
        self.assertIn(
            "### documentation-expert",
            body,
            "### documentation-expert subsection must exist inside ## Agent Contracts.\n"
            f"Actual body:\n{body}",
        )

        # Check for globally-numbered '- [ ] AC-N:' lines anywhere in the body
        ac_n_pattern = re.compile(r"^- \[ \] AC-\d+:", re.MULTILINE)
        matches = ac_n_pattern.findall(body)

        self.assertGreater(
            len(matches),
            0,
            "Expected at least one '- [ ] AC-N:' line (globally numbered checklist item) "
            "in the '### documentation-expert' subsection, but none were found.\n\n"
            "Fix: emit one '- [ ] AC-N:' line per documented AC in the subsection, "
            "with N starting at 1 and incrementing globally (not restarting per subsection).\n\n"
            f"Actual body:\n{body}",
        )

        # Numbering must start at AC-1 (the ticket covers at least the source AC)
        self.assertIn(
            "- [ ] AC-1:",
            body,
            "Expected '- [ ] AC-1:' as the first globally-numbered item, but it was "
            "not found in the ticket body.\n\n"
            "Fix: ensure the global counter starts at 1 and the first item in the "
            "'### documentation-expert' section is '- [ ] AC-1: <description>'.\n\n"
            f"Actual body:\n{body}",
        )

    def test_contract_lines_not_present_when_no_doc_expert(self) -> None:
        # covers: BO-2200c-1
        """When documentation-expert is NOT in the agents map as 'needed', the
        '## Agent Contracts' section must NOT be emitted.

        This is the guard against spurious emission: only doc-required tickets carry
        the section. Non-doc tickets must remain unchanged (no empty section added).

        This test is also RED before the fix if the implementation accidentally emits
        the section for all tickets.  However, since the primary issue is absence (not
        spurious presence), this test may pass trivially before the fix — that is
        acceptable: the primary RED signal comes from the three tests above.

        NOTE: assertion uses line-anchored regex to avoid false positives from
        the string appearing inside gherkin criteria text.
        """
        ac = {
            "id": "BO-2200C1-NODOC",
            "title": "Ticket without documentation requirement",
            "component": "build-orchestration",
            "assigned_agent": "python-coder",
            "estimated_complexity": "S",
            "criteria": "Given a non-doc ticket\nWhen generated\nThen no agent-contracts block",
            "doc_links": [],
        }
        # agents_map with NO documentation-expert
        no_doc_map = {
            "test-writer": "needed",
            "python-coder": "needed",
            "test-runner": "needed",
            "pr-reviewer": "needed",
            "commit": "needed",
            "pull-request": "needed",
        }

        body = _build_ticket_body(ac, "BO-2200C1-NODOC", agents_map=no_doc_map)

        has_doc_expert_heading = bool(
            re.search(r"^### documentation-expert\s*$", body, re.MULTILINE)
        )
        self.assertFalse(
            has_doc_expert_heading,
            "The '### documentation-expert' subsection heading must NOT be emitted "
            "when documentation-expert is absent from the agents map.\n\n"
            f"Actual body:\n{body}",
        )


if __name__ == "__main__":
    unittest.main()
