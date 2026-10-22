"""
MODULE: unit_tests/build_orchestration/test_bo_4300b_1.py
AC: BO-4300b-1 -- The same request from any folder in or around the project gives the same workspace
Real-subprocess proof against the DEPLOYED maker (real temp repos, real bare hub, no git mock).
Red baseline: worktree_layout.py, the BO-4300b resolution order and the Q5 sibling landing root
do not exist yet.

DECISION HISTORY
====================================================================
- 2026-09-30 22:00 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04,
  BO-4300b-1]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
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


_REPO = Path(__file__).resolve().parent.parent.parent
_RESOLVER_CODE = (
    "import sys, json; sys.path.insert(0, sys.argv[1]); import workspace_root as w; "
    "print(json.dumps([w.resolve(c) for c in sys.argv[2:]]))"
)


def _deployed_scripts() -> Path:
    return ensure_deployed_layout() / ".leafcutter" / "scripts"


def resolve_in_process(cwds: list[Path], ceiling: Path | None = None) -> list[dict]:
    """Call the DEPLOYED resolver module in ONE fresh process for every cwd in turn."""
    proc = subprocess.run([sys.executable, "-c", _RESOLVER_CODE, str(_deployed_scripts()), *map(str, cwds)],
                          capture_output=True, text=True, env=_env(ceiling), timeout=120)
    if proc.returncode != 0:
        raise AssertionError(f"resolver process failed: {proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])


class TestBO4300b1AnyStartingPoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="bo4300b1-")
        cls.tmp = Path(cls._tmp.name)
        cls.parent, cls.proj, _ = clean_parent(cls.tmp)
        cls.w1 = Path(maker(["ensure", "--kind", "scratch", "--slug", "alpha"], cls.proj)["answer"]["workspace_path"])
        deep = cls.proj / "sp-a" / "sp-b" / "sp-c"
        deep.mkdir(parents=True)
        sibling = cls.tmp / "parent-proj" / "sibling"
        sibling.mkdir()
        beta = maker(["ensure", "--kind", "scratch", "--slug", "beta"], cls.proj)["answer"]
        cls.beta_path = Path(beta.get("workspace_path", cls.tmp / "missing"))
        starts = {"project_top": cls.proj, "three_levels_down": deep, "parent_above": cls.parent,
                  "sibling_beside": sibling, "inside_w1": cls.w1 / "sub1", "inside_beta": cls.beta_path}
        (cls.w1 / "sub1").mkdir(exist_ok=True)
        cls.answers = {k: maker(["ensure", "--kind", "scratch", "--slug", "beta"], v)["answer"] for k, v in starts.items()}
        cls.starts = starts

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def test_beta_is_answered_ok_with_same_location_from_every_starting_point(self):
        # covers: BO-4300b-1
        # angle: criterion
        """Six starting points, one location."""
        for name, ans in self.answers.items():
            with self.subTest(start=name):
                self.assertEqual(ans.get("status"), "ok", ans)
        self.assertEqual(len({str(Path(a["workspace_path"]).resolve()) for a in self.answers.values()}), 1)

    def test_every_starting_point_resolves_the_same_project(self):
        # covers: BO-4300b-1
        # angle: criterion
        """Every answer's repo_root is proj."""
        for name, ans in self.answers.items():
            with self.subTest(start=name):
                self.assertTrue(same(ans.get("repo_root", self.parent), self.proj), ans)

    def test_beta_never_lands_inside_the_starting_folder(self):
        # covers: BO-4300b-1
        # angle: boundary
        """beta is in proj's landing place and not inside the folder the request started from."""
        for name, ans in self.answers.items():
            with self.subTest(start=name):
                ws = Path(ans["workspace_path"])
                self.assertTrue(same(ws.parent, self.parent / "proj-worktrees" / "scratch"), ws)
                start = Path(self.starts[name])
                landing = self.parent / "proj-worktrees" / "scratch"
                # A start that is an ancestor of the whole landing place (the folder above
                # the project) legitimately contains beta; any other start must not.
                if not inside(landing, start):
                    self.assertFalse(ws.resolve() != start.resolve() and inside(ws, start), ws)

    def test_resolver_and_commit_guardian_resolver_agree_on_ordinary_cases(self):
        # covers: BO-4300b-1
        # angle: seam
        """On an ordinary repository the new resolver and _resolve_root.find_project_root agree."""
        code = ("import sys; sys.path.insert(0, sys.argv[1]); "
                "from _resolve_root import find_project_root; print(find_project_root())")
        guardian = _REPO / "templates" / "scripts" / "commit_guardian"
        for start in (self.proj, self.starts["three_levels_down"]):
            old = subprocess.run([sys.executable, "-c", code, str(guardian)], cwd=str(start),
                                 capture_output=True, text=True, env=_env(), timeout=60)
            new = resolve_in_process([start])[0]
            self.assertEqual(new.get("status"), "ok", new)
            self.assertTrue(same(old.stdout.strip(), new["project_root"]), (old.stdout, old.stderr, new))


