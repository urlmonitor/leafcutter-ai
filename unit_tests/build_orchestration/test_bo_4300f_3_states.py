"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_3_states.py
AC: BO-4300f-3-iii -- an old workspace in a state a copy of its files would lose is kept for a decision
    (pr-reviewer findings M-3 and M-6 of ticket 08).
TICKET: tickets/00_inbox/epics/EPIC-WorkspaceMakerHardening/
    08_TICKET-20261022-cut-over-canonical-deferred-readiness-lossless.md

M-6: every operation state is a REAL one produced by git: rebase-merge, rebase-apply, cherry-pick, revert and
     bisect, each kept (one parameterised test with subTests).
M-3: a multi-commit cherry-pick in progress whose CHERRY_PICK_HEAD is gone (only the sequencer is left), a
     skip-worktree entry that hides an edit from status, and a stash made on a DETACHED HEAD (which keeps
     detached workspaces, not a workspace on a branch).

Real subprocess against the DEPLOYED maker; no raw linked-checkout command spelled here.

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


class StateCase(KeepCase):
    def side_branch(self, folder: Path, name: str, text: str) -> None:
        """A branch off main holding a README that conflicts with the workspace's own."""
        self.git(["checkout", "-q", "-b", name, "main"], folder)
        self.commit(folder, "README.md", text, f"{name} side")

    def conflicting(self, short: str) -> Path:
        """A workspace on feature/<short> with its own README commit and a conflicting side branch."""
        folder = self.legacy(f"feature/{short}")
        self.side_branch(folder, f"side-{short}", "side\n")
        self.git(["checkout", "-q", f"feature/{short}"], folder)
        self.commit(folder, "README.md", "ours\n", "ours")
        return folder

    def make_cherry_pick(self) -> Path:
        folder = self.conflicting("cp")
        self.assertNotEqual(self.run_git(["cherry-pick", "side-cp"], folder).returncode, 0)
        return folder

    def make_revert(self) -> Path:
        folder = self.legacy("feature/rv")
        self.commit(folder, "README.md", "first\n", "first")
        self.commit(folder, "README.md", "second\n", "second")
        self.assertNotEqual(self.run_git(["revert", "--no-edit", "HEAD~1"], folder).returncode, 0)
        return folder

    def make_rebase(self, short: str, flag: str) -> Path:
        folder = self.conflicting(short)
        self.assertNotEqual(self.run_git(["rebase", flag, f"side-{short}"], folder).returncode, 0)
        return folder

    def make_bisect(self) -> Path:
        folder = self.legacy("feature/bs")
        shas = []
        for i in range(3):
            self.commit(folder, f"f{i}.txt", f"{i}\n", f"c{i}")
            shas.append(self.git(["rev-parse", "HEAD"], folder))
        for args in (["bisect", "start"], ["bisect", "bad", shas[2]], ["bisect", "good", shas[0]]):
            self.git(args, folder)
        return folder


class TestOperationStates(StateCase):
    def test_every_operation_in_progress_keeps_the_workspace(self):
        # covers: BO-4300f-3-iii
        # angle: boundary
        """M-6: a real rebase (merge backend), rebase (apply backend), cherry-pick, revert and bisect left
        unfinished are each listed in needs_decision with a reason naming the operation, their folder and registration kept.
        Must implement: all six admin-folder markers (MERGE_HEAD, CHERRY_PICK_HEAD, REVERT_HEAD, BISECT_LOG,
        rebase-merge, rebase-apply) are recognised, not only the first two.
        WRONG VERSION caught: a state recognised by name only for merge, so the others are carried as files."""
        builders = {
            "rebase-merge": (lambda: self.make_rebase("rbm", "--merge"), "rebase-merge"),
            "rebase-apply": (lambda: self.make_rebase("rba", "--apply"), "rebase-apply"),
            "cherry-pick": (self.make_cherry_pick, "CHERRY_PICK_HEAD"),
            "revert": (self.make_revert, "REVERT_HEAD"),
            "bisect": (self.make_bisect, "BISECT_LOG"),
        }
        word = {"rebase-merge": "rebase", "rebase-apply": "rebase", "cherry-pick": "cherry", "revert": "revert",
                "bisect": "bisect"}
        world = {}
        for state, (build, marker) in builders.items():
            world[state] = build()
            self.assertTrue((self.admin_of(world[state]) / marker).exists(), msg=f"fixture: no {marker} for {state}")
        answer = self.migrate_ok()
        for state, folder in world.items():
            with self.subTest(state=state):
                self.assert_kept(answer, folder, word[state])


