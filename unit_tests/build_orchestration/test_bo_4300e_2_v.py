"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2_v.py
AC: BO-4300e-2-v -- A folder left by a clearing that stopped part-way is finished, but only inside
this project's own landing place.

Real-subprocess proof against the DEPLOYED maker. Fixture: workspaces made by `ensure`, then
gutted (repository gone) into the three half-cleared shapes. Workspaces use KIND "feature" (the
shared helper's kind). Helpers come from test_bo_4300e_2.py.

DECISION HISTORY
====================================================================
- 2026-10-26 [test-writer/fast-lane bo-4300e-2, BO-4300e-2-v]: Created the red baseline.
====================================================================
"""
from __future__ import annotations

import json
import os
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import make_project
from unit_tests.build_orchestration.test_bo_4300e_2 import KIND, WorkspaceCase, _force_rmtree


class HalfClearedCase(WorkspaceCase):
    def gut(self, ws: Path, keep_record: bool) -> Path:
        """Leave *ws* as a clearing that stopped part-way leaves it: repository and content gone."""
        record = ws / ".leafcutter" / "workspace.json"
        saved = record.read_bytes() if keep_record else None
        for child in sorted(ws.iterdir()):
            if child.is_dir():
                _force_rmtree(child)
            else:
                os.chmod(child, 0o600)
                child.unlink()
        if saved is not None:
            record.parent.mkdir()
            record.write_bytes(saved)
        return ws

    def shop_shapes(self) -> dict[str, Path]:
        """alpha empty; gamma record only; delta record plus an empty sub-folder "build"."""
        shapes = {}
        for slug in ("alpha", "gamma", "delta"):
            ws = self.ensure(slug)
            self.git(["push", "-q", "origin", "HEAD"], ws)
            shapes[slug] = self.gut(ws, keep_record=slug != "alpha")
        (shapes["delta"] / "build").mkdir()
        return shapes

    def blog_empty(self) -> tuple[Path, Path]:
        fx = make_project(self.tmp / "blog-world")
        self.blog_project = fx["project"]
        folder = fx["landing_place"] / KIND / "alpha"
        folder.mkdir(parents=True)
        return folder, fx["hub"]

    def foreign_record_folder(self, slug: str) -> Path:
        """A half-cleared folder in SHOP's own landing place whose record names blog as its project."""
        ws = self.gut(self.ensure(slug), keep_record=True)
        record = ws / ".leafcutter" / "workspace.json"
        data = json.loads(record.read_text(encoding="utf-8"))
        data["project_root"] = str(self.blog_project)
        record.write_text(json.dumps(data), encoding="utf-8")
        return ws

    def remove_from_shop(self, target: Path) -> dict[str, Any]:
        return self.cli(["remove", "--path", str(target), "--repo-root", str(self.project),
                         "--delete-remote-branch"])


class TestHalfClearedFolders(HalfClearedCase):
    def test_three_half_cleared_shapes_are_cleared_and_leave_nothing(self):
        # covers: BO-4300e-2-v
        # angle: reachability
        """AC-1: the real CLI answers ok for shop's empty, record-only and record-plus-empty-folder
        leftovers, and nothing remains at any location."""
        for slug, folder in self.shop_shapes().items():
            self.assertTrue(folder.is_dir(), msg=f"fixture: {slug} is gone before the request")
            res = self.remove_from_shop(folder)
            self.assertEqual(res["answer"].get("status"), "ok", msg=f"{slug}: {res}")
            self.assertEqual(res["exit_code"], 0, msg=f"{slug}: {res}")
            self.assertFalse(os.path.lexists(folder), msg=f"{slug}: something remains")

    def test_half_cleared_folders_are_not_answered_not_found(self):
        # covers: BO-4300e-2-v
        # angle: discrimination
        """AC-1: none of the three requests is NOT_FOUND (the observed defect: a maker still requiring
        the folder's own .git); each is ok. The blog-side control proves the maker does not simply
        finish every folder."""
        blog_folder, _hub = self.blog_empty()
        for slug, folder in self.shop_shapes().items():
            res = self.remove_from_shop(folder)
            self.assertNotEqual(res["answer"].get("code"), "NOT_FOUND", msg=f"{slug}: {res}")
            self.assertEqual(res["answer"].get("status"), "ok", msg=f"{slug}: {res}")
        self.assertEqual(self.remove_from_shop(blog_folder)["answer"].get("code"), "NOT_FOUND")
        # A folder inside shop's own landing place whose record names ANOTHER project is not ours.
        foreign = self.foreign_record_folder("zeta")
        before = {p.relative_to(foreign).as_posix() for p in foreign.rglob("*")}
        self.assertIn(".leafcutter/workspace.json", before, msg="fixture: record missing")
        res = self.remove_from_shop(foreign)
        self.assertEqual((res["answer"].get("status"), res["answer"].get("code")), ("refused", "NOT_FOUND"),
                         msg=f"{res}")
        self.assertTrue(foreign.is_dir(), msg="the other project's folder was deleted")
        self.assertEqual({p.relative_to(foreign).as_posix() for p in foreign.rglob("*")}, before)

    def test_other_projects_half_cleared_folder_is_refused_and_untouched(self):
        # covers: BO-4300e-2-v
        # angle: boundary
        """AC-1: from shop, blog's empty feature/alpha is refused NOT_FOUND (exit 2), the message says
        shop has no workspace at that location, and the folder is identical before and after. Control:
        shop's own empty leftover is finished in the same run."""
        blog_folder, _hub = self.blog_empty()
        shapes = self.shop_shapes()
        before = {p.relative_to(blog_folder).as_posix() for p in blog_folder.rglob("*")}
        res = self.remove_from_shop(blog_folder)
        answer = res["answer"]
        self.assertEqual((answer.get("status"), answer.get("code")), ("refused", "NOT_FOUND"), msg=f"{res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        message = os.path.normcase(str(answer.get("message", ""))).replace("\\", "/")
        self.assertIn(os.path.normcase(str(blog_folder)).replace("\\", "/"), message, msg=f"{answer}")
        self.assertIn("no workspace", message.lower(), msg=f"{answer}")
        self.assertTrue(blog_folder.is_dir(), msg="blog's folder was deleted")
        self.assertEqual({p.relative_to(blog_folder).as_posix() for p in blog_folder.rglob("*")}, before)
        self.assertEqual(self.remove_from_shop(shapes["alpha"])["answer"].get("status"), "ok")

    def test_finishing_half_cleared_folders_sends_nothing_to_either_hub(self):
        # covers: BO-4300e-2-v
        # angle: criterion
        """AC-1: shop's and blog's hub refs are identical before and after all four requests, which
        carry --delete-remote-branch so a push would be visible (the lines were pushed first)."""
        blog_folder, blog_hub = self.blog_empty()
        shapes = self.shop_shapes()
        fmt = ["for-each-ref", "--format=%(refname) %(objectname)"]
        shop_before, blog_before = self.refs(self.hub), self.git(fmt, blog_hub)
        self.assertIn("refs/heads/", shop_before)
        results = [self.remove_from_shop(f) for f in (*shapes.values(), blog_folder)]
        self.assertEqual([r["answer"].get("status") for r in results], ["ok", "ok", "ok", "refused"],
                         msg=f"{results}")
        self.assertEqual(self.refs(self.hub), shop_before, msg="shop's shared project changed")
        self.assertEqual(self.git(fmt, blog_hub), blog_before, msg="blog's shared project changed")

    def test_record_less_folder_holding_files_is_refused_with_no_token(self):
        # covers: BO-4300e-2-v
        # angle: boundary
        """A folder in shop's own landing place with no repository and no workspace record is finished
        only when empty (user decision 2026-10-29): one holding a file is refused NOT_FOUND with no
        discard token, even when a token is presented, and stays identical. Control: the empty
        record-less alpha is finished."""
        shapes = self.shop_shapes()
        stray = shapes["alpha"].parent / "stray"
        stray.mkdir()
        (stray / "notes.txt").write_text("not a workspace\n", encoding="utf-8")
        for token in (None, "0" * 32):
            extra = ["--discard-token", token] if token else []
            answer = self.cli(["remove", "--path", str(stray), "--repo-root", str(self.project), *extra])["answer"]
            self.assertEqual((answer.get("status"), answer.get("code")), ("refused", "NOT_FOUND"), msg=f"{answer}")
            self.assertNotIn("discard_token", answer, msg=f"{answer}")
            self.assertEqual(answer.get("files"), ["notes.txt"], msg=f"{answer}")
            self.assertEqual((stray / "notes.txt").read_text(encoding="utf-8"), "not a workspace\n")
        self.assertEqual(self.remove_from_shop(shapes["alpha"])["answer"].get("status"), "ok")


if __name__ == "__main__":
    unittest.main()