class TestBO4300b1Refusals(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300b1r-")
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def _dev_layout(self):
        parent, proj, hub = clean_parent(self.tmp)
        (parent / ".git").mkdir()
        (parent / "CLAUDE.md").write_text("# workspace parent\n", encoding="utf-8", newline="\n")
        return parent, proj, hub

    def test_workspace_parent_with_empty_git_and_claude_md_is_never_resolved_as_the_project(self):
        # covers: BO-4300b-1
        # angle: failure
        """Dev-layout parent (empty .git/ + CLAUDE.md): ok -> AMBIGUOUS_REPO -> NO_REPO, never the parent."""
        parent, proj, hub = self._dev_layout()
        args = ["ensure", "--kind", "scratch", "--slug", "p"]
        one = maker(args, parent, ceiling=self.tmp)["answer"]
        self.assertEqual(one.get("status"), "ok", one)
        self.assertTrue(same(one["repo_root"], proj))
        self.assertEqual(resolve_in_process([parent], self.tmp)[0].get("project_root") and
                         same(resolve_in_process([parent], self.tmp)[0]["project_root"], proj), True)
        other = parent / "other"
        _run_git(["clone", "-q", str(hub), str(other)], parent)
        two = maker(args, parent, ceiling=self.tmp)["answer"]
        self.assertEqual(two.get("code"), "AMBIGUOUS_REPO", two)
        self.assertIn("proj", json.dumps(two.get("candidates")))
        self.assertIn("other", json.dumps(two.get("candidates")))
        self.assertEqual(resolve_in_process([parent], self.tmp)[0].get("status"), "AMBIGUOUS_REPO")
        force_rmtree(proj)
        force_rmtree(other)
        shutil.rmtree(parent / "proj-worktrees", ignore_errors=True)
        three = maker(args, parent, ceiling=self.tmp)["answer"]
        self.assertEqual(three.get("code"), "NO_REPO", three)
        self.assertNotEqual(three.get("repo_root"), str(parent))
        res = resolve_in_process([parent], self.tmp)[0]
        self.assertEqual(res.get("status"), "NO_REPO", res)
        self.assertNotEqual(res.get("project_root"), str(parent))

    def test_resolution_never_anchors_on_the_makers_own_location(self):
        # covers: BO-4300b-1
        # angle: boundary
        """Maker deployed inside project A's install, started elsewhere: NO_REPO naming that folder."""
        _parent, proj_a, _ = clean_parent(self.tmp, "proja")
        install = proj_a / ".leafcutter" / "scripts"
        install.mkdir(parents=True)
        for src in _deployed_scripts().glob("*.py"):
            shutil.copy2(src, install / src.name)
        base = self.tmp / "elsewhere-base"
        start = base / "start"
        start.mkdir(parents=True)
        res = run_maker(["ensure", "--kind", "scratch", "--slug", "x"], cwd=start,
                        maker_path=install / "worktree.py", env=_env(base))
        ans = res["answer"]
        self.assertEqual(ans.get("code"), "NO_REPO", ans)
        self.assertTrue(same(ans.get("searched_from", ""), start), ans)
        self.assertNotIn(str(proj_a.resolve()), json.dumps(ans.get("repo_root", "")))

    def test_inside_a_workspace_the_project_comes_from_its_marker_only(self):
        # covers: BO-4300b-1
        # angle: criterion
        """Project from W1's marker; a marker pointing at a missing folder gives NO_REPO naming the marker."""
        parent, proj, _ = clean_parent(self.tmp)
        w1 = Path(maker(["ensure", "--kind", "scratch", "--slug", "w1"], proj)["answer"]["workspace_path"])
        deep = w1 / "a" / "b" / "c"
        deep.mkdir(parents=True)
        args = ["ensure", "--kind", "scratch", "--slug", "w2"]
        ok = maker(args, deep)["answer"]
        self.assertEqual(ok.get("status"), "ok", ok)
        self.assertTrue(same(ok["repo_root"], proj))
        marker = w1 / ".leafcutter" / "workspace.json"
        data = json.loads(marker.read_text(encoding="utf-8"))
        data["project_root"] = str(self.tmp / "no-such-project")
        marker.write_text(json.dumps(data), encoding="utf-8", newline="\n")
        bad = maker(["ensure", "--kind", "scratch", "--slug", "w3"], deep)["answer"]
        self.assertEqual(bad.get("code"), "NO_REPO", bad)
        self.assertIn("workspace.json", json.dumps(bad).replace("\\\\", "/"), bad)
        self.assertFalse(same(bad.get("repo_root", self.tmp), w1))

    def test_resolver_recomputes_on_every_call(self):
        # covers: BO-4300b-1
        # angle: seam
        """One process, deployed resolver called for A, B, A: no answer carried over."""
        _pa, proj_a, _ = clean_parent(self.tmp, "proja")
        _pb, proj_b, _ = clean_parent(self.tmp, "projb")
        results = resolve_in_process([proj_a, proj_b, proj_a])
        self.assertEqual([r.get("status") for r in results], ["ok"] * 3, results)
        self.assertTrue(same(results[0]["project_root"], proj_a))
        self.assertTrue(same(results[1]["project_root"], proj_b))
        self.assertTrue(same(results[2]["project_root"], proj_a))


if __name__ == "__main__":
    unittest.main()
