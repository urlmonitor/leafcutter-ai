"""
MODULE: unit_tests/agents/test_a_newly_declared_emission_surface_is_discovered_not_ignored.py
GOAL: INF-400b-2-ii descriptor 5 — the most important descriptor. Adding a
      fifth declared emission surface with a divergent key set makes the
      parity check fail, proving the surface set is DERIVED from the
      declared source (config/agent_registry.json's v3 agents + the signoff
      skill) rather than hard-coded to today's four paths.

Mechanism (seam angle): this test does not call an internal "add a surface"
hook. It writes a REAL temporary copy of config/agent_registry.json with one
additional v3-marked agent entry appended — the exact declared-source shape a
real future PR would add — and passes THAT file as `registry_path` to the
real, unmodified `discover_emission_surfaces` production seam. If discovery
were hard-coded to the current three template paths plus the skill, the new
entry would never be seen and this test would fail to detect the planted
divergence; it does not fail, which is the proof the seam is declaration-
driven.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HELPER_PATH = _REPO_ROOT / "unit_tests" / "agents" / "_emission_shape.py"
_REGISTRY_PATH = _REPO_ROOT / "config" / "agent_registry.json"

_spec = importlib.util.spec_from_file_location("_emission_shape", _HELPER_PATH)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HELPER_PATH}"
_emission_shape: Any = importlib.util.module_from_spec(_spec)
sys.modules["_emission_shape"] = _emission_shape
_spec.loader.exec_module(_emission_shape)

discover_emission_surfaces = _emission_shape.discover_emission_surfaces
check_parity = _emission_shape.check_parity


class TestANewlyDeclaredEmissionSurfaceIsDiscoveredNotIgnored(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_dir = Path(self._tmp.name)

    def test_a_newly_declared_emission_surface_is_discovered_not_ignored(self):
        # covers: INF-400b-2-ii
        # angle: seam
        real_baseline = check_parity(discover_emission_surfaces())
        self.assertTrue(
            real_baseline.ok,
            "precondition failed: the real declared surfaces (without any "
            f"planted fifth surface) must already be reconciled: {real_baseline.problems}",
        )

        with open(_REGISTRY_PATH, encoding="utf-8") as fh:
            registry = json.load(fh)

        # A divergent fifth surface, written to a real file the discovery
        # seam has never seen a path for. Its declared key set (missing
        # "component") deliberately diverges from the normative shape.
        fifth_agent_path = self.tmp_dir / "fifth-agent-v3.md"
        fifth_agent_path.write_text(
            "## S9 Knowledge Loop — Emission\n\n"
            "```json\n"
            '{"event": "knowledge_captured", "timestamp": "<ISO-8601>", '
            '"agent": "fifth-agent-v3", "destination": "<routed_file_path>", '
            '"entry_kind": "<entry_kind>"}\n'
            "```\n",
            encoding="utf-8",
        )

        registry = dict(registry)
        registry["agents"] = [*registry["agents"], {
            "id": "fifth-agent-v3",
            "description": (
                "Fifth Agent for v3 ticket-creation pipeline (test-only, "
                "planted to prove discovery is not hard-coded to 4 paths)."
            ),
            "template_path": str(fifth_agent_path),
        }]

        temp_registry_path = self.tmp_dir / "agent_registry.json"
        temp_registry_path.write_text(json.dumps(registry), encoding="utf-8")

        surfaces = discover_emission_surfaces(registry_path=temp_registry_path)

        surface_labels = {s.label for s in surfaces}
        self.assertIn(
            "fifth-agent-v3",
            surface_labels,
            "discovery must find the newly declared registry entry, not just "
            "the three surfaces that existed at authoring time",
        )
        self.assertEqual(
            5,
            len(surfaces),
            f"expected normative skill + 3 existing v3 agents + 1 new = 5, got: {surface_labels}",
        )

        result = check_parity(surfaces)
        self.assertFalse(
            result.ok,
            "the fifth surface's divergent key set must be caught, not ignored",
        )
        self.assertTrue(
            any("fifth-agent-v3" in p for p in result.problems),
            f"failure must name the newly discovered surface: {result.problems}",
        )
