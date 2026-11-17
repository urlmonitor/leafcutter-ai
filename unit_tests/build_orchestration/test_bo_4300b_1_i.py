"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_1_i.py
AC: BO-4300b-1-i -- Starting inside another workspace never nests the new one there or roots it on that work
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: worktree_layout.py, the BO-4300b resolution order and the Q5 sibling landing root
do not exist yet.

DECISION HISTORY
====================================================================
- 2026-09-30 22:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04,
  BO-4300b-1-i]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
====================================================================
"""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
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



def _snapshot(ws: Path) -> dict:
    return {
        "head": git_out(["rev-parse", "HEAD"], ws),
        "branch": git_out(["rev-parse", "--abbrev-ref", "HEAD"], ws),
        "status": git_out(["status", "--porcelain"], ws),
        "readme": (ws / "README.md").read_bytes(),
    }


class TestBO4300b1i(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b1i-")
        self.addCleanup(self._tmp.cleanup)
        self.parent, self.proj, self.hub = clean_parent(Path(self._tmp.name))
        self.w1_ans = maker(["ensure", "--kind", "scratch", "--slug", "w1"], self.proj)["answer"]
        self.w1 = Path(self.w1_ans["workspace_path"])
        _configure_identity(self.w1)
        (self.w1 / "W1_ONLY.txt").write_text("w1 only\n", encoding="utf-8", newline="\n")
        _run_git(["add", "-A"], self.w1)
        _run_git(["commit", "-q", "--no-verify", "-m", "w1 extra commit"], self.w1)
        self.w1_commit = git_out(["rev-parse", "HEAD"], self.w1)
        with open(self.w1 / "README.md", "ab") as fh:
            fh.write(b"uncommitted change\n")
        self.before = _snapshot(self.w1)
        start = self.w1 / "sp-a"
        start.mkdir(exist_ok=True)
        self.res = maker(["ensure", "--kind", "scratch", "--slug", "beta"], start)
        self.beta = self.res["answer"]

    def test_request_from_inside_w1_places_beta_beside_w1(self):
        # covers: BO-4300b-1-i
        # angle: criterion
        """beta lands in the landing place beside W1, never inside W1."""
        self.assertEqual(self.beta.get("status"), "ok", self.beta)
        beta_path = Path(self.beta["workspace_path"])
        self.assertFalse(inside(beta_path, self.w1))
        self.assertTrue(same(Path(beta_path).parent, self.parent / "proj-worktrees" / "scratch"), beta_path)
        self.assertTrue(same(beta_path.parent, self.w1.parent))

    def test_beta_starts_at_hub_main_and_w1_commit_is_unreachable(self):
        # covers: BO-4300b-1-i
        # angle: criterion
        """beta's base is the hub main tip; W1's extra commit is not an ancestor of beta HEAD."""
        self.assertEqual(self.beta.get("status"), "ok", self.beta)
        hub_main = git_out(["rev-parse", "main"], self.hub)
        self.assertEqual(self.beta["base_commit"], hub_main)
        beta_path = Path(self.beta["workspace_path"])
        rc = subprocess.run(["git", "merge-base", "--is-ancestor", self.w1_commit, "HEAD"],
                            cwd=str(beta_path), capture_output=True, env=_env()).returncode
        # 1 = object known but not an ancestor; 128 = object absent from beta entirely.
        self.assertIn(rc, (1, 128), "W1 commit must not be reachable from beta")

    def test_w1_is_byte_identical_after_the_request(self):
        # covers: BO-4300b-1-i
        # angle: boundary
        """W1's files, uncommitted change and branch ref are unchanged by the request."""
        self.assertEqual(self.beta.get("status"), "ok", self.beta)
        self.assertTrue(same(Path(self.beta["workspace_path"]).parent, self.parent / "proj-worktrees" / "scratch"), self.beta)
        after = _snapshot(self.w1)
        after["status"] = "\n".join(line for line in after["status"].splitlines() if "sp-a" not in line)
        before = dict(self.before)
        before["status"] = "\n".join(line for line in before["status"].splitlines() if "sp-a" not in line)
        self.assertEqual(after, before)

    def test_ticket_04_reachable_from_entry_point(self):
        # covers: BO-4300b-1
        # angle: reachability
        """CLI via subprocess from each starting folder answers ok and the workspace really exists."""
        deep = self.proj / "a" / "b" / "c"
        deep.mkdir(parents=True)
        paths = set()
        for start in [self.proj, deep, self.parent, self.w1]:
            res = maker(["ensure", "--kind", "scratch", "--slug", "reach"], start)
            ans = res["answer"]
            self.assertEqual(ans.get("status"), "ok", (start, ans))
            self.assertEqual(res["exit_code"], 0)
            ws = Path(ans["workspace_path"])
            self.assertTrue((ws / ".leafcutter" / "workspace.json").is_file())
            self.assertTrue(same(git_out(["rev-parse", "--show-toplevel"], ws), ws))
            paths.add(str(ws.resolve()))
        self.assertEqual(len(paths), 1)


if __name__ == "__main__":
    unittest.main()
