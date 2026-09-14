"""
MODULE: unit_tests/agents/test_v3_agent_emission_shape_matches_section_7.py
GOAL: INF-700b-1 descriptor 3 (test_spec) — the emission JSON from
      product-owner.md, business-analyst.md and it-po.md S9/§9 blocks must
      each declare a `text` key, and their required key sets must match
      signoff SKILL.md section 7 step 4's, so the schema change lands on all
      four surfaces in a single change and no install ever runs a mixed
      contract (it_requirements #3).

BUSINESS CONTEXT: INF-400b-2-ii already reconciled the pre-existing
      ticket-vs-agent+component divergence between these four surfaces (see
      unit_tests/agents/test_all_documented_emission_shapes_declare_the_same_
      key_set.py), so today the four surfaces already agree on their
      required key set -- but NONE of them yet declares `text`. This test is
      therefore deliberately stricter than a bare parity check: parity alone
      would already be satisfied by four surfaces that all omit `text`
      identically, which would let this AC's own schema change go entirely
      unimplemented while the test stayed green. Asserting `text` is present
      in every surface's required set is what makes this test a genuine
      pin of INF-700b-1's it_requirements #3 rather than a restatement of
      the already-closed INF-400b-2-ii parity check.

Parses the real shipped JSON blocks (never a hard-coded copy of the field
list) via the shared _emission_shape helper, so a future fifth surface is
discovered rather than silently skipped.
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
extract_emission_object = _emission_shape.extract_emission_object
producer_required_keys = _emission_shape.producer_required_keys


class TestV3AgentEmissionShapeMatchesSection7(unittest.TestCase):
    def test_v3_agent_emission_shape_matches_section_7(self) -> None:
        # covers: INF-700b-1
        # angle: real_artifact
        surfaces = discover_emission_surfaces()
        # Sanity: the declared source must actually resolve to more than one
        # surface (the normative signoff skill plus at least the three v3
        # agents), or the equality check below would vacuously pass.
        self.assertGreater(
            len(surfaces),
            1,
            "expected more than one declared knowledge_captured emission surface",
        )

        required_by_label: dict[str, frozenset[str]] = {}
        for surface in surfaces:
            obj = extract_emission_object(surface.path)
            required_by_label[surface.label] = producer_required_keys(obj)

        missing_text = {
            label: sorted(keys)
            for label, keys in required_by_label.items()
            if "text" not in keys
        }
        self.assertEqual(
            {},
            missing_text,
            "INF-700b-1 it_requirements #3 requires `text` be added to all four "
            "emission surfaces in a single change, but these surfaces do not "
            f"yet declare it as required: {missing_text}",
        )

        baseline_label, baseline_keys = next(iter(required_by_label.items()))
        mismatches = {
            label: sorted(keys)
            for label, keys in required_by_label.items()
            if keys != baseline_keys
        }
        self.assertEqual(
            {},
            mismatches,
            "required key sets diverge across emission surfaces once `text` is "
            f"expected on all of them: baseline ({baseline_label}) = "
            f"{sorted(baseline_keys)}; mismatches = {mismatches}",
        )


if __name__ == "__main__":
    unittest.main()
