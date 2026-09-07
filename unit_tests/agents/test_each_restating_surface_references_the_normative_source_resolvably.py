"""
MODULE: unit_tests/agents/test_each_restating_surface_references_the_normative_source_resolvably.py
GOAL: INF-400b-2-ii descriptor 6 — the reference each restating v3 agent
      template gives for the authoritative emission shape resolves to an
      EXISTING file, both in the package checkout (templates/skills/signoff/
      SKILL.md) and its deployed counterpart (.claude/skills/signoff/
      SKILL.md), so a reader following it never lands on a missing target.

"Resolvably" is the operative word: this test does not stop at confirming the
path SUBSTRING is mentioned in the template text (a grep-only check would
pass on a typo'd path or a path to a file that was since deleted). It
extracts the referenced path strings and calls Path.exists() on each one.
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
find_normative_references = _emission_shape.find_normative_references


class TestEachRestatingSurfaceReferencesTheNormativeSourceResolvably(unittest.TestCase):
    def test_each_restating_surface_references_the_normative_source_resolvably(self):
        # covers: INF-400b-2-ii
        # angle: reachability
        surfaces = discover_emission_surfaces()
        restating = [s for s in surfaces if not s.is_normative]
        self.assertTrue(restating, "expected at least one restating surface to check")

        failures = []
        for surface in restating:
            text = surface.path.read_text(encoding="utf-8")
            checkout_ref, deployed_ref = find_normative_references(text)

            if checkout_ref is None:
                failures.append(f"{surface.label}: no checkout-layout reference found")
                continue
            if deployed_ref is None:
                failures.append(f"{surface.label}: no deployed-layout reference found")
                continue

            checkout_target = _REPO_ROOT / checkout_ref
            deployed_target = _REPO_ROOT / deployed_ref

            if not checkout_target.exists():
                failures.append(
                    f"{surface.label}: checkout reference {checkout_ref!r} does not resolve "
                    f"to a real file ({checkout_target})"
                )
            if not deployed_target.exists():
                failures.append(
                    f"{surface.label}: deployed reference {deployed_ref!r} does not resolve "
                    f"to a real file ({deployed_target})"
                )

        self.assertEqual(
            [],
            failures,
            "restating surface(s) reference the normative source unresolvably:\n"
            + "\n".join(failures),
        )
