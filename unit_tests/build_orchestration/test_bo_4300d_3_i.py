"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_3_i.py
AC: BO-4300d-3-i -- A workspace for the same work made the old way is not quietly taken over
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
The legacy worktree is made only by the shared legacy_worktree() helper (BO-4300f-4).
Red baseline: OCCUPIED_LEGACY_WORKTREE detection (read-only on .git/worktrees, matching the exact
canonical branch or a declared legacy alias, wherever the folder is) does not exist yet.

DECISION HISTORY
====================================================================
- 2026-10-09 12:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06,
  BO-4300d-3-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
====================================================================
"""
from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_ii_fixtures import (
    git,
    landing_entries,
    maker,
    new_project,
    same,
    snapshot,
)
from unit_tests.build_orchestration._workspace_maker_fixtures import legacy_worktree, unlink_checkout


def admin_state(project: Path) -> dict[str, bytes]:
    """Every file under the main checkout's .git/worktrees, for before/after equality."""
    root = project / ".git" / "worktrees"
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


class TestBO4300d3i(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300d3i-", ignore_cleanup_errors=True)
        self.addCleanup(self._tmp.cleanup)
        fx = new_project(Path(self._tmp.name))
        self.project, self.landing = fx["project"], fx["landing_place"]
        self.args = ["ensure", "--kind", "epic", "--slug", "alpha"]

    def legacy_at_location(self) -> Path:
        return legacy_worktree(self.project, "EPIC-Alpha", unsent=True, at=self.landing / "epic" / "alpha")

    def legacy_in_old_folder(self) -> Path:
        return legacy_worktree(self.project, "EPIC-Alpha", unsent=True)  # <parent>/worktrees/EPIC-Alpha

    def test_legacy_worktree_for_same_work_is_refused_as_legacy_occupant(self):
        # covers: BO-4300d-3-i
        # angle: failure
        """A legacy worktree at alpha's location: refused OCCUPIED_LEGACY_WORKTREE, message names the bring-over step."""
        legacy = self.legacy_at_location()
        res = maker(self.args, self.project)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]),
                         ("refused", "OCCUPIED_LEGACY_WORKTREE", 2), ans)
        self.assertRegex(ans.get("message", ""), re.compile(r"brought over|bring[- ]over|bring it over", re.I))
        self.assertTrue(same((ans.get("occupant") or {}).get("path", "."), legacy), ans)
        self.assertNotIn("workspace_path", ans)

    def test_legacy_worktree_commit_and_registration_unchanged(self):
        # covers: BO-4300d-3-i
        # angle: boundary
        """Files, the extra commit and the .git/worktrees entry are byte-identical before and after."""
        for place in ("location", "old-folder"):
            with self.subTest(place=place):
                if place == "location":
                    legacy = self.legacy_at_location()
                else:
                    unlink_checkout(self.project, ["--force", str(self.landing / "epic" / "alpha")])
                    git(["branch", "-q", "-D", "EPIC-Alpha"], self.project)
                    legacy = self.legacy_in_old_folder()
                before = (snapshot(legacy), admin_state(self.project), (legacy / ".git").read_bytes())
                ans = maker(self.args, self.project)["answer"]
                self.assertEqual(ans.get("code"), "OCCUPIED_LEGACY_WORKTREE", ans)
                self.assertEqual((snapshot(legacy), admin_state(self.project), (legacy / ".git").read_bytes()), before)
                self.assertEqual(git(["log", "-1", "--format=%s"], legacy), "unsent legacy work")

    def test_legacy_worktree_in_its_old_folder_under_legacy_name_is_refused_not_twinned(self):
        # covers: BO-4300d-3-i
        # angle: failure
        """EPIC-Alpha registered outside the landing root: refused with that folder as occupant.path, no twin made."""
        legacy = self.legacy_in_old_folder()
        self.assertFalse(str(legacy).startswith(str(self.landing.resolve())))
        res = maker(self.args, self.project)
        ans = res["answer"]
        self.assertEqual((ans.get("status"), ans.get("code")), ("refused", "OCCUPIED_LEGACY_WORKTREE"), ans)
        self.assertTrue(same((ans.get("occupant") or {}).get("path", "."), legacy), ans)
        self.assertFalse((self.landing / "epic" / "alpha").exists())
        self.assertEqual(landing_entries(self.landing), [])


if __name__ == "__main__":
    unittest.main()
