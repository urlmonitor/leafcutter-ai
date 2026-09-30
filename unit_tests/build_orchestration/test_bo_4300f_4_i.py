"""
MODULE: unit_tests/build_orchestration/test_bo_4300f_4_i.py
AC: BO-4300f-4-i -- "Running the proof leaves the developer's own project
    unchanged" (L3, child of BO-4300f-4).
TICKET: tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/
    02_TICKET-20260928-BO-4300-deployed-maker-test-support.md

WHAT THIS PROVES
====================================================================
The session-level developer-repo guard (unit_tests/build_orchestration/
_developer_repo_guard.py, wired into unit_tests/build_orchestration/
conftest.py per ADR-051) snapshots a developer repository's registered
worktrees, refs/branches and local git config before the whole workspace
proof suite runs and compares after; ANY difference fails the session
(BO-4300f-4-i's own wording -- no root-prefix filtering, per ADR-051
decision 2). This module proves that mechanism at three levels:

- test_developer_repo_registrations_branches_and_config_unchanged_by_suite
  (angle: boundary) -- the snapshot/diff empty-vs-one-change boundary:
  diff_snapshots(x, x) is empty, and one real registered worktree added
  between snapshots makes it non-empty and names the change.
- test_no_temporary_project_is_registered_in_or_linked_from_developer_repo
  (angle: criterion) -- runs the shared fixture module's own project
  builder INSIDE a throwaway real developer-repo stand-in's neighbourhood,
  wrapped by the guard, and asserts no worktree/remote/alternates/config
  entry in that repo ever points into the suite's own temp directory.
- test_ticket_02_reachable_from_entry_point (angle: reachability) -- the
  REAL entry point: `python -m pytest` as a subprocess against an isolated
  fixture "developer repo" wired to the real guard module via a real
  conftest.py, running one deliberately-leaking dummy test underneath it,
  and asserts the pytest process itself fails, naming the leak -- never a
  direct call to a guard function.

None of these three tests touch the ACTUAL checkout this agent session is
running in -- each builds its own real, throwaway git repository to stand
in for "the developer's own project" (BO-4300f-4-i's Given clause names
the role generically; the mechanism under test is repo-root-parametrized,
never hardcoded to cwd). Wiring the guard to the REAL checkout is
conftest.py's job (python-coder, ADR-051), not this module's.

DEPENDS ON (not yet built -- expected RED state, see class docstrings):
- unit_tests/build_orchestration/_developer_repo_guard.py (this ticket)
- unit_tests/build_orchestration/_workspace_maker_fixtures.py (this ticket)

CONTRACT ASSUMPTIONS this file is written against (python-coder's job to
satisfy, not to reinterpret without a test-repair pass -- see the
Source-of-Truth Discipline in this file's own governing skill):
- snapshot_developer_repo(repo_root: Path) -> a snapshot object exposing
  at least `.worktrees` (str), `.refs` (str), `.config` (str) attributes,
  each the raw output of `git worktree list --porcelain`,
  `git for-each-ref`, `git config --local --list` respectively.
- diff_snapshots(before, after) -> list[str], empty when identical, one
  entry per real difference, each entry naming what changed.
- developer_repo_guard(repo_root, lock_timeout_s=None) -> a context
  manager: acquires ADR-051's session-exclusive advisory lock, snapshots
  on entry, snapshots and raises DeveloperRepoChangedError on exit if the
  two differ.

DECISION HISTORY
====================================================================
- 2026-09-28 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02,
  BO-4300f-4-i / BO-4300f-4]: Initial red test stubs written against the
  guard/fixture contract this ticket's own Implementation Notes and
  ADR-051 specify. Neither _developer_repo_guard.py nor
  _workspace_maker_fixtures.py exist yet -- ModuleNotFoundError is the
  expected RED state until python-coder builds them.
====================================================================
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from unit_tests.build_orchestration._bo_4300a_1_fixtures import run_git
from unit_tests.build_orchestration._developer_repo_guard import (
    diff_snapshots,
    snapshot_developer_repo,
)
from unit_tests.build_orchestration._workspace_maker_fixtures import make_project

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _make_stand_in_dev_repo(path: Path) -> Path:
    """A real, throwaway git repo standing in for "the developer's own
    project" -- never the actual checkout this test module runs inside."""
    path.mkdir(parents=True, exist_ok=True)
    run_git(["-c", "init.defaultBranch=main", "init", "-q"], path)
    run_git(["config", "user.email", "devrepo@example.com"], path)
    run_git(["config", "user.name", "Dev Repo"], path)
    (path / "README.md").write_text("stand-in developer project\n", encoding="utf-8")
    run_git(["add", "-A"], path)
    run_git(["commit", "-q", "-m", "initial"], path)
    return path


