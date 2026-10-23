"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_5_i.py
AC: BO-4300b-5-i -- a project under a folder whose name contains spaces gets a usable workspace.
Real-subprocess proof against the deployed maker (see test_bo_4300c_2.py).

DECISION HISTORY
====================================================================
- 2026-09-30 10:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03,
  BO-4300b-5-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
====================================================================
"""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project, run_maker

_SPACED = "My Projects"


class TestBO4300b5iSpacedFolder(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b5i-")
        self.addCleanup(self._tmp.cleanup)
        proj = make_project(Path(self._tmp.name) / _SPACED)
        self.project = proj["project"]
        self.res = run_maker(["ensure", "--kind", "scratch", "--slug", "alpha"], cwd=self.project)

    def test_project_under_folder_with_spaces_is_answered_ok(self):
        # covers: BO-4300b-5-i
        # angle: criterion
        """A project under 'My Projects' gets an ok answer (exit 0, code OK)."""
        self.assertEqual(self.res["answer"]["status"], "ok", self.res["stderr"])
        self.assertEqual(self.res["answer"]["code"], "OK")
        self.assertEqual(self.res["exit_code"], 0)

    def test_answer_reproduces_the_spaced_folder_name_exactly(self):
        # covers: BO-4300b-5-i
        # angle: boundary
        """workspace_path and its POSIX alias contain 'My Projects' verbatim (never split or escaped)."""
        ans = self.res["answer"]
        self.assertIn(_SPACED, ans["workspace_path"])
        self.assertIn(_SPACED, ans["workspace_path_posix"])
        self.assertIn(_SPACED, ans["repo_root_posix"])

    def test_git_command_at_the_exact_answered_location_succeeds(self):
        # covers: BO-4300b-5-i
        # angle: criterion
        """git rev-parse at exactly the answered location succeeds (argv list, never a shell string)."""
        proc = subprocess.run(
            ["git", "-C", self.res["answer"]["workspace_path"], "rev-parse", "--is-inside-work-tree"],
            capture_output=True, text=True, timeout=60, check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout.strip(), "true")


if __name__ == "__main__":
    unittest.main()
