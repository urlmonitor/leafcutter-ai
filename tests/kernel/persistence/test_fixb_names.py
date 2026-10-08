"""
MODULE: tests.kernel.persistence.test_fixb_names
GOAL: Prove identifier validation rejects a trailing newline.
BUSINESS CONTEXT: `$` matches before a final newline, so `abc\n` used to pass as a safe path
    component and artifact name; ids come from hosts and clients.
ARCHITECTURE: The real validators, no IO.
"""

from __future__ import annotations

import unittest

from kernel.persistence.fsutil import UnsafePathComponent, safe_component
from kernel.persistence.memory import InvalidArtifactName, MemoryArtifactStore


class TestTrailingNewline(unittest.TestCase):
    """A trailing newline is never part of a valid name."""

    def test_safe_component_rejects_a_trailing_newline(self) -> None:
        with self.assertRaises(UnsafePathComponent):
            safe_component("run-1\n")

    def test_artifact_names_reject_a_trailing_newline(self) -> None:
        with self.assertRaises(InvalidArtifactName):
            MemoryArtifactStore().write_artifact("run-1", "report.md\n", "x")


if __name__ == "__main__":
    unittest.main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-01 20:00 [python-coder]: Regression for review finding R3-4.
#   (#KernelBootstrapV0/FIXB)
# ====================================================================
