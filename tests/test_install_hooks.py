"""Tests for install_hooks() in build_helpers.py.

These tests are written BEFORE the implementation exists (TDD, test-first).
All tests are expected to be RED (failing) until python-coder implements
install_hooks() in build_helpers.py.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "scripts" / "build_helpers.py"


def _get_install_hooks():
    """Late-load install_hooks so tests can fail at test-run time, not collection."""
    spec = importlib.util.spec_from_file_location("build_helpers_ih", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "install_hooks")


class TestInstallHooksNoPrecommitBinary(unittest.TestCase):
    """install_hooks() returns 'skipped (pre-commit not found)' when pre-commit is absent."""

    def test_install_hooks_no_precommit_binary(self):
        """When pre-commit is not on PATH, install_hooks must skip gracefully.

        Must implement:
            build_helpers.install_hooks(target_root: Path, dry_run: bool) -> str
            - shutil.which("pre-commit") returns None → return "skipped (pre-commit not found)"
            - must NOT call subprocess.run with pre-commit install
        """
        install_hooks = _get_install_hooks()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with patch("shutil.which", return_value=None) as mock_which:
                with patch("subprocess.run") as mock_run:
                    result = install_hooks(target, dry_run=False)

        self.assertEqual(result, "skipped (pre-commit not found)")
        mock_run.assert_not_called()


class TestInstallHooksDryRun(unittest.TestCase):
    """install_hooks() with dry_run=True prints a message and does nothing."""

    def test_install_hooks_dry_run(self):
        """When dry_run=True, install_hooks must return 'dry-run' without running any subprocess.

        Must implement:
            - if dry_run: print "[DRY-RUN] would run pre-commit install" and return "dry-run"
            - subprocess.run must NOT be called
        """
        install_hooks = _get_install_hooks()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with patch("shutil.which", return_value="/usr/bin/pre-commit"):
                with patch("subprocess.run") as mock_run:
                    result = install_hooks(target, dry_run=True)

        self.assertEqual(result, "dry-run")
        mock_run.assert_not_called()


class TestInstallHooksDefaultHooksPathIsUnset(unittest.TestCase):
    """When core.hooksPath is '.git/hooks', install_hooks unsets it and proceeds."""

    def test_install_hooks_default_hookspath_is_unset(self):
        """When core.hooksPath is redundant default '.git/hooks', must unset it and install.

        Must implement:
            - subprocess.run(["git", "-C", ..., "config", "--get", "core.hooksPath"])
              returns CompletedProcess with stdout=".git/hooks\\n" and returncode=0
            - git config --unset core.hooksPath is called
            - pre-commit install is called
            - return value is "installed"
        """
        install_hooks = _get_install_hooks()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)

            def mock_run(cmd, **kwargs):
                result = MagicMock()
                if isinstance(cmd, list) and "config" in cmd and "--get" in cmd and "core.hooksPath" in cmd:
                    result.returncode = 0
                    result.stdout = ".git/hooks\n"
                elif isinstance(cmd, list) and "config" in cmd and "--unset" in cmd:
                    result.returncode = 0
                    result.stdout = ""
                elif isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == "pre-commit":
                    result.returncode = 0
                    result.stdout = ""
                else:
                    result.returncode = 0
                    result.stdout = ""
                return result

            with patch("shutil.which", return_value="/usr/bin/pre-commit"):
                with patch("subprocess.run", side_effect=mock_run) as mock_sub:
                    result = install_hooks(target, dry_run=False)

        self.assertEqual(result, "installed")

        # Verify unset was called
        unset_calls = [
            c for c in mock_sub.call_args_list
            if isinstance(c.args[0], list) and "--unset" in c.args[0] and "core.hooksPath" in c.args[0]
        ]
        self.assertTrue(len(unset_calls) >= 1, "git config --unset core.hooksPath was not called")

        # Verify pre-commit install was called
        precommit_calls = [
            c for c in mock_sub.call_args_list
            if isinstance(c.args[0], list) and len(c.args[0]) > 0 and c.args[0][0] == "pre-commit"
        ]
        self.assertTrue(len(precommit_calls) >= 1, "pre-commit install was not called")


class TestInstallHooksCustomHooksPathIsSkipped(unittest.TestCase):
    """When core.hooksPath is a custom path, install_hooks warns and skips."""

    def test_install_hooks_custom_hookspath_is_skipped(self):
        """When core.hooksPath is '.husky' (non-default), must skip pre-commit install.

        Must implement:
            - git config --get core.hooksPath returns ".husky"
            - install_hooks does NOT call pre-commit install
            - return value is "skipped (custom hooksPath)"
        """
        install_hooks = _get_install_hooks()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)

            def mock_run(cmd, **kwargs):
                result = MagicMock()
                if isinstance(cmd, list) and "config" in cmd and "--get" in cmd and "core.hooksPath" in cmd:
                    result.returncode = 0
                    result.stdout = ".husky\n"
                else:
                    result.returncode = 0
                    result.stdout = ""
                return result

            with patch("shutil.which", return_value="/usr/bin/pre-commit"):
                with patch("subprocess.run", side_effect=mock_run) as mock_sub:
                    result = install_hooks(target, dry_run=False)

        self.assertEqual(result, "skipped (custom hooksPath)")

        # Verify pre-commit install was NOT called
        precommit_calls = [
            c for c in mock_sub.call_args_list
            if isinstance(c.args[0], list) and len(c.args[0]) > 0 and c.args[0][0] == "pre-commit"
        ]
        self.assertEqual(len(precommit_calls), 0, "pre-commit install should NOT have been called")


class TestInstallHooksHooksPathAbsentProceeds(unittest.TestCase):
    """When core.hooksPath is absent (returncode=1), install_hooks proceeds normally."""

    def test_install_hooks_hookspath_absent_proceeds(self):
        """When git config --get core.hooksPath returns non-zero (key absent), must proceed.

        Must implement:
            - git config --get core.hooksPath returns returncode=1 (key absent)
            - install_hooks calls pre-commit install
            - return value is "installed"
        """
        install_hooks = _get_install_hooks()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)

            def mock_run(cmd, **kwargs):
                result = MagicMock()
                if isinstance(cmd, list) and "config" in cmd and "--get" in cmd and "core.hooksPath" in cmd:
                    result.returncode = 1  # key absent
                    result.stdout = ""
                elif isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == "pre-commit":
                    result.returncode = 0
                    result.stdout = ""
                else:
                    result.returncode = 0
                    result.stdout = ""
                return result

            with patch("shutil.which", return_value="/usr/bin/pre-commit"):
                with patch("subprocess.run", side_effect=mock_run) as mock_sub:
                    result = install_hooks(target, dry_run=False)

        self.assertEqual(result, "installed")

        # Verify pre-commit install was called
        precommit_calls = [
            c for c in mock_sub.call_args_list
            if isinstance(c.args[0], list) and len(c.args[0]) > 0 and c.args[0][0] == "pre-commit"
        ]
        self.assertTrue(len(precommit_calls) >= 1, "pre-commit install was not called")


class TestInstallHooksPrecommitFailureIsNonfatal(unittest.TestCase):
    """When pre-commit install raises CalledProcessError, install_hooks returns 'failed' without raising."""

    def test_install_hooks_precommit_failure_is_nonfatal(self):
        """pre-commit install failure must be caught and return 'failed', not propagate.

        Must implement:
            - pre-commit install raises subprocess.CalledProcessError
            - install_hooks catches it and returns "failed"
            - no exception propagates to caller
        """
        install_hooks = _get_install_hooks()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)

            def mock_run(cmd, **kwargs):
                result = MagicMock()
                if isinstance(cmd, list) and "config" in cmd and "--get" in cmd and "core.hooksPath" in cmd:
                    result.returncode = 1  # key absent
                    result.stdout = ""
                    return result
                elif isinstance(cmd, list) and len(cmd) > 0 and cmd[0] == "pre-commit":
                    raise subprocess.CalledProcessError(
                        returncode=1,
                        cmd=cmd,
                        output=b"",
                        stderr=b"pre-commit: error: could not install hooks",
                    )
                return result

            with patch("shutil.which", return_value="/usr/bin/pre-commit"):
                with patch("subprocess.run", side_effect=mock_run):
                    # Must NOT raise — failure is non-fatal
                    result = install_hooks(target, dry_run=False)

        self.assertEqual(result, "failed")


if __name__ == "__main__":
    unittest.main()
