"""
MODULE: test_git_recovery
GOAL: Unit tests for templates/scripts/git_recovery.py covering the
    human-invoked-only gate, non-TTY exit, confirmation gate, and error
    handling policy required by AC BO-1600d-1.
BUSINESS CONTEXT: Verifies that the BO-1600d-1 acceptance criteria are
    satisfied: recovery never auto-runs, non-TTY exits without git write,
    confirmation gate blocks on non-"yes", "yes" proceeds past the gate,
    and subprocess/OS errors are caught and logged at WARNING level.
ARCHITECTURE: Pure unit tests using importlib.util to load the template
    script directly, unittest.mock for sys.stdin/builtins.input/subprocess,
    and unittest.TestCase. All tests complete in < 5 seconds with no
    filesystem side-effects and no actual git operations.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Bootstrap — load the template script by absolute path
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_MODULE_PATH = _REPO_ROOT / "templates" / "scripts" / "git_recovery.py"

spec = importlib.util.spec_from_file_location("git_recovery", _MODULE_PATH)
_mod = importlib.util.module_from_spec(spec)
sys.modules["git_recovery"] = _mod
spec.loader.exec_module(_mod)

main = _mod.main
run_status_probe = _mod.run_status_probe
parse_args = _mod.parse_args


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_probe_result():
    """Return a MagicMock that mimics a successful subprocess.run result."""
    mock_result = MagicMock()
    mock_result.stdout = ""
    mock_result.returncode = 0
    return mock_result


# ---------------------------------------------------------------------------
# Test 1 & 2: Recovery never auto-runs / non-TTY exits clean
# ---------------------------------------------------------------------------

class TestNonTTYExitsWithoutGitWrite(unittest.TestCase):
    """Verify no git subprocess call is made and exit is clean when not in a TTY."""

    @patch("subprocess.run")
    @patch("sys.stdin")
    def test_no_subprocess_call_when_not_tty(self, mock_stdin, mock_subprocess_run):
        """Non-TTY execution must not trigger any git subprocess calls.

        This is the core BO-1600d-1 guarantee: recovery never auto-runs.
        """
        mock_stdin.isatty.return_value = False

        with self.assertRaises(SystemExit) as ctx:
            main(["--repo", "/tmp"])

        self.assertEqual(ctx.exception.code, 0)
        mock_subprocess_run.assert_not_called()

    @patch("subprocess.run")
    @patch("sys.stdin")
    def test_exits_zero_non_tty(self, mock_stdin, mock_subprocess_run):
        """Exit code must be 0 when running non-interactively."""
        mock_stdin.isatty.return_value = False

        with self.assertRaises(SystemExit) as ctx:
            main(["--repo", "/tmp"])

        self.assertEqual(ctx.exception.code, 0)

    @patch("subprocess.run")
    @patch("sys.stdin")
    def test_prints_interactive_message_non_tty(self, mock_stdin, mock_subprocess_run):
        """An informative message must be printed when not attached to a TTY."""
        mock_stdin.isatty.return_value = False

        captured_output = []
        with self.assertRaises(SystemExit), patch("builtins.print") as mock_print:
            main(["--repo", "/tmp"])
            captured_output.extend(mock_print.call_args_list)

        # Collect all print calls
        printed = " ".join(
            str(call) for call in mock_print.call_args_list
        )
        self.assertIn("interactive", printed.lower())


# ---------------------------------------------------------------------------
# Test 3: Confirmation gate blocks on anything other than "yes"
# ---------------------------------------------------------------------------

class TestConfirmationGateBlocks(unittest.TestCase):
    """Confirmation gate must block (no post-gate subprocess calls) unless the
    user types exactly 'yes'."""

    @patch("subprocess.run")
    @patch("builtins.input", return_value="no")
    @patch("sys.stdin")
    def test_answer_no_makes_no_post_gate_subprocess_call(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Answering 'no' must not trigger any subprocess call after the probe."""
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = _make_probe_result()

        main(["--repo", "/tmp"])

        # subprocess.run called exactly once (the read-only probe) — no post-gate calls.
        mock_subprocess_run.assert_called_once()

    @patch("subprocess.run")
    @patch("builtins.input")
    @patch("sys.stdin")
    def test_answer_empty_makes_no_post_gate_subprocess_call(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Answering with an empty string must not proceed past the gate."""
        mock_stdin.isatty.return_value = True
        mock_input.return_value = ""
        mock_subprocess_run.return_value = _make_probe_result()

        main(["--repo", "/tmp"])

        # Only the probe — no additional subprocess calls after the gate.
        mock_subprocess_run.assert_called_once()

    @patch("subprocess.run")
    @patch("builtins.input", return_value="YES")
    @patch("sys.stdin")
    def test_answer_uppercase_yes_makes_no_post_gate_subprocess_call(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Gate must be case-sensitive: 'YES' is not accepted as confirmation."""
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = _make_probe_result()

        main(["--repo", "/tmp"])

        mock_subprocess_run.assert_called_once()


# ---------------------------------------------------------------------------
# Test 4: Confirmation gate accepts "yes"
# ---------------------------------------------------------------------------

class TestConfirmationGateAcceptsYes(unittest.TestCase):
    """Confirmation gate must allow the function to proceed when user types 'yes'."""

    @patch("subprocess.run")
    @patch("builtins.input", return_value="yes")
    @patch("sys.stdin")
    def test_yes_proceeds_past_gate(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Answering 'yes' must not raise SystemExit and must reach the input() call."""
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = _make_probe_result()

        # Must return normally — no SystemExit, no early abort.
        main(["--repo", "/tmp"])

        # Confirm that the gate was reached (input() was called).
        mock_input.assert_called_once()

    @patch("subprocess.run")
    @patch("builtins.input", return_value="yes")
    @patch("sys.stdin")
    def test_yes_does_not_raise_system_exit(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Answering 'yes' must not trigger sys.exit() at the gate."""
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = _make_probe_result()

        try:
            main(["--repo", "/tmp"])
        except SystemExit as exc:
            self.fail(f"main() raised SystemExit({exc.code}) unexpectedly after 'yes' answer")


# ---------------------------------------------------------------------------
# Test 5: Error handling — subprocess/OS errors are caught and logged
# ---------------------------------------------------------------------------

class TestErrorHandlingSubprocessFailure(unittest.TestCase):
    """Subprocess and OS errors must be caught, logged at WARNING, and not
    propagate as unhandled exceptions."""

    @patch("sys.stdin")
    def test_subprocess_error_logged_not_propagated(self, mock_stdin):
        """CalledProcessError from the probe must be logged at WARNING and not raised."""
        mock_stdin.isatty.return_value = True

        exc = subprocess.CalledProcessError(128, ["git", "status"])

        with patch("subprocess.run", side_effect=exc):
            # assertLogs verifies at least one WARNING was emitted by the logger.
            with self.assertLogs("git_recovery", level="WARNING") as log_ctx:
                # Must NOT raise — exception is caught inside run_status_probe.
                main(["--repo", "/tmp"])

        self.assertTrue(
            any("WARNING" in line for line in log_ctx.output),
            "Expected at least one WARNING log entry; got: %s" % log_ctx.output,
        )

    @patch("sys.stdin")
    def test_os_error_logged_not_propagated(self, mock_stdin):
        """OSError from the probe must be logged at WARNING and not raised."""
        mock_stdin.isatty.return_value = True

        with patch("subprocess.run", side_effect=OSError("git: no such file")):
            with self.assertLogs("git_recovery", level="WARNING") as log_ctx:
                # Must NOT raise.
                main(["--repo", "/tmp"])

        self.assertTrue(
            any("WARNING" in line for line in log_ctx.output),
            "Expected at least one WARNING log entry; got: %s" % log_ctx.output,
        )

    @patch("sys.stdin")
    def test_subprocess_error_returns_gracefully(self, mock_stdin):
        """After a probe failure, main() must return cleanly without further calls."""
        mock_stdin.isatty.return_value = True
        exc = subprocess.CalledProcessError(128, ["git", "status"])

        with patch("subprocess.run", side_effect=exc):
            with self.assertLogs("git_recovery", level="WARNING"):
                result = main(["--repo", "/tmp"])

        # main() returns None on graceful abort.
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
