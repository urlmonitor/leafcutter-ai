"""
MODULE: tests.kernel.config.test_dk_400a_1
GOAL: The split config section exists in the model, the shipped default and the committed schema
    (AC DK-400a-1).
BUSINESS CONTEXT: Every split tunable lives in config/kernel_config.default.json; the schema
    clients read must equal the one generated from the model.
ARCHITECTURE: Real committed files; the schema is regenerated from KernelConfig.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

from kernel.config import KernelConfig, kernel_config_schema, load_kernel_config

REPO = Path(__file__).resolve().parents[3]
SPLIT_KEYS = {"enabled", "bundle_threshold", "max_parts", "max_parts_per_run"}


class TestSplitConfigSchema(unittest.TestCase):
    """The split section is in model, default file and committed schema."""

    def test_kernel_config_schema_includes_split_section(self) -> None:
        # covers: DK-400a-1
        # angle: real_artifact
        """Regenerated schema has the split section and equals the committed file."""
        generated = kernel_config_schema()
        self.assertIn("split", generated["properties"])
        ref = generated["properties"]["split"]["$ref"].rsplit("/", 1)[-1]
        self.assertTrue(SPLIT_KEYS <= set(generated["$defs"][ref]["properties"]))
        committed = json.loads((REPO / "config" / "kernel_config.schema.json")
                               .read_text(encoding="utf-8"))
        self.assertEqual(committed, generated)
        default = json.loads((REPO / "config" / "kernel_config.default.json")
                             .read_text(encoding="utf-8"))
        self.assertTrue(SPLIT_KEYS <= set(default["split"]))
        self.assertEqual(default["split"]["bundle_threshold"], 0.8)
        self.assertIn("split", KernelConfig.model_fields)
        self.assertEqual(load_kernel_config(env={}).split.bundle_threshold, 0.8)
        # split.enabled is deliberately not pinned: false in E1/E2, pinned on by DK-400e-1.
