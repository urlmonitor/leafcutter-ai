"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_iii.py
AC: BO-4300e-2-iii -- Clearing only ever removes one of this project's own workspaces.

Given a project "shop" with a ready workspace "alpha" in shop's landing place, a project "blog"
beside it with a ready workspace "alpha" in blog's landing place, and a folder "stray" outside
both landing places that holds a copy of a workspace record naming shop, when clearing is
requested from shop for blog's "alpha", and for "stray", each request is refused (NOT_FOUND:
shop has no workspace at that location), blog's "alpha" and "stray" are identical before and
after, and clearing shop's "alpha" from shop is still answered cleared.

Real-subprocess proof against the DEPLOYED maker, two real projects with their own hubs, no mock
of git, never a build.py spawn of its own. The refused requests carry --delete-remote-branch, so
a maker that pushed anything for them would also change blog's hub, which is checked too.
Helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/04, BO-4300e-2-iii]: Created the red
  baseline.
- 2026-10-22 [test-writer/EPIC-WorkspaceMakerHardening/04, pr-reviewer rework]: Guard tests for
  the reworked remove: forged marker branch, the <landing>/<kind>/<slug> slot rule, and
  _holder_entry never raising on a psutil error (in-process against the DEPLOYED worktree_remove).
====================================================================
"""
from __future__ import annotations

import contextlib
import importlib
import json
import os
import shutil
import sys
import types
import unittest
from pathlib import Path
from unittest import mock

from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path, make_project
from unit_tests.build_orchestration.test_bo_4300e_2 import INSTALL_ARTIFACTS, KIND, WorkspaceCase


class TestClearingStaysInsideTheProject(WorkspaceCase):
    def blog_alpha(self) -> tuple[Path, Path, Path]:
        """Blog: ``(project, hub, ready workspace "alpha")`` with alpha's line pushed to blog's hub."""
        fx = make_project(self.tmp / "blog-world")
        blog = fx["project"]
        res = self.cli(["ensure", "--kind", KIND, "--slug", "alpha", "--repo-root", str(blog)], cwd=blog)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"blog fixture ensure failed: {res}")
        ws = Path(res["answer"]["workspace_path"])
        with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8", newline="\n") as fh:
            fh.write("\n".join(INSTALL_ARTIFACTS) + "\n")
        self.git(["push", "-q", "origin", "HEAD"], ws)
        return blog, fx["hub"], ws

    def remove_from_shop(self, target: Path) -> dict:
        args = ["remove", "--path", str(target), "--repo-root", str(self.project), "--delete-remote-branch"]
        return self.cli(args, cwd=self.project)

    def assert_not_found(self, res: dict, target: Path) -> None:
        self.assertEqual(res["answer"].get("code"), "NOT_FOUND", msg=f"{res}")
        self.assertEqual(res["answer"].get("status"), "refused", msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        message = os.path.normcase(res["answer"].get("message", "")).replace("\\", "/")
        self.assertIn(os.path.normcase(str(target)).replace("\\", "/"), message,
                      msg=f"the refusal does not say where shop has no workspace: {res}")

    def test_clearing_another_projects_or_a_stray_folder_is_not_found_and_changes_nothing(self):
        # covers: BO-4300e-2-iii
        # angle: deployed
        """AC-1: from shop, remove of blog's alpha and of a stray folder holding a copy of shop's
        marker are each NOT_FOUND; both trees (.git included) are byte-identical after, blog's hub
        line is untouched; the control (shop's own alpha) is still cleared. Must be implemented:
        cmd_remove resolves the project and acts only on a path inside its landing place."""
        shop_alpha = self.ensure("alpha")
        _blog, blog_hub, blog_alpha = self.blog_alpha()
        stray = self.tmp / "stray"
        marker = shop_alpha / ".leafcutter" / "workspace.json"
        self.assertTrue(marker.is_file(), msg="fixture: shop's alpha has no marker to copy")
        (stray / ".leafcutter").mkdir(parents=True)
        shutil.copyfile(marker, stray / ".leafcutter" / "workspace.json")
        (stray / "keep.txt").write_text("stray content\n", encoding="utf-8", newline="\n")

        blog_before = self.snap(blog_alpha, with_git=True)
        stray_before = self.snap(stray, with_git=True)
        blog_branch = self.git(["rev-parse", "--abbrev-ref", "HEAD"], blog_alpha)
        hub_before = self.git(["rev-parse", blog_branch], blog_hub)
        self.assertTrue(blog_before and stray_before)

        self.assert_not_found(self.remove_from_shop(blog_alpha), blog_alpha)
        self.assert_not_found(self.remove_from_shop(stray), stray)

        self.assertEqual(self.snap(blog_alpha, with_git=True), blog_before, msg="blog's alpha changed")
        self.assertEqual(self.snap(stray, with_git=True), stray_before, msg="the stray folder changed")
        self.assertEqual(self.git(["rev-parse", blog_branch], blog_hub), hub_before,
                         msg="blog's line on its hub changed")

        control = self.remove_from_shop(shop_alpha)
        self.assertEqual(control["answer"].get("status"), "ok", msg=f"{control}")
        self.assertFalse(shop_alpha.exists(), msg="shop's own alpha was not cleared")


@contextlib.contextmanager
def deployed_worktree_remove():
    """Import the DEPLOYED ``worktree_remove`` in-process (its folder on ``sys.path`` only for the
    duration) and forget every module it pulled in afterwards, so no copy leaks to a sibling test."""
    scripts = str(deployed_maker_path().parent)
    before = set(sys.modules)
    sys.path.insert(0, scripts)
    try:
        yield importlib.import_module("worktree_remove")
    finally:
        with contextlib.suppress(ValueError):
            sys.path.remove(scripts)
        for name in set(sys.modules) - before:
            if name.startswith(("worktree", "leafcutter_sweep")):
                del sys.modules[name]


def forge_marker(ws: Path, **changes) -> None:
    """Rewrite fields of the workspace's marker file (the way a copied or hand-edited marker lies)."""
    path = ws / ".leafcutter" / "workspace.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record.update(changes)
    path.write_text(json.dumps(record), encoding="utf-8", newline="\n")


class TestRemoveOnlyActsOnARealWorkspaceSlot(WorkspaceCase):
    def assert_refused_unchanged(self, res: dict, folder: Path, before: dict, hub_before: str, why: str) -> None:
        self.assertEqual((res["answer"].get("status"), res["answer"].get("code")), ("refused", "NOT_FOUND"),
                         msg=f"{why}: {res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{why}: {res}")
        self.assertEqual(self.snap(folder, with_git=True), before, msg=f"{why}: the folder changed")
        self.assertEqual(self.refs(self.hub), hub_before, msg=f"{why}: the hub changed")

    def test_forged_marker_branch_that_is_not_the_checked_out_branch_is_not_found(self):
        # covers: BO-4300e-2-iii
        # angle: failure
        """A marker naming a branch other than the one the folder has checked out is NOT_FOUND (exit 2)
        with and without --delete-remote-branch; nothing is fetched, pushed or deleted. Fixture: the
        hub holds a branch "victim" the workspace has never fetched, so a fetch would add
        refs/remotes/origin/victim (caught by the .git digest) and a delete would remove it (caught by
        the hub refs). The wrong version caught: trusting the marker's branch without comparing it to
        the folder's own checked-out branch (it would delete "victim" on the hub). Control: the
        unforged workspace is removed ok in the AC-1 test of this file."""
        ws = self.ensure("alpha")
        self.git(["push", "-q", str(self.hub), "HEAD:refs/heads/victim"], ws)
        forge_marker(ws, branch="victim")
        before = self.snap(ws, with_git=True)
        hub_before = self.refs(self.hub)
        self.assertIn("refs/heads/victim", hub_before)
        self.assertTrue(before)
        for flag in ([], ["--delete-remote-branch"]):
            res = self.cli(["remove", "--path", str(ws), "--repo-root", str(self.project), *flag])
            self.assert_refused_unchanged(res, ws, before, hub_before, f"forged branch, flags={flag}")

    def copy_workspace(self, ws: Path, dest: Path) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(ws, dest, symlinks=True)
        return dest

    def test_a_folder_off_the_landing_slot_is_not_found_and_unchanged(self):
        # covers: BO-4300e-2-iii
        # angle: boundary
        """Boundary of the <landing>/<kind>/<slug> rule: a full copy of a ready workspace (own .git, valid
        marker, matching branch) one level too deep, one level too shallow, or under an unknown kind is
        NOT_FOUND (exit 2) and byte-identical afterwards; so is a slot with a marker but no .git of
        its own. The wrong versions caught: a prefix-only 'inside the landing place' check (deeper,
        shallower), a missing kind check (unknown-kind), a missing own-.git check (no-own-git)."""
        ws = self.ensure("alpha")
        cases = {
            "deeper": self.copy_workspace(ws, self.landing / KIND / "outer" / "inner"),
            "shallower": self.copy_workspace(ws, self.landing / "shallow"),
            "unknown-kind": self.copy_workspace(ws, self.landing / "bogus-kind" / "alpha"),
        }
        nogit = self.copy_workspace(ws, self.landing / KIND / "nogit")
        shutil.rmtree(nogit / ".git", onerror=lambda func, target, _exc: (os.chmod(target, 0o700), func(target)))
        cases["no-own-git"] = nogit
        hub_before = self.refs(self.hub)
        for why, folder in cases.items():
            before = self.snap(folder, with_git=True)
            self.assertTrue(before, msg=why)
            for flag in ([], ["--delete-remote-branch"]):
                res = self.cli(["remove", "--path", str(folder), "--repo-root", str(self.project), *flag])
                self.assert_refused_unchanged(res, folder, before, hub_before, f"{why}, flags={flag}")
        self.assertTrue(ws.is_dir())

    def test_holder_entry_never_raises_when_psutil_errors(self):
        # covers: BO-4300c-2
        # angle: failure
        """_holder_entry (in-process, the DEPLOYED module) answers {pid:int, name:str} even when psutil
        raises NoSuchProcess or AccessDenied, which are psutil.Error (an Exception, NOT an OSError); the
        name falls back to the first word of the command line, or "unknown". The wrong version caught:
        `except OSError` (the original defect: remove crashed with a traceback instead of
        PROCESS_HOLDS_FILES). Control: a psutil that works supplies the name."""
        class NoSuchProcess(Exception):
            pass

        class AccessDenied(Exception):
            pass

        def fake_psutil(error):
            mod = types.ModuleType("psutil")
            mod.NoSuchProcess, mod.AccessDenied = NoSuchProcess, AccessDenied

            def process(pid):
                if error is None:
                    return types.SimpleNamespace(name=lambda: "from-psutil")
                raise error(pid)

            mod.Process = process
            return mod

        with deployed_worktree_remove() as wr:
            for error in (NoSuchProcess, AccessDenied):
                with mock.patch.dict(sys.modules, {"psutil": fake_psutil(error)}):
                    got = wr._holder_entry({"pid": 4242, "cmdline": "/usr/bin/sleep 30"})
                    self.assertEqual(got, {"pid": 4242, "name": "sleep"}, msg=error.__name__)
                    self.assertIs(type(got["pid"]), int)
                    self.assertEqual(wr._holder_entry({"pid": 7}), {"pid": 7, "name": "unknown"})
            with mock.patch.dict(sys.modules, {"psutil": fake_psutil(None)}):
                self.assertEqual(wr._holder_entry({"pid": 5, "cmdline": "x y"}), {"pid": 5, "name": "from-psutil"})


if __name__ == "__main__":
    unittest.main()
