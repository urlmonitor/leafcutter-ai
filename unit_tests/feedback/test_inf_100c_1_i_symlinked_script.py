"""
MODULE: unit_tests/feedback/test_inf_100c_1_i_symlinked_script.py
GOAL: AC INF-100c-1-i -- when the worktree's deployed submit_feedback.py is a
      symlink to a copy elsewhere (no sibling config/), config resolution must
      stay anchored at the worktree's own .leafcutter/ (the invoked path), not
      follow the symlink out of it.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h


class TestSymlinkedScriptStaysInLeafcutter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="lc_wt_symlink_"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.worktree = self.tmp / "wt"
        self.worktree.mkdir()
        self.lc = h.deploy_install(self.worktree, git=False)
        h.declare(self.lc)
        self.config_dir = self.lc / "config"

        # A shared copy of scripts/feedback elsewhere; NO config/ beside it.
        shared_fb = self.tmp / "shared" / "scripts" / "feedback"
        shutil.copytree(self.lc / "scripts" / "feedback", shared_fb)
        real = self.lc / "scripts" / "feedback" / "submit_feedback.py"
        real.unlink()
        os.symlink(shared_fb / "submit_feedback.py", real)
        self.script = real

    def test_criterion_config_root_anchored_at_worktree_leafcutter(self):
        # covers: INF-100c-1-i
        # angle: criterion
        """_find_config_root() must return the worktree's .leafcutter/config."""
        spec = importlib.util.spec_from_file_location("sf_symlinked", str(self.script))
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(self.script.resolve().parent))
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path.remove(str(self.script.resolve().parent))
        self.assertEqual(
            os.path.abspath(mod._find_config_root()),
            os.path.abspath(self.config_dir),
        )

    def test_reachability_cli_succeeds_via_symlinked_script(self):
        # covers: INF-100c-1-i
        # angle: reachability
        """Running the real CLI through the symlink finds the worktree's config
        and prints a feedback id."""
        jsonl = self.tmp / "fb.jsonl"
        result = subprocess.run(
            [sys.executable, str(self.script), "--ticket", "tickets/x.md",
             "--phase", "test-runner", "--category", "complete",
             "--note", "symlink probe", "--jsonl", str(jsonl)],
            capture_output=True, text=True, cwd=str(self.worktree), timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertRegex(result.stdout.strip(), h.FEEDBACK_ID_RE)


class TestCiShimDirectorySymlink(unittest.TestCase):
    """CI layout: <root>/scripts/feedback is a build shim symlink into
    <root>/.leafcutter/scripts/feedback (parent contract INF-100c-1)."""

    def test_regression_shim_dir_symlink_resolves_to_leafcutter_config(self):
        # covers: INF-100c-1
        # angle: regression
        """Loading the script through the shim dir must still anchor config
        at <root>/.leafcutter/config, not <root>/config."""
        root = Path(tempfile.mkdtemp(prefix="lc_ci_shim_"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        lc = h.deploy_install(root, git=False)
        h.declare(lc)
        shim = root / "scripts" / "feedback"
        if shim.is_symlink() or shim.is_file():
            shim.unlink()
        elif shim.is_dir():
            shutil.rmtree(shim)
        shim.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(lc / "scripts" / "feedback", shim)

        script = shim / "submit_feedback.py"
        spec = importlib.util.spec_from_file_location("sf_ci_shim", str(script))
        mod = importlib.util.module_from_spec(spec)
        sys.path.insert(0, str(script.resolve().parent))
        try:
            spec.loader.exec_module(mod)
        finally:
            sys.path.remove(str(script.resolve().parent))
        self.assertEqual(
            os.path.abspath(mod._find_config_root()),
            os.path.abspath(lc / "config"),
        )


if __name__ == "__main__":
    unittest.main()
