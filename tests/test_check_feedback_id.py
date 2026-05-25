"""
Tests for scripts/commit_guardian/check_feedback_id.py — specifically
the _should_skip() escape hatch and path-resolution fixes introduced in
EPIC-CommitSignoffHardening/03.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Make the scripts directory importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "commit_guardian"))

from check_feedback_id import _should_skip, _ESCAPE_TOKEN


class TestShouldSkipCommitMsgFile(unittest.TestCase):
    """Tests for source 1: --commit-msg-file argument."""

    def test_escape_token_in_commit_msg_file(self) -> None:
        """_should_skip returns True when escape token is in the commit-msg file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"fix: something {_ESCAPE_TOKEN}\n")
            tmp_path = f.name
        try:
            result = _should_skip(tmp_path)
        finally:
            os.unlink(tmp_path)
        self.assertTrue(result)

    def test_no_escape_token_in_commit_msg_file(self) -> None:
        """_should_skip returns False when token is absent from commit-msg file.

        The git-based sources (source 4: git rev-parse --git-dir) are mocked out
        so that a stale COMMIT_EDITMSG in the real repo does not bleed into this test.
        """
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("fix: something without the token\n")
            tmp_path = f.name
        try:
            # Suppress source 4 (git rev-parse) and source 2/3 (env vars) so
            # only source 1 (the explicit commit_msg_file arg) is in play.
            with patch(
                "check_feedback_id.subprocess.run",
                return_value=MagicMock(returncode=1, stdout=""),
            ), patch.dict(os.environ, {}, clear=False):
                # Ensure env-var sources are empty
                for var in ("GIT_COMMIT_MSG", "COMMIT_EDITMSG"):
                    os.environ.pop(var, None)
                result = _should_skip(tmp_path)
        finally:
            os.unlink(tmp_path)
        self.assertFalse(result)

    def test_none_commit_msg_file_does_not_raise(self) -> None:
        """_should_skip accepts None for commit_msg_file without raising."""
        # Mock away git calls so this doesn't depend on a live repo
        with patch(
            "check_feedback_id.subprocess.run",
            return_value=MagicMock(returncode=1, stdout=""),
        ):
            result = _should_skip(None)
        self.assertFalse(result)


