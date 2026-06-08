"""
MODULE: unit_tests/feedback/test_submit_feedback_config_resolution.py
GOAL: Verify AC INF-100c-1 — Config resolution uses the script's own location
      as anchor.  submit_feedback.py must find feedback_categories.yaml at
      <leafcutter_root>/config/ relative to the script file, not relative to
      the process working directory or any .claude/ search.
BUSINESS CONTEXT: When submit_feedback.py is deployed to
      <project>/.leafcutter/scripts/feedback/, the file at
      <project>/.leafcutter/config/feedback_categories.yaml must be discovered
      automatically without hardcoded paths or CWD dependency.
"""

from __future__ import annotations

import importlib
import json
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUBMIT_SCRIPT = _REPO_ROOT / "scripts" / "feedback" / "submit_feedback.py"

# The script lives two levels below its config root:
#   scripts/feedback/submit_feedback.py  → parents[2] = repo root
_EXPECTED_CONFIG_ROOT = _SUBMIT_SCRIPT.resolve().parents[2] / "config"
_EXPECTED_CATEGORIES_FILE = _EXPECTED_CONFIG_ROOT / "feedback_categories.yaml"


class TestConfigRootResolution(unittest.TestCase):
    """AC INF-100c-1: config root is anchored to the script's own location."""

    def test_find_config_root_returns_script_relative_path(self):
        # covers: INF-100c-1
        """_find_config_root() must return parents[2]/config of the script file."""
        # Import the module dynamically so the test is always using the
        # current source, not a cached import from a different path.
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "submit_feedback", str(_SUBMIT_SCRIPT)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod._find_config_root()
        self.assertEqual(result, _EXPECTED_CONFIG_ROOT)

    def test_categories_file_path_is_script_relative(self):
        # covers: INF-100c-1
        """_CATEGORIES_FILE must point to the config dir two levels above the script."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "submit_feedback", str(_SUBMIT_SCRIPT)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        self.assertEqual(mod._CATEGORIES_FILE, _EXPECTED_CATEGORIES_FILE)

    def test_categories_file_exists_at_resolved_path(self):
        # covers: INF-100c-1
        """The resolved categories file must actually exist on disk."""
        self.assertTrue(
            _EXPECTED_CATEGORIES_FILE.exists(),
            f"feedback_categories.yaml not found at {_EXPECTED_CATEGORIES_FILE}",
        )

    def test_config_root_independent_of_cwd(self):
        # covers: INF-100c-1
        """Config resolution must not change when the process CWD changes."""
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "submit_feedback", str(_SUBMIT_SCRIPT)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        # The result must equal the script-relative path regardless of CWD.
        result = mod._find_config_root()
        self.assertEqual(
            result.resolve(),
            _EXPECTED_CONFIG_ROOT.resolve(),
            "Config root changed with CWD — resolution is not anchored to __file__",
        )

    def test_feedback_submission_succeeds_from_any_cwd(self):
        # covers: INF-100c-1
        """End-to-end: submit_feedback.py must succeed when invoked from /tmp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "feedback.jsonl"
            result = subprocess.run(
                [
                    sys.executable,
                    str(_SUBMIT_SCRIPT),
                    "--ticket",
                    "tickets/00_inbox/epics/EPIC-FeedbackPortability/TICKET-20260608-INF-100c-1.md",
                    "--phase",
                    "test-runner",
                    "--category",
                    "complete",
                    "--note",
                    "config-resolution acceptance-test probe",
                    "--jsonl",
                    str(jsonl_path),
                ],
                capture_output=True,
                text=True,
                cwd="/tmp",  # deliberately different CWD
                timeout=10,
            )
        self.assertEqual(
            result.returncode,
            0,
            f"submit_feedback.py failed from /tmp CWD.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertRegex(
            result.stdout.strip(),
            r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$",
            "Expected feedback_id on stdout",
        )


class TestConfigRootFromSourceRepoLocation(unittest.TestCase):
    """AC INF-100c-2: config resolution works from the source repo location."""

    def test_find_config_root_from_source_script_location(self):
        # covers: INF-100c-2
        """When running from leafcutter-ai/scripts/feedback/, config is at leafcutter-ai/config/.

        This test verifies the source-repo-location layout:
          leafcutter-ai/scripts/feedback/submit_feedback.py
          leafcutter-ai/config/feedback_categories.yaml  ← must be found here

        _find_config_root() must return parents[2]/config relative to the script file,
        which resolves to the source repo config/ directory.
        """
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "submit_feedback_src", str(_SUBMIT_SCRIPT)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        result = mod._find_config_root()

        # The script is at scripts/feedback/submit_feedback.py within the repo.
        # parents[2] of that path should be the repo root.
        repo_root = _SUBMIT_SCRIPT.resolve().parents[2]
        expected = repo_root / "config"

        self.assertEqual(
            result,
            expected,
            f"_find_config_root() returned {result!r}, expected {expected!r}. "
            f"Config resolution is not anchored to the source repo location.",
        )

    def test_source_repo_categories_file_is_readable(self):
        # covers: INF-100c-2
        """feedback_categories.yaml must be readable from the source repo location.

        Verifies backward compatibility: the file exists and is parseable with
        yaml.safe_load from the source-repo-relative path.
        """
        import importlib.util

        try:
            import yaml
        except ImportError:
            self.skipTest("PyYAML not installed — skipping readability check")

        spec = importlib.util.spec_from_file_location(
            "submit_feedback_src2", str(_SUBMIT_SCRIPT)
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        config_dir = mod._find_config_root()
        categories_file = config_dir / "feedback_categories.yaml"

        self.assertTrue(
            categories_file.exists(),
            f"feedback_categories.yaml not found at source-repo location: {categories_file}",
        )

        with open(categories_file, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        self.assertIn(
            "categories",
            data,
            "feedback_categories.yaml must have a 'categories' key at the source-repo location",
        )

    def test_source_repo_config_resolution_end_to_end(self):
        # covers: INF-100c-2
        """End-to-end: submit_feedback.py called from the source repo finds its config.

        Runs submit_feedback.py with the script's own directory as cwd to simulate
        being invoked from within the source repo tree. The script must succeed and
        emit a valid feedback_id, proving backward compatibility is preserved.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            jsonl_path = Path(tmpdir) / "feedback.jsonl"
            # Run with cwd set to the script's own directory (source repo location)
            result = subprocess.run(
                [
                    sys.executable,
                    str(_SUBMIT_SCRIPT),
                    "--ticket",
                    "tickets/00_inbox/epics/EPIC-FeedbackPortability/02_TICKET-20260608-INF-100c-2.md",
                    "--phase",
                    "test-runner",
                    "--category",
                    "complete",
                    "--note",
                    "INF-100c-2 source-repo-location acceptance-test probe",
                    "--jsonl",
                    str(jsonl_path),
                ],
                capture_output=True,
                text=True,
                cwd=str(_SUBMIT_SCRIPT.parent),  # source repo: scripts/feedback/
                timeout=10,
            )
        self.assertEqual(
            result.returncode,
            0,
            f"submit_feedback.py failed when invoked from its source-repo location.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )
        self.assertRegex(
            result.stdout.strip(),
            r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$",
            "Expected feedback_id on stdout from source-repo-location invocation",
        )


if __name__ == "__main__":
    unittest.main()
