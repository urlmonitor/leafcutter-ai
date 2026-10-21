"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_2_ii.py
AC: BO-4300b-2-ii -- An out-of-date installed copy inside the project does not change which project is found
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: worktree_layout.py, the BO-4300b resolution order and the Q5 sibling landing root
do not exist yet.

DECISION HISTORY
====================================================================
- 2026-09-30 22:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04,
  BO-4300b-2-ii]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
====================================================================
"""
from __future__ import annotations

import os
import shutil
import stat
import tempfile
import unittest
from pathlib import Path

from unit_tests.build_orchestration._workspace_maker_fixtures import (  # fixtures first: avoids the builders cycle
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



class TestBO4300b2ii(unittest.TestCase):
    MARKER = "STALE-INNER-COPY-MARKER-4300b2ii"

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b2ii-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        # dev layout: package project "pkg" inside a parent holding the CURRENT install;
        # pkg itself carries an out-of-date gitignored inner install.
        self.parent, self.pkg, _ = clean_parent(self.tmp, "pkg")
        stale = self.pkg / ".leafcutter" / "scripts"
        stale.mkdir(parents=True)
        (stale / "worktree.py").write_text(f"# {self.MARKER}\nraise SystemExit(99)\n", encoding="utf-8", newline="\n")
        (self.pkg / ".leafcutter" / "stale_marker.txt").write_text(self.MARKER, encoding="utf-8", newline="\n")
        (self.parent / ".leafcutter" / "scripts").mkdir(parents=True)
        self.w = maker(["ensure", "--kind", "scratch", "--slug", "alpha"], self.pkg)["answer"]

    def test_stale_inner_install_does_not_change_the_project_found(self):
        # covers: BO-4300b-2-ii
        # covers: BO-4100d-4
        # angle: criterion
        """Requests from the parent, pkg's top folder and inside a workspace agree on project and location."""
        self.assertEqual(self.w.get("status"), "ok", self.w)
        ws = Path(self.w["workspace_path"])
        answers = [maker(["ensure", "--kind", "scratch", "--slug", "alpha"], start)["answer"]
                   for start in (self.parent, self.pkg, ws)]
        for ans in answers:
            self.assertEqual(ans.get("status"), "ok", ans)
            self.assertTrue(same(ans["repo_root"], self.pkg), ans)
            self.assertTrue(same(ans["workspace_path"], ws), ans)

    def test_workspace_install_is_built_from_its_own_contents(self):
        # covers: BO-4300b-2-ii
        # angle: real_artifact
        """The workspace's install output carries the workspace's own stamp; nothing from the stale copy."""
        self.assertEqual(self.w.get("status"), "ok", self.w)
        ws = Path(self.w["workspace_path"])
        self.assertTrue(same(Path(ws).parent, self.parent / "pkg-worktrees" / "scratch"), self.w)
        stamp = (ws / "BUILD_STAMP.txt").read_text(encoding="utf-8").strip()
        installed = (ws / "INSTALLED_MARKER.txt").read_text(encoding="utf-8")
        self.assertIn(stamp, installed)
        self.assertFalse((ws / ".leafcutter" / "stale_marker.txt").exists())
        for path in ws.rglob("*"):
            if ".git" in path.relative_to(ws).parts or not path.is_file():
                continue
            self.assertNotIn(self.MARKER.encode(), path.read_bytes(), path)


if __name__ == "__main__":
    unittest.main()
