"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_3_i.py
AC: BO-4300b-3-i -- Started where no project can be found, the request is refused and says where it looked
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: worktree_layout.py, the BO-4300b resolution order and the Q5 sibling landing root
do not exist yet.

DECISION HISTORY
====================================================================
- 2026-09-30 22:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04,
  BO-4300b-3-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
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



class TestBO4300b3i(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b3i-")
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name) / "base"
        self.empty = self.base / "empty"
        self.empty.mkdir(parents=True)

    def test_request_from_empty_folder_is_refused_no_repo_naming_the_folder(self):
        # covers: BO-4300b-3-i
        # covers: BO-4100d-4
        # angle: criterion
        """Refused NO_REPO, searched_from is the start folder, exit 2."""
        res = maker(["ensure", "--kind", "scratch", "--slug", "x"], self.empty, ceiling=self.base)
        ans = res["answer"]
        self.assertEqual(ans.get("status"), "refused", ans)
        self.assertEqual(ans.get("code"), "NO_REPO", ans)
        self.assertTrue(same(ans.get("searched_from", ""), self.empty), ans)
        self.assertEqual(res["exit_code"], 2)

    def test_no_repo_refusal_leaves_folder_and_neighbours_unchanged(self):
        # covers: BO-4300b-3-i
        # angle: failure
        """A recursive listing of the folder and its parent is identical before and after."""
        before = (tree_listing(self.base), tree_listing(self.base.parent))
        res = maker(["ensure", "--kind", "scratch", "--slug", "x"], self.empty, ceiling=self.base)
        self.assertEqual((res["answer"].get("status"), res["answer"].get("code")), ("refused", "NO_REPO"), res["answer"])
        self.assertEqual((tree_listing(self.base), tree_listing(self.base.parent)), before)


if __name__ == "__main__":
    unittest.main()