class TestOtherHiddenState(StateCase):
    def test_a_cherry_pick_sequence_with_no_current_pick_is_kept(self):
        # covers: BO-4300f-3-iii
        # angle: boundary
        """M-3: `git cherry-pick A B` stops on A; A is resolved and committed by hand, so CHERRY_PICK_HEAD is
        gone but the sequencer (B still to do) remains. The workspace is kept.
        WRONG VERSION caught: looking for CHERRY_PICK_HEAD only."""
        folder = self.conflicting("sq")
        self.git(["checkout", "-q", "side-sq"], folder)
        self.commit(folder, "OTHER.txt", "second pick\n", "second pick")
        self.git(["checkout", "-q", "feature/sq"], folder)
        self.assertNotEqual(self.run_git(["cherry-pick", "side-sq~1", "side-sq"], folder).returncode, 0)
        write(folder / "README.md", "resolved\n")
        self.git(["add", "README.md"], folder)
        self.git(["commit", "-q", "-m", "resolved by hand"], folder)
        admin = self.admin_of(folder)
        self.assertFalse((admin / "CHERRY_PICK_HEAD").exists(), msg="fixture: the current pick must be done")
        self.assertTrue((admin / "sequencer").exists(), msg="fixture: no sequencer left")
        self.assert_kept(self.migrate_ok(), folder)

    def test_a_skip_worktree_entry_keeps_the_workspace(self):
        # covers: BO-4300f-3-iii
        # angle: discrimination
        """M-3: an edit hidden from `status` by skip-worktree is work a copy would lose; the workspace
        (otherwise nothing unsent) is kept with the edit intact.
        WRONG VERSION caught: trusting `status` alone, retiring the workspace and deleting the edit."""
        folder = self.legacy("feature/sw")
        self.git(["update-index", "--skip-worktree", "README.md"], folder)
        write(folder / "README.md", "hidden edit\n")
        self.assertEqual(self.git(["status", "--porcelain"], folder), "", msg="fixture: edit must be hidden")
        self.assert_kept(self.migrate_ok(), folder)
        self.assertEqual((folder / "README.md").read_text(encoding="utf-8"), "hidden edit\n")

    def test_a_stash_made_on_a_detached_head_keeps_detached_workspaces_only(self):
        # covers: BO-4300f-3-iii
        # angle: discrimination
        """M-3: a stash made while HEAD was detached ('On (no branch)') keeps the detached workspace, and
        does not keep a clean workspace on a branch (control: retired).
        WRONG VERSION caught: the stash check skipping a workspace with no branch."""
        detached = self.legacy("feature/dt")
        self.git(["checkout", "-q", "--detach"], detached)
        write(detached / "README.md", "detached edit\n")
        self.git(["stash", "push", "-q", "-m", "on a detached head"], detached)
        control = self.legacy("feature/ctl")
        stash_before = self.git(["stash", "list"])
        self.assertIn("no branch", stash_before, msg="fixture: the stash must name no branch")

        answer = self.migrate_ok()
        self.assert_kept(answer, detached, "stash")
        self.assertEqual(self.bucket_of(answer, control), "retired", msg=f"{answer}")
        self.assertEqual(self.git(["stash", "list"]), stash_before)


if __name__ == "__main__":
    unittest.main()
