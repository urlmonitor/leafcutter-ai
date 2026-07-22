"""
MODULE: unit_tests/commit_guardian/test_resolve_root_git_preferred.py
GOAL: Tests for DEFECT M-4 — _resolve_root.find_project_root() uses __file__
      path walking instead of git rev-parse --show-toplevel, so a symlinked
      deployed layout resolves the leafcutter-ai package directory rather than
      the consumer project root.

=== DEFECT M-4 (_resolve_root uses __file__ not git rev-parse) ===

In scripts/commit_guardian/_resolve_root.py:

    def find_project_root() -> Path:
        global _PROJECT_ROOT
        if _PROJECT_ROOT is not None:
            return _PROJECT_ROOT

        here = Path(__file__).resolve().parent  # <-- resolves symlink target
        for ancestor in [here, *here.parents]:
            if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
                _PROJECT_ROOT = ancestor
                return _PROJECT_ROOT

        _PROJECT_ROOT = here.parent.parent
        return _PROJECT_ROOT

The problem: in a deployed consumer layout, check_done_proof.py is symlinked
from the consumer's .leafcutter/ directory to the leafcutter-ai/ package:

    /consumer-project/.leafcutter/scripts/commit_guardian/check_done_proof.py
         → symlink → /home/.../leafcutter-ai/scripts/commit_guardian/check_done_proof.py

When Python resolves `Path(__file__).resolve()`, it follows the symlink and
returns the PACKAGE path, not the consumer project path.  Walking up from
the package's check_done_proof.py finds the leafcutter-ai/ git root (which
has its own .git and CLAUDE.md), not the consumer project root.

The fix: call `git rev-parse --show-toplevel` first.  This git command
always reports the root of the git repository that CONTAINS the current
working directory (the consumer project), regardless of symlinks.  Falling
back to __file__ path-walking only when git is unavailable.

=== Contract these tests enforce ===

  find_project_root() MUST:
  1. Call subprocess.run (or equivalent) with 'git rev-parse --show-toplevel'
     as the preferred resolution method.
  2. Return the path reported by git when git exits 0.
  3. Fall back to __file__ walking only when git returns non-zero or raises.

=== Red baseline ===

  All tests are RED because the current implementation never calls
  subprocess.run — it only uses Path(__file__).resolve().  The mock assertion
  `mock_run.assert_called_once()` (or `assert_called()`) fails because
  subprocess.run is never invoked.

=== Test isolation ===

  The module-level _PROJECT_ROOT cache is reset to None between tests using
  direct attribute assignment.  This ensures each test starts with a fresh
  resolution call rather than a cached result.
"""
from __future__ import annotations

import sys
import unittest
import unittest.mock
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Repo path wiring
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "scripts" / "commit_guardian"
sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

import _resolve_root  # noqa: E402
from _resolve_root import find_project_root  # noqa: E402


def _reset_cache() -> None:
    """Reset the module-level _PROJECT_ROOT cache to force fresh resolution."""
    _resolve_root._PROJECT_ROOT = None


# ---------------------------------------------------------------------------
# TestFindProjectRootGitPreferred — DEFECT M-4
# ---------------------------------------------------------------------------


