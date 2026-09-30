"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_2_i.py
AC: BO-4300b-2-i -- Two projects in the same folder never share or collide on a workspace
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: worktree_layout.py, the BO-4300b resolution order and the Q5 sibling landing root
do not exist yet.

DECISION HISTORY
====================================================================
- 2026-09-30 22:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04,
  BO-4300b-2-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
====================================================================
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
    ensure_deployed_layout,
    make_project,
    run_maker,
)
from unit_tests.build_orchestration._workspace_maker_builders import (
    _configure_identity,
    _isolated_git_env,
    _run_git,
)


def _env(ceiling: Path | None = None) -> dict[str, str]:
    env = dict(_isolated_git_env())
    if ceiling is not None:
        env["GIT_CEILING_DIRECTORIES"] = str(ceiling)
    return env


def clean_parent(tmp: Path, name: str = "proj", hook: str = "accept") -> tuple[Path, Path, Path]:
    """Real bare hub + a project clone inside a parent folder that holds ONLY the project."""
    fx = make_project(Path(tmp) / f"fx-{name}", hook=hook)
    parent = Path(tmp) / f"parent-{name}"
    parent.mkdir(parents=True)
    proj = parent / name
    _run_git(["clone", "-q", str(fx["hub"]), str(proj)], parent)
    _configure_identity(proj)
    return parent, proj, fx["hub"]


def maker(args: list[str], cwd: Path, ceiling: Path | None = None) -> dict:
    return run_maker(args, cwd=Path(cwd), env=_env(ceiling))


def same(a, b) -> bool:
    return Path(a).resolve() == Path(b).resolve()


def inside(child, parent) -> bool:
    try:
        Path(child).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def git_out(args: list[str], cwd: Path) -> str:
    return _run_git(args, Path(cwd)).stdout.strip()


def tree_listing(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*"))


def force_rmtree(path: Path) -> None:
    def _chmod(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    shutil.rmtree(path, onerror=_chmod)



def _files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in Path(root).rglob("*") if ".git" not in p.relative_to(root).parts)


def _snap(ws: Path) -> dict:
    return {"head": git_out(["rev-parse", "HEAD"], ws), "status": git_out(["status", "--porcelain"], ws),
            "files": _files(ws)}


class TestBO4300b2i(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b2i-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        # shop and blog side by side in ONE parent folder
        self.parent, self.shop, self.shop_hub = clean_parent(self.tmp, "shop")
        fx = make_project(self.tmp / "fx-blog", hook="accept")
        self.blog = self.parent / "blog"
        _run_git(["clone", "-q", str(fx["hub"]), str(self.blog)], self.parent)
        _configure_identity(self.blog)
        self.blog_hub = fx["hub"]

    def _ensure(self, project: Path, *extra: str) -> dict:
        return maker(["ensure", "--kind", "scratch", "--slug", "alpha", "--repo-root", str(project), *extra], project)["answer"]

    def test_same_slug_in_two_projects_gives_two_distinct_workspaces(self):
        # covers: BO-4300b-2-i
        # angle: criterion
        """alpha in shop and alpha in blog are two workspaces, each a clone of its own project."""
        a, b = self._ensure(self.shop), self._ensure(self.blog)
        self.assertEqual((a.get("status"), b.get("status")), ("ok", "ok"), (a, b))
        self.assertFalse(same(a["workspace_path"], b["workspace_path"]))
        self.assertTrue(same(Path(a["workspace_path"]).parent, self.parent / "shop-worktrees" / "scratch"), a)
        self.assertTrue(same(Path(b["workspace_path"]).parent, self.parent / "blog-worktrees" / "scratch"), b)
        self.assertTrue(same(git_out(["remote", "get-url", "origin"], Path(a["workspace_path"])), self.shop_hub))
        self.assertTrue(same(git_out(["remote", "get-url", "origin"], Path(b["workspace_path"])), self.blog_hub))

    def test_shops_workspace_is_unchanged_by_blogs_request(self):
        # covers: BO-4300b-2-i
        # angle: boundary
        """shop's alpha workspace is identical before and after blog's request."""
        a = self._ensure(self.shop)
        self.assertEqual(a.get("status"), "ok", a)
        ws = Path(a["workspace_path"])
        self.assertTrue(same(Path(ws).parent, self.parent / "shop-worktrees" / "scratch"), a)
        before = _snap(ws)
        self.assertEqual(self._ensure(self.blog).get("status"), "ok")
        self.assertEqual(_snap(ws), before)

    def test_locate_returns_each_projects_own_workspace(self):
        # covers: BO-4300b-2-i
        # angle: criterion
        """locate alpha run in shop returns shop's, in blog returns blog's."""
        a, b = self._ensure(self.shop), self._ensure(self.blog)
        self.assertEqual((a.get("status"), b.get("status")), ("ok", "ok"), (a, b))
        la = maker(["locate", "--kind", "scratch", "--slug", "alpha"], self.shop)["answer"]
        lb = maker(["locate", "--kind", "scratch", "--slug", "alpha"], self.blog)["answer"]
        self.assertEqual((la.get("status"), lb.get("status")), ("ok", "ok"), (la, lb))
        self.assertTrue(same(Path(la["workspace_path"]).parent, self.parent / "shop-worktrees" / "scratch"), la)
        self.assertTrue(same(la["workspace_path"], a["workspace_path"]))
        self.assertTrue(same(lb["workspace_path"], b["workspace_path"]))

    def test_two_projects_land_in_their_own_sibling_folders(self):
        # covers: BO-4300b-2-i
        # angle: criterion
        """shop's alpha is under <parent>/shop-worktrees/, blog's under <parent>/blog-worktrees/."""
        a, b = self._ensure(self.shop), self._ensure(self.blog)
        self.assertEqual((a.get("status"), b.get("status")), ("ok", "ok"), (a, b))
        self.assertTrue(same(Path(a["workspace_path"]).parent, self.parent / "shop-worktrees" / "scratch"), a)
        self.assertTrue(same(Path(b["workspace_path"]).parent, self.parent / "blog-worktrees" / "scratch"), b)

    def test_shared_landing_root_override_refuses_rather_than_collides(self):
        # covers: BO-4300b-2-i
        # angle: failure
        """Same --landing-root for both: blog's alpha is refused OCCUPIED (other-project); shop's is untouched."""
        root = self.tmp / "shared-landing"
        root.mkdir()
        a = self._ensure(self.shop, "--landing-root", str(root))
        self.assertEqual(a.get("status"), "ok", a)
        self.assertTrue(same(Path(a["workspace_path"]), root / "scratch" / "alpha"), a)
        ws = Path(a["workspace_path"])
        before = _snap(ws)
        b = self._ensure(self.blog, "--landing-root", str(root))
        self.assertEqual(b.get("status"), "refused", b)
        self.assertEqual(b.get("code"), "OCCUPIED", b)
        self.assertIn("other-project", json.dumps(b))
        self.assertEqual(_snap(ws), before)


if __name__ == "__main__":
    unittest.main()