class TestGuardSnapshotDiffBoundary(unittest.TestCase):
    """angle: boundary -- diff_snapshots' empty/one-change edge."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300f4i-devrepo-")
        self.tmp_path = Path(self._tmp.name)
        self.dev_repo = _make_stand_in_dev_repo(self.tmp_path / "devrepo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_developer_repo_registrations_branches_and_config_unchanged_by_suite(self):
        # covers: BO-4300f-4-i
        # angle: boundary
        """MUST BE IMPLEMENTED: snapshot_developer_repo(repo_root) captures
        `git worktree list --porcelain`, `git for-each-ref`, and
        `git config --local --list`; diff_snapshots(before, after) is an
        empty list when nothing changed (the zero-diff boundary) and a
        non-empty list naming the change when exactly one real worktree is
        registered between the two snapshots (the one-diff boundary)."""
        before = snapshot_developer_repo(self.dev_repo)
        after_unchanged = snapshot_developer_repo(self.dev_repo)
        self.assertEqual(
            diff_snapshots(before, after_unchanged), [],
            msg="two snapshots of an untouched repo must diff to an empty list",
        )

        extra_worktree = self.tmp_path / "extra-worktree"
        run_git(["branch", "extra-branch"], self.dev_repo)
        run_git(["worktree", "add", str(extra_worktree), "extra-branch"], self.dev_repo)
        try:
            after_changed = snapshot_developer_repo(self.dev_repo)
            diff = diff_snapshots(before, after_changed)
            self.assertNotEqual(diff, [], msg="a real registered worktree must be detected as a diff")
            self.assertTrue(
                any("extra-worktree" in str(entry) or "extra-branch" in str(entry) for entry in diff),
                msg=f"diff does not name the change: {diff}",
            )
        finally:
            run_git(["worktree", "remove", "--force", str(extra_worktree)], self.dev_repo, check=False)


class TestNoTemporaryProjectLeaksIntoDeveloperRepo(unittest.TestCase):
    """angle: criterion -- BO-4300f-4-i's Then-clause on the guard
    directly: no worktree entry, remote, alternates file or config value in
    the developer repository points into the suite's own temp directory."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="bo4300f4i-criterion-")
        self.tmp_path = Path(self._tmp.name)
        self.dev_repo = _make_stand_in_dev_repo(self.tmp_path / "devrepo")
        self.suite_tmp = self.tmp_path / "suite-scratch"
        self.suite_tmp.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_no_temporary_project_is_registered_in_or_linked_from_developer_repo(self):
        # covers: BO-4300f-4-i
        # angle: criterion
        """MUST BE IMPLEMENTED: running the shared fixture module's own
        project builder inside self.suite_tmp (standing in for a full
        proof-suite run's temp projects/workspaces) must never register a
        worktree, remote, alternates file, or config value in
        self.dev_repo that points into self.suite_tmp."""
        before = snapshot_developer_repo(self.dev_repo)

        made = make_project(self.suite_tmp, layout="dev")
        project = Path(made["project"])
        self.assertTrue(project.exists(), msg=f"make_project did not create {project}")

        after = snapshot_developer_repo(self.dev_repo)
        diff = diff_snapshots(before, after)
        self.assertEqual(
            diff, [],
            msg=f"developer repo snapshot changed after an unrelated suite fixture ran elsewhere: {diff}",
        )

        suite_tmp_str = str(self.suite_tmp)
        self.assertNotIn(
            suite_tmp_str, after.worktrees,
            msg="developer repo worktree list references the suite's own temp dir",
        )
        self.assertNotIn(
            suite_tmp_str, after.config,
            msg="developer repo local config references the suite's own temp dir",
        )
        alternates = self.dev_repo / ".git" / "objects" / "info" / "alternates"
        if alternates.exists():
            self.assertNotIn(
                suite_tmp_str, alternates.read_text(encoding="utf-8"),
                msg="developer repo objects/info/alternates references the suite's own temp dir",
            )


