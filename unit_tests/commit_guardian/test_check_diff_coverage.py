"""
MODULE: test_check_diff_coverage
GOAL: Unit tests for check_diff_coverage.py — verifies that the diff-cover
    hook exits cleanly (fail-open) when the diff-cover binary is absent or
    when coverage.xml does not exist.
BUSINESS CONTEXT: AC GE-101a (originally GE-100d). The hook must never block
    a commit simply because the diff-cover tool is not installed or because
    the coverage artifact has not been generated yet.
ARCHITECTURE: Tests import check_diff_coverage module directly and call its
    public helper functions with mocked inputs. main() is exercised through
    unittest.mock.patch to control shutil.which and Path.exists. No subprocess
    calls are made; diff-cover is never actually invoked.

====================================================================
DECISION HISTORY
====================================================================
- 2026-06-18 [python-coder/TICKET-20260616-GE-100d-1]: Added fallback-chain
  tests for AC GE-101a-1. New test classes: TestRemoteBranchIsReachable,
  TestBranchExistsLocally, TestResolveCompareBranch, TestMainUsesResolvedBranch.
  Covers all three legs of the fallback (configured branch reachable, local
  fallback, HEAD~1 fallback) and verifies main() passes the resolved branch
  to _run_diff_cover rather than the raw config string.
- 2026-06-18 [python-coder/TICKET-20260616-GE-100d]: Initial tests for
  AC GE-101a. Covers binary-absent path (exits 0, advisory to stderr) and
  coverage.xml-absent path (exits 0, advisory to stderr). Written alongside
  the hook implementation (test-writer phase was skipped for this ticket).
====================================================================
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Bootstrap sys.path so the module can be imported directly
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_HOOK_DIR = _REPO_ROOT / "scripts" / "commit_guardian"

if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

import check_diff_coverage  # noqa: E402  (path manipulation required)


class TestDiffCoverBinaryAbsent(unittest.TestCase):
    """AC GE-101a, scenario 1: diff-cover binary not present on PATH."""

    def test_exits_zero_when_binary_missing(self) -> None:
        """main() exits 0 when DIFF_COVERAGE_ENABLED=True and binary absent."""
        with (
            patch.object(check_diff_coverage, "DIFF_COVERAGE_ENABLED", True),
            patch.object(check_diff_coverage, "_diff_cover_binary", return_value=None),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            result = check_diff_coverage.main()

        self.assertEqual(
            result,
            0,
            msg=f"Expected exit 0 when diff-cover binary is absent, got {result}.",
        )
        advisory = mock_stderr.getvalue()
        self.assertIn(
            "diff-cover",
            advisory,
            msg=f"Advisory should mention 'diff-cover'. Got: {advisory!r}",
        )

    def test_advisory_contains_install_guidance(self) -> None:
        """Advisory message includes installation guidance when binary is absent."""
        with (
            patch.object(check_diff_coverage, "DIFF_COVERAGE_ENABLED", True),
            patch.object(check_diff_coverage, "_diff_cover_binary", return_value=None),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            check_diff_coverage.main()

        advisory = mock_stderr.getvalue()
        self.assertIn(
            "pip install",
            advisory,
            msg=f"Advisory should include 'pip install' guidance. Got: {advisory!r}",
        )

    def test_disabled_hook_skips_immediately(self) -> None:
        """main() exits 0 immediately when DIFF_COVERAGE_ENABLED=False."""
        with (
            patch.object(check_diff_coverage, "DIFF_COVERAGE_ENABLED", False),
            patch.object(check_diff_coverage, "_diff_cover_binary") as mock_binary,
        ):
            result = check_diff_coverage.main()

        self.assertEqual(result, 0)
        mock_binary.assert_not_called()


class TestCoverageXmlAbsent(unittest.TestCase):
    """AC GE-101a, scenario 2: diff-cover present but coverage.xml absent."""

    def test_exits_zero_when_coverage_xml_missing(self) -> None:
        """main() exits 0 when binary is present but coverage.xml does not exist."""
        with (
            patch.object(check_diff_coverage, "DIFF_COVERAGE_ENABLED", True),
            patch.object(
                check_diff_coverage,
                "_diff_cover_binary",
                return_value="/usr/local/bin/diff-cover",
            ),
            patch.object(
                check_diff_coverage,
                "_coverage_xml_exists",
                return_value=False,
            ),
            patch.object(
                check_diff_coverage,
                "_resolve_coverage_xml",
                return_value=Path("/project/coverage.xml"),
            ),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            result = check_diff_coverage.main()

        self.assertEqual(
            result,
            0,
            msg=f"Expected exit 0 when coverage.xml is absent, got {result}.",
        )
        advisory = mock_stderr.getvalue()
        self.assertIn(
            "coverage.xml",
            advisory,
            msg=f"Advisory should mention 'coverage.xml'. Got: {advisory!r}",
        )

    def test_advisory_contains_generation_guidance(self) -> None:
        """Advisory message includes guidance on generating coverage.xml."""
        with (
            patch.object(check_diff_coverage, "DIFF_COVERAGE_ENABLED", True),
            patch.object(
                check_diff_coverage,
                "_diff_cover_binary",
                return_value="/usr/local/bin/diff-cover",
            ),
            patch.object(
                check_diff_coverage,
                "_coverage_xml_exists",
                return_value=False,
            ),
            patch.object(
                check_diff_coverage,
                "_resolve_coverage_xml",
                return_value=Path("/project/coverage.xml"),
            ),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            check_diff_coverage.main()

        advisory = mock_stderr.getvalue()
        self.assertIn(
            "pytest",
            advisory,
            msg=f"Advisory should mention pytest for coverage generation. Got: {advisory!r}",
        )


class TestDiffCoverBinaryDetection(unittest.TestCase):
    """Unit tests for _diff_cover_binary() helper."""

    def test_returns_none_when_not_on_path(self) -> None:
        """_diff_cover_binary() returns None when shutil.which finds nothing."""
        with patch("shutil.which", return_value=None):
            result = check_diff_coverage._diff_cover_binary()
        self.assertIsNone(result)

    def test_returns_path_when_found(self) -> None:
        """_diff_cover_binary() returns the binary path when shutil.which succeeds."""
        with patch("shutil.which", return_value="/usr/local/bin/diff-cover"):
            result = check_diff_coverage._diff_cover_binary()
        self.assertEqual(result, "/usr/local/bin/diff-cover")


class TestCoverageXmlExistence(unittest.TestCase):
    """Unit tests for _coverage_xml_exists() helper."""

    def test_returns_false_for_nonexistent_path(self) -> None:
        """_coverage_xml_exists() returns False when the path does not exist."""
        non_existent = Path("/tmp/this_file_does_not_exist_12345.xml")
        result = check_diff_coverage._coverage_xml_exists(non_existent)
        self.assertFalse(result)

    def test_returns_true_for_existing_file(self) -> None:
        """_coverage_xml_exists() returns True when the path exists."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".xml") as tmp:
            result = check_diff_coverage._coverage_xml_exists(Path(tmp.name))
        self.assertTrue(result)


