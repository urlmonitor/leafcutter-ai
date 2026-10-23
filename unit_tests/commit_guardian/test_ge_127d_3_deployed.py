"""
MODULE: unit_tests/commit_guardian/test_ge_127d_3_deployed.py
COVERS: GE-127d-3 -- the deployed descriptor. Reads the shared reference layout
    (a real build.py deploy produced once per run); never spawns a build of its
    own.

DECISION HISTORY
- 2026-10-20 [GE-127d-3/test-writer]: Initial authoring.
"""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_3_content as content  # noqa: E402
import _ge_127d_3_fixture as fx  # noqa: E402


class TestDeployedMeasureCoversEveryCheckedExtension(unittest.TestCase):
    @pytest.mark.shared_layout_reader
    @pytest.mark.usefixtures("shared_reference_layout")
    def test_ge_127d_3_the_deployed_measure_has_a_tokenizer_for_every_checked_extension(self):
        # covers: GE-127d-3
        # angle: deployed
        """In a cold subprocess importing only from the DEPLOYED commit_guardian
        directory, every file_size.checked_extensions entry measures a generated
        file holding one comment in every style of its language to exactly its
        code-line count -- none falls back to a raw count, none raises
        ModuleNotFoundError (the new _file_size_measure sub-package reached the deploy)."""
        deployed = fx.deployed_guardian_dir()
        config = json.loads((deployed / "commit_guardian.json").read_text(encoding="utf-8"))
        extensions = config["file_size"]["checked_extensions"]
        self.assertTrue(extensions, msg="the deployed configuration must name checked extensions")
        self.assertTrue(
            (deployed / "_file_size_measure").is_dir(), msg="the measure sub-package must reach the deploy"
        )
        items, wanted = [], []
        for ext in extensions:
            for style in content.styles_for(ext):
                text, expected = content.build_text(ext, 4, 1, style)
                items.append((ext, text))
                wanted.append((ext, style, expected))
        measured = fx.measure_texts(items, src_dir=deployed)
        wrong = [(ext, style, got, want) for (ext, style, want), got in zip(wanted, measured) if got != want]
        self.assertEqual([], wrong, msg="every checked extension must measure by its own tokenizer when deployed")


if __name__ == "__main__":
    unittest.main()
