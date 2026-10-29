"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_3_ii.py
AC: BO-4300e-3-ii -- A failed deletion of the line on the shared project leaves the workspace in place.

Given a workspace "alpha" holding nothing unsent, whose line of work exists on the shared project,
and a shared project that refuses to delete that line, when clearing "alpha" is requested together
with deletion of its line on the shared project, the request ends with a failure naming the
deletion on the shared project as the step that failed, "alpha"'s folder and files are identical
before and after, and the line of work on the shared project is identical before and after.

Fixture: the project's bare hub gets hooks/update that exits 1 for a ref deletion (new value all
zeros). A control proves the hook really rejects deletions before the maker is asked anything.
Real-subprocess proof against the DEPLOYED maker; helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/04, BO-4300e-3-ii]: Created the red
  baseline.
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/04, pr-reviewer rework]: Hub-branch guard
  tests: protected branches, empty / option-like marker branch, and a failed local delete after the
  hub branch was deleted (in-process, the one place that failure can be forced reliably).
====================================================================
"""
from __future__ import annotations

import argparse
import os
import subprocess
import unittest
from unittest import mock

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project  # noqa: F401  (first: breaks the builders<->fixtures import cycle)
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env
from unit_tests.build_orchestration.test_bo_4300e_2 import WorkspaceCase
from unit_tests.build_orchestration.test_bo_4300e_2_iii import deployed_worktree_remove, forge_marker

ZEROS = "0" * 40
UPDATE_HOOK = (
    "#!/bin/sh\n"
    f'if [ "$3" = "{ZEROS}" ]; then\n'
    '  echo "deletion refused by the hub" >&2\n'
    "  exit 1\n"
    "fi\n"
    "exit 0\n"
)


class TestRemoteDeletionFailsClosed(WorkspaceCase):
    def install_rejecting_hook(self) -> None:
        hook = self.hub / "hooks" / "update"
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(UPDATE_HOOK, encoding="utf-8", newline="\n")
        os.chmod(hook, 0o755)

    def test_failed_remote_branch_deletion_leaves_workspace_and_hub_line_in_place(self):
        # covers: BO-4300e-3-ii
        # angle: deployed
        """AC-2: with a hub that rejects ref deletion, remove --delete-remote-branch of a workspace
        holding nothing unsent answers error/GIT_FAILED (exit 1) with a step naming the deletion;
        the workspace tree (.git included) and the hub's line are identical before and after.
        Must be implemented: the hub branch is deleted BEFORE any local deletion and a failed push
        is GIT_FAILED. The wrong version caught: the push result ignored and the folder deleted."""
        ws = self.ensure("alpha")
        branch = self.git(["rev-parse", "--abbrev-ref", "HEAD"], ws)
        self.git(["push", "-q", "origin", "HEAD"], ws)
        self.install_rejecting_hook()

        # Control: the hook really rejects a deletion (so a later failure is the hub's refusal).
        self.git(["push", "-q", "origin", "HEAD:refs/heads/probe-line"], ws)
        probe = subprocess.run(["git", "push", "origin", "--delete", "probe-line"], cwd=str(ws),
                               capture_output=True, text=True, env=_isolated_git_env(), check=False)
        self.assertNotEqual(probe.returncode, 0, msg="fixture: the hub accepted a ref deletion")
        self.assertTrue(self.git(["rev-parse", "--verify", "--quiet", "probe-line"], self.hub))

        before = self.snap(ws, with_git=True)
        hub_before = self.git(["rev-parse", branch], self.hub)
        self.assertTrue(before)

        res = self.cli(["remove", "--path", str(ws), "--delete-remote-branch"])
        answer = res["answer"]
        self.assertEqual((answer.get("status"), answer.get("code")), ("error", "GIT_FAILED"), msg=f"{res}")
        self.assertEqual(res["exit_code"], 1, msg=f"{res}")
        step = answer.get("step")
        self.assertTrue(isinstance(step, str) and "delete" in step.lower(),
                        msg=f"step does not name the deletion: {res}")
        self.assertTrue(ws.is_dir(), msg="the workspace folder is gone although the hub refused")
        self.assertEqual(self.snap(ws, with_git=True), before, msg="the workspace changed")
        self.assertEqual(self.git(["rev-parse", branch], self.hub), hub_before, msg="the hub line changed")


class TestHubBranchGuards(WorkspaceCase):
    def on_branch(self, ws, name: str) -> None:
        """Make *name* the folder's checked-out branch AND the marker's branch (a consistent workspace)."""
        self.git(["checkout", "-q", "-B", name], ws)
        forge_marker(ws, branch=name)

    def refused_before_anything(self, ws, code: str) -> dict:
        """Run remove --delete-remote-branch; assert the refusal, exit 2, and that nothing changed anywhere."""
        self.git(["push", "-q", str(self.hub), "HEAD:refs/heads/victim"], ws)  # a fetch would now add origin/victim
        before = self.snap(ws, with_git=True)
        hub_before = self.git(["for-each-ref", "--format=%(refname) %(objectname)"], self.hub)
        res = self.cli(["remove", "--path", str(ws), "--repo-root", str(self.project), "--delete-remote-branch"])
        self.assertEqual((res["answer"].get("status"), res["answer"].get("code")), ("refused", code), msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        self.assertEqual(self.snap(ws, with_git=True), before, msg="the workspace changed (a fetch ran?)")
        self.assertEqual(self.git(["for-each-ref", "--format=%(refname) %(objectname)"], self.hub), hub_before,
                         msg="the hub changed")
        return res

    def test_protected_branches_are_never_deleted_on_the_hub(self):
        # covers: BO-4300e-3-ii
        # angle: discrimination
        """With --delete-remote-branch, a workspace whose (consistent) branch is main, master, or the hub's
        default is refused ON_PROTECTED_BRANCH, exit 2, with a `branch` field, before any fetch or
        push; the hub branch is unchanged. Wrong versions caught: protecting only "main" (master and
        the hub default "trunk" cases), ignoring the hub default, deleting before the check (hub
        change), or fetching first (the .git digest, via the hub's unfetched "victim" branch)."""
        for name, make_default in (("main", False), ("master", False), ("trunk", True)):
            with self.subTest(branch=name):
                ws = self.ensure(f"p-{name}")
                self.on_branch(ws, name)
                self.git(["push", "-q", str(self.hub), f"HEAD:refs/heads/{name}"], ws)
                if make_default:
                    self.git(["symbolic-ref", "HEAD", f"refs/heads/{name}"], self.hub)
                    self.git(["fetch", "-q", "origin"], ws)
                    self.git(["symbolic-ref", "refs/remotes/origin/HEAD", f"refs/remotes/origin/{name}"], ws)
                res = self.refused_before_anything(ws, "ON_PROTECTED_BRANCH")
                self.assertEqual(res["answer"].get("branch"), name, msg=f"{res}")
                self.assertTrue(self.git(["rev-parse", "--verify", f"refs/heads/{name}"], self.hub))

    def test_an_unprotected_branch_is_deleted_on_the_hub_then_the_folder(self):
        # covers: BO-4300e-3-ii
        # angle: criterion
        """Control for the protection test: the same request for an ordinary, pushed branch answers ok, the
        hub branch is gone and so is the folder. The wrong version caught: a guard that refuses
        every --delete-remote-branch request."""
        ws = self.ensure("ordinary")
        branch = self.git(["branch", "--show-current"], ws)
        self.git(["push", "-q", "origin", "HEAD"], ws)
        res = self.cli(["remove", "--path", str(ws), "--repo-root", str(self.project), "--delete-remote-branch"])
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertFalse(ws.exists())
        self.assertEqual(self.git(["for-each-ref", f"refs/heads/{branch}"], self.hub), "")

    def test_an_empty_marker_branch_is_not_found(self):
        # covers: BO-4300e-3-ii
        # angle: boundary
        """A detached folder whose marker carries no branch (null) with --delete-remote-branch is NOT_FOUND
        (exit 2); nothing is fetched, pushed or deleted. The wrong version caught: running
        `git push origin --delete ""` (or defaulting to HEAD) for an empty branch name."""
        ws = self.ensure("nobranch")
        self.git(["checkout", "-q", "--detach"], ws)
        forge_marker(ws, branch=None)
        self.refused_before_anything(ws, "NOT_FOUND")

    def test_an_option_like_marker_branch_is_not_found(self):
        # covers: BO-4300e-3-ii
        # angle: boundary
        """A folder genuinely checked out on a branch named "-x" (made with plumbing; git refuses it
        porcelain-side) whose marker says "-x" is NOT_FOUND (exit 2) with --delete-remote-branch; the
        hub's own "-x" branch survives. The wrong version caught: passing the name to
        `git push origin --delete -x` where git would read it as an option."""
        ws = self.ensure("dash")
        sha = self.git(["rev-parse", "HEAD"], ws)
        self.git(["update-ref", "refs/heads/-x", sha], ws)
        self.git(["symbolic-ref", "HEAD", "refs/heads/-x"], ws)
        self.git(["update-ref", "refs/heads/-x", sha], self.hub)
        forge_marker(ws, branch="-x")
        self.assertEqual(self.git(["branch", "--show-current"], ws), "-x", msg="fixture: -x not checked out")
        self.refused_before_anything(ws, "NOT_FOUND")
        self.assertEqual(self.git(["rev-parse", "--verify", "refs/heads/-x"], self.hub), sha)

    def remove_with_failing_local_delete(self, slug: str, delete_remote: bool) -> tuple[dict, object, str]:
        ws = self.ensure(slug)
        branch = self.git(["branch", "--show-current"], ws)
        self.git(["push", "-q", "origin", "HEAD"], ws)
        args = argparse.Namespace(path=str(ws), repo_root=str(self.project), landing_root=None,
                                  delete_remote_branch=delete_remote, discard_token=None)
        with deployed_worktree_remove() as wr, mock.patch.dict(os.environ, self.env()), \
                mock.patch.object(wr, "_holding_programs", return_value=[]), \
                mock.patch.object(wr, "delete_whole_folder", return_value="Could not remove all of it (injected)") as gone:
            answer = wr.cmd_remove(args)
        self.assertEqual(gone.call_count, 1, msg="the local delete was not attempted exactly once")
        return answer, ws, branch

    def test_failed_local_delete_after_the_hub_branch_went_says_so(self):
        # covers: BO-4300e-3-ii
        # angle: failure
        """In-process against the DEPLOYED module (the local delete cannot be made to fail reliably through the
        CLI on Linux, where a root test user ignores read-only folders): delete_whole_folder is made to
        report a leftover. The hub branch is deleted first, so the answer is PROCESS_HOLDS_FILES with
        hub_branch_deleted: true and a message saying the shared project's branch was already deleted;
        the folder is still there. Wrong versions caught: the flag or the sentence missing; deleting
        the hub branch only after the local delete (the hub branch would survive). Control: without
        --delete-remote-branch the hub branch survives and the answer carries no hub_branch_deleted."""
        answer, ws, branch = self.remove_with_failing_local_delete("stuck-a", delete_remote=True)
        self.assertEqual(answer.get("code"), "PROCESS_HOLDS_FILES", msg=f"{answer}")
        self.assertIs(answer.get("hub_branch_deleted"), True, msg=f"{answer}")
        message = answer.get("message", "").lower()
        self.assertTrue("already deleted" in message and "shared project" in message, msg=f"{answer}")
        self.assertTrue(ws.is_dir())
        self.assertEqual(self.git(["for-each-ref", f"refs/heads/{branch}"], self.hub), "")

        control, ws2, branch2 = self.remove_with_failing_local_delete("stuck-b", delete_remote=False)
        self.assertEqual(control.get("code"), "PROCESS_HOLDS_FILES", msg=f"{control}")
        self.assertNotIn("hub_branch_deleted", control)
        self.assertNotIn("already deleted", control.get("message", "").lower())
        self.assertNotEqual(self.git(["for-each-ref", f"refs/heads/{branch2}"], self.hub), "")


if __name__ == "__main__":
    unittest.main()
