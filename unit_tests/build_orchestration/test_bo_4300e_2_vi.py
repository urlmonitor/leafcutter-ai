"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_vi.py
AC: BO-4300e-2-vi -- A half-cleared folder that still holds files is refused as unverifiable, and
only the one-time token for exactly those files lets it go.

Real-subprocess proof against the DEPLOYED maker. Fixture: `ticket/epsilon` is made by `ensure`,
then its repository and content are deleted, leaving the workspace record, and `src/app.py` plus
`notes.txt` are added beside it. Workspaces use KIND "feature" (the shared helper's kind). The
refusal shape follows the BO-4300e-3 discard token: `unsent.files`, `discard_token`, then
`--discard-token` and `discarded.files`. Helpers come from test_bo_4300e_2.py / _2_v.py.

DECISION HISTORY
====================================================================
- 2026-10-26 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-vi]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration.test_bo_4300e_2_v import HalfClearedCase

FILES = ["notes.txt", "src/app.py"]


class EpsilonCase(HalfClearedCase):
    def epsilon(self, slug: str = "epsilon") -> Path:
        ws = self.gut(self.ensure(slug), keep_record=True)
        (ws / "src").mkdir()
        (ws / "src" / "app.py").write_text("print('app')\n", encoding="utf-8", newline="\n")
        (ws / "notes.txt").write_text("notes\n", encoding="utf-8", newline="\n")
        return ws

    def request(self, ws: Path, token: str | None = None) -> dict[str, Any]:
        args = ["remove", "--path", str(ws), "--repo-root", str(self.project)]
        return self.cli(args + (["--discard-token", token] if token else []))

    def refusal(self, ws: Path) -> dict[str, Any]:
        res = self.request(ws)
        self.assertEqual(res["answer"].get("status"), "refused", msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        return res


class TestHalfClearedFolderWithFiles(EpsilonCase):
    def test_half_cleared_folder_with_files_is_refused_as_unverifiable(self):
        # covers: BO-4300e-2-vi
        # angle: reachability
        """AC-1: the real CLI refuses (exit 2, no token given) a half-cleared folder holding files,
        stating the workspace was half-cleared and its remaining files cannot be checked against the
        shared project. The folder is still there."""
        ws = self.epsilon()
        res = self.refusal(ws)
        message = str(res["answer"].get("message", "")).lower()
        self.assertTrue("half-cleared" in message or "half cleared" in message, msg=f"{res['answer']}")
        self.assertIn("cannot be checked", message, msg=f"{res['answer']}")
        self.assertTrue(ws.is_dir())

    def test_refusal_lists_the_two_files_and_returns_a_token(self):
        # covers: BO-4300e-2-vi
        # angle: criterion
        """AC-1: the refusal lists exactly src/app.py and notes.txt (workspace-relative, forward
        slashes, deterministic sorted order, the record not among them) and carries a discard_token;
        the token is not found in stderr or in any file of the folder."""
        ws = self.epsilon()
        res = self.refusal(ws)
        unsent = res["answer"].get("unsent") or {}
        self.assertEqual(unsent.get("files"), FILES, msg=f"{res['answer']}")
        token = res["answer"].get("discard_token")
        self.assertTrue(isinstance(token, str) and token, msg=f"no token: {res['answer']}")
        self.assertNotIn(token, res["stderr"])
        for name, digest in self.snap(ws, with_git=True).items():
            self.assertNotIn(token, (ws / name).read_text(encoding="utf-8", errors="replace"), msg=name)

    def test_refused_half_cleared_folder_is_identical(self):
        # covers: BO-4300e-2-vi
        # angle: discrimination
        """AC-1: the folder (record, files, everything) is identical before and after the refusal.
        Catches a maker that finishes a half-cleared folder holding files without a valid token, and
        one that touches the folder while computing the token. Control: the same request with a
        valid token (in the next test) does clear it, so 'identical' is not 'nothing ran'."""
        ws = self.epsilon()
        before = self.snap(ws, with_git=True)
        self.assertEqual(sorted(before), [".leafcutter/workspace.json", *FILES])
        self.refusal(ws)
        self.assertTrue(ws.is_dir(), msg="the folder was deleted without a token")
        self.assertEqual(self.snap(ws, with_git=True), before)

    def test_valid_token_clears_and_lists_both_files_as_discarded(self):
        # covers: BO-4300e-2-vi
        # angle: criterion
        """AC-1: repeating the request with the returned --discard-token is answered ok, the answer's
        discarded files list both paths, and nothing remains at the location."""
        ws = self.epsilon()
        token = self.refusal(ws)["answer"].get("discard_token")
        self.assertTrue(token, msg="no token to present")
        res = self.request(ws, token)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual((res["answer"].get("discarded") or {}).get("files"), FILES, msg=f"{res['answer']}")
        self.assertFalse(os.path.lexists(ws))

    def test_token_goes_stale_when_a_file_changes(self):
        # covers: BO-4300e-2-vi
        # angle: discrimination
        """AC-1: in a second run of the same setup, after the refusal notes.txt is changed (variants:
        a file added, a file removed); the earlier token is refused and the folder is identical before
        and after that request. Catches a token bound to the folder path only, one bound to file names
        only (a changed notes.txt still matching), and a token scheme unrelated to BO-4300e-3's."""
        def change_content(ws: Path) -> None:
            (ws / "notes.txt").write_text("changed after the refusal\n", encoding="utf-8", newline="\n")

        def add_file(ws: Path) -> None:
            (ws / "extra.txt").write_text("new\n", encoding="utf-8", newline="\n")

        def remove_file(ws: Path) -> None:
            (ws / "notes.txt").unlink()

        real = self.ensure("eta")  # a real BO-4300e-3 refusal: an ordinary workspace holding an unsent file
        self.dirty(real, "unsent.txt")
        e3 = self.request(real)["answer"]
        self.assertEqual(e3.get("code"), "UNSENT_WORK", msg=f"fixture: {e3}")
        e3_token = e3.get("discard_token")
        self.assertTrue(isinstance(e3_token, str) and e3_token, msg=f"fixture: {e3}")
        half = self.refusal(self.epsilon("epsilon-shape")).get("answer", {}).get("discard_token")
        self.assertEqual(len(half), len(e3_token), msg=f"half-cleared token {half!r} vs BO-4300e-3 {e3_token!r}")
        self.assertEqual(set(half) - set("0123456789abcdef"), set(), msg=f"{half!r}")
        self.assertEqual(set(e3_token) - set("0123456789abcdef"), set(), msg=f"fixture: {e3_token!r}")
        for index, (why, change) in enumerate((("content", change_content), ("added", add_file),
                                               ("removed", remove_file))):
            ws = self.epsilon(f"epsilon-{index}")
            token = self.refusal(ws)["answer"].get("discard_token")
            self.assertTrue(token, msg=why)
            change(ws)
            before = self.snap(ws, with_git=True)
            res = self.request(ws, token)
            self.assertNotEqual(res["answer"].get("status"), "ok", msg=f"{why}: a stale token cleared it: {res}")
            self.assertEqual(res["answer"].get("status"), "refused", msg=f"{why}: {res}")
            self.assertTrue(ws.is_dir(), msg=f"{why}: the folder was deleted")
            self.assertEqual(self.snap(ws, with_git=True), before, msg=f"{why}: the folder changed")


if __name__ == "__main__":
    unittest.main()
