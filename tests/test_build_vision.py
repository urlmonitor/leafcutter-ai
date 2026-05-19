"""
MODULE: test_build_vision
GOAL: Unit tests for the build_vision() phase in build_phases.py.
BUSINESS CONTEXT: Verifies that build_vision creates docs/vision.md from
    VISION.template.md when absent, skips the write when the file already exists,
    and correctly handles --dry-run mode.
ARCHITECTURE: Standard unittest. No database, no network, no file I/O to
    project directories. Uses tempfile.TemporaryDirectory for all output.
    Adds the leafcutter/scripts/ directory to sys.path so that
    build_phases.py's relative imports resolve correctly, then loads the module
    via importlib.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Load build_phases module from its canonical location (outside unit_tests/)
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_BUILD_PHASES_PATH = _SCRIPTS_DIR / "build_phases.py"

# Prepend the scripts directory so that build_phases.py's relative imports
# (template_compiler, build_precommit, etc.) resolve correctly during exec_module.
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


def _load_build_phases():
    """Load build_phases.py as a module without side-effects.

    Returns:
        The loaded build_phases module object with all public symbols accessible.
    """
    spec = importlib.util.spec_from_file_location(
        "portable_build_phases", _BUILD_PHASES_PATH
    )
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load build_phases.py from {_BUILD_PHASES_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_build_phases = _load_build_phases()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBuildVision(unittest.TestCase):
    """Tests for build_vision() in build_phases.py."""

    def test_build_vision_creates_when_absent(self):
        """Case 1: vision.md is absent — build_vision should create it."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target_root = Path(tmpdir)
            docs_dir = target_root / "docs"
            docs_dir.mkdir(parents=True)

            # Precondition: docs/vision.md does not exist
            vision_path = docs_dir / "vision.md"
            self.assertFalse(vision_path.exists())

            # Call build_vision with force=True (force is ignored by the phase,
            # but we pass it to confirm the override behaves correctly)
            result = _build_phases.build_vision(
                target_root, config={}, dry_run=False, force=True
            )

            # Assert: returns 1 (file was written)
            self.assertEqual(result, 1)

            # Assert: file was created
            self.assertTrue(vision_path.exists())

            content = vision_path.read_text(encoding="utf-8")

            # Assert: file contains <!-- QUESTION: markers (intact, not stripped)
            self.assertIn("<!-- QUESTION:", content)

            # Assert: file contains all 8 required section headings
            required_sections = [
                "## Mission Statement",
                "## Current Phase",
                "## What We're NOT Doing",
                "## Strategic Assets",
                "## Roadmap",
                "## Success Criteria",
                "## Key Decisions Log",
                "## Epics Mapping",
            ]
            for section in required_sections:
                self.assertIn(section, content,
                              f"Missing required section: {section}")

    def test_build_vision_skips_when_exists(self):
        """Case 2: vision.md already exists — build_vision should not overwrite it."""
        sentinel = "SENTINEL_CONTENT_DO_NOT_OVERWRITE\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            target_root = Path(tmpdir)
            docs_dir = target_root / "docs"
            docs_dir.mkdir(parents=True)

            vision_path = docs_dir / "vision.md"
            vision_path.write_text(sentinel, encoding="utf-8")

            # Call build_vision with force=True — the phase must ignore force
            result = _build_phases.build_vision(
                target_root, config={}, dry_run=False, force=True
            )

            # Assert: returns 0 (no write)
            self.assertEqual(result, 0)

            # Assert: file content is unchanged (sentinel preserved)
            self.assertEqual(vision_path.read_text(encoding="utf-8"), sentinel)

    def test_build_vision_dry_run_no_write(self):
        """Case 3: dry-run with absent vision.md — should log intent but not write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            target_root = Path(tmpdir)
            docs_dir = target_root / "docs"
            docs_dir.mkdir(parents=True)

            vision_path = docs_dir / "vision.md"
            self.assertFalse(vision_path.exists())

            # Call build_vision in dry-run mode
            result = _build_phases.build_vision(
                target_root, config={}, dry_run=True, force=True
            )

            # Assert: returns 1 (intent to write)
            self.assertEqual(result, 1)

            # Assert: file does NOT exist on disk (dry-run means no actual write)
            self.assertFalse(vision_path.exists())


if __name__ == "__main__":
    unittest.main()
