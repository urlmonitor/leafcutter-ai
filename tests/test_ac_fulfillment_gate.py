"""
MODULE: test_ac_fulfillment_gate
GOAL: Verify the ac-fulfillment-gate agent template and registry entry are
    correctly authored as specified in TICKET-20260605-ACFulfillmentGate.
BUSINESS CONTEXT: The ac-fulfillment-gate agent runs at priority 11.7 in the
    ticket-supervisor phase chain (after ac-validator at 11.5, before commit at 12).
    These tests verify that the required artifacts (agent template, registry entry,
    and building-epics SKILL.md update) are present and correctly formed before
    the commit phase locks the worktree.
ARCHITECTURE: Reads artifact files directly from the repo tree. No I/O to external
    services. Each test class targets one artifact; all tests are deterministic.
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Repo root discovery
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"
_AGENT_TEMPLATE_PATH = _REPO_ROOT / "templates" / "agents" / "ac-fulfillment-gate.md"
_BUILDING_EPICS_SKILL_PATH = (
    _REPO_ROOT / "templates" / "skills" / "building-epics" / "SKILL.md"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_frontmatter(text: str) -> dict:
    """Parse the YAML frontmatter block from a markdown file.

    Raises ValueError if the file does not start with a YAML block (---...---).
    """
    if not text.startswith("---"):
        raise ValueError("File does not start with a YAML frontmatter block")
    end = text.index("---", 3)
    yaml_block = text[3:end].strip()
    return yaml.safe_load(yaml_block)


def _load_registry() -> list[dict]:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["agents"]


def _find_agent(agents: list[dict], agent_id: str) -> dict | None:
    for agent in agents:
        if agent.get("id") == agent_id:
            return agent
    return None


# ---------------------------------------------------------------------------
# Test: agent template frontmatter
# ---------------------------------------------------------------------------


class TestAcFulfillmentGateTemplateFrontmatter(unittest.TestCase):
    """
    Test: test_ac_fulfillment_gate_template_frontmatter_valid

    Verify templates/agents/ac-fulfillment-gate.md has valid frontmatter
    with required fields: name, model: sonnet, tools include Bash/Read/Edit,
    signoff: true, portable: true.
    """

    def setUp(self):
        # covers: UNKNOWN
        if not _AGENT_TEMPLATE_PATH.exists():
            self.skipTest(
                f"Agent template not yet created: {_AGENT_TEMPLATE_PATH} — "
                "this test is red until llm-expert writes the template"
            )
        text = _AGENT_TEMPLATE_PATH.read_text(encoding="utf-8")
        try:
            self.fm = _parse_frontmatter(text)
        except (ValueError, yaml.YAMLError) as exc:
            self.fail(f"Failed to parse frontmatter from {_AGENT_TEMPLATE_PATH}: {exc}")

    def test_name_is_ac_fulfillment_gate(self):
        # covers: UNKNOWN
        """name field must be 'ac-fulfillment-gate'."""
        self.assertEqual(
            self.fm.get("name"),
            "ac-fulfillment-gate",
            "frontmatter 'name' must equal 'ac-fulfillment-gate'",
        )

    def test_model_is_sonnet(self):
        # covers: UNKNOWN
        """model field must be 'sonnet'."""
        self.assertEqual(
            self.fm.get("model"),
            "sonnet",
            "frontmatter 'model' must be 'sonnet'",
        )

    def test_tools_include_bash(self):
        # covers: UNKNOWN
        """tools field must include Bash."""
        tools_raw = self.fm.get("tools", "")
        tools_str = str(tools_raw)
        self.assertIn(
            "Bash",
            tools_str,
            "frontmatter 'tools' must include 'Bash'",
        )

    def test_tools_include_read(self):
        # covers: UNKNOWN
        """tools field must include Read."""
        tools_raw = self.fm.get("tools", "")
        tools_str = str(tools_raw)
        self.assertIn(
            "Read",
            tools_str,
            "frontmatter 'tools' must include 'Read'",
        )

    def test_tools_include_edit(self):
        # covers: UNKNOWN
        """tools field must include Edit."""
        tools_raw = self.fm.get("tools", "")
        tools_str = str(tools_raw)
        self.assertIn(
            "Edit",
            tools_str,
            "frontmatter 'tools' must include 'Edit'",
        )

    def test_signoff_is_true(self):
        # covers: UNKNOWN
        """signoff field must be true."""
        self.assertTrue(
            self.fm.get("signoff"),
            "frontmatter 'signoff' must be true",
        )

    def test_portable_is_true(self):
        # covers: UNKNOWN
        """portable field must be true."""
        self.assertTrue(
            self.fm.get("portable"),
            "frontmatter 'portable' must be true",
        )


class TestAcFulfillmentGateTemplateExists(unittest.TestCase):
    """Verify that the ac-fulfillment-gate agent template file exists at all."""

    def test_template_file_exists(self):
        # covers: UNKNOWN
        """templates/agents/ac-fulfillment-gate.md must exist."""
        self.assertTrue(
            _AGENT_TEMPLATE_PATH.exists(),
            f"Agent template not found: {_AGENT_TEMPLATE_PATH}\n"
            "Expected: llm-expert creates this file as part of "
            "TICKET-20260605-ACFulfillmentGate implementation.",
        )


# ---------------------------------------------------------------------------
# Test: building-epics SKILL.md phase ordering
# ---------------------------------------------------------------------------


class TestBuildingEpicsSkillIncludesAcFulfillmentGate(unittest.TestCase):
    """
    Test: test_building_epics_skill_includes_ac_fulfillment_gate_priority

    Verify templates/skills/building-epics/SKILL.md phase ordering includes
    ac-fulfillment-gate at priority 11.7, after ac-validator (11.5) and
    before commit (12).
    """

    def setUp(self):
        # covers: UNKNOWN
        if not _BUILDING_EPICS_SKILL_PATH.exists():
            self.fail(
                f"building-epics SKILL.md not found at: {_BUILDING_EPICS_SKILL_PATH}"
            )
        self.skill_text = _BUILDING_EPICS_SKILL_PATH.read_text(encoding="utf-8")

    def test_ac_fulfillment_gate_mentioned(self):
        # covers: UNKNOWN
        """building-epics SKILL.md must mention ac-fulfillment-gate."""
        self.assertIn(
            "ac-fulfillment-gate",
            self.skill_text,
            "building-epics SKILL.md must reference 'ac-fulfillment-gate' in "
            "the phase ordering table or canonical phase ordering section.",
        )

    def test_ac_fulfillment_gate_priority_11_7(self):
        # covers: UNKNOWN
        """The phase ordering must specify ac-fulfillment-gate at priority 11.7."""
        # Look for a line that associates ac-fulfillment-gate with 11.7
        pattern = re.compile(
            r"11\.7.*ac-fulfillment-gate|ac-fulfillment-gate.*11\.7",
            re.IGNORECASE,
        )
        match = pattern.search(self.skill_text)
        self.assertIsNotNone(
            match,
            "building-epics SKILL.md must associate 'ac-fulfillment-gate' with "
            "priority 11.7. Pattern searched: '11.7.*ac-fulfillment-gate' or "
            "'ac-fulfillment-gate.*11.7'",
        )

    def test_ac_fulfillment_gate_after_ac_validator(self):
        # covers: UNKNOWN
        """In the SKILL.md table, ac-fulfillment-gate (11.7) must appear after
        ac-validator (11.5) in the document."""
        ac_validator_pos = self.skill_text.find("ac-validator")
        ac_fulfillment_pos = self.skill_text.find("ac-fulfillment-gate")

        # Both must be present
        self.assertNotEqual(
            ac_validator_pos, -1,
            "ac-validator not found in building-epics SKILL.md",
        )
        self.assertNotEqual(
            ac_fulfillment_pos, -1,
            "ac-fulfillment-gate not found in building-epics SKILL.md",
        )

        self.assertGreater(
            ac_fulfillment_pos,
            ac_validator_pos,
            "ac-fulfillment-gate (11.7) must appear AFTER ac-validator (11.5) "
            "in the SKILL.md document to reflect correct phase ordering.",
        )

    def test_ac_fulfillment_gate_before_commit(self):
        # covers: UNKNOWN
        """In the SKILL.md phase ordering, ac-fulfillment-gate (11.7) must appear
        before commit (12) in the table or text."""
        # Find the priority table section — look for the table row for commit
        # (priority 12) and verify ac-fulfillment-gate (11.7) comes before it.
        # We use the first occurrence of each in the document as the ordering proxy.
        ac_fulfillment_pos = self.skill_text.find("ac-fulfillment-gate")
        # Find the commit row in the priority table (look for "| 12 |" pattern)
        commit_priority_match = re.search(r"\|\s*12\s*\|", self.skill_text)

        self.assertNotEqual(
            ac_fulfillment_pos, -1,
            "ac-fulfillment-gate not found in building-epics SKILL.md",
        )
        self.assertIsNotNone(
            commit_priority_match,
            "Priority-12 row for commit not found in building-epics SKILL.md table.",
        )

        self.assertLess(
            ac_fulfillment_pos,
            commit_priority_match.start(),
            "ac-fulfillment-gate must appear before the commit priority-12 row "
            "in building-epics SKILL.md.",
        )


# ---------------------------------------------------------------------------
# Test: agent_registry.json entry
# ---------------------------------------------------------------------------


class TestAcFulfillmentGateAgentRegistryEntry(unittest.TestCase):
    """
    Test: test_ac_fulfillment_gate_agent_registry_entry

    Verify config/agent_registry.json contains an ac-fulfillment-gate entry
    with tier: phase, role: quality, spawned_by includes ticket-supervisor,
    and priority: 11.7.
    """

    def setUp(self):
        # covers: UNKNOWN
        agents = _load_registry()
        self.entry = _find_agent(agents, "ac-fulfillment-gate")

    def test_entry_exists(self):
        # covers: UNKNOWN
        """ac-fulfillment-gate entry must exist in agent_registry.json."""
        self.assertIsNotNone(
            self.entry,
            "ac-fulfillment-gate not found in config/agent_registry.json agents list. "
            "Expected: llm-expert adds this entry as part of "
            "TICKET-20260605-ACFulfillmentGate implementation.",
        )

    def test_tier_is_phase(self):
        # covers: UNKNOWN
        """ac-fulfillment-gate tier must be 'phase'."""
        self.assertEqual(
            self.entry.get("tier"),
            "phase",
            "ac-fulfillment-gate.tier must be 'phase'",
        )

    def test_role_is_quality(self):
        # covers: UNKNOWN
        """ac-fulfillment-gate role must be 'quality'."""
        self.assertEqual(
            self.entry.get("role"),
            "quality",
            "ac-fulfillment-gate.role must be 'quality'",
        )

    def test_spawned_by_includes_ticket_supervisor(self):
        # covers: UNKNOWN
        """ac-fulfillment-gate spawned_by must include 'ticket-supervisor'."""
        spawned_by = self.entry.get("spawned_by", [])
        self.assertIn(
            "ticket-supervisor",
            spawned_by,
            "ac-fulfillment-gate.spawned_by must include 'ticket-supervisor'",
        )

    def test_priority_is_11_7(self):
        # covers: UNKNOWN
        """ac-fulfillment-gate priority must be 11.7."""
        self.assertAlmostEqual(
            float(self.entry.get("priority", 0)),
            11.7,
            places=1,
            msg="ac-fulfillment-gate.priority must be 11.7",
        )

    def test_is_ticket_phase_true(self):
        # covers: UNKNOWN
        """ac-fulfillment-gate is_ticket_phase must be true."""
        self.assertTrue(
            self.entry.get("is_ticket_phase"),
            "ac-fulfillment-gate.is_ticket_phase must be True",
        )


if __name__ == "__main__":
    unittest.main()