class TestFindProjectRootGitPreferred(unittest.TestCase):
    """find_project_root() must prefer git rev-parse --show-toplevel.

    DEFECT M-4: the current implementation walks up from Path(__file__).resolve()
    without ever calling git, so symlinked deployments resolve the wrong root.
    """

    def setUp(self) -> None:
        """Reset the module cache before each test."""
        _reset_cache()

    def tearDown(self) -> None:
        """Reset the module cache after each test (cleanup)."""
        _reset_cache()

    def test_m4_find_project_root_calls_git_rev_parse(self) -> None:
        # covers: BO-2500b-1-i
        """find_project_root() must call 'git rev-parse --show-toplevel'.

        DEFECT M-4: the current implementation uses Path(__file__).resolve()
        and never calls subprocess.run.  This test mocks subprocess.run and
        asserts it is called with git rev-parse arguments.

        To make this green, update find_project_root() to try:
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=False
            )
            if result.returncode == 0:
                return Path(result.stdout.strip())
        before falling back to __file__-based path walking.
        """
        fake_root = "/fake/consumer/project"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_root + "\n"

        with unittest.mock.patch("subprocess.run", return_value=mock_result) as mock_run:
            _reset_cache()
            result = find_project_root()

        # Assert subprocess.run was called at least once.
        # DEFECT M-4: This assertion fails because subprocess.run is never called.
        self.assertTrue(
            mock_run.called,
            "DEFECT M-4: find_project_root() never called subprocess.run. "
            "It must call 'git rev-parse --show-toplevel' as the PREFERRED "
            "resolution method before falling back to __file__ path-walking. "
            "Fix: add a subprocess.run(['git', 'rev-parse', '--show-toplevel'], ...) "
            "call at the start of find_project_root().",
        )

        # Assert the call used git rev-parse --show-toplevel.
        call_args = mock_run.call_args
        cmd = call_args[0][0] if call_args[0] else call_args[1].get("args", [])
        cmd_str = " ".join(str(c) for c in cmd)
        self.assertIn("git", cmd_str, "subprocess.run must be called with 'git'.")
        self.assertIn("rev-parse", cmd_str, "subprocess.run must be called with 'rev-parse'.")
        self.assertIn("--show-toplevel", cmd_str, "subprocess.run must be called with '--show-toplevel'.")

    def test_m4_git_output_used_as_return_value(self) -> None:
        # covers: BO-2500b-1-i
        """find_project_root() must return the path from git rev-parse --show-toplevel.

        When git exits 0 and stdout contains a path, that path must be returned
        (not a path derived from Path(__file__)).  This ensures the consumer
        project root is returned in symlinked layouts.
        """
        # A fake consumer project root — NOT related to the leafcutter-ai package.
        fake_consumer_root = "/home/user/my-consumer-project"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fake_consumer_root + "\n"

        with unittest.mock.patch("subprocess.run", return_value=mock_result):
            _reset_cache()
            result = find_project_root()

        self.assertEqual(
            str(result),
            fake_consumer_root,
            f"DEFECT M-4: find_project_root() returned {result!r} instead of "
            f"{fake_consumer_root!r} (from git rev-parse --show-toplevel). "
            "The git output must be used as the return value when git exits 0.",
        )

    def test_m4_falls_back_when_git_fails(self) -> None:
        # covers: BO-2500b-1-i
        """find_project_root() must fall back to __file__ walking when git fails.

        When git rev-parse exits non-zero (e.g. not a git repo), the function
        must fall back to the __file__-based ancestor walking.  The fallback
        must still find a valid root (the current repo has .git and CLAUDE.md).
        """
        mock_result = MagicMock()
        mock_result.returncode = 128  # git error (not a git repository)
        mock_result.stdout = ""

        with unittest.mock.patch("subprocess.run", return_value=mock_result):
            _reset_cache()
            result = find_project_root()

        # The fallback must return a non-empty path that exists on disk.
        self.assertIsInstance(
            result,
            Path,
            "Fallback result must be a Path when git fails.",
        )
        self.assertTrue(
            result.exists(),
            f"Fallback result {result!r} must exist on disk. "
            "The __file__-based fallback must find the repo root.",
        )

    def test_m4_falls_back_when_git_raises_oserror(self) -> None:
        # covers: BO-2500b-1-i
        """find_project_root() must fall back gracefully when subprocess.run raises OSError.

        When git is not available (e.g. stripped Docker image), subprocess.run
        raises OSError.  The function must catch it and fall back to __file__
        path walking rather than propagating the error.

        To make this green, wrap the subprocess.run call in try/except OSError.
        """
        with unittest.mock.patch("subprocess.run", side_effect=OSError("git not found")):
            _reset_cache()
            try:
                result = find_project_root()
            except OSError as exc:
                self.fail(
                    f"DEFECT M-4: find_project_root() raised OSError({exc}) when "
                    "subprocess.run (git) raised. The fallback to __file__ path "
                    "walking must be triggered when git is unavailable — "
                    "wrap the subprocess.run call in try/except OSError.",
                )

        self.assertIsInstance(
            result,
            Path,
            "Fallback result must be a Path when git raises OSError.",
        )


if __name__ == "__main__":
    unittest.main()
