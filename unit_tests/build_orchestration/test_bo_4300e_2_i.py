"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_i.py
AC: BO-4300e-2-i -- A workspace with very long file paths on Windows is cleared completely.

Given a (Windows) machine and a workspace holding nothing unsent whose contents include a file path
longer than 260 characters, when the workspace is cleared, the answer states it was cleared and no
folder or file of it remains at its location. The long-path arm runs on every platform.

Real-subprocess proof against the DEPLOYED maker; the deep path is created with the extended-length
prefix on Windows and listed in the workspace's own .git/info/exclude, so it is not "unsent work".
Helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-12 16:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08,
  BO-4300e-2-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
====================================================================
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase

_EXT = "\\\\?\\"


def extended(path: Path) -> str:
    """The spelling that reaches a path longer than 260 characters on Windows."""
    text = str(path)
    return _EXT + text if os.name == "nt" and not text.startswith(_EXT) else text


class TestLongPathsAreCleared(WorkspaceCase):
    def test_workspace_with_path_over_260_chars_is_removed_completely(self):
        # covers: BO-4300e-2-i
        # angle: boundary
        """AC-3: the answer is ok and nothing remains at the location -- not the folder, not the
        deep file. Control: a second clean workspace without long paths is cleared in the same run."""
        ws = self.ensure("alpha")
        control = self.ensure("control")
        with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("deep/\n")
        deep = ws / "deep"
        for i in range(6):
            deep = deep / (f"segment{i}-" + "x" * 44)
        deep_file = deep / "long-path-file.txt"
        os.makedirs(extended(deep), exist_ok=True)
        with open(extended(deep_file), "w", encoding="utf-8", newline="\n") as fh:
            fh.write("deep\n")
        self.assertGreater(len(str(deep_file)), 260, msg="fixture path is not long enough")
        self.assertTrue(os.path.exists(extended(deep_file)))

        res = self.remove(ws)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["answer"].get("code"), "OK")
        self.assertFalse(os.path.lexists(extended(deep_file)), msg="the deep file survived an ok answer")
        self.assertFalse(os.path.lexists(extended(ws)), msg="the workspace folder survived an ok answer")
        self.assertEqual(self.remove(control)["answer"].get("status"), "ok")


class TestYSideRenameIsUnsent(WorkspaceCase):
    def test_y_side_rename_is_unsent_work_and_names_both_paths(self):
        # covers: BO-4300e-2-i
        # angle: deployed
        """M17: a tracked file renamed in the working tree and recorded with `git add -N` is status
        ' R' (a Y-side rename, source path as its own -z record). remove refuses UNSENT_WORK and
        unsent.files is exactly the old and the new path; the workspace stays. The wrong version
        caught: only an X-side R/C consumes the source record, so the source is read as a mangled
        entry of its own."""
        import subprocess

        from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env

        ws = self.ensure("alpha")
        old, new = "BUILD_STAMP.txt", "RENAMED_STAMP.txt"
        os.rename(ws / old, ws / new)
        self.git(["add", "-N", new], ws)
        status = subprocess.run(["git", "status", "--porcelain=v1", "-z"], cwd=str(ws), capture_output=True,
                                text=True, env=_isolated_git_env(), check=True).stdout
        self.assertTrue(status.startswith(" R "), msg=f"fixture: not a Y-side rename: {status!r}")

        res = self.remove(ws)
        self.assertEqual((res["answer"].get("code"), res["exit_code"]), ("UNSENT_WORK", 2), msg=f"{res}")
        files = [f.replace("\\", "/") for f in res["answer"]["unsent"]["files"]]
        self.assertEqual(sorted(files), sorted([old, new]), msg=f"{res['answer']}")
        self.assertTrue(ws.is_dir())


if __name__ == "__main__":
    unittest.main()
