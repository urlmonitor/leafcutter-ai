"""
MODULE: unit_tests/agents/test_all_documented_emission_shapes_declare_the_same_key_set.py
GOAL: INF-400b-2-ii descriptor 1 — parse the JSON object out of every shipped
      description of the knowledge_captured record and assert they all declare
      the same required key set.

This is the defect stated as an assertion: before INF-400b-2-ii's
reconciliation, signoff SKILL.md section 7 step 4 keyed the record on
`ticket` and omitted `agent`/`component`; the three v3 agent templates keyed
it on `agent` + `component` and omitted `ticket`. This test parses the real
shipped files with a JSON parser (never a grep for a field-name substring) so
it cannot be satisfied by an unparseable or absent block.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HELPER_PATH = _REPO_ROOT / "unit_tests" / "agents" / "_emission_shape.py"

_spec = importlib.util.spec_from_file_location("_emission_shape", _HELPER_PATH)
assert _spec is not None and _spec.loader is not None, f"could not load spec for {_HELPER_PATH}"
_emission_shape: Any = importlib.util.module_from_spec(_spec)
sys.modules["_emission_shape"] = _emission_shape
_spec.loader.exec_module(_emission_shape)

discover_emission_surfaces = _emission_shape.discover_emission_surfaces
check_parity = _emission_shape.check_parity


class TestAllDocumentedEmissionShapesDeclareTheSameKeySet(unittest.TestCase):
    def test_all_documented_emission_shapes_declare_the_same_key_set(self):
        # covers: INF-400b-2-ii
        # angle: real_artifact
        surfaces = discover_emission_surfaces()
        # Sanity: the declared source must actually resolve to more than one
        # surface, or this test would vacuously pass on an empty parity check.
        self.assertGreater(
            len(surfaces),
            1,
            "expected more than one declared knowledge_captured emission surface",
        )

        result = check_parity(surfaces)

        self.assertTrue(
            result.ok,
            "shipped emission-shape descriptions disagree on required keys: "
            + "; ".join(result.problems),
        )
