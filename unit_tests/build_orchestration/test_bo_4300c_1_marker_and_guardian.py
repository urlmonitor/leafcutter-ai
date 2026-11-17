"""
MODULE: unit_tests/build_orchestration/test_bo_4300c_1_marker_and_guardian.py
AC: BO-4300c-1 -- pr-reviewer H-2: the canary rejection marker, and commit_guardian.json exclusion.
Real git repos in temp dirs; the real precommit_canary.py is run as a hook.

DECISION HISTORY
====================================================================
- 2026-10-09 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: Created for H-2.
- 2026-10-09 [test-writer/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: Dropped the
  content-scanning guardian-json class; superseded by the path-keyed canary contract.
====================================================================
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "templates" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import worktree_canaries as wc  # noqa: E402

MARK = "PRECOMMIT_CANARY_REJECTED"


def _git(cwd, *args):
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True, check=False)


def _repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "feature")
    for k, v in (("user.name", "t"), ("user.email", "t@example.invalid"), ("commit.gpgsign", "false")):
        _git(repo, "config", k, v)
    (repo / "a.txt").write_text("x\n", encoding="utf-8", newline="\n")
    _git(repo, "add", "a.txt")
    assert _git(repo, "commit", "-q", "-m", "init").returncode == 0
    return repo


class Base(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        self.repo = _repo(self.tmp)

    def head(self):
        return _git(self.repo, "rev-parse", "HEAD").stdout.strip()

    def hook(self, stage, body):
        h = self.repo / ".git" / "hooks" / stage
        h.write_text("#!/bin/sh\n" + body, encoding="utf-8", newline="\n")
        h.chmod(0o755)


class TestMarkerRequired(Base):
    SPEC = {"path": "bad.txt", "content": "bad\n", "message": "bad message"}

    def test_h2_pre_commit_markerless_failure_not_fired(self):
        # covers: BO-4300c-1
        # angle: discrimination
        """A hook that fails without the marker (any unrelated failure) is not a fired canary."""
        self.hook("pre-commit", "exit 1\n")
        self.assertFalse(wc._pre_commit_fires(self.repo, self.SPEC, self.head()))

    def test_h2_pre_commit_marker_failure_fired(self):
        # covers: BO-4300c-1
        # angle: criterion
        """Control: the same failure with the marker is a fired canary."""
        self.hook("pre-commit", f"echo {MARK}\nexit 1\n")
        self.assertTrue(wc._pre_commit_fires(self.repo, self.SPEC, self.head()))

    def test_h2_commit_msg_markerless_failure_not_fired(self):
        # covers: BO-4300c-1
        # angle: discrimination
        """commit-msg hook failing without the marker is not fired."""
        self.hook("commit-msg", "exit 1\n")
        self.assertFalse(wc._commit_msg_fires(self.repo, self.SPEC, self.head()))

    def test_h2_commit_msg_marker_failure_fired(self):
        # covers: BO-4300c-1
        # angle: criterion
        """Control: commit-msg failure with the marker is fired."""
        self.hook("commit-msg", f"echo {MARK}\nexit 1\n")
        self.assertTrue(wc._commit_msg_fires(self.repo, self.SPEC, self.head()))

    def test_h2_post_merge_markerless_failure_not_fired(self):
        # covers: BO-4300c-1
        # angle: discrimination
        """post-merge hook exiting non-zero without the marker is not fired."""
        self.hook("post-merge", "exit 1\n")
        self.assertFalse(wc._post_merge_fires(self.repo, self.SPEC, self.head(), "feature"))

    def test_h2_post_merge_marker_failure_fired(self):
        # covers: BO-4300c-1
        # angle: criterion
        """Control: post-merge failure with the marker is fired."""
        self.hook("post-merge", f"echo {MARK}\nexit 1\n")
        self.assertTrue(wc._post_merge_fires(self.repo, self.SPEC, self.head(), "feature"))


# TestCommitGuardianJsonNotRejected removed 2026-10-09: it encoded the superseded content-scanning
# canary and its commit_guardian.json exclusion. The path-keyed contract is pinned in
# test_bo_4300c_1_path_keyed_canaries.py.


if __name__ == "__main__":
    unittest.main()
