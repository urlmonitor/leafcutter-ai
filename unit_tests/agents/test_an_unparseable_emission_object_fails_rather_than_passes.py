"""
MODULE: unit_tests/agents/test_an_unparseable_emission_object_fails_rather_than_passes.py
GOAL: INF-400b-2-ii descriptor 4 — a surface whose documented object is not
      valid JSON, or whose emission block is absent entirely, is reported as
      a failure and never counted as conformant. Silence is not a pass.

Covers three shapes of "unparseable":
  (a) the file has a fenced ```json block but its content is malformed JSON,
  (b) the file has no knowledge_captured block at all,
  (c) the file does not exist on disk.

Also asserts the real declared surfaces are already reconciled as a
precondition, mirroring descriptor 3 — otherwise a check that is broken in a
way that always reports failure would trivially satisfy this test too.
"""

from __future__ import annotations

import importlib.util
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
extract_emission_object = _emission_shape.extract_emission_object
EmissionSurface = _emission_shape.EmissionSurface
EmissionBlockError = _emission_shape.EmissionBlockError


class TestAnUnparseableEmissionObjectFailsRatherThanPasses(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_dir = Path(self._tmp.name)

    def test_malformed_json_block_is_reported_as_failure(self):
        # covers: INF-400b-2-ii
        # angle: failure
        real_baseline = check_parity(discover_emission_surfaces())
        self.assertTrue(
            real_baseline.ok,
            f"precondition failed: real surfaces must be reconciled: {real_baseline.problems}",
        )

        bad_path = self.tmp_dir / "malformed.md"
        bad_path.write_text(
            "Emits knowledge_captured:\n```json\n"
            '{"event": "knowledge_captured", "timestamp": "<ISO>", NOT_VALID_JSON}\n'
            "```\n",
            encoding="utf-8",
        )
        with self.assertRaises(EmissionBlockError):
            extract_emission_object(bad_path)

        surfaces = discover_emission_surfaces() + [
            EmissionSurface(label="malformed-surface", path=bad_path)
        ]
        result = check_parity(surfaces)
        self.assertFalse(result.ok, "a malformed emission block must never be counted conformant")
        self.assertTrue(
            any("malformed-surface" in p for p in result.problems),
            f"failure must name the offending surface: {result.problems}",
        )

    def test_absent_emission_block_is_reported_as_failure(self):
        # covers: INF-400b-2-ii
        # angle: failure
        real_baseline = check_parity(discover_emission_surfaces())
        self.assertTrue(
            real_baseline.ok,
            f"precondition failed: real surfaces must be reconciled: {real_baseline.problems}",
        )

        no_block_path = self.tmp_dir / "no_block.md"
        no_block_path.write_text(
            "This agent template mentions knowledge_captured in prose but has "
            "no fenced JSON example anywhere in the file.\n",
            encoding="utf-8",
        )
        with self.assertRaises(EmissionBlockError):
            extract_emission_object(no_block_path)

        surfaces = discover_emission_surfaces() + [
            EmissionSurface(label="no-block-surface", path=no_block_path)
        ]
        result = check_parity(surfaces)
        self.assertFalse(result.ok, "an absent emission block must never be counted conformant")
        self.assertTrue(
            any("no-block-surface" in p for p in result.problems),
            f"failure must name the offending surface: {result.problems}",
        )

    def test_missing_file_is_reported_as_failure_not_skipped(self):
        # covers: INF-400b-2-ii
        # angle: failure
        real_baseline = check_parity(discover_emission_surfaces())
        self.assertTrue(
            real_baseline.ok,
            f"precondition failed: real surfaces must be reconciled: {real_baseline.problems}",
        )

        missing_path = self.tmp_dir / "does_not_exist.md"
        self.assertFalse(missing_path.exists())

        surfaces = discover_emission_surfaces() + [
            EmissionSurface(label="missing-surface", path=missing_path)
        ]
        result = check_parity(surfaces)
        self.assertFalse(result.ok, "a missing surface file must never be silently skipped")
        self.assertTrue(
            any("missing-surface" in p for p in result.problems),
            f"failure must name the offending surface: {result.problems}",
        )
