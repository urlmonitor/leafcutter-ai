"""
MODULE: unit_tests/build_orchestration/test_bo_4300d_2_iii.py
AC: BO-4300d-2-iii -- A half-made workspace in which work has since been done is not wiped to
    finish it
Real-subprocess proof against the DEPLOYED maker. The half-made folder comes from a really failed
install; the work's hand change is then made in it (tracked/f00.txt, a file the stub build also
rewrites); the folder's identity is witnessed by its inode and a sentinel inside its .git.
Helpers live in test_bo_4300d_1.py / test_bo_4300d_2.py.

DECISION HISTORY
====================================================================
- 2026-10-10 18:10 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07,
  BO-4300d-2-iii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
====================================================================
"""
from __future__ import annotations

import os
import unittest

from unit_tests.build_orchestration.test_bo_4300c_1 import MakerTestCase, ensure
from unit_tests.build_orchestration.test_bo_4300d_1 import SLUG, build_count
from unit_tests.build_orchestration.test_bo_4300d_2 import half_made

CHANGED = "tracked/f00.txt"
EDIT = b"HAND CHANGE MADE IN THE HALF-MADE FOLDER\n"


class TestHandChangeSurvives(MakerTestCase):
    def changed_half_made(self) -> dict:
        fx = half_made(self, rewrite_tracked=2)
        ws = fx["ws"]
        (ws / CHANGED).write_bytes(EDIT)
        (ws / ".git" / "IDENTITY_SENTINEL").write_text("same folder\n", encoding="utf-8")
        fx["inode"] = os.stat(ws).st_ino
        return fx

    def test_hand_changed_file_in_half_made_workspace_survives(self):
        # covers: BO-4300d-2-iii
        # angle: criterion
        """The changed file is byte-identical after the request."""
        fx = self.changed_half_made()
        ans = ensure(fx, SLUG)["answer"]
        self.assertTrue(ans.get("status") == "ok" or ans.get("code") == "WORK_AT_RISK", ans)
        self.assertEqual((fx["ws"] / CHANGED).read_bytes(), EDIT, ans)
        if ans.get("status") == "ok":
            self.assertEqual(build_count(fx["ws"]), 1, "ok means the install really completed in place")
            self.assertEqual(ans.get("workspace_action"), "completed", ans)

    def test_answer_is_ok_with_change_or_work_at_risk_naming_it(self):
        # covers: BO-4300d-2-iii
        # angle: failure
        """The answer is ok with the change intact, or WORK_AT_RISK naming the changed file -- nothing else."""
        fx = self.changed_half_made()
        res = ensure(fx, SLUG)
        ans = res["answer"]
        if ans.get("status") == "ok":
            self.assertEqual((fx["ws"] / CHANGED).read_bytes(), EDIT)
            return
        self.assertEqual((ans.get("status"), ans.get("code"), res["exit_code"]), ("refused", "WORK_AT_RISK", 2), ans)
        self.assertIn(CHANGED, (ans.get("unsent") or {}).get("files", []), ans)
        self.assertNotIn("workspace_path", ans)

    def test_folder_is_never_recreated_while_holding_the_change(self):
        # covers: BO-4300d-2-iii
        # angle: boundary
        """The folder's identity (inode) and a sentinel inside its .git are the same before and after."""
        fx = self.changed_half_made()
        ans = ensure(fx, SLUG)["answer"]
        self.assertTrue(ans.get("status") == "ok" or ans.get("code") == "WORK_AT_RISK", ans)
        ws = fx["ws"]
        self.assertTrue((ws / ".git" / "IDENTITY_SENTINEL").is_file(), "the folder was deleted and made again")
        self.assertEqual(os.stat(ws).st_ino, fx["inode"])
        self.assertEqual((ws / CHANGED).read_bytes(), EDIT)
        self.assertTrue((ws / ".git").is_dir())


if __name__ == "__main__":
    unittest.main()
