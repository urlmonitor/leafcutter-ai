"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_3.py
AC: BO-4300b-3 -- When more than one project could be meant, the request is refused and names them
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: worktree_layout.py, the BO-4300b resolution order and the Q5 sibling landing root
do not exist yet.

DECISION HISTORY
====================================================================
- 2026-09-30 22:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04,
  BO-4300b-3]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
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



class TestBO4300b3(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b3-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.parent, self.shop, _ = clean_parent(self.tmp, "shop")
        fx = make_project(self.tmp / "fx-blog", hook="accept")
        self.blog = self.parent / "blog"
        _run_git(["clone", "-q", str(fx["hub"]), str(self.blog)], self.parent)
        _configure_identity(self.blog)
        self.args = ["ensure", "--kind", "scratch", "--slug", "alpha"]

    def _state(self) -> dict:
        state = {str(p): (git_out(["branch", "-a"], p), tree_listing(p)) for p in (self.shop, self.blog)}
        state["parent"] = tree_listing(self.parent)
        return state

    def test_two_candidate_projects_are_refused_as_ambiguous(self):
        # covers: BO-4300b-3
        # angle: criterion
        """From a folder containing shop and blog: refused AMBIGUOUS_REPO naming both, exit 2."""
        res = maker(self.args, self.parent, ceiling=self.tmp)
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "refused", ans)
        self.assertEqual(ans.get("code"), "AMBIGUOUS_REPO", ans)
        text = json.dumps(ans.get("candidates"))
        self.assertIn("shop", text)
        self.assertIn("blog", text)
        self.assertEqual(res["exit_code"], 2)

    def test_ambiguous_refusal_creates_nothing_in_either_project(self):
        # covers: BO-4300b-3
        # angle: failure
        """Neither project gains a branch, a landing-place entry or a lock file."""
        before = self._state()
        res = maker(self.args, self.parent, ceiling=self.tmp)
        self.assertEqual(res["answer"].get("code"), "AMBIGUOUS_REPO", res["answer"])
        self.assertEqual(self._state(), before)
        self.assertFalse((self.parent / "shop-worktrees").exists())
        self.assertFalse((self.parent / "blog-worktrees").exists())

    def test_naming_the_project_resolves_ambiguity(self):
        # covers: BO-4300b-3
        # angle: criterion
        """The same request with --repo-root shop is answered ok with a clone of shop."""
        res = maker([*self.args, "--repo-root", str(self.shop)], self.parent, ceiling=self.tmp)
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "ok", ans)
        self.assertTrue(same(ans["repo_root"], self.shop))
        ws = Path(ans["workspace_path"])
        self.assertTrue(same(Path(ws).parent, self.parent / "shop-worktrees" / "scratch"), ans)
        self.assertTrue(same(git_out(["remote", "get-url", "origin"], ws), git_out(["remote", "get-url", "origin"], self.shop)))


if __name__ == "__main__":
    unittest.main()
