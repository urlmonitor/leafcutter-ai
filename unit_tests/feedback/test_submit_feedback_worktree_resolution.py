"""
MODULE: unit_tests/feedback/test_submit_feedback_worktree_resolution.py
GOAL: Verify AC INF-100c-1-i — Config resolution in a worktree of a deployed project.
      When submit_feedback.py runs from a worktree's .leafcutter/scripts/feedback/,
      config resolution must NOT walk past the .leafcutter/ directory into the
      worktree's parent.  Config must be found at the worktree's own
      .leafcutter/config/feedback_categories.yaml.
BUSINESS CONTEXT: A git worktree created from a deployed project that has
      .leafcutter/ preserves the same .leafcutter/ layout.  The script must
      resolve its config relative to its own __file__ location, never by
      searching upward past .leafcutter/.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SUBMIT_SCRIPT = _REPO_ROOT / "scripts" / "feedback" / "submit_feedback.py"
_REAL_CATEGORIES = _REPO_ROOT / "config" / "feedback_categories.yaml"


def _load_module_from_path(script_path: Path, module_name: str = "submit_feedback"):
    """Load a Python module from an arbitrary filesystem path."""
    spec = importlib.util.spec_from_file_location(module_name, str(script_path))
    assert spec is not None and spec.loader is not None, f"could not load spec for {script_path}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestWorktreeConfigResolution(unittest.TestCase):
    """AC INF-100c-1-i: config resolution does not walk past .leafcutter/."""

    def setUp(self):
        """Create a simulated worktree with .leafcutter/ layout."""
        self.tmpdir = tempfile.mkdtemp(prefix="leafcutter_wt_test_")
        self.worktree = Path(self.tmpdir) / "my-project-worktree"
        self.worktree.mkdir()

        # Simulate .leafcutter/ deployment layout inside the worktree
        leafcutter_dir = self.worktree / ".leafcutter"
        scripts_dir = leafcutter_dir / "scripts" / "feedback"
        config_dir = leafcutter_dir / "config"
        scripts_dir.mkdir(parents=True)
        config_dir.mkdir(parents=True)

        # Deploy submit_feedback.py into the worktree's .leafcutter/scripts/feedback/
        self.deployed_script = scripts_dir / "submit_feedback.py"
        shutil.copy2(str(_SUBMIT_SCRIPT), str(self.deployed_script))

        # Deploy a minimal (but valid) feedback_categories.yaml into the
        # worktree's .leafcutter/config/ so end-to-end submission works.
        shutil.copy2(str(_REAL_CATEGORIES), str(config_dir / "feedback_categories.yaml"))

        # Also create a parent config dir to verify the script does NOT use it
        parent_config_dir = self.worktree / "config"
        parent_config_dir.mkdir()
        # Deliberately leave it empty — if the script reads it, it will fail
        # (no feedback_categories.yaml there).

        self.config_dir = config_dir
        self.scripts_dir = scripts_dir

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    # ------------------------------------------------------------------
    # AC INF-100c-1-i: resolution anchors to .leafcutter/, not parent
    # ------------------------------------------------------------------

    def test_find_config_root_does_not_escape_leafcutter(self):
        # covers: INF-100c-1-i
        """_find_config_root() from the deployed script must resolve to
        .leafcutter/config/, NOT to the parent project's config/."""
        mod = _load_module_from_path(self.deployed_script)

        result = mod._find_config_root()

        # Must resolve to .leafcutter/config inside the worktree
        self.assertEqual(
            result.resolve(),
            self.config_dir.resolve(),
            (
                "_find_config_root() escaped .leafcutter/ — it resolved to "
                f"{result} instead of {self.config_dir}"
            ),
        )

    def test_find_config_root_not_parent_config(self):
        # covers: INF-100c-1-i
        """Config root must NOT be the worktree's top-level config/ directory."""
        mod = _load_module_from_path(self.deployed_script)

        result = mod._find_config_root()
        parent_config = self.worktree / "config"

        self.assertNotEqual(
            result.resolve(),
            parent_config.resolve(),
            (
                "_find_config_root() walked past .leafcutter/ to the parent "
                f"config dir: {result}"
            ),
        )

    def test_categories_file_resolves_within_leafcutter(self):
        # covers: INF-100c-1-i
        """_CATEGORIES_FILE from the deployed script must point inside .leafcutter/."""
        mod = _load_module_from_path(self.deployed_script)

        categories_file = mod._CATEGORIES_FILE

        expected = self.config_dir / "feedback_categories.yaml"
        self.assertEqual(
            categories_file.resolve(),
            expected.resolve(),
            (
                "_CATEGORIES_FILE is not inside .leafcutter/config/. "
                f"Got: {categories_file}"
            ),
        )

    def test_submission_succeeds_from_worktree_cwd(self):
        # covers: INF-100c-1-i
        """End-to-end: submit_feedback.py deployed into .leafcutter/scripts/feedback/
        must succeed when CWD is the worktree root (not the .leafcutter/ dir)."""
        jsonl_path = Path(self.tmpdir) / "feedback_wt_test.jsonl"
        result = subprocess.run(
            [
                sys.executable,
                str(self.deployed_script),
                "--ticket",
                "tickets/00_inbox/epics/EPIC-FeedbackPortability/01_TICKET-20260608-INF-100c-1-i.md",
                "--phase",
                "test-runner",
                "--category",
                "complete",
                "--note",
                "worktree config-resolution acceptance-test probe",
                "--jsonl",
                str(jsonl_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(self.worktree),  # CWD is the worktree root
            timeout=10,
        )
        self.assertEqual(
            result.returncode,
            0,
            (
                "submit_feedback.py failed when run from worktree root CWD.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            ),
        )
        self.assertRegex(
            result.stdout.strip(),
            r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$",
            "Expected a feedback_id on stdout",
        )

    def test_submission_succeeds_from_parent_dir(self):
        # covers: INF-100c-1-i
        """End-to-end: submit_feedback.py must succeed when CWD is the worktree's
        parent directory (simulating git worktree add from the main repo dir)."""
        jsonl_path = Path(self.tmpdir) / "feedback_parent_test.jsonl"
        result = subprocess.run(
            [
                sys.executable,
                str(self.deployed_script),
                "--ticket",
                "tickets/00_inbox/epics/EPIC-FeedbackPortability/01_TICKET-20260608-INF-100c-1-i.md",
                "--phase",
                "test-runner",
                "--category",
                "complete",
                "--note",
                "worktree-parent CWD acceptance-test probe",
                "--jsonl",
                str(jsonl_path),
            ],
            capture_output=True,
            text=True,
            cwd=self.tmpdir,  # CWD is the parent of the worktree
            timeout=10,
        )
        self.assertEqual(
            result.returncode,
            0,
            (
                "submit_feedback.py failed when run from the parent of the worktree.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            ),
        )
        self.assertRegex(
            result.stdout.strip(),
            r"^fb_\d{4}-\d{2}-\d{2}_[0-9a-f]{8}$",
            "Expected a feedback_id on stdout",
        )

    def test_parent_dir_missing_categories_does_not_affect_resolution(self):
        # covers: INF-100c-1-i
        """If the parent config/ has no feedback_categories.yaml, the deployed
        script must still succeed (proving it reads from .leafcutter/config/)."""
        # Ensure there is NO feedback_categories.yaml at the parent config/
        parent_yaml = self.worktree / "config" / "feedback_categories.yaml"
        self.assertFalse(
            parent_yaml.exists(),
            "Test setup error: parent config/feedback_categories.yaml should not exist",
        )

        jsonl_path = Path(self.tmpdir) / "feedback_isolation_test.jsonl"
        result = subprocess.run(
            [
                sys.executable,
                str(self.deployed_script),
                "--ticket",
                "tickets/00_inbox/epics/EPIC-FeedbackPortability/01_TICKET-20260608-INF-100c-1-i.md",
                "--phase",
                "test-runner",
                "--category",
                "complete",
                "--note",
                "isolation test: no parent categories file",
                "--jsonl",
                str(jsonl_path),
            ],
            capture_output=True,
            text=True,
            cwd=str(self.worktree),
            timeout=10,
        )
        self.assertEqual(
            result.returncode,
            0,
            (
                "submit_feedback.py failed despite .leafcutter/config/ being intact — "
                "it may be reading from parent config/.\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
