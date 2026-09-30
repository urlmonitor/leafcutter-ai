"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_2.py
AC: BO-4300b-2 -- A project that installed the tools gets its workspaces the same way
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: worktree_layout.py, the BO-4300b resolution order and the Q5 sibling landing root
do not exist yet.

DECISION HISTORY
====================================================================
- 2026-09-30 22:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04,
  BO-4300b-2]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
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



class TestBO4300b2(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b2-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.parent, self.shop, self.hub = clean_parent(self.tmp, "shop")
        self.args = ["ensure", "--kind", "scratch", "--slug", "alpha"]

    def test_adopter_request_from_top_and_parent_folder_gives_same_location(self):
        # covers: BO-4300b-2
        # angle: criterion
        """The deployed maker (outside shop's history) answers ok with one location from both folders."""
        a = maker(self.args, self.shop)["answer"]
        b = maker(self.args, self.parent)["answer"]
        self.assertEqual((a.get("status"), b.get("status")), ("ok", "ok"), (a, b))
        self.assertTrue(same(a["workspace_path"], b["workspace_path"]))

    def test_adopter_workspace_is_clone_of_shop_at_hub_main_with_own_install(self):
        # covers: BO-4300b-2
        # angle: criterion
        """Clone of shop (origin = hub), base = hub main tip, install files are regular files inside it."""
        ans = maker(self.args, self.shop)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        ws = Path(ans["workspace_path"])
        self.assertTrue(same(Path(ws).parent, self.parent / "shop-worktrees" / "scratch"), ans)
        self.assertTrue(same(git_out(["remote", "get-url", "origin"], ws), self.hub))
        self.assertEqual(ans["base_commit"], git_out(["rev-parse", "main"], self.hub))
        installed = ws / "INSTALLED_MARKER.txt"
        self.assertTrue(installed.is_file() and not installed.is_symlink())
        self.assertIn((ws / "BUILD_STAMP.txt").read_text(encoding="utf-8").strip(), installed.read_text(encoding="utf-8"))

    def test_adopter_location_is_stable_and_in_shops_landing_place(self):
        # covers: BO-4300b-2
        # angle: boundary
        """Repeated requests give one location, in the one place set aside for shop's workspaces."""
        paths = {str(Path(maker(self.args, start)["answer"].get("workspace_path", "?")).resolve())
                 for start in (self.shop, self.shop, self.parent)}
        self.assertEqual(len(paths), 1, paths)
        self.assertTrue(same(Path(paths.pop()).parent, self.parent / "shop-worktrees" / "scratch"))

    def test_workspace_lands_in_the_sibling_folder_named_after_the_project(self):
        # covers: BO-4300b-2
        # angle: criterion
        """<parent>/shop-worktrees/<kind>/alpha, and shop's working tree (incl. ignored) is unchanged."""
        before = git_out(["status", "--porcelain", "--ignored"], self.shop)
        ans = maker(self.args, self.shop)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertTrue(same(ans["workspace_path"], self.parent / "shop-worktrees" / "scratch" / "alpha"), ans)
        self.assertEqual(git_out(["status", "--porcelain", "--ignored"], self.shop), before)

    def test_dev_layout_lands_beside_the_package_repository(self):
        # covers: BO-4300b-2
        # angle: boundary
        """Package repo pkg in a non-repo workspace folder: <folder>/pkg-worktrees/<kind>/alpha."""
        folder, pkg, _ = clean_parent(self.tmp, "pkg")
        (folder / ".leafcutter" / "scripts").mkdir(parents=True)
        ans = maker(self.args, pkg)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        ws = Path(ans["workspace_path"])
        self.assertTrue(same(ws, folder / "pkg-worktrees" / "scratch" / "alpha"), ans)
        self.assertFalse(same(ws, folder / "worktrees" / "alpha"))
        self.assertFalse(inside(ws, pkg))

    def test_valid_landing_root_override_is_used_and_needed_to_find_it_again(self):
        # covers: BO-4300b-2
        # angle: boundary
        """--landing-root is used; locate needs the same override (else NOT_FOUND)."""
        root = self.tmp / "custom-landing"
        root.mkdir()
        ans = maker([*self.args, "--landing-root", str(root)], self.shop)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertTrue(same(ans["workspace_path"], root / "scratch" / "alpha"), ans)
        loc = ["locate", "--kind", "scratch", "--slug", "alpha"]
        found = maker([*loc, "--landing-root", str(root)], self.shop)["answer"]
        self.assertEqual(found.get("status"), "ok", found)
        self.assertTrue(same(found["workspace_path"], ans["workspace_path"]))
        self.assertEqual(maker(loc, self.shop)["answer"].get("code"), "NOT_FOUND")

    def test_invalid_landing_root_override_is_refused_as_usage_writing_nothing(self):
        # covers: BO-4300b-2
        # angle: failure
        """--landing-root inside shop, and inside an existing workspace: exit 64, USAGE, nothing written."""
        first = maker(self.args, self.shop)["answer"]
        self.assertEqual(first.get("status"), "ok", first)
        existing = Path(first["workspace_path"])
        for bad in (self.shop / "landing-inside", existing / "landing-inside"):
            with self.subTest(root=str(bad)):
                before = tree_listing(self.parent)
                res = maker(["ensure", "--kind", "scratch", "--slug", "beta", "--landing-root", str(bad)], self.shop)
                ans = res["answer"]
                self.assertEqual(res["exit_code"], 64, ans)
                self.assertEqual((ans.get("status"), ans.get("code")), ("error", "USAGE"), ans)
                self.assertIn("landing-root", ans.get("message", ""), ans)
                self.assertNotIn("unrecognized", ans.get("message", ""), ans)
                self.assertFalse(bad.exists())
                self.assertEqual(tree_listing(self.parent), before)
                self.assertNotIn("beta", git_out(["branch", "-a"], self.shop))

    def test_landing_place_is_not_taken_from_the_environment(self):
        # covers: BO-4300b-2
        # angle: seam
        """Landing-root-like environment variables do not move the workspace."""
        elsewhere = self.tmp / "env-elsewhere"
        elsewhere.mkdir()
        env = _env()
        for name in ("LANDING_ROOT", "LEAFCUTTER_LANDING_ROOT", "WORKTREE_LANDING_ROOT", "LEAFCUTTER_WORKTREES"):
            env[name] = str(elsewhere)
        ans = run_maker(self.args, cwd=self.shop, env=env)["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertTrue(same(ans["workspace_path"], self.parent / "shop-worktrees" / "scratch" / "alpha"), ans)
        self.assertEqual(list(elsewhere.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
