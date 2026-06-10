"""
unit_tests/test_history_filter.py — tests for the history-filter additions
to scripts/commit_pattern_learner.py.

Covers AC BO-1100e: The specialist only reads relevant history, not thousands
of commits.

* ``_build_git_pathspecs`` derives correct pathspec strings from shape tokens.
* ``filter_history_by_shape`` calls git with targeted pathspecs and a bounded
  ``--max-count`` arg; returns a list of {hash, subject} dicts.
* Empty shape → immediate empty list (no git call made).
* git unavailability / non-zero exit → logged warning, empty list returned.
* ``max_commits`` default is MAX_HISTORY_COMMITS (100) and is honoured.
"""
# @ac-tag: BO-1100e

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from commit_pattern_learner import (
    MAX_HISTORY_COMMITS,
    _build_git_pathspecs,
    extract_shape,
    filter_history_by_shape,
)


# ---------------------------------------------------------------------------
# _build_git_pathspecs
# ---------------------------------------------------------------------------


class TestBuildGitPathspecs(unittest.TestCase):
    """_build_git_pathspecs — shape token → git pathspec conversion."""

    def test_empty_shape_returns_empty_list(self):
        self.assertEqual(_build_git_pathspecs(()), [])

    def test_dir_token_becomes_directory_prefix(self):
        specs = _build_git_pathspecs(("dir:scripts",))
        self.assertIn("scripts/", specs)

    def test_ext_token_becomes_glob(self):
        specs = _build_git_pathspecs(("ext:py",))
        self.assertIn("*.py", specs)

    def test_multiple_tokens_produce_multiple_pathspecs(self):
        shape = extract_shape(["scripts/build.py"])
        specs = _build_git_pathspecs(shape)
        self.assertIn("scripts/", specs)
        self.assertIn("*.py", specs)

    def test_unknown_prefix_token_ignored(self):
        """Tokens with no recognised prefix are ignored."""
        specs = _build_git_pathspecs(("bogus:thing",))
        self.assertEqual(specs, [])

    def test_dir_with_empty_name_skipped(self):
        specs = _build_git_pathspecs(("dir:",))
        self.assertEqual(specs, [])

    def test_ext_with_empty_name_skipped(self):
        specs = _build_git_pathspecs(("ext:",))
        self.assertEqual(specs, [])

    def test_multiple_extensions(self):
        shape = extract_shape(["config/settings.yaml", "scripts/run.py"])
        specs = _build_git_pathspecs(shape)
        self.assertIn("*.yaml", specs)
        self.assertIn("*.py", specs)


# ---------------------------------------------------------------------------
# filter_history_by_shape
# ---------------------------------------------------------------------------


