"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_review_fixes.py
AC: BO-4300c-1 / BO-4300c-1-iii -- pr-reviewer fixes H-2, M-1, M-2, M-3 in worktree_readiness.
Real git repositories in temp dirs; git itself is never mocked.

DECISION HISTORY
====================================================================
- 2026-10-01 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: Created the
  review-fix regression tests. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
====================================================================
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "templates" / "scripts"))

import worktree_canaries as wc  # noqa: E402
import worktree_readiness as wr  # noqa: E402


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def _make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "feature")
    _git(repo, "config", "user.name", "t")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "a.txt").write_text("committed\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "a.txt")
    assert _git(repo, "commit", "-q", "-m", "init").returncode == 0
    return repo


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.repo = _make_repo(self.tmp)


class TestTreeIsCleanFailsClosed(Base):
    def test_m1_clean_repo_is_clean_and_dirty_repo_is_not(self):
        # covers: BO-4300c-1-iii
        # angle: boundary
        """tree_is_clean: True on a clean tree, False after an uncommitted tracked edit."""
        self.assertTrue(wr.tree_is_clean(self.repo))
        (self.repo / "a.txt").write_text("edited\n", encoding="utf-8")
        self.assertFalse(wr.tree_is_clean(self.repo))

    def test_m1_git_failure_is_not_clean(self):
        # covers: BO-4300c-1-iii
        # angle: failure
        """A directory where `git diff HEAD` fails (not a repo) must NOT be reported clean."""
        plain = self.tmp / "not-a-repo"
        plain.mkdir()
        self.assertFalse(wr.tree_is_clean(plain))

    def test_m1_repo_without_commits_is_not_clean(self):
        # covers: BO-4300c-1-iii
        # angle: failure
        """`git diff HEAD` fails with no HEAD; that is unreadable, not clean."""
        empty = self.tmp / "empty"
        empty.mkdir()
        _git(empty, "init", "-q")
        self.assertFalse(wr.tree_is_clean(empty))


class TestHooksDir(Base):
    def test_m2_default_is_common_git_dir_hooks(self):
        # covers: BO-4300c-1
        # angle: criterion
        """Without core.hooksPath, the hooks directory is <git dir>/hooks."""
        got = wr.hooks_dir(self.repo)
        self.assertEqual(got.resolve(), (self.repo / ".git" / "hooks").resolve())

    def test_m2_absolute_core_hooks_path_wins(self):
        # covers: BO-4300c-1
        # angle: discrimination
        """core.hooksPath (absolute) is returned, not the .git/hooks default."""
        custom = self.tmp / "custom-hooks"
        custom.mkdir()
        _git(self.repo, "config", "core.hooksPath", str(custom))
        self.assertEqual(wr.hooks_dir(self.repo).resolve(), custom.resolve())

    def test_m2_relative_core_hooks_path_resolves_against_workspace(self):
        # covers: BO-4300c-1
        # angle: boundary
        """A relative core.hooksPath resolves against the workspace root."""
        (self.repo / "my-hooks").mkdir()
        _git(self.repo, "config", "core.hooksPath", "my-hooks")
        self.assertEqual(wr.hooks_dir(self.repo).resolve(), (self.repo / "my-hooks").resolve())

    def test_m2_shim_presence_is_read_from_configured_dir(self):
        # covers: BO-4300c-1
        # angle: seam
        """A shim in .git/hooks is NOT seen when core.hooksPath points elsewhere."""
        (self.repo / ".git" / "hooks" / "pre-commit").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        custom = self.tmp / "other-hooks"
        custom.mkdir()
        _git(self.repo, "config", "core.hooksPath", str(custom))
        self.assertFalse(wc._hook_shim_exists(self.repo, "pre-commit"))
        (custom / "pre-commit").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        self.assertTrue(wc._hook_shim_exists(self.repo, "pre-commit"))


class TestCanaryRejectionMustBeTheHooks(Base):
    SPEC = {"path": "bad.txt", "content": "bad\n", "message": "bad message"}

    def _install_hook(self, stage: str, body: str) -> None:
        hook = self.repo / ".git" / "hooks" / stage
        hook.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
        hook.chmod(0o755)

    def _head(self) -> str:
        return _git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def _break_commits(self) -> None:
        """Make every commit fail for a non-canary reason (--no-verify does not skip prepare-commit-msg)."""
        self._install_hook("prepare-commit-msg", "exit 1\n")

    def test_m3_pre_commit_rejecting_hook_counts_as_fired(self):
        # covers: BO-4300c-1
        # angle: criterion
        """Control: a hook that rejects while --no-verify succeeds is a fired canary."""
        self._install_hook("pre-commit", "echo PRECOMMIT_CANARY_REJECTED\nexit 1\n")
        self.assertTrue(wc._pre_commit_fires(self.repo, self.SPEC, self._head()))

    def test_m3_pre_commit_unrelated_rejection_is_not_fired(self):
        # covers: BO-4300c-1
        # angle: discrimination
        """Commits fail for a non-hook reason (control fails too): not counted as the hook firing."""
        self._install_hook("pre-commit", "exit 1\n")
        self._break_commits()
        self.assertFalse(wc._pre_commit_fires(self.repo, self.SPEC, self._head()))

    def test_m3_pre_commit_passing_hook_is_not_fired(self):
        # covers: BO-4300c-1
        # angle: failure
        """A hook that accepts the known-bad commit has not fired."""
        self._install_hook("pre-commit", "exit 0\n")
        self.assertFalse(wc._pre_commit_fires(self.repo, self.SPEC, self._head()))

    def test_m3_pre_commit_leaves_tip_and_tree_untouched(self):
        # covers: BO-4300c-1
        # angle: real_artifact
        """After the canary the tip is unchanged and the known-bad file is gone."""
        self._install_hook("pre-commit", "echo PRECOMMIT_CANARY_REJECTED\nexit 1\n")
        head = self._head()
        wc._pre_commit_fires(self.repo, self.SPEC, head)
        self.assertEqual(self._head(), head)
        self.assertFalse((self.repo / "bad.txt").exists())

    def test_m3_commit_msg_rejecting_hook_counts_as_fired(self):
        # covers: BO-4300c-1
        # angle: criterion
        """Control: a commit-msg hook that rejects while --no-verify succeeds is fired."""
        self._install_hook("commit-msg", "echo PRECOMMIT_CANARY_REJECTED\nexit 1\n")
        self.assertTrue(wc._commit_msg_fires(self.repo, self.SPEC, self._head()))

    def test_m3_commit_msg_unrelated_rejection_is_not_fired(self):
        # covers: BO-4300c-1
        # angle: discrimination
        """Commits fail for a non-hook reason: the commit-msg canary is not counted as fired."""
        self._install_hook("commit-msg", "exit 1\n")
        self._break_commits()
        self.assertFalse(wc._commit_msg_fires(self.repo, self.SPEC, self._head()))


class TestProveReadyRefusesDirtyTreeBeforeCanaries(Base):
    def _patches(self, canaries_rv=None):
        ok_checks = {**{k: True for k in wr._STRUCTURAL}, "tree_clean": True}
        return [
            mock.patch.object(wr, "run_install_build", return_value={"ok": True, "excerpt": ""}),
            mock.patch.object(wr, "install_shims"),
            mock.patch.object(wr, "declared_stages", return_value=["pre-commit"]),
            mock.patch.object(wr, "compute_checks", return_value=dict(ok_checks)),
        ]

    def test_h2_dirty_tracked_tree_refuses_and_edit_survives(self):
        # covers: BO-4300c-1-iii
        # angle: discrimination
        """A pre-existing uncommitted edit (resumed line) is refused as tree_clean=False; run_canaries
        never runs (it would reset --hard the edit away) and the edit is still on disk."""
        (self.repo / "a.txt").write_text("uncommitted work\n", encoding="utf-8", newline="\n")
        patches = self._patches()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        with mock.patch.object(wr, "run_canaries") as canaries:
            ans = wr.prove_ready(self.repo, "hub", kind="work", branch="feature", project_root=self.tmp,
                                 config_path=self.tmp / "cfg.json")
        canaries.assert_not_called()
        self.assertEqual(ans["code"], "VERIFY_FAILED", ans)
        self.assertIn("tree_clean", ans["failed_ingredients"])
        self.assertNotIn("location", ans)
        self.assertEqual((self.repo / "a.txt").read_text(encoding="utf-8"), "uncommitted work\n")

    def test_h2_clean_tree_does_reach_canaries(self):
        # covers: BO-4300c-1-iii
        # angle: discrimination
        """Control: on a clean tree the guard does not refuse and run_canaries is called."""
        patches = self._patches()
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        with mock.patch.object(wr, "run_canaries", return_value={"pre-commit": True}) as canaries:
            wr.prove_ready(self.repo, "hub", kind="work", branch="feature", project_root=self.tmp,
                           config_path=self.tmp / "cfg.json")
        canaries.assert_called_once()


if __name__ == "__main__":
    unittest.main()
