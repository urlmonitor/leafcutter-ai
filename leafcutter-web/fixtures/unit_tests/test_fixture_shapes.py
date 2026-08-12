"""
Unit tests: fixture entity records are shaped identically to real artifacts — UXP-551-1.

These tests load the JSON entity mock-data files directly from leafcutter-web/fixtures/
and assert that each record satisfies the field invariants documented in the mock-data
file itself. No separate fixture authoring is needed: the same records the mock-mode
Atlas renders are what the test suite asserts against (UXP-551-1 feed-forward principle).

Covers: UXP-551, UXP-551-1
"""

import json
import unittest
from pathlib import Path

FIXTURE_ROOT = Path(__file__).parent.parent


def _load(relative: str) -> dict:
    path = FIXTURE_ROOT / relative
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


class TestAgentEntityShape(unittest.TestCase):
    """UXP-551-1: Agent entity records match the shape the real agent_registry.json uses."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load("docs/product-truth/mock-data/leafcutter/build-pipeline.mock.json")
        cls.records = cls.data["entities"]["Agent"]["records"]

    def test_all_records_have_id(self):
        for r in self.records:
            self.assertIsInstance(r["id"], str)
            self.assertGreater(len(r["id"]), 0)

    def test_all_records_have_name(self):
        for r in self.records:
            self.assertIsInstance(r["name"], str)

    def test_is_ticket_phase_is_boolean(self):
        for r in self.records:
            self.assertIsInstance(r["is_ticket_phase"], bool)

    def test_category_is_known_enum(self):
        valid = {"implementation", "planning", "testing", "research", "supervisor"}
        for r in self.records:
            self.assertIn(r["category"], valid, f"Unknown category in record {r['id']!r}")

    def test_phase_order_none_for_non_phase_agents(self):
        for r in self.records:
            if not r["is_ticket_phase"]:
                self.assertIsNone(r.get("phase_order"), f"{r['id']} should have phase_order=null")


class TestTicketEntityShape(unittest.TestCase):
    """UXP-551-1: Ticket entity records match the shape of real ticket markdown frontmatter."""

    @classmethod
    def setUpClass(cls):
        cls.data = _load("docs/product-truth/mock-data/leafcutter/build-pipeline.mock.json")
        cls.records = cls.data["entities"]["Ticket"]["records"]

    def test_all_records_have_slug(self):
        for r in self.records:
            self.assertIsInstance(r["slug"], str)
            self.assertGreater(len(r["slug"]), 0)

    def test_status_is_known_enum(self):
        valid = {"todo", "in_progress", "done", "blocked"}
        for r in self.records:
            self.assertIn(r["status"], valid)

    def test_priority_is_known_enum(self):
        valid = {"critical", "high", "medium", "low"}
        for r in self.records:
            self.assertIn(r["priority"], valid)


class TestFlowEntityShape(unittest.TestCase):
    """UXP-551: Flow fixture files match the shape the flows.ts loader expects."""

    def _flows(self):
        flows_dir = FIXTURE_ROOT / "docs/product-truth/flows/leafcutter"
        return [json.loads(fp.read_text()) for fp in flows_dir.glob("*.flow.json")]

    def test_each_flow_has_required_keys(self):
        for flow in self._flows():
            for key in ("id", "name", "steps", "branches", "kind", "source"):
                self.assertIn(key, flow, f"Flow {flow.get('id')!r} missing key {key!r}")

    def test_steps_have_required_fields(self):
        for flow in self._flows():
            for step in flow["steps"]:
                self.assertIn("id", step)
                self.assertIn("label", step)
                self.assertIn("order", step)

    def test_at_least_two_flows(self):
        self.assertGreaterEqual(len(self._flows()), 2)


if __name__ == "__main__":
    unittest.main()