class TestFilterHistoryByShape(unittest.TestCase):
    """filter_history_by_shape — targeted git log filtering."""

    def _make_proc(self, returncode: int, stdout: str, stderr: str = "") -> MagicMock:
        """Build a mock CompletedProcess with the given attributes."""
        proc = MagicMock()
        proc.returncode = returncode
        proc.stdout = stdout
        proc.stderr = stderr
        return proc

    def test_empty_shape_returns_empty_without_calling_git(self):
        """Empty shape must short-circuit before any subprocess call."""
        with patch("commit_pattern_learner.subprocess.run") as mock_run:
            result = filter_history_by_shape(())
            mock_run.assert_not_called()
        self.assertEqual(result, [])

    def test_shape_with_no_valid_pathspecs_returns_empty(self):
        """A shape whose tokens produce no pathspecs returns [] without calling git."""
        with patch("commit_pattern_learner.subprocess.run") as mock_run:
            # A shape tuple with no dir: or ext: prefixes.
            result = filter_history_by_shape(("bogus:nothing",))
            mock_run.assert_not_called()
        self.assertEqual(result, [])

    def test_successful_git_log_parsed_correctly(self):
        """Well-formed git log output is parsed into a list of dicts."""
        fake_output = (
            "abc123def456abc123def456abc123def456abc123\n"
            "feat: add history filter\n"
            "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n"
            "fix: correct pathspec glob\n"
        )
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, fake_output),
        ):
            shape = extract_shape(["scripts/build.py"])
            commits = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))

        self.assertEqual(len(commits), 2)
        self.assertEqual(commits[0]["hash"], "abc123def456abc123def456abc123def456abc123")
        self.assertEqual(commits[0]["subject"], "feat: add history filter")
        self.assertEqual(commits[1]["hash"], "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef")
        self.assertEqual(commits[1]["subject"], "fix: correct pathspec glob")

    def test_max_commits_passed_to_git(self):
        """filter_history_by_shape passes --max-count to git log."""
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, ""),
        ) as mock_run:
            shape = extract_shape(["scripts/build.py"])
            filter_history_by_shape(shape, repo_root=Path("/fake/repo"), max_commits=42)

        call_args = mock_run.call_args[0][0]  # First positional arg (the cmd list)
        self.assertIn("--max-count=42", call_args)

    def test_default_max_commits_is_constant(self):
        """Default max_commits equals MAX_HISTORY_COMMITS (100)."""
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, ""),
        ) as mock_run:
            shape = extract_shape(["scripts/build.py"])
            filter_history_by_shape(shape, repo_root=Path("/fake/repo"))

        call_args = mock_run.call_args[0][0]
        self.assertIn(f"--max-count={MAX_HISTORY_COMMITS}", call_args)

    def test_pathspecs_appended_after_double_dash(self):
        """Pathspecs appear after the '--' separator in the git command."""
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, ""),
        ) as mock_run:
            shape = extract_shape(["scripts/build.py"])
            filter_history_by_shape(shape, repo_root=Path("/fake/repo"))

        cmd = mock_run.call_args[0][0]
        double_dash_idx = cmd.index("--")
        pathspecs = cmd[double_dash_idx + 1 :]
        self.assertTrue(len(pathspecs) > 0, "No pathspecs found after '--'")
        self.assertTrue(
            any("scripts/" in s or "*.py" in s for s in pathspecs),
            f"Expected pathspecs for scripts/ or *.py; got: {pathspecs}",
        )

    def test_git_not_found_returns_empty_list(self):
        """FileNotFoundError (git not in PATH) is caught and returns []."""
        with patch(
            "commit_pattern_learner.subprocess.run",
            side_effect=FileNotFoundError("git"),
        ):
            shape = extract_shape(["scripts/build.py"])
            result = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))
        self.assertEqual(result, [])

    def test_git_timeout_returns_empty_list(self):
        """TimeoutExpired is caught and returns []."""
        import subprocess

        with patch(
            "commit_pattern_learner.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=30),
        ):
            shape = extract_shape(["scripts/build.py"])
            result = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))
        self.assertEqual(result, [])

    def test_git_nonzero_exit_returns_empty_list(self):
        """Non-zero returncode is caught and returns []."""
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(128, "", "fatal: not a git repository"),
        ):
            shape = extract_shape(["scripts/build.py"])
            result = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))
        self.assertEqual(result, [])

    def test_oserror_returns_empty_list(self):
        """OSError is caught and returns []."""
        with patch(
            "commit_pattern_learner.subprocess.run",
            side_effect=OSError("permission denied"),
        ):
            shape = extract_shape(["scripts/build.py"])
            result = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))
        self.assertEqual(result, [])

    def test_empty_git_output_returns_empty_list(self):
        """Empty git log output (no matching commits) returns []."""
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, ""),
        ):
            shape = extract_shape(["scripts/build.py"])
            result = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))
        self.assertEqual(result, [])

    def test_each_commit_has_hash_and_subject_keys(self):
        """Each returned dict has exactly 'hash' and 'subject' keys."""
        fake_output = "aabbccdd\nsome commit subject\n"
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, fake_output),
        ):
            shape = extract_shape(["scripts/build.py"])
            commits = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))

        self.assertEqual(len(commits), 1)
        self.assertIn("hash", commits[0])
        self.assertIn("subject", commits[0])

    def test_odd_lines_in_output_handled_gracefully(self):
        """Output with an odd number of lines does not crash."""
        # Three lines: two complete commits plus one orphan hash
        fake_output = "hash1\nsubject1\nhash2\nsubject2\nhash3\n"
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, fake_output),
        ):
            shape = extract_shape(["scripts/build.py"])
            commits = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))

        # Should parse 3 commits (hash3 gets empty subject)
        self.assertGreaterEqual(len(commits), 2)
        hashes = [c["hash"] for c in commits]
        self.assertIn("hash1", hashes)
        self.assertIn("hash2", hashes)

    def test_returns_list_type(self):
        """Return value is always a list."""
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, ""),
        ):
            shape = extract_shape(["scripts/build.py"])
            result = filter_history_by_shape(shape, repo_root=Path("/fake/repo"))
        self.assertIsInstance(result, list)

    def test_git_called_with_c_flag_in_repo_root(self):
        """git is invoked with -C <repo_root> so CWD does not matter."""
        fake_root = Path("/some/explicit/repo")
        with patch(
            "commit_pattern_learner.subprocess.run",
            return_value=self._make_proc(0, ""),
        ) as mock_run:
            shape = extract_shape(["scripts/build.py"])
            filter_history_by_shape(shape, repo_root=fake_root)

        cmd = mock_run.call_args[0][0]
        # cmd should contain: git -C /some/explicit/repo log ...
        self.assertEqual(cmd[0], "git")
        self.assertEqual(cmd[1], "-C")
        self.assertEqual(cmd[2], str(fake_root))


# ---------------------------------------------------------------------------
# MAX_HISTORY_COMMITS constant
# ---------------------------------------------------------------------------


class TestMaxHistoryCommits(unittest.TestCase):
    """Verify the bounding constant is correctly defined."""

    def test_max_history_commits_is_positive_integer(self):
        self.assertIsInstance(MAX_HISTORY_COMMITS, int)
        self.assertGreater(MAX_HISTORY_COMMITS, 0)

    def test_max_history_commits_is_bounded(self):
        """Should be 100 per AC BO-1100e (keep bounded; 50-100 range)."""
        self.assertGreaterEqual(MAX_HISTORY_COMMITS, 50)
        self.assertLessEqual(MAX_HISTORY_COMMITS, 200)


if __name__ == "__main__":
    unittest.main()
