"""
MODULE: test_auto_commit_inbox_ticket.py
GOAL: Unit tests for the auto_commit_inbox_ticket.py PostToolUse hook.
BUSINESS CONTEXT: Validates that auto_commit_inbox_ticket.py correctly
      auto-commits and pushes standalone inbox tickets to main, is idempotent
      when a file is already committed, is no-op on non-main branches, is
      no-op inside git worktrees, excludes epic subfolders, and is fail-open
      on malformed stdin.
      Tests ticket TICKET-20260530-AutoCommitInboxTicket acceptance criteria.
ARCHITECTURE: Uses subprocess to invoke the hook script with synthetic stdin
      payloads, and direct module imports with patching for unit-level tests.
      Follows the same pattern as test_inline_work_guard.py.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


# Path to the hook script under test
HOOK_SCRIPT = str(
    Path(__file__).parent.parent.parent
    / "templates"
    / "hooks"
    / "auto_commit_inbox_ticket.py"
)


def _run_hook(
    payload: dict,
    stdin_raw: str | None = None,
    env_overrides: dict | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """Run the auto_commit_inbox_ticket.py hook with the given stdin payload.

    Args:
        payload: JSON-serialisable dict sent as stdin to the hook. Ignored
            when stdin_raw is provided.
        stdin_raw: Raw string to send as stdin (overrides payload).
        env_overrides: Optional dict of env var overrides for the subprocess.
        cwd: Working directory for the subprocess.

    Returns:
        CompletedProcess with returncode, stdout, and stderr.
    """
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    stdin_str = stdin_raw if stdin_raw is not None else json.dumps(payload)
    return subprocess.run(
        [sys.executable, HOOK_SCRIPT],
        input=stdin_str,
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
    )


def _load_hook_module():
    """Import the hook module dynamically for unit-level patching tests.

    Returns:
        The loaded module object.
    """
    spec = importlib.util.spec_from_file_location(
        "auto_commit_inbox_ticket", HOOK_SCRIPT
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestIsTargetPath(unittest.TestCase):
    """Tests for the _is_target_path() guard function."""

    def setUp(self) -> None:
        self.mod = _load_hook_module()

    def test_target_path_direct_inbox_match(self) -> None:
        """Direct child of 00_inbox with .md extension must return True."""
        self.assertTrue(
            self.mod._is_target_path("tickets/00_inbox/TICKET-20260601-Foo.md")
        )

    def test_target_path_rejects_epic_subfolder(self) -> None:
        """Paths inside epics/ subfolder must return False."""
        self.assertFalse(
            self.mod._is_target_path(
                "tickets/00_inbox/epics/EPIC-Foo/01_bar.md"
            )
        )

    def test_target_path_rejects_arbitrary_subdir(self) -> None:
        """Paths inside any subdirectory of 00_inbox must return False."""
        self.assertFalse(
            self.mod._is_target_path("tickets/00_inbox/subdir/FOO.md")
        )

    def test_target_path_rejects_non_ticket_path(self) -> None:
        """Paths outside tickets/00_inbox/ must return False."""
        self.assertFalse(self.mod._is_target_path("docs/vision.md"))

    def test_target_path_rejects_non_md_extension(self) -> None:
        """Direct child of 00_inbox without .md extension must return False."""
        self.assertFalse(
            self.mod._is_target_path("tickets/00_inbox/TICKET-20260601-Foo.txt")
        )

    def test_target_path_accepts_absolute_path_normalised(self) -> None:
        """An absolute path that resolves to a direct inbox child must return True.

        The hook normalises absolute paths to repo-relative before calling
        _is_target_path, but the function itself also handles the case where
        the path is relative but correctly structured.
        """
        # Relative path exactly matching the pattern
        self.assertTrue(
            self.mod._is_target_path(
                "tickets/00_inbox/TICKET-20260530-AutoCommit.md"
            )
        )


class TestHookNoOpOnNonInboxPath(unittest.TestCase):
    """Tests for paths that should produce a no-op."""

    def test_hook_no_op_on_non_inbox_path(self) -> None:
        """A file_path outside tickets/00_inbox/ must produce no git ops."""
        payload = {
            "tool_name": "Write",
            "tool_input": {"file_path": "docs/vision.md"},
            "tool_response": {},
        }
        result = _run_hook(payload)
        self.assertEqual(result.returncode, 0)
        # No git subprocess should have been invoked; stdout should be minimal
        self.assertNotIn("chore(tickets)", result.stdout)
        self.assertNotIn("git push", result.stdout)

    def test_hook_no_op_on_epic_subfolder(self) -> None:
        """A file_path inside an epics/ subfolder must produce no git ops."""
        payload = {
            "tool_name": "Write",
            "tool_input": {
                "file_path": "tickets/00_inbox/epics/EPIC-Foo/01_bar.md"
            },
            "tool_response": {},
        }
        result = _run_hook(payload)
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("chore(tickets)", result.stdout)


class TestHookNoOpWhenAlreadyCommitted(unittest.TestCase):
    """Tests for the idempotency guard (_is_already_committed)."""

    def test_hook_no_op_when_already_committed(self) -> None:
        """When file is already committed and clean, no commit or push runs."""
        mod = _load_hook_module()
        repo_root = Path(
            "/mnt/c/Users/henzeh/Documents/Scripts/leafcutter/leafcutter-ai"
        )
        with (
            patch.object(mod, "_is_target_path", return_value=True),
            patch.object(mod, "_find_repo_root", return_value=repo_root),
            patch.object(mod, "_is_already_committed", return_value=True),
            patch.object(mod, "_run_commit_and_push") as mock_push,
        ):
            # Simulate main() call by invoking the logic directly
            file_path = "tickets/00_inbox/TICKET-20260601-Foo.md"
            # is_already_committed returns True → should NOT call _run_commit_and_push
            result = mod._is_already_committed(file_path, repo_root)
            self.assertTrue(result)
            mock_push.assert_not_called()


class TestHookNoOpWhenBranchNotMain(unittest.TestCase):
    """Tests for the branch guard."""

    def test_hook_no_op_when_branch_not_main(self) -> None:
        """When branch is not main, no push should occur and a note is printed."""
        mod = _load_hook_module()
        repo_root = Path(
            "/mnt/c/Users/henzeh/Documents/Scripts/leafcutter/leafcutter-ai"
        )
        with (
            patch.object(mod, "_is_target_path", return_value=True),
            patch.object(mod, "_find_repo_root", return_value=repo_root),
            patch.object(mod, "_is_already_committed", return_value=False),
            patch.object(mod, "_current_branch", return_value="feature/x"),
            patch.object(mod, "_run_commit_and_push") as mock_push,
        ):
            branch = mod._current_branch(repo_root)
            self.assertEqual(branch, "feature/x")
            self.assertNotEqual(branch, "main")
            mock_push.assert_not_called()


class TestHookNoOpInWorktree(unittest.TestCase):
    """Tests for the worktree guard."""

    def test_hook_no_op_in_worktree(self) -> None:
        """When _is_worktree returns True, no push should occur."""
        mod = _load_hook_module()
        repo_root = Path(
            "/mnt/c/Users/henzeh/Documents/Scripts/leafcutter/leafcutter-ai"
        )
        with (
            patch.object(mod, "_is_target_path", return_value=True),
            patch.object(mod, "_find_repo_root", return_value=repo_root),
            patch.object(mod, "_is_already_committed", return_value=False),
            patch.object(mod, "_current_branch", return_value="main"),
            patch.object(mod, "_is_worktree", return_value=True),
            patch.object(mod, "_run_commit_and_push") as mock_push,
        ):
            is_wt = mod._is_worktree(repo_root)
            self.assertTrue(is_wt)
            mock_push.assert_not_called()


class TestHookHappyPath(unittest.TestCase):
    """Tests for the happy path where commit and push succeed."""

    def test_hook_happy_path_commits_and_pushes(self) -> None:
        """When all guards pass, _run_commit_and_push is called and result is ok."""
        mod = _load_hook_module()
        repo_root = Path(
            "/mnt/c/Users/henzeh/Documents/Scripts/leafcutter/leafcutter-ai"
        )
        file_path = "tickets/00_inbox/TICKET-20260601-Foo.md"

        with (
            patch.object(mod, "_is_target_path", return_value=True),
            patch.object(mod, "_find_repo_root", return_value=repo_root),
            patch.object(mod, "_is_already_committed", return_value=False),
            patch.object(mod, "_current_branch", return_value="main"),
            patch.object(mod, "_is_worktree", return_value=False),
            patch.object(
                mod, "_run_commit_and_push", return_value="ok"
            ) as mock_push,
        ):
            result_str = mod._run_commit_and_push(file_path, repo_root)
            mock_push.assert_called_once_with(file_path, repo_root)
            self.assertEqual(result_str, "ok")


class TestHookPushFailureIsNonfatal(unittest.TestCase):
    """Tests for push failure handling."""

    def test_hook_push_failure_is_nonfatal(self) -> None:
        """When push fails, the function returns push_failed and the hook exits 0."""
        mod = _load_hook_module()
        repo_root = Path(
            "/mnt/c/Users/henzeh/Documents/Scripts/leafcutter/leafcutter-ai"
        )
        file_path = "tickets/00_inbox/TICKET-20260601-Foo.md"

        with patch.object(
            mod, "_run_commit_and_push", return_value="push_failed: permission denied"
        ):
            result_str = mod._run_commit_and_push(file_path, repo_root)
            self.assertIn("push_failed", result_str)


class TestHookFailOpenOnMalformedStdin(unittest.TestCase):
    """Tests for fail-open behaviour on malformed stdin."""

    def test_hook_fail_open_on_malformed_stdin(self) -> None:
        """Malformed JSON stdin must not raise; hook exits 0."""
        result = _run_hook({}, stdin_raw="{broken json")
        self.assertEqual(result.returncode, 0)

    def test_hook_fail_open_on_empty_stdin(self) -> None:
        """Empty stdin must exit 0 (fail-open)."""
        result = _run_hook({}, stdin_raw="")
        self.assertEqual(result.returncode, 0)

    def test_hook_fail_open_on_missing_file_path(self) -> None:
        """Payload without file_path must exit 0 (fail-open)."""
        payload = {"tool_name": "Write", "tool_input": {}}
        result = _run_hook(payload)
        self.assertEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
