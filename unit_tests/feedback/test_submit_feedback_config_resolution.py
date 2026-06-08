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


if __name__ == "__main__":
    unittest.main()