class TestCoverageXmlFreshness(unittest.TestCase):
    """Unit tests for _coverage_xml_is_fresh() helper."""

    def test_fresh_when_age_check_disabled(self) -> None:
        """_coverage_xml_is_fresh() returns True when max_age_seconds is 0."""
        any_path = Path("/any/path/coverage.xml")
        result = check_diff_coverage._coverage_xml_is_fresh(any_path, max_age_seconds=0)
        self.assertTrue(result)

    def test_fresh_file_passes(self) -> None:
        """_coverage_xml_is_fresh() returns True for a recently modified file."""
        import tempfile
        import time
        with tempfile.NamedTemporaryFile(suffix=".xml") as tmp:
            # File was just created — it is definitely fresh
            result = check_diff_coverage._coverage_xml_is_fresh(
                Path(tmp.name), max_age_seconds=3600
            )
        self.assertTrue(result)

    def test_stale_file_fails(self) -> None:
        """_coverage_xml_is_fresh() returns False when mtime is too old."""
        with patch.object(Path, "stat") as mock_stat:
            mock_stat_result = MagicMock()
            # mtime 2 hours ago
            import time
            mock_stat_result.st_mtime = time.time() - 7200
            mock_stat.return_value = mock_stat_result
            result = check_diff_coverage._coverage_xml_is_fresh(
                Path("/fake/coverage.xml"), max_age_seconds=3600
            )
        self.assertFalse(result)


