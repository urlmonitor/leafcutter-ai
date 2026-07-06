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
plan_recovery_actions = _mod.plan_recovery_actions
print_recovery_plan = _mod.print_recovery_plan
execute_recovery_plan = _mod.execute_recovery_plan
RecoveryAction = _mod.RecoveryAction

# detect_zero_byte_objects is safe to bind at module level — it EXISTS in the
# current implementation.  detect_corrupt_branch_refs, detect_poisoned_index, and
# verify_recovery_integrity are accessed via getattr() INSIDE test bodies because
# they are NOT yet implemented; binding them here would raise AttributeError and
# break all 18 existing tests.
detect_zero_byte_objects = _mod.detect_zero_byte_objects


# ---------------------------------------------------------------------------
# Test-only exception — used by test_ac4_failed_step_halts_plan_execution
# to avoid TRY003 (inline string in raise) and BLE001 (blind except).
# ---------------------------------------------------------------------------

class _SimulatedStepFailure(RuntimeError):
    """Raised by a mock recovery step to simulate step failure during tests."""


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
            str(c) for c in mock_print.call_args_list
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
        """Answering 'no' must not trigger any git WRITE subprocess call.

        Note: plan_recovery_actions() now also calls 'git --version' (read-only)
        in addition to the status probe, so we check for absence of write
        commands rather than asserting a specific total call count.
        """
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = _make_probe_result()

        main(["--repo", "/tmp"])

        # No write-capable commands may have been called.
        write_cmds = {"fetch", "update-ref", "read-tree"}
        for c in mock_subprocess_run.call_args_list:
            cmd = c[0][0] if c[0] else []
            self.assertFalse(
                any(w in cmd for w in write_cmds),
                f"Write command must not be called when gate is not passed; got: {cmd}",
            )

    @patch("subprocess.run")
    @patch("builtins.input")
    @patch("sys.stdin")
    def test_answer_empty_makes_no_post_gate_subprocess_call(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Answering with an empty string must not proceed past the gate.

        Note: plan_recovery_actions() now also calls 'git --version' (read-only)
        in addition to the status probe, so we check for absence of write
        commands rather than asserting a specific total call count.
        """
        mock_stdin.isatty.return_value = True
        mock_input.return_value = ""
        mock_subprocess_run.return_value = _make_probe_result()

        main(["--repo", "/tmp"])

        # No write-capable commands may have been called.
        write_cmds = {"fetch", "update-ref", "read-tree"}
        for c in mock_subprocess_run.call_args_list:
            cmd = c[0][0] if c[0] else []
            self.assertFalse(
                any(w in cmd for w in write_cmds),
                f"Write command must not be called when gate is not passed; got: {cmd}",
            )

    @patch("subprocess.run")
    @patch("builtins.input", return_value="YES")
    @patch("sys.stdin")
    def test_answer_uppercase_yes_makes_no_post_gate_subprocess_call(
        self, mock_stdin, mock_input, mock_subprocess_run
    ):
        """Gate must be case-sensitive: 'YES' is not accepted as confirmation.

        Note: plan_recovery_actions() now also calls 'git --version' (read-only)
        in addition to the status probe, so we check for absence of write
        commands rather than asserting a specific total call count.
        """
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = _make_probe_result()

        main(["--repo", "/tmp"])

        # No write-capable commands may have been called.
        write_cmds = {"fetch", "update-ref", "read-tree"}
        for c in mock_subprocess_run.call_args_list:
            cmd = c[0][0] if c[0] else []
            self.assertFalse(
                any(w in cmd for w in write_cmds),
                f"Write command must not be called when gate is not passed; got: {cmd}",
            )


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
        """Answering 'no' must trigger no git WRITE operations.

        Note: plan_recovery_actions() now also calls 'git --version' (read-only)
        in addition to the status probe, so we check for absence of write
        commands rather than asserting a specific total call count.
        """
        mock_stdin.isatty.return_value = True
        mock_subprocess_run.return_value = self._make_probe_result()

        main(["--repo", "/tmp"])

        # No write-capable commands may have been called.
        write_cmds = {"fetch", "update-ref", "read-tree"}
        for c in mock_subprocess_run.call_args_list:
            cmd = c[0][0] if c[0] else []
            self.assertFalse(
                any(w in cmd for w in write_cmds),
                f"Write command must not be called when gate is not passed; got: {cmd}",
            )

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


# ===========================================================================
# NEW TEST GROUPS — BO-1600d-3 (real repair-step engine)
# Tests written BEFORE implementation: all new groups must be RED until
# python-coder implements detect_corrupt_branch_refs, detect_poisoned_index,
# get_reflog_tip, and verify_recovery_integrity in git_recovery.py.
# ===========================================================================


# ---------------------------------------------------------------------------
# Test Group (a): Zero-byte detection and removal + re-fetch ordering
# ---------------------------------------------------------------------------

class TestZeroByteDetectionAndRemovalOrder(unittest.TestCase):
    """Detailed tests for the zero-byte detection, removal, and re-fetch pipeline.

    These tests verify:
    - detect_zero_byte_objects returns only zero-byte paths.
    - plan_recovery_actions includes a remove action when zero-byte objects exist.
    - The refetch action appears AFTER the remove action in the plan.
    - execute_recovery_plan calls the remove callable before the fetch callable.
    """

    def test_ac1_detect_returns_only_zero_byte_paths(self):
        # covers: UNKNOWN
        """detect_zero_byte_objects must return zero-byte paths and exclude non-zero files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            zero_file = obj_dir / "cd1234deadbeef"
            zero_file.write_bytes(b"")
            nonzero_file = obj_dir / "ef5678deadbeef"
            nonzero_file.write_bytes(b"git object content")

            result = detect_zero_byte_objects(repo)

        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1, f"Expected exactly 1 zero-byte path; got {result}")
        self.assertIn(zero_file, result)
        self.assertNotIn(nonzero_file, result)

    def test_ac1_plan_includes_remove_action_for_zero_byte_objects(self):
        # covers: UNKNOWN
        """plan_recovery_actions must include a remove action when zero-byte objects exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            (obj_dir / "cd1234deadbeef").write_bytes(b"")

            plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        has_remove = any("remove" in d or "zero" in d for d in descriptions)
        self.assertTrue(
            has_remove,
            f"Plan must include a remove action for zero-byte objects; got: {descriptions}",
        )

    def test_ac1_plan_refetch_appears_after_remove_action(self):
        # covers: UNKNOWN
        """The refetch action must appear at a higher index than the remove action in the plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            (obj_dir / "cd1234deadbeef").write_bytes(b"")

            plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        remove_idx = next(
            (i for i, d in enumerate(descriptions) if "remove" in d or "zero" in d), None
        )
        fetch_idx = next(
            (i for i, d in enumerate(descriptions) if "fetch" in d), None
        )
        self.assertIsNotNone(remove_idx, "No remove action found in plan")
        self.assertIsNotNone(fetch_idx, "No refetch action found in plan")
        self.assertLess(
            remove_idx,
            fetch_idx,
            f"Remove action (index {remove_idx}) must precede refetch (index {fetch_idx})",
        )

    def test_ac1_execute_calls_removal_before_fetch(self):
        # covers: UNKNOWN
        """execute_recovery_plan must invoke the remove callable before the fetch callable."""
        call_order: list = []

        def mock_remove() -> None:
            call_order.append("remove")

        def mock_fetch() -> None:
            call_order.append("fetch")

        plan = [
            RecoveryAction("Remove zero-byte objects", mock_remove),
            RecoveryAction("Re-fetch from origin", mock_fetch),
        ]

        execute_recovery_plan(plan)

        self.assertEqual(
            call_order,
            ["remove", "fetch"],
            f"Expected call order ['remove', 'fetch'], got {call_order}",
        )


