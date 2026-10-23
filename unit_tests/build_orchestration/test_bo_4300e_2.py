"""
MODULE: unit_tests/build_orchestration/test_bo_4300e_2.py
AC: BO-4300e-2 -- Clearing a workspace answers at once and never waits for someone to say yes.

Given an unattended run asks the workspace maker to clear "alpha" (nothing unsent) and "beta"
(one unpushed commit, one uncommitted change, no authorisation to lose work), each request ends
with an answer without waiting for any input, "alpha" is gone completely, "beta" is refused naming
the unpushed commit by identifier and the uncommitted file by path, and "beta" is unchanged.

Real-subprocess proof against the DEPLOYED maker (`worktree.py remove`, resolved through the
shared locator), real temp repos, real bare hub, no mock of git, no import of the maker module,
never a build.py spawn of its own. Fixture writes pin newline="\\n"; git runs with the isolated
HOME / GIT_CONFIG_GLOBAL / GIT_CONFIG_NOSYSTEM of the shared builders.

SHARED HELPERS: the ticket's files_touched lists no separate helper module, so the helpers of this
ticket's sibling modules (test_bo_4300e_1, _1_i, _2_i, _2_ii, _3, _3_i) live here and the siblings
import the FUNCTIONS and the base class only (the ticket-07 precedent in test_bo_4300d_1.py).

FIXTURE NOTE ("nothing unsent"): the stub install writes INSTALLED_MARKER.txt and the maker writes
<ws>/.leafcutter/ (untracked). They are maker/install artifacts, not the work's; the helper lists
them in the workspace's own .git/info/exclude so "alpha holds nothing unsent" is literally true.

DECISION HISTORY
====================================================================
- 2026-10-12 16:30 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08,
  BO-4300e-2]: Created the red baseline. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
====================================================================
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from unit_tests.build_orchestration._workspace_maker_fixtures import deployed_maker_path, make_project
from unit_tests.build_orchestration._workspace_maker_builders import _isolated_git_env, _run_git

KIND = "feature"
INSTALL_ARTIFACTS = (".leafcutter/", "INSTALLED_MARKER.txt")


def _force_rmtree(path: Path) -> None:
    def _chmod(func, target, _exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)

    shutil.rmtree(path, onerror=_chmod)


def parse_answer(stdout: str) -> dict[str, Any]:
    """The one JSON object on stdout (empty dict when there is none)."""
    objs = []
    for line in stdout.splitlines():
        try:
            objs.append(json.loads(line))
        except ValueError:
            continue
    return objs[0] if len(objs) == 1 and isinstance(objs[0], dict) else {}


def shas_name(commits: list[str], sha: str) -> bool:
    """True when some listed commit identifier names *sha* (full or abbreviated, >= 7 chars)."""
    return any(len(c) >= 7 and sha.startswith(c) for c in commits)


def names_file(files: list[str], name: str) -> bool:
    """True when some listed path names the file *name* (any separator spelling)."""
    return any(f.replace("\\", "/").split("/")[-1] == name for f in files)


class WorkspaceCase(unittest.TestCase):
    """Real project + hub + isolated HOME per test, and the helpers every sibling uses."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="bo4300e-")).resolve()
        self.addCleanup(_force_rmtree, self.tmp)
        self.home = self.tmp / "home"
        self.home.mkdir()
        shutil.copyfile(_isolated_git_env()["GIT_CONFIG_GLOBAL"], self.home / ".gitconfig")
        self.fx = make_project(self.tmp / "world")
        self.project: Path = self.fx["project"]
        self.hub: Path = self.fx["hub"]
        self.landing: Path = self.fx["landing_place"]

    # ---------------------------------------------------------------- running
    def env(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        env = _isolated_git_env()
        env.update(HOME=str(self.home), USERPROFILE=str(self.home),
                   GIT_CONFIG_GLOBAL=str(self.home / ".gitconfig"))
        env.update(extra or {})
        return env

    def cli(self, args: list[str], cwd: Path | None = None, extra_env: dict[str, str] | None = None,
            stdin: str = "devnull", timeout: int = 90) -> dict[str, Any]:
        """Run the DEPLOYED maker as a real process; never lets it wait on input (stdin closed, or an
        open pipe nobody writes to). A hang past *timeout* is a failure, not a skip."""
        cmd = [sys.executable, str(deployed_maker_path()), *args]
        proc = subprocess.Popen(cmd, cwd=str(cwd or self.project), env=self.env(extra_env),
                                stdin=subprocess.DEVNULL if stdin == "devnull" else subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            self.fail(f"the maker did not answer within {timeout}s (waiting for input?): {args}")
        return {"answer": parse_answer(out), "exit_code": proc.returncode, "stdout": out, "stderr": err}

    def ensure(self, slug: str, extra_env: dict[str, str] | None = None) -> Path:
        res = self.cli(["ensure", "--kind", KIND, "--slug", slug, "--repo-root", str(self.project)],
                       extra_env=extra_env)
        if extra_env is None:
            self.assertEqual(res["answer"].get("status"), "ok", msg=f"fixture ensure failed: {res}")
            ws = Path(res["answer"]["workspace_path"])
            with open(ws / ".git" / "info" / "exclude", "a", encoding="utf-8", newline="\n") as fh:
                fh.write("\n".join(INSTALL_ARTIFACTS) + "\n")
            return ws
        return self.landing / KIND / slug

    def remove(self, ws: Path, token: str | None = None, **kw: Any) -> dict[str, Any]:
        args = ["remove", "--path", str(ws)] + (["--discard-token", token] if token else [])
        return self.cli(args, **kw)

    # ----------------------------------------------------------------- state
    def git(self, args: list[str], cwd: Path) -> str:
        return _run_git(args, cwd).stdout.strip()

    def commit_unsent(self, ws: Path, name: str, text: str = "unsent\n") -> str:
        (ws / name).write_text(text, encoding="utf-8", newline="\n")
        self.git(["add", name], ws)
        self.git(["commit", "-q", "-m", f"unsent {name}"], ws)
        return self.git(["rev-parse", "HEAD"], ws)

    def dirty(self, ws: Path, name: str, text: str = "uncommitted\n") -> None:
        (ws / name).write_text(text, encoding="utf-8", newline="\n")

    @staticmethod
    def snap(ws: Path, with_git: bool = False) -> dict[str, str]:
        """sha256 of every file under *ws* (the maker's marker included); .git only when asked."""
        out: dict[str, str] = {}
        for p in sorted(ws.rglob("*")):
            rel = p.relative_to(ws)
            if p.is_file() and (with_git or ".git" not in rel.parts):
                out[rel.as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
        return out

    def refs(self, ws: Path) -> str:
        return self.git(["for-each-ref", "--format=%(refname) %(objectname)"], ws)

    def make_unsent(self, slug: str, tag: str) -> tuple[Path, str]:
        """A ready workspace holding one unpushed commit and one uncommitted file."""
        ws = self.ensure(slug)
        sha = self.commit_unsent(ws, f"commit-{tag}.txt", f"unpushed {tag}\n")
        self.dirty(ws, f"dirty-{tag}.txt", f"uncommitted {tag}\n")
        return ws, sha

    def refuse(self, ws: Path, token: str | None = None) -> dict[str, Any]:
        res = self.remove(ws, token)
        self.assertEqual(res["answer"].get("code"), "UNSENT_WORK", msg=f"expected a refusal: {res}")
        self.assertEqual(res["exit_code"], 2, msg=f"{res}")
        return res["answer"]


class TestRemoveAnswersAtOnce(WorkspaceCase):
    def _alpha_and_beta(self) -> tuple[Path, Path, str]:
        alpha = self.ensure("alpha")
        beta, sha = self.make_unsent("beta", "b")
        return alpha, beta, sha

    def test_remove_answers_without_waiting_for_input(self):
        # covers: BO-4300e-2
        # angle: failure
        """AC-5: both requests end with an answer while stdin is an open pipe nobody writes to; a
        maker that prompts (or reads stdin) hangs past the timeout. Must be implemented: remove
        never reads stdin."""
        alpha, beta, _sha = self._alpha_and_beta()
        res_alpha = self.remove(alpha, stdin="open", timeout=40)
        res_beta = self.remove(beta, stdin="open", timeout=40)
        self.assertEqual(res_alpha["answer"].get("status"), "ok", msg=f"{res_alpha}")
        self.assertEqual(res_beta["answer"].get("code"), "UNSENT_WORK", msg=f"{res_beta}")

    def test_clean_workspace_is_removed_completely(self):
        # covers: BO-4300e-2
        # angle: criterion
        """AC-5: alpha's folder no longer exists and the answer is ok with removed_path."""
        alpha, _beta, _sha = self._alpha_and_beta()
        res = self.remove(alpha)
        self.assertEqual(res["answer"].get("status"), "ok", msg=f"{res}")
        self.assertEqual(res["exit_code"], 0)
        self.assertIn("removed_path", res["answer"], msg=f"{res}")
        self.assertEqual(os.path.normcase(res["answer"]["removed_path"]), os.path.normcase(str(alpha)))
        self.assertFalse(alpha.exists(), msg=f"{alpha} still exists after an ok answer")
        self.assertFalse(os.path.lexists(alpha))

    def test_workspace_with_unsent_work_is_refused_naming_commit_and_file(self):
        # covers: BO-4300e-2
        # angle: criterion
        """AC-5: beta is refused UNSENT_WORK; unsent.commits holds exactly the unpushed sha and
        unsent.files exactly the uncommitted path."""
        _alpha, beta, sha = self._alpha_and_beta()
        answer = self.refuse(beta)
        unsent = answer.get("unsent") or {}
        self.assertEqual(len(unsent.get("commits", [])), 1, msg=f"{answer}")
        self.assertTrue(shas_name(unsent["commits"], sha), msg=f"{sha} not in {unsent}")
        self.assertEqual(len(unsent.get("files", [])), 1, msg=f"{answer}")
        self.assertTrue(names_file(unsent["files"], "dirty-b.txt"), msg=f"{unsent}")

    def test_refused_workspace_is_unchanged(self):
        # covers: BO-4300e-2
        # angle: boundary
        """AC-5: beta's files (marker included) and commits are identical before and after; the
        control (alpha) really is removed in the same run, so 'unchanged' is not 'nothing ran'."""
        alpha, beta, _sha = self._alpha_and_beta()
        files_before, heads_before = self.snap(beta), self.refs(beta)
        self.assertTrue(files_before)
        self.refuse(beta)
        self.assertEqual(self.remove(alpha)["answer"].get("status"), "ok")
        self.assertFalse(alpha.exists())
        self.assertEqual(self.snap(beta), files_before)
        self.assertEqual(self.refs(beta), heads_before)


if __name__ == "__main__":
    unittest.main()