class TestResolveCoverageXml(unittest.TestCase):
    """Unit tests for _resolve_coverage_xml() helper."""

    def test_absolute_path_returned_unchanged(self) -> None:
        """_resolve_coverage_xml() returns an absolute path as-is."""
        absolute = Path("/absolute/path/coverage.xml")
        result = check_diff_coverage._resolve_coverage_xml(str(absolute))
        self.assertEqual(result, absolute)

    def test_relative_path_resolved_against_project_root(self) -> None:
        """_resolve_coverage_xml() resolves relative paths against project_root."""
        result = check_diff_coverage._resolve_coverage_xml("coverage.xml")
        self.assertEqual(result, check_diff_coverage.project_root / "coverage.xml")


class TestRemoteBranchIsReachable(unittest.TestCase):
    """Unit tests for _remote_branch_is_reachable() helper (AC GE-101a-1)."""

    def test_returns_true_when_ref_resolves(self) -> None:
        """_remote_branch_is_reachable() returns True when git rev-parse exits 0."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = check_diff_coverage._remote_branch_is_reachable("origin/main")
        self.assertTrue(result)

    def test_returns_false_when_ref_absent(self) -> None:
        """_remote_branch_is_reachable() returns False when git rev-parse exits non-zero."""
        mock_result = MagicMock()
        mock_result.returncode = 128
        with patch("subprocess.run", return_value=mock_result):
            result = check_diff_coverage._remote_branch_is_reachable("origin/main")
        self.assertFalse(result)

    def test_returns_false_on_os_error(self) -> None:
        """_remote_branch_is_reachable() returns False when subprocess raises OSError."""
        with (
            patch("subprocess.run", side_effect=OSError("git not found")),
            patch("sys.stderr", new_callable=StringIO),
        ):
            result = check_diff_coverage._remote_branch_is_reachable("origin/main")
        self.assertFalse(result)

    def test_returns_false_on_timeout(self) -> None:
        """_remote_branch_is_reachable() returns False when subprocess times out."""
        with (
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("git", 10)),
            patch("sys.stderr", new_callable=StringIO),
        ):
            result = check_diff_coverage._remote_branch_is_reachable("origin/main")
        self.assertFalse(result)


class TestBranchExistsLocally(unittest.TestCase):
    """Unit tests for _branch_exists_locally() helper (AC GE-101a-1)."""

    def test_returns_true_when_local_branch_exists(self) -> None:
        """_branch_exists_locally() returns True when the local ref resolves."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = check_diff_coverage._branch_exists_locally("main")
        self.assertTrue(result)

    def test_returns_false_when_local_branch_absent(self) -> None:
        """_branch_exists_locally() returns False when the local ref does not exist."""
        mock_result = MagicMock()
        mock_result.returncode = 128
        with patch("subprocess.run", return_value=mock_result):
            result = check_diff_coverage._branch_exists_locally("main")
        self.assertFalse(result)

    def test_returns_false_on_os_error(self) -> None:
        """_branch_exists_locally() returns False when subprocess raises OSError."""
        with (
            patch("subprocess.run", side_effect=OSError("git not found")),
            patch("sys.stderr", new_callable=StringIO),
        ):
            result = check_diff_coverage._branch_exists_locally("main")
        self.assertFalse(result)


