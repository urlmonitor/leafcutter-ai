"""
MODULE: test_build_feedback
GOAL: Integration tests for the build_feedback phase and deployed feedback
    script layout. Verifies that build_feedback copies the correct files to
    the target project and that submit_feedback.py produces valid JSONL from
    the deployed location.
BUSINESS CONTEXT: The feedback scripts must work from a consumer project
    layout where build.py deploys them to scripts/feedback/.
ARCHITECTURE: Uses tempfile.TemporaryDirectory to simulate a deployed consumer
    project. Tests exercise both the build phase and the deployed script.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

sys.path.insert(0, str(_SCRIPTS_DIR))

from build_phases import build_feedback  # noqa: E402


class TestBuildFeedbackPhase(unittest.TestCase):
    """Verify that build_feedback deploys the expected files."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target_root = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_deploys_feedback_scripts(self):
        written = build_feedback(self.target_root, {}, dry_run=False, force=True)
        self.assertGreaterEqual(written, 3)

        expected_scripts = [
            "scripts/feedback/submit_feedback.py",
            "scripts/feedback/emit_hook_finding.py",
            "scripts/feedback/list_tags.py",
        ]
        for rel in expected_scripts:
            path = self.target_root / rel
            self.assertTrue(path.exists(), f"Missing deployed file: {rel}")

    def test_deploys_feedback_categories_yaml(self):
        build_feedback(self.target_root, {}, dry_run=False, force=True)
        config_path = self.target_root / "config" / "feedback_categories.yaml"
        self.assertTrue(config_path.exists(), "feedback_categories.yaml not deployed to config/")

    def test_creates_debugging_logs_dir(self):
        build_feedback(self.target_root, {}, dry_run=False, force=True)
        logs_dir = self.target_root / "debugging" / "logs"
        self.assertTrue(logs_dir.is_dir(), "debugging/logs/ directory not created")

    def test_dry_run_writes_nothing(self):
        written = build_feedback(self.target_root, {}, dry_run=True, force=True)
        self.assertGreaterEqual(written, 3)
        self.assertFalse(
            (self.target_root / "scripts" / "feedback").exists(),
            "dry-run should not create files",
        )

    def test_idempotent_second_run(self):
        build_feedback(self.target_root, {}, dry_run=False, force=True)
        written_2 = build_feedback(self.target_root, {}, dry_run=False, force=True)
        self.assertEqual(written_2, 0, "Second run should skip identical files")


class TestDeployedSubmitFeedback(unittest.TestCase):
    """Verify submit_feedback.py works from a deployed consumer layout."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.target_root = Path(self._tmpdir.name)
        # Create .claude/ marker so _find_project_root() resolves correctly
        (self.target_root / ".claude").mkdir()
        build_feedback(self.target_root, {}, dry_run=False, force=True)

    def tearDown(self):
        self._tmpdir.cleanup()

    def _load_deployed_submit_feedback(self):
        sf_path = self.target_root / "scripts" / "feedback" / "submit_feedback.py"
        spec = importlib.util.spec_from_file_location(
            "deployed_submit_feedback", sf_path,
        )
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    def test_submit_produces_valid_jsonl(self):
        mod = self._load_deployed_submit_feedback()
        jsonl_path = self.target_root / "debugging" / "logs" / "feedback.jsonl"

        exit_code = mod.main([
            "--ticket", "tickets/00_inbox/TEST-TICKET.md",
            "--phase", "python-coder",
            "--category", "complete",
            "--tags", "test-tag",
            "--note", "Integration test feedback entry",
            "--jsonl", str(jsonl_path),
        ])
        self.assertEqual(exit_code, 0)
        self.assertTrue(jsonl_path.exists(), "feedback.jsonl was not created")

        lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)

        entry = json.loads(lines[0])
        self.assertIn("feedback_id", entry)
        self.assertEqual(entry["phase"], "python-coder")
        self.assertEqual(entry["category"], "complete")
        self.assertEqual(entry["tags"], ["test-tag"])
        self.assertEqual(entry["note"], "Integration test feedback entry")
        self.assertIn("timestamp", entry)
        self.assertTrue(entry["feedback_id"].startswith("fb_"))

    def test_config_resolution_from_deployed_location(self):
        mod = self._load_deployed_submit_feedback()
        cats = mod._load_categories()
        self.assertIn("complete", cats)
        self.assertIn("quality-concern", cats)


if __name__ == "__main__":
    unittest.main()
