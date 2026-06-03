"""
Tests for _bootstrap() in templates/scripts/setup_ticket_worktree.py.

These are TDD stubs written BEFORE python-coder implements the symlink feature.
All new tests in this file are expected to be RED (failing) until python-coder
replaces the shutil.copy call for .env with os.symlink + OSError fallback.

Tests use unittest.mock.patch to avoid filesystem or subprocess calls.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SETUP_SCRIPT = _REPO_ROOT / "templates" / "scripts" / "setup_ticket_worktree.py"


def _load_setup_module():
    """Load setup_ticket_worktree from its absolute path."""
    scripts_dir = str(_REPO_ROOT / "templates" / "scripts")
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    spec = importlib.util.spec_from_file_location(
        "setup_ticket_worktree", _SETUP_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["setup_ticket_worktree"] = mod
    spec.loader.exec_module(mod)
    return mod


class TestBootstrapEnvIsSymlinked(unittest.TestCase):
    """_bootstrap() creates a symlink for .env, not a copy."""

    def test_bootstrap_env_is_symlinked(self):
        """
        Given the main_repo/.env file exists,
        When _bootstrap() is called,
        Then os.symlink is called with (main_repo/.env, worktree/.env)
        And shutil.copy is NOT called for .env.
        """
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        with (
            patch.object(mod.os, "symlink") as mock_symlink,
            patch.object(mod.shutil, "copy") as mock_copy,
            patch.object(mod.subprocess, "run"),
        ):
            mod._bootstrap(main_repo, worktree)

        # os.symlink must be called for .env
        mock_symlink.assert_any_call(main_repo / ".env", worktree / ".env")

        # shutil.copy must NOT be called for .env
        copy_calls_for_env = [
            c for c in mock_copy.call_args_list if ".env" in str(c)
        ]
        self.assertEqual(
            copy_calls_for_env,
            [],
            "shutil.copy should not be called for .env when symlink succeeds",
        )


class TestBootstrapEnvSymlinkSkippedWhenMissing(unittest.TestCase):
    """_bootstrap() silently skips .env when the source does not exist."""

    def test_bootstrap_env_symlink_skipped_when_missing(self):
        """
        Given main_repo/.env does not exist (os.symlink raises FileNotFoundError),
        When _bootstrap() is called,
        Then no exception propagates and no .env symlink/copy is created.
        """
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        with (
            patch.object(
                mod.os, "symlink", side_effect=FileNotFoundError("no such file")
            ) as mock_symlink,
            patch.object(mod.shutil, "copy") as mock_copy,
            patch.object(mod.subprocess, "run"),
        ):
            # Must not raise
            mod._bootstrap(main_repo, worktree)

        # shutil.copy should not be called for .env as a fallback for
        # FileNotFoundError (source simply doesn't exist)
        copy_calls_for_env = [
            c for c in mock_copy.call_args_list if ".env" in str(c)
        ]
        self.assertEqual(
            copy_calls_for_env,
            [],
            "shutil.copy should not be called for .env when source is missing",
        )


class TestBootstrapEnvFallbackOnOSError(unittest.TestCase):
    """_bootstrap() falls back to shutil.copy when os.symlink raises OSError."""

    def test_bootstrap_env_fallback_on_oserror(self):
        """
        Given os.symlink raises OSError (e.g. WinError 1314 or EPERM),
        When _bootstrap() is called,
        Then shutil.copy is called for .env as fallback
        And a warning is printed to stderr.
        """
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        win_err = OSError(1314, "A required privilege is not held by the client")

        import io

        fake_stderr = io.StringIO()

        with (
            patch.object(mod.os, "symlink", side_effect=win_err),
            patch.object(mod.shutil, "copy") as mock_copy,
            patch.object(mod.subprocess, "run"),
            patch("sys.stderr", fake_stderr),
        ):
            mod._bootstrap(main_repo, worktree)

        # shutil.copy must be called for .env as fallback
        mock_copy.assert_any_call(main_repo / ".env", worktree / ".env")

        # A warning must have been written to stderr
        warning_output = fake_stderr.getvalue()
        self.assertTrue(
            len(warning_output) > 0,
            "A warning should be printed to stderr when falling back from symlink to copy",
        )


class TestBootstrapMcpJsonStillCopied(unittest.TestCase):
    """_bootstrap() always copies .mcp.json, never symlinks it."""

    def test_bootstrap_mcp_json_still_copied(self):
        """
        Given main_repo/.mcp.json exists,
        When _bootstrap() is called,
        Then shutil.copy is called for .mcp.json (regardless of the .env path).
        """
        mod = _load_setup_module()

        main_repo = Path("/fake/main")
        worktree = Path("/fake/worktree")

        with (
            patch.object(mod.os, "symlink"),
            patch.object(mod.shutil, "copy") as mock_copy,
            patch.object(mod.subprocess, "run"),
        ):
            mod._bootstrap(main_repo, worktree)

        # shutil.copy must be called for .mcp.json
        mock_copy.assert_any_call(main_repo / ".mcp.json", worktree / ".mcp.json")


if __name__ == "__main__":
    unittest.main()