class TestResolveCompareBranch(unittest.TestCase):
    """Unit tests for _resolve_compare_branch() — AC GE-101a-1 fallback chain."""

    def test_returns_configured_branch_when_reachable(self) -> None:
        """_resolve_compare_branch() returns the configured branch when reachable."""
        with (
            patch.object(
                check_diff_coverage, "_remote_branch_is_reachable", return_value=True
            ),
        ):
            result = check_diff_coverage._resolve_compare_branch("origin/main")
        self.assertEqual(result, "origin/main")

    def test_falls_back_to_local_branch_when_remote_unreachable(self) -> None:
        """Falls back to local 'main' when 'origin/main' is unreachable but 'main' exists."""
        with (
            patch.object(
                check_diff_coverage, "_remote_branch_is_reachable", return_value=False
            ),
            patch.object(
                check_diff_coverage, "_branch_exists_locally", return_value=True
            ),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            result = check_diff_coverage._resolve_compare_branch("origin/main")
        self.assertEqual(result, "main")
        advisory = mock_stderr.getvalue()
        self.assertIn("origin/main", advisory)
        self.assertIn("main", advisory)

    def test_falls_back_to_head_tilde_1_when_neither_exists(self) -> None:
        """Falls back to HEAD~1 when neither 'origin/main' nor 'main' exists locally."""
        with (
            patch.object(
                check_diff_coverage, "_remote_branch_is_reachable", return_value=False
            ),
            patch.object(
                check_diff_coverage, "_branch_exists_locally", return_value=False
            ),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
        ):
            result = check_diff_coverage._resolve_compare_branch("origin/main")
        self.assertEqual(result, "HEAD~1")
        advisory = mock_stderr.getvalue()
        self.assertIn("HEAD~1", advisory)

    def test_local_branch_name_stripped_from_remote_prefix(self) -> None:
        """The local fallback strips the remote/ prefix correctly (e.g. origin/develop -> develop)."""
        with (
            patch.object(
                check_diff_coverage, "_remote_branch_is_reachable", return_value=False
            ),
            patch.object(
                check_diff_coverage, "_branch_exists_locally", return_value=True
            ) as mock_local,
            patch("sys.stderr", new_callable=StringIO),
        ):
            result = check_diff_coverage._resolve_compare_branch("origin/develop")
        self.assertEqual(result, "develop")
        mock_local.assert_called_once_with("develop")

    def test_no_remote_prefix_branch_falls_back_to_itself(self) -> None:
        """A branch name with no slash (e.g. 'main') is tried locally as-is when unreachable."""
        with (
            patch.object(
                check_diff_coverage, "_remote_branch_is_reachable", return_value=False
            ),
            patch.object(
                check_diff_coverage, "_branch_exists_locally", return_value=True
            ) as mock_local,
            patch("sys.stderr", new_callable=StringIO),
        ):
            result = check_diff_coverage._resolve_compare_branch("main")
        self.assertEqual(result, "main")
        mock_local.assert_called_once_with("main")


class TestMainUsesResolvedBranch(unittest.TestCase):
    """Integration: main() calls _resolve_compare_branch and passes result to _run_diff_cover."""

    def test_main_resolves_branch_before_running_diff_cover(self) -> None:
        """main() uses the resolved branch (not the raw config value) when diff-cover runs."""
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".xml") as tmp:
            with (
                patch.object(check_diff_coverage, "DIFF_COVERAGE_ENABLED", True),
                patch.object(
                    check_diff_coverage,
                    "_diff_cover_binary",
                    return_value="/usr/local/bin/diff-cover",
                ),
                patch.object(
                    check_diff_coverage,
                    "_resolve_coverage_xml",
                    return_value=Path(tmp.name),
                ),
                patch.object(
                    check_diff_coverage, "_coverage_xml_exists", return_value=True
                ),
                patch.object(
                    check_diff_coverage, "_coverage_xml_is_fresh", return_value=True
                ),
                patch.object(
                    check_diff_coverage,
                    "_resolve_compare_branch",
                    return_value="main",
                ) as mock_resolve,
                patch.object(
                    check_diff_coverage,
                    "_run_diff_cover",
                    return_value=(0, ""),
                ) as mock_run,
                patch.object(
                    check_diff_coverage,
                    "DIFF_COVERAGE_COMPARE_BRANCH",
                    "origin/main",
                ),
            ):
                check_diff_coverage.main()

        mock_resolve.assert_called_once_with("origin/main")
        call_args = mock_run.call_args
        # compare_branch is the third positional arg
        self.assertEqual(call_args[0][2], "main")


if __name__ == "__main__":
    unittest.main()
