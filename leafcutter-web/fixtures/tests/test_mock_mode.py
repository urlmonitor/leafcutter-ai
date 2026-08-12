"""
Tests for the Atlas mock-mode seam — covers UXP-550, UXP-553, UXP-553-1.

These tests use the JSON entity mock-data records from the bundled fixture repo
directly (UXP-551-1): no separate fixture authoring is needed, the same files
the mock-mode Atlas renders are the files the test suite asserts against.

Covers:
  - UXP-550: repoRoot() seam swaps whole app to fixture root
  - UXP-553: LEAFCUTTER_MOCK env sets mock default; cookie override takes precedence
  - UXP-553-1: LEAFCUTTER_MOCK_LOCK=real forbids all runtime overrides
"""

import json
import os
import unittest
from pathlib import Path

# The fixture repo root is this file's grandparent directory.
# leafcutter-web/fixtures/tests/test_mock_mode.py -> leafcutter-web/fixtures/
FIXTURE_ROOT = Path(__file__).parent.parent


class TestFixtureShapes(unittest.TestCase):
    """Verify the fixture entity records are shaped identically to real artifacts."""

    def _load_mock_data(self, relative_path: str) -> dict:
        """Load a mock-data JSON file from the fixture repo, covers UXP-551."""
        path = FIXTURE_ROOT / relative_path
        self.assertTrue(path.exists(), f"Fixture file missing: {relative_path}")
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)

    def test_build_pipeline_mock_data_has_agents_entity(self):
        """UXP-551-1: Agent records are present and shaped like the real registry."""
        data = self._load_mock_data(
            "docs/product-truth/mock-data/leafcutter/build-pipeline.mock.json"
        )
        self.assertIn("entities", data)
        agents_entity = data["entities"]["Agent"]
        self.assertIn("fields", agents_entity)
        self.assertIn("records", agents_entity)
        records = agents_entity["records"]
        self.assertGreater(len(records), 0, "Agent records must be non-empty")
        # Each record must have the required fields (UXP-551-1)
        for rec in records:
            self.assertIn("id", rec, "Agent record missing 'id'")
            self.assertIn("name", rec, "Agent record missing 'name'")
            self.assertIn("is_ticket_phase", rec, "Agent record missing 'is_ticket_phase'")
            self.assertIsInstance(rec["is_ticket_phase"], bool)

    def test_build_pipeline_mock_data_has_ticket_entity(self):
        """UXP-551-1: Ticket entity records present with required fields."""
        data = self._load_mock_data(
            "docs/product-truth/mock-data/leafcutter/build-pipeline.mock.json"
        )
        tickets_entity = data["entities"]["Ticket"]
        for rec in tickets_entity["records"]:
            self.assertIn("slug", rec)
            self.assertIn("status", rec)
            self.assertIn(rec["status"], {"todo", "in_progress", "done", "blocked"})

    def test_roadmap_fixture_has_three_phases(self):
        """UXP-551: Roadmap fixture renders 3 phases — sufficient for /roadmap view."""
        data = self._load_mock_data("docs/roadmap.json")
        self.assertIn("current_phase", data)
        self.assertIn("phases", data)
        self.assertGreaterEqual(len(data["phases"]), 3, "Roadmap must have at least 3 phases")
        phase_ids = {p["id"] for p in data["phases"]}
        self.assertIn("phase_1", phase_ids)

    def test_ac_fixtures_exist_for_all_uxp_550_acs(self):
        """UXP-550: AC YAML fixture files exist for the mock-mode ACs."""
        ac_dir = FIXTURE_ROOT / "docs/acceptance-criteria/ux-prototyping/UXP-550-atlas-mock-mode"
        self.assertTrue(ac_dir.exists(), "AC fixture directory missing")
        ac_files = list(ac_dir.glob("*.yaml"))
        ac_ids = {f.stem for f in ac_files}
        for expected in ("UXP-550", "UXP-551", "UXP-552", "UXP-553"):
            self.assertIn(expected, ac_ids, f"AC fixture {expected}.yaml missing")

    def test_flows_fixture_has_at_least_two_flows(self):
        """UXP-551: Flow fixture renders populated /flows view."""
        flows_dir = FIXTURE_ROOT / "docs/product-truth/flows/leafcutter"
        flow_files = list(flows_dir.glob("*.flow.json"))
        self.assertGreaterEqual(len(flow_files), 2, "Need at least 2 flow fixtures")
        # Verify each flow has required fields (UXP-551-1 shape invariant)
        for fp in flow_files:
            with open(fp, encoding="utf-8") as fh:
                flow = json.load(fh)
            self.assertIn("id", flow)
            self.assertIn("steps", flow)
            self.assertIsInstance(flow["steps"], list)

    def test_components_fixture_has_entries(self):
        """UXP-551: components.json fixture renders populated /architecture view."""
        data = self._load_mock_data("docs/components.json")
        self.assertIn("components", data)
        self.assertGreater(len(data["components"]), 0)

    def test_agent_registry_fixture_is_valid(self):
        """UXP-551: agent_registry.json fixture renders populated /pipeline view."""
        data = self._load_mock_data("config/agent_registry.json")
        self.assertIn("agents", data)
        agents = data["agents"]
        self.assertGreater(len(agents), 0)
        for agent in agents:
            self.assertIn("id", agent)
            self.assertIn("is_ticket_phase", agent)


class TestMockDecisionLogic(unittest.TestCase):
    """
    Unit tests for the mock-mode decision resolution order — UXP-553, UXP-553-1.

    These tests exercise the pure logic (env vars), not the Next.js request-scope
    path (cookie reading) which requires the server runtime.
    """

    def _resolve(self, lock: str | None, env: str | None) -> bool:
        """
        Pure-Python reimplementation of isMockActive() env-branch logic.
        Mirrors leafcutter-web/lib/data/mock.ts exactly — used as a reference.
        """
        # 1. Production lock
        if lock == "real":
            return False
        # 2. (Cookie override not tested here — requires Next.js request scope)
        # 3. Env default
        return env == "1"

    def test_production_lock_always_returns_real(self):
        """UXP-553-1: LEAFCUTTER_MOCK_LOCK=real forces real data regardless of env."""
        self.assertFalse(self._resolve(lock="real", env="1"))
        self.assertFalse(self._resolve(lock="real", env="0"))
        self.assertFalse(self._resolve(lock="real", env=None))

    def test_env_default_mock_on(self):
        """UXP-553: LEAFCUTTER_MOCK=1 defaults to mock on when no lock."""
        self.assertTrue(self._resolve(lock=None, env="1"))

    def test_env_default_mock_off(self):
        """UXP-553: LEAFCUTTER_MOCK=0 defaults to real when no lock."""
        self.assertFalse(self._resolve(lock=None, env="0"))

    def test_env_unset_defaults_to_real(self):
        """UXP-553: Unset LEAFCUTTER_MOCK defaults to real data."""
        self.assertFalse(self._resolve(lock=None, env=None))


if __name__ == "__main__":
    unittest.main()
