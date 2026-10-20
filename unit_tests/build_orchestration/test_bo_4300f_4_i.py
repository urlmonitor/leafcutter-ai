"""
MODULE: test_bo_4300f_4_i
GOAL: Red-first behavioural tests for BO-4300f-4-i -- running the workspace proof
    suite leaves the developer's own project unchanged: its registered
    workspaces, branches and version-control settings are identical afterwards,
    and nothing made by the suite is registered in, or linked from, it.

FIXTURE API (python-coder delivers it in ``_workspace_maker_fixtures.py``):
    developer_repo_snapshot(repo=None) -> dict
        Records of a repository (default: the developer's own project, REPO_ROOT):
        keys ``worktrees`` (git worktree list --porcelain), ``refs`` (git
        for-each-ref) and ``config`` (git config --local --list), each a str.
    developer_repo_references_into(folder, repo=None) -> list[str]
        Every record (worktree entry, remote, alternates file line, config value)
        of ``repo`` that points into ``folder``; ``[]`` when none does.
    developer_repo_guard(repo=None) -> context manager
        Snapshots on entry, compares on exit, raises AssertionError naming the
        changed record kind on any difference.
    The pytest session registers the same guard (plugin in pytest.ini); at the end
    of a session it prints the terminal-summary line
    ``developer-repo-guard: unchanged`` (or ``developer-repo-guard: CHANGED``
    and fails the session).

ENTRY POINT (reachability): ``python -m pytest <one test>`` run as a subprocess
    from the developer's project root with real argv; the session guard it
    registers must report on the developer repository.

Scratch "developer" repositories are built in a temp folder with an isolated git
environment, so no test here can write into the real developer repository.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:  # guarded so an absent fixture module fails each test at RUN time
    from . import _workspace_maker_fixtures as _fixtures
    from ._bo4300b1_helpers import bounded_env
    from ._bo4300a1_helpers import git_ok
    _FIXTURES_IMPORT_ERROR = None
except ImportError as _exc:
    _fixtures = None
    _FIXTURES_IMPORT_ERROR = _exc

REPO_ROOT = Path(__file__).resolve().parents[2]


def _fx():
    assert _fixtures is not None, (
        f"fixture module not importable: {_FIXTURES_IMPORT_ERROR!r}")
    return _fixtures


def _tmp(testcase: unittest.TestCase) -> Path:
    holder = tempfile.TemporaryDirectory(prefix="bo4300f4i_")
    testcase.addCleanup(holder.cleanup)
    return Path(holder.name).resolve()


def _scratch_developer_repo(tmp: Path) -> tuple[Path, dict]:
    """A real repository standing in for the developer's project, isolated config."""
    env = bounded_env(tmp)
    repo = tmp / "developer"
    repo.mkdir()
    git_ok(repo, env, "init", "-b", "main")
    (repo / "README.md").write_text("developer project\n", encoding="utf-8")
    git_ok(repo, env, "add", "-A")
    git_ok(repo, env, "commit", "-m", "init")
    return repo, env


class TestBo4300f4i(unittest.TestCase):
    maxDiff = None

    def test_developer_repo_registrations_branches_and_config_unchanged_by_suite(self):
        # covers: BO-4300f-4-i
        # angle: boundary
        """AC-1: before/after snapshots of the developer repository are identical."""
        fx = _fx()
        tmp = _tmp(self)
        before = fx.developer_repo_snapshot()
        # boundary: each of the three record kinds is really captured (not empty)
        self.assertEqual(set(before), {"worktrees", "refs", "config"})
        self.assertIn(str(REPO_ROOT), before["worktrees"])
        self.assertTrue(before["refs"].strip(), "no branches recorded")
        self.assertTrue(before["config"].strip(), "no local settings recorded")
        # a real mini proof: project, hub, maker run and a legacy worktree
        proj = fx.make_project(tmp, layout="dev")
        fx.legacy_worktree(proj, "legacy-one")
        got = fx.run_maker(["ensure", "--kind", "feature", "--slug", "beta"], cwd=proj["project"])
        self.assertEqual(got["answer"].get("status"), "ok", got["answer"])
        self.assertEqual(fx.developer_repo_snapshot(), before)
        # discrimination: a suite that leaked a worktree / branch / setting is caught
        repo, env = _scratch_developer_repo(tmp)
        clean = fx.developer_repo_snapshot(repo)
        git_ok(repo, env, "worktree", "add", "-b", "leak", str(tmp / "leaked"), "main")
        leaked = fx.developer_repo_snapshot(repo)
        self.assertNotEqual(leaked["worktrees"], clean["worktrees"])
        self.assertNotEqual(leaked["refs"], clean["refs"])
        git_ok(repo, env, "config", "--local", "user.email", "fixture@example.invalid")
        self.assertNotEqual(fx.developer_repo_snapshot(repo)["config"], clean["config"])
        with self.assertRaises(AssertionError):
            with fx.developer_repo_guard(repo):
                git_ok(repo, env, "branch", "stray")
        with fx.developer_repo_guard(repo):  # control row: no change passes
            pass

    def test_no_temporary_project_is_registered_in_or_linked_from_developer_repo(self):
        # covers: BO-4300f-4-i
        # angle: criterion
        """AC-2: nothing in the developer repository points into the suite's temp folder."""
        fx = _fx()
        tmp = _tmp(self)
        proj = fx.make_project(tmp, layout="dev")
        fx.legacy_worktree(proj, "legacy-two")
        fx.run_maker(["ensure", "--kind", "feature", "--slug", "gamma"], cwd=proj["project"])
        self.assertEqual(fx.developer_repo_references_into(tmp), [])
        # control row / discrimination: a scratch repo linked into tmp is reported
        repo, env = _scratch_developer_repo(tmp)
        folder = tmp / "elsewhere"
        folder.mkdir()
        self.assertEqual(fx.developer_repo_references_into(folder, repo), [])
        git_ok(repo, env, "worktree", "add", "-b", "linked", str(folder / "wt"), "main")
        git_ok(repo, env, "remote", "add", "hub", str(folder / "hub.git"))
        (repo / ".git" / "objects" / "info" / "alternates").write_text(
            str(folder / "objects") + "\n", encoding="utf-8")
        found = fx.developer_repo_references_into(folder, repo)
        self.assertGreaterEqual(len(found), 3, found)
        for kind in ("wt", "hub.git", "objects"):
            self.assertTrue(any(kind in item for item in found), (kind, found))

    def test_bo_4300f_4_i_reachable_from_entry_point(self):
        # covers: BO-4300f-4-i
        # angle: reachability
        """A real pytest session from the project root runs the guard and reports it."""
        _fx()
        done = subprocess.run(  # noqa: S603
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider",
             "unit_tests/build_orchestration/test_bo4500a_1_iv_path_validation.py"
             "::TestNamedPathValidation"
             "::test_never_existed_path_is_refused_not_nothing_to_commit"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600, check=False)
        output = done.stdout + done.stderr
        self.assertIn("developer-repo-guard: unchanged", output, output[-1500:])
        self.assertNotIn("developer-repo-guard: CHANGED", output)
        self.assertEqual(done.returncode, 0, output[-1500:])
