"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3_keep.py
AC: BO-4300f-3 / BO-4300f-3-iii -- the cut-over keeps work when a step fails or the state is not what it
    proved (pr-reviewer findings H-1, H-2, M-1, M-2 of ticket 08).
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    08_TICKET-20261022-cut-over-canonical-deferred-readiness-lossless.md

H-1: retiring the old folder fails partway after a verified bring-over -> the new clone is KEPT (its uncommitted
     and untracked files still there) and the old workspace is in needs_decision naming BOTH locations.
H-2: only WSL's exact 'initializing' lock on a MISSING folder is a stuck entry; 'initializing my env', or the
     exact text on a PRESENT folder, is a user lock and keeps the workspace.
M-1: a failing `git stash list` keeps the workspace with a 'could not ...' reason (never "no stash").
M-2: a file changed in the old folder after the proof and before the delete keeps it.

Faults are injected in a separate process by the shared driver (see _bo_4300f_3_keep_fixtures); the deployed
cut-over is what runs. A failing `status` is not exercised here: the unsent-work proof uses the same call, so
its failure is indistinguishable from the guard's.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/08, BO-4300f-3-iii]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300f_3_keep_fixtures import KeepCase, write
from unit_tests.build_orchestration._workspace_maker_fixtures import legacy_worktree  # noqa: F401


def _spell(text: str) -> str:
    return text.replace("\\", "/").lower()