# ---------------------------------------------------------------------------
# Test Group (b): Branch ref reset to reflog tip
# ---------------------------------------------------------------------------

class TestPlanBranchRefReset(unittest.TestCase):
    """Tests for branch ref reset functionality — AC part (b).

    All tests in this class are expected to be RED until python-coder adds:
    - detect_corrupt_branch_refs(repo_path) -> list[tuple[str, str]]
    - get_reflog_tip(repo_path, branch_name) -> str
    - plan_recovery_actions() wired to use both functions.
    """

    def test_ac2_detect_corrupt_branch_refs_function_exists(self):
        # covers: UNKNOWN
        """detect_corrupt_branch_refs must be defined in git_recovery.py."""
        fn = getattr(_mod, "detect_corrupt_branch_refs", None)
        self.assertIsNotNone(
            fn,
            "detect_corrupt_branch_refs must be defined in git_recovery.py but was not found",
        )

    def test_ac2_plan_includes_reset_action_when_corrupt_ref_detected(self):
        # covers: UNKNOWN
        """plan_recovery_actions must include a branch-ref reset action when detect_corrupt_branch_refs returns a corrupt ref."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(
                _mod,
                "detect_corrupt_branch_refs",
                return_value=[("feature-branch", "deadbeefdeadbeef")],
            ):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        has_ref_reset = any(
            ("reset" in d) and ("ref" in d or "branch" in d) for d in descriptions
        )
        self.assertTrue(
            has_ref_reset,
            f"Plan must include a branch-ref reset action; got: {descriptions}",
        )

    def test_ac2_affected_branch_name_appears_in_action_description(self):
        # covers: UNKNOWN
        """The affected branch name must appear in the plan action description (not hardcoded)."""
        arbitrary_branch = "epic-concurrent-dispatch-x47"

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(
                _mod,
                "detect_corrupt_branch_refs",
                return_value=[(arbitrary_branch, "abc123")],
            ):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description for a in plan]
        has_branch_in_desc = any(arbitrary_branch in d for d in descriptions)
        self.assertTrue(
            has_branch_in_desc,
            f"Branch name '{arbitrary_branch}' must appear in action description; "
            f"got: {descriptions}",
        )

    def test_ac2_reflog_tip_sha_used_as_reset_target(self):
        # covers: UNKNOWN
        """The reflog tip SHA (from get_reflog_tip) must appear in the ref-reset action description."""
        corrupt_branch = "my-feature-branch"
        reflog_tip_sha = "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2"

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(
                _mod,
                "detect_corrupt_branch_refs",
                return_value=[(corrupt_branch, "deadbeef")],
            ):
                with patch.object(_mod, "get_reflog_tip", return_value=reflog_tip_sha):
                    plan = plan_recovery_actions(repo)

        ref_reset_actions = [
            a
            for a in plan
            if "reset" in a.description.lower()
            and ("ref" in a.description.lower() or "branch" in a.description.lower())
        ]
        self.assertGreater(
            len(ref_reset_actions), 0, "No ref-reset action found in plan"
        )
        ref_desc = ref_reset_actions[0].description
        self.assertIn(
            reflog_tip_sha,
            ref_desc,
            f"Reflog tip SHA must appear in action description; got: {ref_desc!r}",
        )


# ---------------------------------------------------------------------------
# Test Group (c): Index cache-tree rebuild
# ---------------------------------------------------------------------------

class TestPlanCacheTreeRebuild(unittest.TestCase):
    """Tests for index cache-tree rebuild functionality — AC part (c).

    All tests in this class are expected to be RED until python-coder adds:
    - detect_poisoned_index(repo_path) -> bool
    - plan_recovery_actions() wired to use detect_poisoned_index.
    - The cache-tree rebuild action must invoke 'git read-tree HEAD'.
    """

    def test_ac3_detect_poisoned_index_function_exists(self):
        # covers: UNKNOWN
        """detect_poisoned_index must be defined in git_recovery.py."""
        fn = getattr(_mod, "detect_poisoned_index", None)
        self.assertIsNotNone(
            fn,
            "detect_poisoned_index must be defined in git_recovery.py but was not found",
        )

    def test_ac3_plan_includes_cache_tree_rebuild_when_poisoned(self):
        # covers: UNKNOWN
        """plan_recovery_actions must include a cache-tree rebuild action when detect_poisoned_index returns True."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(_mod, "detect_poisoned_index", return_value=True):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        has_cache_tree = any(
            ("cache" in d and "tree" in d)
            or ("rebuild" in d and "index" in d)
            or "read-tree" in d
            for d in descriptions
        )
        self.assertTrue(
            has_cache_tree,
            f"Plan must include a cache-tree rebuild action when index is poisoned; "
            f"got: {descriptions}",
        )

    def test_ac3_cache_tree_action_calls_git_read_tree_head(self):
        # covers: UNKNOWN
        """Executing the cache-tree rebuild action must invoke 'git read-tree HEAD'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(_mod, "detect_poisoned_index", return_value=True):
                plan = plan_recovery_actions(repo)

        cache_tree_actions = [
            a
            for a in plan
            if ("cache" in a.description.lower() and "tree" in a.description.lower())
            or ("rebuild" in a.description.lower() and "index" in a.description.lower())
            or "read-tree" in a.description.lower()
        ]
        self.assertGreater(
            len(cache_tree_actions),
            0,
            f"No cache-tree rebuild action in plan; got: {[a.description for a in plan]}",
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            cache_tree_actions[0].execute()

        self.assertTrue(mock_run.called, "subprocess.run was not called by the cache-tree rebuild action")
        all_calls_str = str(mock_run.call_args_list)
        self.assertIn(
            "read-tree",
            all_calls_str,
            f"'git read-tree HEAD' must appear in subprocess call; got: {all_calls_str}",
        )


# ---------------------------------------------------------------------------
# Test Group (d): Dependency ordering
# ---------------------------------------------------------------------------

class TestDependencyOrdering(unittest.TestCase):
    """Tests for dependency ordering — AC part (d).

    Ordering rule: remove+refetch (a) BEFORE branch-ref reset (b) BEFORE cache-tree rebuild (c).
    Skipping rule: absent precondition → action absent from plan.
    Halt rule: a failing step stops execution; remaining steps are NOT executed.
    """

    def test_ac4_remove_and_refetch_before_branch_ref_reset(self):
        # covers: UNKNOWN
        """Remove+refetch steps must appear before branch-ref reset in the plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            (obj_dir / "cd1234deadbeef").write_bytes(b"")  # zero-byte object

            with patch.object(
                _mod,
                "detect_corrupt_branch_refs",
                return_value=[("main", "deadbeef")],
            ):
                with patch.object(_mod, "get_reflog_tip", return_value="abc1234"):
                    plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        remove_idx = next(
            (i for i, d in enumerate(descriptions) if "remove" in d or "zero" in d), None
        )
        fetch_idx = next(
            (i for i, d in enumerate(descriptions) if "fetch" in d), None
        )
        reset_idx = next(
            (i for i, d in enumerate(descriptions) if "reset" in d and ("ref" in d or "branch" in d)),
            None,
        )
        self.assertIsNotNone(remove_idx, "No remove action in plan")
        self.assertIsNotNone(fetch_idx, "No refetch action in plan")
        self.assertIsNotNone(reset_idx, "No branch-ref reset action in plan")
        self.assertLess(remove_idx, reset_idx, "Remove must precede branch-ref reset")
        self.assertLess(fetch_idx, reset_idx, "Refetch must precede branch-ref reset")

    def test_ac4_remove_and_refetch_before_cache_tree_rebuild(self):
        # covers: UNKNOWN
        """Remove+refetch steps must appear before cache-tree rebuild in the plan."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            (obj_dir / "cd1234deadbeef").write_bytes(b"")

            with patch.object(_mod, "detect_poisoned_index", return_value=True):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        remove_idx = next(
            (i for i, d in enumerate(descriptions) if "remove" in d or "zero" in d), None
        )
        fetch_idx = next(
            (i for i, d in enumerate(descriptions) if "fetch" in d), None
        )
        cache_idx = next(
            (
                i
                for i, d in enumerate(descriptions)
                if ("cache" in d and "tree" in d) or ("rebuild" in d and "index" in d)
            ),
            None,
        )
        self.assertIsNotNone(remove_idx, "No remove action in plan")
        self.assertIsNotNone(fetch_idx, "No refetch action in plan")
        self.assertIsNotNone(cache_idx, "No cache-tree rebuild action in plan")
        self.assertLess(remove_idx, cache_idx, "Remove must precede cache-tree rebuild")
        self.assertLess(fetch_idx, cache_idx, "Refetch must precede cache-tree rebuild")

    def test_ac4_ref_reset_excluded_when_no_corrupt_refs(self):
        # covers: UNKNOWN
        """Branch-ref reset action must be ABSENT from plan when detect_corrupt_branch_refs returns empty list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(_mod, "detect_corrupt_branch_refs", return_value=[]):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        has_reset = any(
            "reset" in d and ("ref" in d or "branch" in d) for d in descriptions
        )
        self.assertFalse(
            has_reset,
            f"Plan must NOT include ref-reset when no corrupt refs exist; got: {descriptions}",
        )

    def test_ac4_cache_tree_excluded_when_index_clean(self):
        # covers: UNKNOWN
        """Cache-tree rebuild action must be ABSENT from plan when detect_poisoned_index returns False."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(_mod, "detect_poisoned_index", return_value=False):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        has_cache_tree = any(
            ("cache" in d and "tree" in d) or ("rebuild" in d and "index" in d)
            for d in descriptions
        )
        self.assertFalse(
            has_cache_tree,
            f"Plan must NOT include cache-tree rebuild when index is clean; got: {descriptions}",
        )

    def test_ac4_failed_step_halts_plan_execution(self):
        # covers: UNKNOWN
        """A failing step must halt execute_recovery_plan; remaining steps must NOT be executed."""
        executed: list = []

        def step1_fails() -> None:
            executed.append("step1")
            raise _SimulatedStepFailure

        def step2_must_not_run() -> None:
            executed.append("step2")

        plan = [
            RecoveryAction("Step that fails", step1_fails),
            RecoveryAction("Step that must not run after failure", step2_must_not_run),
        ]

        try:
            execute_recovery_plan(plan)
        except _SimulatedStepFailure:
            pass  # Expected — the failure propagates, halting remaining steps.

        self.assertIn("step1", executed, "Step 1 must have been attempted")
        self.assertNotIn(
            "step2", executed, "Step 2 must NOT execute after step 1 raises"
        )


# ---------------------------------------------------------------------------
# Test Group (e): Post-execution integrity verification
# ---------------------------------------------------------------------------

class TestPostExecutionIntegrityVerification(unittest.TestCase):
    """Tests for post-execution integrity check — AC part (e).

    All tests in this class are expected to be RED until python-coder adds:
    - verify_recovery_integrity(repo_path, plan) -> bool
    - main() wired to call verify_recovery_integrity after execute_recovery_plan.
    """

    def test_ac5_verify_recovery_integrity_function_exists(self):
        # covers: UNKNOWN
        """verify_recovery_integrity must be defined in git_recovery.py."""
        fn = getattr(_mod, "verify_recovery_integrity", None)
        self.assertIsNotNone(
            fn,
            "verify_recovery_integrity must be defined in git_recovery.py but was not found",
        )

    def test_ac5_integrity_check_called_after_execute_recovery_plan(self):
        # covers: UNKNOWN
        """verify_recovery_integrity must be called after execute_recovery_plan completes successfully."""
        verify_fn = getattr(_mod, "verify_recovery_integrity", None)
        self.assertIsNotNone(
            verify_fn,
            "verify_recovery_integrity must exist before this test can proceed",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            call_log: list = []

            def mock_verify(repo_path: Path, plan: list) -> bool:
                call_log.append((str(repo_path), len(plan)))
                return True

            with patch.object(_mod, "verify_recovery_integrity", side_effect=mock_verify):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0, stdout="")
                    with patch("sys.stdin") as mock_stdin:
                        mock_stdin.isatty.return_value = False
                        main(["--repo", str(repo), "--execute"])

        self.assertGreater(
            len(call_log),
            0,
            "verify_recovery_integrity must be called after execute_recovery_plan",
        )

    def test_ac5_integrity_check_receives_executed_plan(self):
        # covers: UNKNOWN
        """verify_recovery_integrity must receive the executed plan so it can scope its checks."""
        verify_fn = getattr(_mod, "verify_recovery_integrity", None)
        self.assertIsNotNone(
            verify_fn,
            "verify_recovery_integrity must exist before this test can proceed",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            captured: dict = {}

            def mock_verify(repo_path: Path, plan: list) -> bool:
                captured["plan"] = plan
                return True

            with patch.object(_mod, "verify_recovery_integrity", side_effect=mock_verify):
                with patch("subprocess.run") as mock_run:
                    mock_run.return_value = MagicMock(returncode=0, stdout="")
                    with patch("sys.stdin") as mock_stdin:
                        mock_stdin.isatty.return_value = False
                        main(["--repo", str(repo), "--execute"])

        self.assertIn(
            "plan", captured, "verify_recovery_integrity must be called with the plan argument"
        )
        self.assertIsInstance(
            captured.get("plan"),
            list,
            "The plan argument passed to verify_recovery_integrity must be a list",
        )


# ---------------------------------------------------------------------------
# Test Group (f): Git version guard — AC BO-1600d-3-i
# ---------------------------------------------------------------------------

class TestGitVersionGuard(unittest.TestCase):
    """Tests for git version guard — AC BO-1600d-3-i.

    Verifies that plan_recovery_actions() checks the installed git version
    before the zero-byte detection block, and that on git < 2.36:
    - The remove action is NOT added to the plan (critical safety invariant).
    - The refetch action is NOT added to the plan.
    - A BLOCKED action is added when zero-byte objects exist.
    - The BLOCKED action raises RuntimeError (with version info) when executed.

    On git >= 2.36:
    - The refetch action IS added.
    - The remove action IS added when zero-byte objects exist and appears BEFORE refetch.
    """

    def test_git_version_function_exists(self):
        """_git_version must be defined in git_recovery.py."""
        fn = getattr(_mod, "_git_version", None)
        self.assertIsNotNone(
            fn,
            "_git_version must be defined in git_recovery.py but was not found",
        )

    def test_git_version_parses_standard_output(self):
        """_git_version must parse 'git version 2.41.0' → (2, 41, 0)."""
        _git_version = getattr(_mod, "_git_version", None)
        self.assertIsNotNone(_git_version, "_git_version not found in module")

        mock_result = MagicMock()
        mock_result.stdout = "git version 2.41.0\n"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = _git_version()

        self.assertEqual(result, (2, 41, 0))

    def test_git_version_parses_short_output(self):
        """_git_version must parse 'git version 2.36' (no patch) → (2, 36, 0)."""
        _git_version = getattr(_mod, "_git_version", None)
        self.assertIsNotNone(_git_version, "_git_version not found in module")

        mock_result = MagicMock()
        mock_result.stdout = "git version 2.36\n"
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = _git_version()

        self.assertEqual(result, (2, 36, 0))

    def test_git_version_subprocess_error_propagates(self):
        """CalledProcessError from git --version must be logged at WARNING and re-raised."""
        _git_version = getattr(_mod, "_git_version", None)
        self.assertIsNotNone(_git_version, "_git_version not found in module")

        exc = subprocess.CalledProcessError(127, ["git", "--version"])

        with patch("subprocess.run", side_effect=exc):
            with self.assertLogs("git_recovery", level="WARNING") as log_ctx:
                with self.assertRaises(subprocess.CalledProcessError):
                    _git_version()

        self.assertTrue(
            any("WARNING" in line for line in log_ctx.output),
            "Expected at least one WARNING log entry when git --version fails",
        )

    def test_old_git_plan_excludes_remove_action_for_zero_byte_objects(self):
        """On old git (2.35.0), plan must NOT include a remove action for zero-byte objects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            (obj_dir / "cd1234deadbeef").write_bytes(b"")  # zero-byte object

            with patch.object(_mod, "_git_version", return_value=(2, 35, 0)):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        # A real remove action starts with "remove". The BLOCKED action starts
        # with "blocked" — exclude it to avoid a false positive from the BLOCKED
        # description's prose which mentions "remove step is not applied".
        has_remove = any(
            d.startswith("remove")
            for d in descriptions
        )
        self.assertFalse(
            has_remove,
            f"Plan must NOT include a remove action when git is too old; got: {descriptions}",
        )

    def test_old_git_plan_excludes_refetch_action(self):
        """On old git (2.35.0), plan must NOT include any refetch action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(_mod, "_git_version", return_value=(2, 35, 0)):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        has_refetch = any("refetch" in d or "re-fetch" in d for d in descriptions)
        self.assertFalse(
            has_refetch,
            f"Plan must NOT include a refetch action when git is too old; got: {descriptions}",
        )

    def test_old_git_plan_includes_blocked_description(self):
        """On old git with zero-byte objects, plan must include a BLOCKED action mentioning 2.36."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            (obj_dir / "cd1234deadbeef").write_bytes(b"")  # zero-byte object

            with patch.object(_mod, "_git_version", return_value=(2, 35, 0)):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description for a in plan]
        blocked_actions = [d for d in descriptions if "BLOCKED" in d]
        self.assertGreater(
            len(blocked_actions),
            0,
            f"Plan must include a BLOCKED action when git is too old; got: {descriptions}",
        )
        blocked_desc = blocked_actions[0]
        self.assertIn(
            "2.36",
            blocked_desc,
            f"BLOCKED description must mention minimum version 2.36; got: {blocked_desc!r}",
        )

    def test_old_git_blocked_action_raises_on_execute(self):
        """Executing the BLOCKED action must raise RuntimeError with version info."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            (obj_dir / "cd1234deadbeef").write_bytes(b"")  # zero-byte object

            with patch.object(_mod, "_git_version", return_value=(2, 35, 0)):
                plan = plan_recovery_actions(repo)

        blocked_actions = [a for a in plan if "BLOCKED" in a.description]
        self.assertGreater(
            len(blocked_actions),
            0,
            "No BLOCKED action found; cannot test execute raises",
        )

        with self.assertRaises(RuntimeError) as ctx:
            blocked_actions[0].execute()

        error_msg = str(ctx.exception)
        self.assertIn(
            "2.36",
            error_msg,
            f"RuntimeError must mention minimum version 2.36; got: {error_msg!r}",
        )

    def test_new_git_plan_includes_refetch_action(self):
        """On new git (2.41.0), plan must include a refetch action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(_mod, "_git_version", return_value=(2, 41, 0)):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        has_refetch = any("fetch" in d for d in descriptions)
        self.assertTrue(
            has_refetch,
            f"Plan must include a refetch action when git >= 2.36; got: {descriptions}",
        )

    def test_new_git_plan_includes_remove_action_with_zero_byte_objects(self):
        """On new git (2.41.0) with zero-byte objects, plan includes remove BEFORE refetch."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            obj_dir = repo / ".git" / "objects" / "ab"
            obj_dir.mkdir(parents=True)
            (obj_dir / "cd1234deadbeef").write_bytes(b"")  # zero-byte object

            with patch.object(_mod, "_git_version", return_value=(2, 41, 0)):
                plan = plan_recovery_actions(repo)

        descriptions = [a.description.lower() for a in plan]
        # A real remove action starts with "remove" (not "blocked").
        remove_idx = next(
            (i for i, d in enumerate(descriptions) if d.startswith("remove")),
            None,
        )
        fetch_idx = next(
            (i for i, d in enumerate(descriptions) if "fetch" in d), None
        )
        self.assertIsNotNone(
            remove_idx,
            f"Plan must include a remove action when git >= 2.36 and zero-byte objects exist; got: {descriptions}",
        )
        self.assertIsNotNone(
            fetch_idx,
            f"Plan must include a refetch action when git >= 2.36; got: {descriptions}",
        )
        self.assertLess(
            remove_idx,
            fetch_idx,
            f"Remove action (index {remove_idx}) must appear before refetch (index {fetch_idx})",
        )


if __name__ == "__main__":
    unittest.main()