class TestSuiteReachableFromRealEntryPoint(unittest.TestCase):
    """angle: reachability -- invokes `python -m pytest` as a real
    subprocess (the production entry point for "the whole workspace proof
    suite [that] runs from inside that project", per BO-4300f-4-i's own
    When-clause), never a direct call to a guard function."""

    def test_ticket_02_reachable_from_entry_point(self):
        # covers: BO-4300f-4
        # angle: reachability
        """surface_invoked: python -m pytest <isolated suite dir> (the
        whole workspace proof suite, as a subprocess inside an isolated
        fixture repo, with a deliberately leaking test).

        MUST BE IMPLEMENTED: an isolated fixture "developer repo" wired to
        the REAL _developer_repo_guard module (via a real conftest.py
        placed next to a deliberately-leaking dummy test) must fail the
        `python -m pytest` subprocess run against it, naming the leak --
        proving the guard is actually wired into pytest's own collection
        and session teardown, not merely importable.
        """
        with tempfile.TemporaryDirectory(prefix="bo4300f4i-reachability-") as tmp:
            tmp_path = Path(tmp)
            dev_repo = _make_stand_in_dev_repo(tmp_path / "devrepo")

            suite_dir = dev_repo / "suite"
            suite_dir.mkdir()
            (suite_dir / "__init__.py").write_text("", encoding="utf-8")
            (suite_dir / "conftest.py").write_text(
                textwrap.dedent(
                    f"""
                    import sys
                    from pathlib import Path
                    sys.path.insert(0, {str(REPO_ROOT)!r})
                    from unit_tests.build_orchestration._developer_repo_guard import (
                        developer_repo_guard,
                    )
                    import pytest

                    @pytest.fixture(scope="session", autouse=True)
                    def _bo4300_devrepo_guard():
                        with developer_repo_guard(Path({str(dev_repo)!r})):
                            yield
                    """
                ),
                encoding="utf-8",
            )
            leaked_worktree = tmp_path / "leaked-worktree"
            (suite_dir / "test_leaky.py").write_text(
                textwrap.dedent(
                    f"""
                    import subprocess

                    def test_deliberately_leaks_a_worktree():
                        subprocess.run(
                            ["git", "branch", "leaked-branch"],
                            cwd={str(dev_repo)!r}, check=True,
                        )
                        subprocess.run(
                            ["git", "worktree", "add", {str(leaked_worktree)!r}, "leaked-branch"],
                            cwd={str(dev_repo)!r}, check=True,
                        )
                        assert True
                    """
                ),
                encoding="utf-8",
            )

            proc = subprocess.run(
                [sys.executable, "-m", "pytest", str(suite_dir), "-p", "no:cacheprovider"],
                cwd=str(dev_repo),
                capture_output=True,
                text=True,
                timeout=60,
            )

            self.assertNotEqual(
                proc.returncode, 0,
                msg=(
                    "the real pytest subprocess run must fail when a test leaks a "
                    f"worktree into the developer repo. stdout={proc.stdout!r} "
                    f"stderr={proc.stderr!r}"
                ),
            )
            combined = (proc.stdout + proc.stderr).lower()
            self.assertTrue(
                "leaked" in combined or "developerrepochangederror" in combined,
                msg=f"failure output does not name the leak: {proc.stdout!r} {proc.stderr!r}",
            )


if __name__ == "__main__":
    unittest.main()
