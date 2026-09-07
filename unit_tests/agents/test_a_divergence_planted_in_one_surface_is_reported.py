"""
MODULE: unit_tests/agents/test_a_divergence_planted_in_one_surface_is_reported.py
GOAL: INF-400b-2-ii descriptor 3 — a copy of one restating template with a
      single emission key renamed makes the parity check fail and name the
      offending file and key; the real, unmodified surface set passes.

Proves the check actually discriminates rather than being trivially
always-green. This test asserts the REAL declared surfaces are already
reconciled (`baseline.ok`) as a precondition — a parity check that always
reported "fine" would pass the discrimination half below for the wrong
reason, so the precondition matters as much as the discrimination itself.
"""

from __future__ import annotations

import importlib.util
import re
import sys
import tempfile
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
EmissionSurface = _emission_shape.EmissionSurface


class TestADivergencePlantedInOneSurfaceIsReported(unittest.TestCase):
    def test_a_divergence_planted_in_one_surface_is_reported(self):
        # covers: INF-400b-2-ii
        # angle: failure
        surfaces = discover_emission_surfaces()

        baseline = check_parity(surfaces)
        self.assertTrue(
            baseline.ok,
            "precondition failed: the real declared surfaces must already be "
            f"reconciled before planting a divergence: {baseline.problems}",
        )

        restating = [s for s in surfaces if not s.is_normative]
        self.assertTrue(restating, "expected at least one restating surface to tamper with")
        target = restating[0]

        original_text = target.path.read_text(encoding="utf-8")
        # Rename exactly one key inside the JSON emission object: "component"
        # becomes "component_renamed". This must hit the JSON literal only,
        # not any other prose occurrence of the word "component" in the file.
        tampered_text, n = re.subn(
            r'"component":', '"component_renamed":', original_text, count=1
        )
        self.assertEqual(1, n, "expected exactly one component: JSON key occurrence to tamper")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tampered_path = Path(tmp_dir) / f"tampered-{target.path.name}"
            tampered_path.write_text(tampered_text, encoding="utf-8")

            tampered_surface = EmissionSurface(
                label=f"{target.label}-TAMPERED", path=tampered_path, is_normative=False
            )
            tampered_surfaces = [s for s in surfaces if s.label != target.label] + [
                tampered_surface
            ]

            tampered_result = check_parity(tampered_surfaces)

        self.assertFalse(tampered_result.ok, "planted divergence must make the check fail")
        joined_problems = " ".join(tampered_result.problems)
        self.assertIn(
            tampered_surface.label,
            joined_problems,
            f"failure must name the offending surface: {tampered_result.problems}",
        )
        self.assertIn(
            "component_renamed",
            joined_problems,
            f"failure must name the offending key: {tampered_result.problems}",
        )
