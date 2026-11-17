"""Finalize Step 3.5 sub-step A: undo a Step 2 merge left in progress, WITHOUT discarding other edits.

History: this file used to assert that the step-3.5-reset-merge prompt ran `git reset --hard HEAD`
after `git merge --abort`. BO-400e-3-v removed the hard reset (it destroyed unrelated uncommitted
edits); the closure is now computed and committed by path, so a stray unstaged `status: done` can no
longer hide a ticket from the closure.

What is protected now, proven behaviourally: the git commands the workflow really dispatches in
`step-3.5-reset-merge`, executed on a real repository,
  * clear a merge left in progress (MERGE_HEAD gone, HEAD unchanged), and
  * leave an unrelated uncommitted edit byte-identical, and
  * change nothing when no merge is in progress.
"""

from __future__ import annotations

import re
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _bo400e3_finalize_harness as H  # noqa: E402


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)


def _init_repo(root: Path) -> Path:
    repo = root / "wt"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "feature")
    _git(repo, "config", "user.email", "t@example.invalid")
    _git(repo, "config", "user.name", "t")
    (repo / "shared.txt").write_text("base\n", encoding="utf-8")
    (repo / "unrelated.txt").write_text("committed\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "branch", "other")
    (repo / "shared.txt").write_text("feature side\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "feature change")
    _git(repo, "checkout", "-q", "other")
    (repo / "shared.txt").write_text("other side\n", encoding="utf-8")
    _git(repo, "commit", "-q", "-am", "other change")
    _git(repo, "checkout", "-q", "feature")
    return repo


def _dispatched_git_commands(repo: Path) -> list[list[str]]:
    """The git commands in the real step-3.5-reset-merge dispatch, in prompt order."""
    result = H.run_finalize("feature", str(repo))
    sent = H.calls(result, "step-3.5-reset-merge")
    assert len(sent) == 1, H.labels(result)
    commands = []
    for line in H.prompt_of(sent[0]).splitlines():
        match = re.search(r"\brun:\s*(git .*)$", line, re.I)
        if match:
            commands.append(shlex.split(match.group(1).strip()))
    return commands


def _apply(commands: list[list[str]]) -> None:
    """Apply the dispatched instructions as the prompt states them: the probe, then the abort only
    when the probe succeeds."""
    assert len(commands) >= 2, f"expected probe + abort instructions, got {commands}"
    probe = subprocess.run(commands[0], capture_output=True, text=True)
    if probe.returncode == 0:
        for command in commands[1:]:
            subprocess.run(command, capture_output=True, text=True)


class TestStep35UndoesAnInProgressMergeWithoutDiscardingEdits(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = _init_repo(Path(tmp.name))

    def _start_conflicting_merge(self):
        merge = _git(self.repo, "merge", "--no-commit", "--no-ff", "other")
        self.assertNotEqual(merge.returncode, 0, "fixture must leave a conflicted merge in progress")
        self.assertEqual(_git(self.repo, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode, 0)

    def test_merge_in_progress_is_undone_and_unrelated_edit_survives(self):
        # covers: BO-400e-3-v
        # angle: discrimination
        # must_catch: sub-step A stops undoing the merge (MERGE_HEAD survives)
        # must_catch: sub-step A uses a hard reset (the unrelated edit is lost)
        head_before = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        self._start_conflicting_merge()
        (self.repo / "unrelated.txt").write_text("my uncommitted edit\n", encoding="utf-8")
        _apply(_dispatched_git_commands(self.repo))
        self.assertNotEqual(_git(self.repo, "rev-parse", "-q", "--verify", "MERGE_HEAD").returncode, 0,
                            "the Step 2 merge is still in progress after sub-step A")
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), head_before)
        self.assertEqual((self.repo / "shared.txt").read_text(encoding="utf-8"), "feature side\n",
                         "step 3.5 must start from the branch's own committed state")
        self.assertEqual((self.repo / "unrelated.txt").read_bytes(), b"my uncommitted edit\n",
                         "an unrelated uncommitted edit was discarded")

    def test_no_merge_in_progress_changes_nothing(self):
        # covers: BO-400e-3-v
        # angle: boundary
        (self.repo / "unrelated.txt").write_text("my uncommitted edit\n", encoding="utf-8")
        head_before = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        _apply(_dispatched_git_commands(self.repo))
        self.assertEqual(_git(self.repo, "rev-parse", "HEAD").stdout.strip(), head_before)
        self.assertEqual((self.repo / "unrelated.txt").read_bytes(), b"my uncommitted edit\n")
        self.assertEqual((self.repo / "shared.txt").read_text(encoding="utf-8"), "feature side\n")


if __name__ == "__main__":
    unittest.main()
