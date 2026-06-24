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
    """Late-load install_hooks so tests can fail at test-run time, not collection.

    Returns:
        Tuple of (install_hooks callable, module object).  The module is exposed
        so callers can patch internal functions (e.g. _resolve_precommit_cmd)
        via unittest.mock.patch.object(mod, ...) when shutil.which alone is not
        sufficient to control all detection fallbacks.
    """
    _scripts_dir = str(_MODULE_PATH.parent)
    if _scripts_dir not in sys.path:
        sys.path.insert(0, _scripts_dir)
    spec = importlib.util.spec_from_file_location("build_helpers_ih", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, "install_hooks"), mod


class TestInstallHooksNoPrecommitBinary(unittest.TestCase):
    """install_hooks() returns 'skipped (pre-commit not found)' when pre-commit is absent."""

    def test_install_hooks_no_precommit_binary(self):
        """When pre-commit is not on PATH, install_hooks must skip gracefully.

        Must implement:
            build_helpers.install_hooks(target_root: Path, dry_run: bool) -> str
            - _resolve_precommit_cmd() returns None → return "skipped (pre-commit not found)"
            - must NOT call subprocess.run with pre-commit install

        Note: _resolve_precommit_cmd is patched directly (rather than shutil.which)
        because it has three detection fallbacks: shutil.which, importlib find_spec,
        and known install paths.  Patching the composed resolver is the correct
        isolation boundary.
        """
        install_hooks, mod = _get_install_hooks()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)
            with patch.object(mod, "_resolve_precommit_cmd", return_value=None):
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
        install_hooks, mod = _get_install_hooks()
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
        install_hooks, mod = _get_install_hooks()
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
        install_hooks, mod = _get_install_hooks()
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
        install_hooks, mod = _get_install_hooks()
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


class TestResolvePrecommitCmdKnownPaths(unittest.TestCase):
    """_resolve_precommit_cmd() skips a known-path candidate whose --version probe fails."""

    def test_resolve_precommit_cmd_skips_nonexecutable_known_path(self):
        """When shutil.which and find_spec return None and the only known-path candidate
        has is_file()=True but --version exits non-zero, _resolve_precommit_cmd returns None.

        Patches:
            - shutil.which -> None (tier 1 finds nothing)
            - importlib.util.find_spec -> None (tier 2 finds nothing)
            - _precommit_known_paths -> yields one fake path with is_file()=True
            - subprocess.run -> returns CompletedProcess with returncode=1 (bad binary)

        Asserts:
            - _resolve_precommit_cmd() returns None (broken candidate is skipped)
        """
        install_hooks, mod = _get_install_hooks()

        fake_path = MagicMock(spec=Path)
        fake_path.is_file.return_value = True
        fake_path.__str__ = lambda self: "/fake/.local/bin/pre-commit"

        probe_result = MagicMock()
        probe_result.returncode = 1

        with patch("shutil.which", return_value=None):
            with patch("importlib.util.find_spec", return_value=None):
                with patch.object(mod, "_precommit_known_paths", return_value=iter([fake_path])):
                    with patch("subprocess.run", return_value=probe_result):
                        result = mod._resolve_precommit_cmd()

        self.assertIsNone(result)


class TestInstallHooksPrecommitFailureIsNonfatal(unittest.TestCase):
    """When pre-commit install raises CalledProcessError, install_hooks returns 'failed' without raising."""

    def test_install_hooks_precommit_failure_is_nonfatal(self):
        # covers: BP-007
        """pre-commit install failure must be caught and return 'failed', not propagate.

        Exercises BP-007's loud-failure clause: when target_root IS a git repo
        and 'pre-commit install' genuinely fails, install_hooks returns 'failed'.
        The mock therefore reports the target as a git repo (rev-parse --git-dir
        exits 0) so execution reaches the pre-commit step rather than being
        short-circuited by the not-a-git-repo guard.

        Must implement:
            - pre-commit install raises subprocess.CalledProcessError
            - install_hooks catches it and returns "failed"
            - no exception propagates to caller
        """
        install_hooks, mod = _get_install_hooks()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp)

            def mock_run(cmd, **kwargs):
                result = MagicMock()
                if isinstance(cmd, list) and "config" in cmd and "--get" in cmd and "core.hooksPath" in cmd:
                    result.returncode = 1  # key absent
                    result.stdout = ""
                    return result
                if isinstance(cmd, list) and "rev-parse" in cmd and "--git-dir" in cmd:
                    result.returncode = 0  # target IS a git repo (BP-007 guard passes)
                    result.stdout = ".git"
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
