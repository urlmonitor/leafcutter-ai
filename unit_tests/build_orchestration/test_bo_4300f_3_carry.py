"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3_carry.py
AC: BO-4300f-3 / BO-4300f-3-iv -- what a brought-over workspace carries (pr-reviewer findings M-3 and M-4 of
    ticket 08).
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    08_TICKET-20261022-cut-over-canonical-deferred-readiness-lossless.md

M-3: an empty untracked directory is carried (git does not list it, so a file-by-file copy drops it); a symlink
     is carried AS a symlink (a copy of its target's bytes is a different file).
M-4: the git-ignored `.env.local` and `build/` of a brought-over workspace arrive byte-identical in the new
     workspace; the old install folder `.leafcutter/` is listed in ignored_removed and NOT carried; a retired
     entry still deletes and reports its ignored files; `ignored_removed` is present on every retired and
     brought-over entry (a list, empty when nothing is deleted).

ASSUMED: ``ignored_removed`` on a brought-over entry lists what the deletion of the old folder removes, i.e.
at least ``.leafcutter/``. What else it lists (carried content) is not asserted, the AC fixes only the
install folder.

Real subprocess against the DEPLOYED maker; no raw linked-checkout command spelled here.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/08, BO-4300f-3-iv]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import os
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300f_3_keep_fixtures import KeepCase, write
from unit_tests.build_orchestration._workspace_maker_fixtures import legacy_worktree  # noqa: F401


class TestCarriedExactly(KeepCase):
    def bring_over(self, name: str) -> tuple[Path, Path]:
        old = self.legacy(name, unsent=True)
        return old, self.landing / name

    def brought(self, old: Path) -> Path:
        answer = self.migrate_ok()
        self.assertEqual(self.bucket_of(answer, old), "brought_over", msg=f"{answer}")
        return Path(self.entry(answer, old, "brought_over")["workspace_path"])

    def test_an_empty_untracked_directory_is_carried(self):
        # covers: BO-4300f-3
        # angle: boundary
        """M-3: an empty untracked directory tree (empty/inner) in the old workspace exists in the brought-over
        one. WRONG VERSION caught: copying only the files git lists."""
        old, _ = self.bring_over("feature/ed")
        (old / "empty" / "inner").mkdir(parents=True)
        ws = self.brought(old)
        self.assertTrue((ws / "empty" / "inner").is_dir(), msg="the empty directory was dropped")

    def test_a_symlink_is_carried_as_a_symlink(self):
        # covers: BO-4300f-3
        # angle: boundary
        """M-3: an untracked symlink link.txt -> UNSENT_WORK.txt arrives as a symlink with the same target,
        not as a copy of the target's bytes. Skipped where the OS cannot create symlinks.
        WRONG VERSION caught: shutil.copy2 following the link."""
        old, _ = self.bring_over("feature/sl")
        try:
            os.symlink("UNSENT_WORK.txt", old / "link.txt")
        except (OSError, NotImplementedError, AttributeError) as exc:
            self.skipTest(f"cannot create symlinks here: {exc}")
        ws = self.brought(old)
        self.assertTrue((ws / "link.txt").is_symlink(), msg="the symlink became a regular file")
        self.assertEqual(os.readlink(ws / "link.txt"), "UNSENT_WORK.txt")


class TestIgnoredContent(KeepCase):
    def setUp(self) -> None:
        super().setUp()
        self.push_ignore_rules(".env.local\nbuild/\n.leafcutter/\n")

    def fill(self, folder: Path) -> dict[str, bytes]:
        write(folder / ".env.local", "SECRET=1\n")
        (folder / "build" / "sub").mkdir(parents=True)
        (folder / "build" / "out.o").write_bytes(b"\x00object\xff\n")
        (folder / "build" / "sub" / "deep.o").write_bytes(b"deeper\n")
        return {rel: (folder / rel).read_bytes() for rel in (".env.local", "build/out.o", "build/sub/deep.o")}

    def test_ignored_files_arrive_byte_identical_and_the_install_folder_does_not(self):
        # covers: BO-4300f-3-iv
        # angle: deployed
        """M-4: a brought-over workspace's ignored `.env.local` and `build/` (two files below it) are
        byte-identical in the new workspace; its old `.leafcutter/` install folder is listed in
        ignored_removed and its content is not carried; a retired workspace with an ignored file still
        deletes and reports it; every retired and brought-over entry has an ignored_removed list.
        WRONG VERSIONS caught: ignored files lost with the old folder; the old install carried over the
        new one; ignored_removed missing when empty."""
        old = self.legacy("feature/ign", unsent=True)
        kept = self.fill(old)
        (old / ".leafcutter").mkdir()
        write(old / ".leafcutter" / "old-shim.txt", "the old install\n")
        retired = self.legacy("feature/rt")
        write(retired / ".env.local", "RETIRED=1\n")
        clean = self.legacy("feature/clean")

        answer = self.migrate_ok()
        ws = Path(self.entry(answer, old, "brought_over")["workspace_path"])
        self.assertEqual({rel: (ws / rel).read_bytes() for rel in kept}, kept, msg="ignored content changed")
        self.assertFalse((ws / ".leafcutter" / "old-shim.txt").exists(), msg="the old install was carried")
        self.assertIn(".leafcutter/", self.entry(answer, old, "brought_over").get("ignored_removed", []))
        self.assertEqual(self.entry(answer, retired, "retired").get("ignored_removed"), [".env.local"])
        self.assertFalse(retired.exists())
        self.assertEqual(self.entry(answer, clean, "retired").get("ignored_removed"), [], msg=f"{answer}")
        for bucket in ("retired", "brought_over"):
            for entry in answer[bucket]:
                self.assertIsInstance(entry.get("ignored_removed"), list, msg=f"{bucket}: {entry}")


if __name__ == "__main__":
    unittest.main()