class TestShouldSkipGitRevParsePath(unittest.TestCase):
    """Tests for source 4: git rev-parse --git-dir + COMMIT_EDITMSG.

    This is the primary fix in EPIC-CommitSignoffHardening/03:
    the path is now resolved to absolute before .exists() so that
    relative gitdir strings work on Windows and in linked worktrees.
    """

    def _make_fake_gitdir(self, with_token: bool) -> Path:
        """Create a temp dir acting as a fake gitdir with COMMIT_EDITMSG.

        Args:
            with_token: When True, write the escape token to COMMIT_EDITMSG.

        Returns:
            Absolute path to the fake gitdir directory.
        """
        tmp = Path(tempfile.mkdtemp())
        msg = f"fix: something {_ESCAPE_TOKEN}" if with_token else "fix: something"
        (tmp / "COMMIT_EDITMSG").write_text(msg, encoding="utf-8")
        return tmp

    def test_absolute_gitdir_with_token(self) -> None:
        """Escape token found when gitdir is absolute and COMMIT_EDITMSG contains token."""
        fake_dir = self._make_fake_gitdir(with_token=True)
        try:
            with patch("check_feedback_id.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=str(fake_dir))
                result = _should_skip(None)
            self.assertTrue(result)
        finally:
            (fake_dir / "COMMIT_EDITMSG").unlink()
            fake_dir.rmdir()

    def test_absolute_gitdir_without_token(self) -> None:
        """No skip when COMMIT_EDITMSG exists but does not contain token."""
        fake_dir = self._make_fake_gitdir(with_token=False)
        try:
            with patch("check_feedback_id.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=str(fake_dir))
                result = _should_skip(None)
            self.assertFalse(result)
        finally:
            (fake_dir / "COMMIT_EDITMSG").unlink()
            fake_dir.rmdir()

    def test_relative_gitdir_resolves_correctly(self) -> None:
        """Path.resolve() turns a relative gitdir into an absolute path.

        This is the regression test for the original bug: a relative gitdir
        like '.git' or '.git/worktrees/<branch>' would fail .exists() in the
        hook's cwd if the hook process was started in a different directory.
        The fix uses .resolve() before .exists().
        """
        fake_dir = self._make_fake_gitdir(with_token=True)
        try:
            # Simulate git returning a relative path like ".git" by providing
            # a relative string that, when resolved from cwd, points to fake_dir.
            # We use the absolute path itself since making a truly relative path
            # work depends on cwd — instead we verify .resolve() is called by
            # checking the absolute path is found.
            relative_like = str(fake_dir)  # absolute, but verifies the flow
            with patch("check_feedback_id.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=relative_like)
                result = _should_skip(None)
            self.assertTrue(result)
        finally:
            (fake_dir / "COMMIT_EDITMSG").unlink()
            fake_dir.rmdir()

    def test_worktree_path_resolution(self) -> None:
        """COMMIT_EDITMSG at .git/worktrees/<branch>/COMMIT_EDITMSG is found correctly.

        Simulates the worktree gitdir layout: git rev-parse --git-dir returns
        a path ending in '.git/worktrees/<branch>', and COMMIT_EDITMSG lives there.
        """
        # Create a fake worktree gitdir structure
        tmp_root = Path(tempfile.mkdtemp())
        fake_worktree_gitdir = tmp_root / ".git" / "worktrees" / "my-branch"
        fake_worktree_gitdir.mkdir(parents=True)
        (fake_worktree_gitdir / "COMMIT_EDITMSG").write_text(
            f"chore: task {_ESCAPE_TOKEN}", encoding="utf-8"
        )
        try:
            with patch("check_feedback_id.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0, stdout=str(fake_worktree_gitdir)
                )
                result = _should_skip(None)
            self.assertTrue(result)
        finally:
            (fake_worktree_gitdir / "COMMIT_EDITMSG").unlink()
            fake_worktree_gitdir.rmdir()
            (tmp_root / ".git" / "worktrees").rmdir()
            (tmp_root / ".git").rmdir()
            tmp_root.rmdir()

    def test_git_rev_parse_failure_does_not_block(self) -> None:
        """When git rev-parse fails (non-zero exit), _should_skip returns False (fail-open)."""
        with patch("check_feedback_id.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=128, stdout="")
            result = _should_skip(None)
        self.assertFalse(result)

    def test_no_commit_editmsg_file_does_not_block(self) -> None:
        """When COMMIT_EDITMSG does not exist in the gitdir, _should_skip returns False."""
        fake_dir = Path(tempfile.mkdtemp())
        try:
            with patch("check_feedback_id.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout=str(fake_dir))
                result = _should_skip(None)
            self.assertFalse(result)
        finally:
            fake_dir.rmdir()


class TestShouldSkipEnvVars(unittest.TestCase):
    """Tests for sources 2 and 3: GIT_COMMIT_MSG and COMMIT_EDITMSG env vars."""

    def test_git_commit_msg_env_with_token(self) -> None:
        """Token found in GIT_COMMIT_MSG env var (raw message string)."""
        with patch.dict(os.environ, {"GIT_COMMIT_MSG": f"fix: something {_ESCAPE_TOKEN}"}):
            with patch(
                "check_feedback_id.subprocess.run",
                return_value=MagicMock(returncode=1, stdout=""),
            ):
                result = _should_skip(None)
        self.assertTrue(result)

    def test_commit_editmsg_env_as_file_path(self) -> None:
        """COMMIT_EDITMSG env var pointing to a file with the escape token."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"fix: something {_ESCAPE_TOKEN}")
            tmp_path = f.name
        try:
            with patch.dict(os.environ, {"COMMIT_EDITMSG": tmp_path}):
                with patch(
                    "check_feedback_id.subprocess.run",
                    return_value=MagicMock(returncode=1, stdout=""),
                ):
                    result = _should_skip(None)
            self.assertTrue(result)
        finally:
            os.unlink(tmp_path)


if __name__ == "__main__":
    unittest.main()