class TestRetireFailsAfterBringOver(KeepCase):
    def world(self) -> tuple[Path, Path, dict[str, bytes]]:
        old = self.legacy("feature/h1", unsent=True)
        with open(old / "README.md", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("uncommitted edit by the person\n")
        write(old / "UNTRACKED_NOTES.txt", "untracked notes\n")
        kept = {n: (old / n).read_bytes() for n in ("README.md", "UNTRACKED_NOTES.txt", "UNSENT_WORK.txt")}
        return old, self.landing / "feature" / "h1", kept

    def assert_clone_kept_and_both_named(self, answer: dict, old: Path, clone: Path, kept: dict) -> None:
        self.assertEqual(self.bucket_of(answer, old), "needs_decision", msg=f"{answer}")
        self.assertEqual(answer["brought_over"], [], msg=f"{answer}")
        reason = _spell(self.entry(answer, old, "needs_decision")["reason"])
        self.assertIn(_spell(str(clone)), reason, msg=f"the reason must name the kept clone: {reason!r}")
        self.assertIn(_spell(str(old)), reason, msg=f"the reason must name the old workspace: {reason!r}")
        self.assertEqual({n: (clone / n).read_bytes() for n in kept}, kept, msg="the kept clone lost work")

    def test_failed_delete_of_the_old_folder_keeps_the_new_clone(self):
        # covers: BO-4300f-3
        # angle: failure
        """H-1: the delete of the old folder fails after the bring-over was verified: the clone at
        <landing>/feature/h1 is kept with its uncommitted edit and untracked file, the old workspace is in
        needs_decision and the reason names both locations. Must implement: no withdrawal of a verified clone.
        WRONG VERSION caught: deleting the clone on a failed retire (the only copy of work if the old
        folder was already partly deleted)."""
        old, clone, kept = self.world()
        answer = self.drive(mode="fail_delete", paths=[str(old)])
        self.assert_clone_kept_and_both_named(answer, old, clone, kept)
        self.assertTrue(old.exists())

    def test_failed_delete_of_the_registration_keeps_the_new_clone(self):
        # covers: BO-4300f-3
        # angle: failure
        """H-1: the old folder is gone but its registration cannot be deleted: the clone is kept with its
        uncommitted edit and untracked file, and the entry is in needs_decision naming both locations."""
        old, clone, kept = self.world()
        answer = self.drive(mode="fail_delete", paths=[str(self.admin_of(old))])
        self.assert_clone_kept_and_both_named(answer, old, clone, kept)


class TestLocks(KeepCase):
    def test_a_user_lock_that_merely_starts_with_initializing_keeps_the_workspace(self):
        # covers: BO-4300f-3-iii
        # angle: discrimination
        """H-2: 'initializing my env' (folder present), the exact text 'initializing' with the folder PRESENT,
        and a lock 'on USB drive' are each kept; WSL's exact 'initializing' on a MISSING folder is still
        removed (unfinished_removed) and nothing else changes.
        WRONG VERSION caught: startswith('initializing') treating a user's own lock as WSL's stuck entry."""
        mine = self.legacy("feature/lk1")
        exact_present = self.legacy("feature/lk2")
        usb = self.legacy("feature/lk3")
        for folder, reason in ((mine, "initializing my env"), (exact_present, "initializing"), (usb, "on USB drive")):
            write(self.admin_of(folder) / "locked", reason)
        stuck = self.make_stuck("stuck-one")

        answer = self.migrate_ok()
        for folder in (mine, exact_present, usb):
            self.assert_kept(answer, folder, "lock")
        self.assertEqual(answer["unfinished_removed"], [stuck], msg=f"{answer}")
        self.assertFalse((self.project / ".git" / "worktrees" / stuck).exists())
        self.assertEqual(answer["retired"] + answer["brought_over"], [], msg=f"{answer}")


class TestCannotCheck(KeepCase):
    def test_a_failing_stash_listing_keeps_the_workspace(self):
        # covers: BO-4300f-3-iii
        # angle: failure
        """M-1: with `git stash list` failing, a workspace that holds nothing unsent is kept, with a reason
        saying a stash check could not be made; a bare 'no stash' answer would retire it.
        WRONG VERSION caught: stashed_on() returning False on a git failure (fail-open)."""
        old = self.legacy("feature/m1")
        answer = self.drive(mode="git_fail", has=["stash", "list"])
        entry = self.assert_kept(answer, old, "could not")
        self.assertIn("stash", entry["reason"].lower(), msg=f"{entry}")


class TestChangedAfterProof(KeepCase):
    def test_a_file_changed_between_proof_and_delete_keeps_the_old_workspace(self):
        # covers: BO-4300f-3
        # angle: discrimination
        """M-2: the unsent-work proof says 'nothing unsent'; then a file appears in the old folder before the
        delete. The workspace is kept with the new file intact; a control workspace without the change is
        still retired. The change is made by wrapping the proof; it lands BEFORE the cut-over's own record of the
        folder, so on its own it does not need a re-check (the snapshot test below covers the re-check).
        WRONG VERSION caught: deleting on the stale proof."""
        old = self.legacy("feature/m2")
        control = self.legacy("feature/m2ok")
        answer = self.drive(mode="change_after_proof", folder=str(old), file="late.txt")
        self.assert_kept(answer, old)
        self.assertEqual((old / "late.txt").read_text(encoding="utf-8"), "changed after the proof\n")
        self.assertEqual(self.bucket_of(answer, control), "retired", msg=f"{answer}")
        self.assertFalse(control.exists())

    def test_a_file_changed_after_the_snapshot_keeps_the_old_workspace(self):
        # covers: BO-4300f-3
        # angle: discrimination
        """M-2: the cut-over records what the old folder holds just before it acts; a file that appears after
        that record and before the delete keeps the workspace (new file intact), while a control without the
        change is retired. The change is made by wrapping the record (worktree_migrate_carry.snapshot).
        WRONG VERSION caught: a record that is never compared again before the delete."""
        old = self.legacy("feature/m2s")
        control = self.legacy("feature/m2sok")
        answer = self.drive(mode="change_after_snapshot", folder=str(old), file="late.txt")
        self.assert_kept(answer, old)
        self.assertEqual((old / "late.txt").read_text(encoding="utf-8"), "changed after the snapshot\n")
        self.assertEqual(self.bucket_of(answer, control), "retired", msg=f"{answer}")


if __name__ == "__main__":
    unittest.main()
