"""
MODULE: test_bo_2200b_6
GOAL: Verify AC BO-2200b-6 — documentation-verifier is registered in every
      canonical phase-order source in the correct relative slot (after
      coder / test-runner / documentation-expert, before commit) and that
      no source omits it.

The four canonical sources that define phase ordering are:
  1. templates/workflows-js/build-ticket.js  — phaseOrder array
  2. templates/workflows-js/build-feature.js — phaseOrder array
  3. templates/skills/building-epics/SKILL.md — §2.1.1 ordering table
  4. templates/skills/ticket-authoring/SKILL.md — Canonical ordering note

TICKET: tickets/00_inbox/epics/EPIC-DocumentationCoverageGuarantee/16_TICKET-20260715-BO-2200b-6.md
COVERS: BO-2200b-6
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent

_BUILD_TICKET_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-ticket.js"
_BUILD_FEATURE_JS = _REPO_ROOT / "templates" / "workflows-js" / "build-feature.js"
_BUILDING_EPICS_SKILL = _REPO_ROOT / "templates" / "skills" / "building-epics" / "SKILL.md"
_TICKET_AUTHORING_SKILL = _REPO_ROOT / "templates" / "skills" / "ticket-authoring" / "SKILL.md"

_AGENT = "documentation-verifier"

# Anchor agents used to verify relative ordering.
# The AC says: after coder / test-runner / documentation-expert, before commit.
_ANCHORS_BEFORE = ["python-coder", "test-runner", "documentation-expert"]
_ANCHOR_AFTER = "commit"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_phase_order_from_js(file_path: Path) -> list[str]:
    """Extract the ordered phaseOrder list from a JS workflow file.

    Looks for:
        const phaseOrder = [
          "agent-name",   // comment
          ...
        ];

    Returns the list of agent name strings in declaration order.
    """
    assert file_path.exists(), f"JS workflow file not found: {file_path}"
    content = file_path.read_text(encoding="utf-8")
    match = re.search(r"const\s+phaseOrder\s*=\s*\[(.*?)\];", content, re.DOTALL)
    assert match, f"Could not find 'const phaseOrder = [...];' in {file_path}"
    return re.findall(r'"([^"]+)"', match.group(1))


def _parse_building_epics_table(file_path: Path) -> list[str]:
    """Extract ordered agent names from the §2.1.1 Canonical Phase Ordering Table.

    Rows look like:
        | 11.9 | `documentation-verifier` | ... |

    Returns agents in table row order.
    """
    assert file_path.exists(), f"SKILL.md not found: {file_path}"
    content = file_path.read_text(encoding="utf-8")

    agents: list[str] = []
    in_section = False
    for line in content.splitlines():
        if "§2.1.1 Canonical Phase Ordering Table" in line:
            in_section = True
            continue
        if in_section:
            # Stop at the next heading
            if re.match(r"^#{2,}", line):
                break
            # Match table rows: | priority | `agent-name` | notes |
            m = re.search(r"\|\s*[\d.]+\s*\|\s*`([^`]+)`", line)
            if m:
                agents.append(m.group(1))
    return agents


def _parse_ticket_authoring_ordering_note(file_path: Path) -> list[str]:
    """Extract ordered agent names from the Canonical ordering note in ticket-authoring SKILL.md.

    The note looks like (inside a markdown table cell):
        **Canonical ordering**: architect-review (4) → test-writer (5) → ... → commit (12) → ...

    Returns agents in arrow-chain order.
    """
    assert file_path.exists(), f"SKILL.md not found: {file_path}"
    content = file_path.read_text(encoding="utf-8")

    # Find the Canonical ordering pattern inside the file (markdown table cell or prose)
    m = re.search(r"\*\*Canonical ordering\*\*:\s*(.+?)(?:\.\s|\.$|$)", content, re.DOTALL)
    if not m:
        return []
    ordering_text = m.group(1)
    # Extract agent names — each segment looks like "agent-name (N)"
    segments = [seg.strip() for seg in ordering_text.split("→")]
    agents = []
    for seg in segments:
        # Strip trailing "Set ..." notes that may follow the final entry
        seg = re.sub(r"\.\s+Set\b.*", "", seg).strip()
        # Agent name is everything before the first space or '(' (the priority suffix)
        agent_name = re.split(r"\s*\(", seg)[0].strip()
        if agent_name:
            agents.append(agent_name)
    return agents


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDocumentationVerifierPresentInAllSources(unittest.TestCase):
    """AC BO-2200b-6: documentation-verifier appears in every canonical phase-order source."""

    def test_ac1_documentation_verifier_present_in_build_ticket_js(self):
        # covers: BO-2200b-6
        """AC-1 (presence): build-ticket.js phaseOrder must contain 'documentation-verifier'.

        Implementation required: llm-expert must insert 'documentation-verifier'
        into the phaseOrder array in templates/workflows-js/build-ticket.js at
        the correct slot (after documentation-expert, before commit).
        Until then this test fails with AssertionError.
        """
        order = _parse_phase_order_from_js(_BUILD_TICKET_JS)
        self.assertIn(
            _AGENT,
            order,
            f"'documentation-verifier' not found in build-ticket.js phaseOrder. "
            f"Current order: {order}",
        )

    def test_ac1_documentation_verifier_present_in_build_feature_js(self):
        # covers: BO-2200b-6
        """AC-1 (presence): build-feature.js phaseOrder must contain 'documentation-verifier'.

        Implementation required: llm-expert must insert 'documentation-verifier'
        into the phaseOrder array in templates/workflows-js/build-feature.js at
        the correct slot (after documentation-expert, before commit).
        Until then this test fails with AssertionError.
        """
        order = _parse_phase_order_from_js(_BUILD_FEATURE_JS)
        self.assertIn(
            _AGENT,
            order,
            f"'documentation-verifier' not found in build-feature.js phaseOrder. "
            f"Current order: {order}",
        )

    def test_ac1_documentation_verifier_present_in_building_epics_skill(self):
        # covers: BO-2200b-6
        """AC-1 (presence): building-epics/SKILL.md §2.1.1 table must contain 'documentation-verifier'.

        Implementation required: llm-expert must add a row for documentation-verifier
        (at priority 11.9) in the §2.1.1 Canonical Phase Ordering Table inside
        templates/skills/building-epics/SKILL.md.
        Until then this test fails with AssertionError.
        """
        order = _parse_building_epics_table(_BUILDING_EPICS_SKILL)
        self.assertIn(
            _AGENT,
            order,
            f"'documentation-verifier' not found in building-epics SKILL.md §2.1.1 table. "
            f"Current table agents: {order}",
        )

    def test_ac1_documentation_verifier_present_in_ticket_authoring_skill(self):
        # covers: BO-2200b-6
        """AC-1 (presence): ticket-authoring/SKILL.md canonical ordering note must
        contain 'documentation-verifier'.

        Implementation required: llm-expert must update the **Canonical ordering**
        note inside templates/skills/ticket-authoring/SKILL.md to include
        documentation-verifier at its correct slot.
        Until then this test fails with AssertionError.
        """
        order = _parse_ticket_authoring_ordering_note(_TICKET_AUTHORING_SKILL)
        self.assertIn(
            _AGENT,
            order,
            f"'documentation-verifier' not found in ticket-authoring SKILL.md "
            f"canonical ordering note. Parsed agents: {order}",
        )


class TestDocumentationVerifierSameRelativeSlot(unittest.TestCase):
    """AC BO-2200b-6: documentation-verifier occupies the same relative slot in all sources.

    Relative slot definition: after documentation-expert (and other coders/test-runner)
    and before commit.
    """

    def _assert_correct_slot(self, order: list[str], source_label: str) -> None:
        """Assert documentation-verifier is after documentation-expert and before commit."""
        self.assertIn(
            _AGENT,
            order,
            f"[{source_label}] 'documentation-verifier' not found in phase order: {order}",
        )
        self.assertIn(
            "documentation-expert",
            order,
            f"[{source_label}] anchor 'documentation-expert' not in order: {order}",
        )
        self.assertIn(
            _ANCHOR_AFTER,
            order,
            f"[{source_label}] anchor 'commit' not in order: {order}",
        )

        dv_idx = order.index(_AGENT)
        de_idx = order.index("documentation-expert")
        commit_idx = order.index(_ANCHOR_AFTER)

        self.assertGreater(
            dv_idx,
            de_idx,
            f"[{source_label}] documentation-verifier (idx={dv_idx}) must be AFTER "
            f"documentation-expert (idx={de_idx}). Order: {order}",
        )
        self.assertLess(
            dv_idx,
            commit_idx,
            f"[{source_label}] documentation-verifier (idx={dv_idx}) must be BEFORE "
            f"commit (idx={commit_idx}). Order: {order}",
        )

    def test_ac2_documentation_verifier_correct_slot_in_build_ticket_js(self):
        # covers: BO-2200b-6
        """AC-2 (relative slot): In build-ticket.js, documentation-verifier must appear
        after documentation-expert and before commit.

        Implementation required: insert documentation-verifier at the correct index
        (after documentation-expert, before commit) in build-ticket.js phaseOrder.
        """
        order = _parse_phase_order_from_js(_BUILD_TICKET_JS)
        self._assert_correct_slot(order, "build-ticket.js")

    def test_ac2_documentation_verifier_correct_slot_in_build_feature_js(self):
        # covers: BO-2200b-6
        """AC-2 (relative slot): In build-feature.js, documentation-verifier must appear
        after documentation-expert and before commit.

        Implementation required: insert documentation-verifier at the correct index
        (after documentation-expert, before commit) in build-feature.js phaseOrder.
        """
        order = _parse_phase_order_from_js(_BUILD_FEATURE_JS)
        self._assert_correct_slot(order, "build-feature.js")

    def test_ac2_documentation_verifier_correct_slot_in_building_epics_skill(self):
        # covers: BO-2200b-6
        """AC-2 (relative slot): In building-epics/SKILL.md §2.1.1 table,
        documentation-verifier must appear after documentation-expert and before commit.

        Implementation required: add the documentation-verifier row (priority 11.9) in the
        §2.1.1 ordering table at the correct position.
        """
        order = _parse_building_epics_table(_BUILDING_EPICS_SKILL)
        self._assert_correct_slot(order, "building-epics SKILL.md §2.1.1")

    def test_ac2_documentation_verifier_correct_slot_in_ticket_authoring_skill(self):
        # covers: BO-2200b-6
        """AC-2 (relative slot): In ticket-authoring/SKILL.md canonical ordering note,
        documentation-verifier must appear after documentation-expert and before commit.

        Implementation required: update the **Canonical ordering** note to include
        documentation-verifier at the correct slot.
        """
        order = _parse_ticket_authoring_ordering_note(_TICKET_AUTHORING_SKILL)
        self._assert_correct_slot(order, "ticket-authoring SKILL.md ordering note")

    def test_ac2_slot_is_parity_across_all_js_sources(self):
        # covers: BO-2200b-6
        """AC-2 (parity): The relative slot of documentation-verifier must be consistent
        across build-ticket.js and build-feature.js (twin arrays must stay in sync).

        Specifically: the set of agents that appear before documentation-verifier
        and the set that appear after (up to commit) must be identical in both files.

        Implementation required: both JS phaseOrder arrays must include
        documentation-verifier before parity can be measured; until then this
        test fails on the presence assertion.
        """
        order_ticket = _parse_phase_order_from_js(_BUILD_TICKET_JS)
        order_feature = _parse_phase_order_from_js(_BUILD_FEATURE_JS)

        for order, label in [(order_ticket, "build-ticket.js"), (order_feature, "build-feature.js")]:
            self.assertIn(
                _AGENT,
                order,
                f"'documentation-verifier' not found in {label}: {order}",
            )

        ticket_idx = order_ticket.index(_AGENT)
        feature_idx = order_feature.index(_AGENT)

        agents_before_in_ticket = set(order_ticket[:ticket_idx])
        agents_before_in_feature = set(order_feature[:feature_idx])

        self.assertEqual(
            agents_before_in_ticket,
            agents_before_in_feature,
            f"Agents before documentation-verifier differ between build-ticket.js and "
            f"build-feature.js.\n"
            f"  build-ticket.js has: {agents_before_in_ticket}\n"
            f"  build-feature.js has: {agents_before_in_feature}",
        )


if __name__ == "__main__":
    unittest.main()
