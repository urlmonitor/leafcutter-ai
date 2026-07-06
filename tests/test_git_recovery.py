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
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, call, patch


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
plan_recovery_actions = _mod.plan_recovery_actions
print_recovery_plan = _mod.print_recovery_plan
execute_recovery_plan = _mod.execute_recovery_plan
RecoveryAction = _mod.RecoveryAction


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


# ---------------------------------------------------------------------------
# Test 6: Dry-run-first behavior (BO-1600d-2)
# ---------------------------------------------------------------------------

class TestDryRunFirstBehavior(unittest.TestCase):
    """Verify the dry-run-first behavior introduced by BO-1600d-2.

    In default mode (no --execute):
    - The plan is always printed before any git write.
    - Answering anything other than "yes" makes zero post-probe git writes.
    - Answering "yes" triggers execution (more than one subprocess.run call).

    With --execute flag:
    - No interactive prompt is shown.
    - Recovery steps are executed (more than one subprocess.run call).

    Invariant:
    - The exact same plan object is passed to both print_recovery_plan and
      execute_recovery_plan, guaranteeing what was printed is what is executed.
    """

    def _make_probe_result(self):
        """Return a MagicMock that mimics a successful subprocess.run result."""
        mock_result = MagicMock()
        mock_result.stdout = ""
        mock_result.returncode = 0
        return mock_result

    # ------------------------------------------------------------------
    # Test 6-1: default mode prints the plan
    # ------------------------------------------------------------------

    @patch("git_recovery.print_recovery_plan")
    @patch("subprocess.run")
    @patch("builtins.input", return_value="no")
    @patch("sys.stdin")
    def test_default_mode_prints_plan(
        self, mock_stdin, mock_input, mock_subprocess_run, mock_print_plan
    ):
        """In default mode, print_recovery_plan must be called at least once."""
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = self._make_probe_result()

        main(["--repo", "/tmp"])

        self.assertGreaterEqual(
            mock_print_plan.call_count,
            1,
            "print_recovery_plan was not called in default (no --execute) mode",
        )

    # ------------------------------------------------------------------
    # Test 6-2: default mode with "no" answer makes no git writes
    # ------------------------------------------------------------------

    @patch("subprocess.run")
    @patch("builtins.input", return_value="no")
    @patch("sys.stdin")
    def test_default_mode_no_git_writes_on_no(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Answering 'no' must result in exactly one subprocess.run call (the probe)."""
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = self._make_probe_result()

        main(["--repo", "/tmp"])

        # Only the status probe — no execute calls.
        mock_subprocess_run.assert_called_once()

    # ------------------------------------------------------------------
    # Test 6-3: interactive "yes" executes the plan
    # ------------------------------------------------------------------

    @patch("subprocess.run")
    @patch("builtins.input", return_value="yes")
    @patch("sys.stdin")
    def test_interactive_yes_executes_plan(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Answering 'yes' must trigger execution: subprocess.run called > once."""
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = self._make_probe_result()

        main(["--repo", "/tmp"])

        self.assertGreater(
            mock_subprocess_run.call_count,
            1,
            "Expected more than one subprocess.run call after 'yes' (probe + execute steps)",
        )

    # ------------------------------------------------------------------
    # Test 6-4: --execute flag skips interactive prompt
    # ------------------------------------------------------------------

    @patch("subprocess.run")
    @patch("builtins.input")
    @patch("sys.stdin")
    def test_execute_flag_skips_interactive_prompt(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """With --execute, builtins.input must NOT be called (no interactive prompt)."""
        mock_stdin.isatty.return_value = False  # non-TTY; --execute bypasses the guard
        mock_subprocess_run.return_value = self._make_probe_result()

        main(["--repo", "/tmp", "--execute"])

        mock_input.assert_not_called()

    # ------------------------------------------------------------------
    # Test 6-5: --execute flag makes git writes
    # ------------------------------------------------------------------

    @patch("subprocess.run")
    @patch("sys.stdin")
    def test_execute_flag_makes_writes(self, mock_stdin, mock_subprocess_run):
        """With --execute, subprocess.run must be called more than once (probe + steps)."""
        mock_stdin.isatty.return_value = False  # non-TTY; --execute bypasses the guard
        mock_subprocess_run.return_value = self._make_probe_result()

        main(["--repo", "/tmp", "--execute"])

        self.assertGreater(
            mock_subprocess_run.call_count,
            1,
            "Expected more than one subprocess.run call with --execute (probe + fetch step)",
        )

    # ------------------------------------------------------------------
    # Test 6-6: the same plan object is passed to print and execute
    # ------------------------------------------------------------------

    @patch("git_recovery.execute_recovery_plan")
    @patch("git_recovery.print_recovery_plan")
    @patch("subprocess.run")
    @patch("builtins.input", return_value="yes")
    @patch("sys.stdin")
    def test_executed_plan_is_same_object_as_printed_plan(
        self,
        mock_stdin,
        mock_input,
        mock_subprocess_run,
        mock_print_plan,
        mock_execute_plan,
    ):
        """The plan object passed to print_recovery_plan must be identical (is) to
        the one passed to execute_recovery_plan."""
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = self._make_probe_result()

        main(["--repo", "/tmp"])

        # Both must have been called.
        self.assertTrue(mock_print_plan.called, "print_recovery_plan was not called")
        self.assertTrue(mock_execute_plan.called, "execute_recovery_plan was not called")

        captured_print = mock_print_plan.call_args[0][0]
        captured_execute = mock_execute_plan.call_args[0][0]

        self.assertIs(
            captured_print,
            captured_execute,
            "print_recovery_plan and execute_recovery_plan received different plan objects",
        )

    # ------------------------------------------------------------------
    # Test 6-7: plan describes zero-byte objects by path
    # ------------------------------------------------------------------

    def test_plan_describes_zero_byte_objects_by_path(self):
        """plan_recovery_actions must include the full path of every zero-byte object
        in the description of the first action when zero-byte objects are present."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            # Construct a fake .git/objects/<2-char-hex-dir>/<file>
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            zero_byte_file = obj_dir / "cd1234deadbeef"
            zero_byte_file.write_bytes(b"")  # zero bytes

            plan = plan_recovery_actions(repo)

        # At least one action in the plan.
        self.assertGreater(len(plan), 0, "plan_recovery_actions returned an empty plan")

        # The first action's description must mention the zero-byte file path.
        first_description = plan[0].description
        self.assertIn(
            str(zero_byte_file),
            first_description,
            f"Expected zero-byte file path in description; got: {first_description!r}",
        )


if __name__ == "__main__":
    unittest.main()
