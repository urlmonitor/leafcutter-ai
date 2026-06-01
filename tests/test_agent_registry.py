"""
MODULE: test_agent_registry
GOAL: Verify that frontend-coder is correctly registered in agent_registry.json.
BUSINESS CONTEXT: The agent registry is the single source of truth for agent
    selection. A missing or malformed frontend-coder entry would prevent the
    business-analyst from assigning the agent to frontend tickets.
ARCHITECTURE: Loads agent_registry.json directly and asserts required fields.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"


def _load_registry() -> list[dict]:
    with _REGISTRY_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data["agents"]


def _find_agent(agents: list[dict], agent_id: str) -> dict | None:
    for agent in agents:
        if agent.get("id") == agent_id:
            return agent
    return None


class TestFrontendCoderRegistered(unittest.TestCase):
    def setUp(self):
        self.agents = _load_registry()
        self.frontend_coder = _find_agent(self.agents, "frontend-coder")

    def test_frontend_coder_exists(self):
        """frontend-coder entry must exist in agent_registry.json."""
        self.assertIsNotNone(
            self.frontend_coder,
            "frontend-coder not found in agent_registry.json agents list"
        )

    def test_is_ticket_phase(self):
        """frontend-coder must be a ticket phase agent."""
        self.assertTrue(
            self.frontend_coder.get("is_ticket_phase"),
            "frontend-coder.is_ticket_phase must be True"
        )

    def test_requires_ticket_section(self):
        """frontend-coder must require a ticket implementation section."""
        self.assertTrue(
            self.frontend_coder.get("requires_ticket_section"),
            "frontend-coder.requires_ticket_section must be True"
        )

    def test_default_status_not_needed(self):
        """frontend-coder default_status must be 'not_needed'."""
        selection = self.frontend_coder.get("selection_criteria", {})
        self.assertEqual(
            selection.get("default_status"),
            "not_needed",
            "frontend-coder selection_criteria.default_status must be 'not_needed'"
        )

    def test_selection_criteria_present(self):
        """frontend-coder must have a non-null selection_criteria."""
        self.assertIsNotNone(
            self.frontend_coder.get("selection_criteria"),
            "frontend-coder.selection_criteria must not be null"
        )

    def test_trigger_conditions_non_empty(self):
        """frontend-coder must have at least one trigger condition."""
        selection = self.frontend_coder.get("selection_criteria", {})
        trigger_conditions = selection.get("trigger_conditions", [])
        self.assertGreater(
            len(trigger_conditions),
            0,
            "frontend-coder must have at least one trigger_condition"
        )

    def test_priority_is_8(self):
        """frontend-coder must be dispatched at priority 8."""
        self.assertEqual(
            self.frontend_coder.get("priority"),
            8,
            "frontend-coder.priority must be 8 (between sql-coder=7 and test-runner=9)"
        )

    def test_dsl_trigger_includes_frontend_extensions(self):
        """At least one DSL trigger must reference frontend file extensions."""
        selection = self.frontend_coder.get("selection_criteria", {})
        trigger_conditions = selection.get("trigger_conditions", [])
        dsl_expressions = [
            tc.get("expression", "")
            for tc in trigger_conditions
            if tc.get("type") == "dsl"
        ]
        self.assertTrue(
            any(ext in expr for expr in dsl_expressions for ext in [".tsx", ".jsx", ".vue", ".svelte"]),
            "At least one DSL trigger must reference frontend file extensions (.tsx, .jsx, .vue, or .svelte)"
        )

    def test_owns_frontend_file_extensions(self):
        """frontend-coder must declare ownership of frontend file extensions."""
        owned = self.frontend_coder.get("owns_file_extensions", [])
        self.assertIn(
            ".tsx",
            owned,
            "frontend-coder.owns_file_extensions must include .tsx"
        )
        self.assertIn(
            ".css",
            owned,
            "frontend-coder.owns_file_extensions must include .css"
        )


if __name__ == "__main__":
    unittest.main()
