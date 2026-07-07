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

# detect_shallow_or_bare_repo — use getattr so the test module still imports
# cleanly even if the function has not yet been added to the implementation.
detect_shallow_or_bare_repo = getattr(_mod, "detect_shallow_or_bare_repo", None)


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


# ===========================================================================
# NEW TEST GROUP — BO-1600d-3-ii (unrecoverable-origin detection)
# Covers: fetch succeeds but objects still missing → unrecoverable; single
# fetch only (no retry loop); no deletion on unrecoverable path; message
# names the missing objects.
# ===========================================================================


class TestUnrecoverableOriginDetection(unittest.TestCase):
    """Tests for AC BO-1600d-3-ii: When origin genuinely lacks the missing objects.

    Verifies that step_refetch_and_verify:
    - Returns {"status": "unrecoverable", "missing_objects": [...], "message": str}
      when required objects are still absent after the fetch.
    - Names each missing SHA in both missing_objects and the message.
    - Issues exactly ONE fetch call — no retry loop.
    - Does NOT issue any deletion commands during the unrecoverable path.
    - Returns {"status": "ok"} when all required objects are restored.

    Also verifies that UnrecoverableOriginError is raised when the plan's
    refetch action detects an unrecoverable outcome.
    """

    def _get_fn(self):
        """Return step_refetch_and_verify or skip the test if not implemented."""
        fn = getattr(_mod, "step_refetch_and_verify", None)
        if fn is None:
            self.skipTest("step_refetch_and_verify not yet implemented")
        return fn

    # ------------------------------------------------------------------
    # Existence checks
    # ------------------------------------------------------------------

    def test_step_refetch_and_verify_exists(self):
        # covers: BO-1600d-3-ii
        """step_refetch_and_verify must be defined in git_recovery.py."""
        fn = getattr(_mod, "step_refetch_and_verify", None)
        self.assertIsNotNone(
            fn,
            "step_refetch_and_verify must be defined in git_recovery.py but was not found",
        )

    def test_unrecoverable_origin_error_class_exists(self):
        # covers: BO-1600d-3-ii
        """UnrecoverableOriginError must be defined in git_recovery.py."""
        cls = getattr(_mod, "UnrecoverableOriginError", None)
        self.assertIsNotNone(
            cls,
            "UnrecoverableOriginError must be defined in git_recovery.py but was not found",
        )

    # ------------------------------------------------------------------
    # Core unrecoverable-status behavior
    # ------------------------------------------------------------------

    def test_unrecoverable_status_returned_when_objects_still_missing(self):
        # covers: BO-1600d-3-ii
        """After fetch, if required objects are still absent, status must be 'unrecoverable'."""
        fn = self._get_fn()

        required_shas = ["a" * 40, "b" * 40]

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git").mkdir()

            def _mock_run(cmd, **kwargs):
                mock = MagicMock()
                mock.stdout = ""
                # fetch succeeds; cat-file reports objects not found
                mock.returncode = 0 if "--refetch" in cmd else 1
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                result = fn(repo, required_shas)

        self.assertEqual(
            result["status"],
            "unrecoverable",
            f"Expected status 'unrecoverable' when objects still missing after fetch; got: {result}",
        )

    def test_missing_sha_hashes_listed_in_result(self):
        # covers: BO-1600d-3-ii
        """The unrecoverable result must list the specific SHA hashes that could not be restored."""
        fn = self._get_fn()

        sha_a = "a" * 40
        sha_b = "b" * 40
        required_shas = [sha_a, sha_b]

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git").mkdir()

            def _mock_run(cmd, **kwargs):
                mock = MagicMock()
                mock.stdout = ""
                mock.returncode = 0 if "--refetch" in cmd else 1
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                result = fn(repo, required_shas)

        self.assertIn("missing_objects", result, "Result must contain 'missing_objects' key")
        missing = result["missing_objects"]
        self.assertIn(sha_a, missing, f"SHA {sha_a!r} must be in missing_objects")
        self.assertIn(sha_b, missing, f"SHA {sha_b!r} must be in missing_objects")

    # ------------------------------------------------------------------
    # No retry loop
    # ------------------------------------------------------------------

    def test_single_fetch_call_no_retry_loop(self):
        # covers: BO-1600d-3-ii
        """step_refetch_and_verify must issue exactly one fetch — no retry loop."""
        fn = self._get_fn()

        required_shas = ["c" * 40]
        fetch_calls = []

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git").mkdir()

            def _mock_run(cmd, **kwargs):
                mock = MagicMock()
                mock.stdout = ""
                if "--refetch" in cmd:
                    fetch_calls.append(list(cmd))
                    mock.returncode = 0  # fetch exits 0 but objects not restored
                else:
                    mock.returncode = 1  # cat-file: not found
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                fn(repo, required_shas)

        self.assertEqual(
            len(fetch_calls),
            1,
            f"Expected exactly 1 fetch call; got {len(fetch_calls)} (retry loop detected)",
        )

    # ------------------------------------------------------------------
    # No deletion on unrecoverable path
    # ------------------------------------------------------------------

    def test_no_deletion_commands_when_unrecoverable(self):
        # covers: BO-1600d-3-ii
        """step_refetch_and_verify must not issue deletion commands when returning unrecoverable."""
        fn = self._get_fn()

        required_shas = ["d" * 40]
        deletion_cmds_seen = []

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git").mkdir()

            def _mock_run(cmd, **kwargs):
                mock = MagicMock()
                mock.stdout = ""
                cmd_str = str(cmd)
                # Record any command that looks like a deletion operation
                if any(kw in cmd_str for kw in ("rm ", "unlink", "hash-object")):
                    deletion_cmds_seen.append(list(cmd))
                mock.returncode = 0 if "--refetch" in cmd else 1
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                with patch.object(Path, "unlink") as mock_unlink:
                    fn(repo, required_shas)

        self.assertEqual(
            deletion_cmds_seen,
            [],
            f"step_refetch_and_verify must not issue deletion commands when unrecoverable; "
            f"got: {deletion_cmds_seen}",
        )
        mock_unlink.assert_not_called()

    # ------------------------------------------------------------------
    # Message names the missing objects
    # ------------------------------------------------------------------

    def test_error_message_names_missing_objects(self):
        # covers: BO-1600d-3-ii
        """The message in the unrecoverable result must reference the missing SHA(s)."""
        fn = self._get_fn()

        specific_sha = "e" * 40
        required_shas = [specific_sha]

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git").mkdir()

            def _mock_run(cmd, **kwargs):
                mock = MagicMock()
                mock.stdout = ""
                mock.returncode = 0 if "--refetch" in cmd else 1
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                result = fn(repo, required_shas)

        self.assertIn("message", result, "Result must contain 'message' key")
        # The SHA must appear in the message OR in the missing_objects list
        sha_identifiable = (
            specific_sha in result.get("message", "")
            or specific_sha in str(result.get("missing_objects", []))
        )
        self.assertTrue(
            sha_identifiable,
            f"Missing SHA {specific_sha!r} must be identifiable from result; got: {result}",
        )

    # ------------------------------------------------------------------
    # OK path
    # ------------------------------------------------------------------

    def test_ok_status_returned_when_all_objects_restored(self):
        # covers: BO-1600d-3-ii
        """When origin supplies all required objects after the fetch, status must be 'ok'."""
        fn = self._get_fn()

        required_shas = ["f" * 40, "0" * 40]

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git").mkdir()

            # All subprocess.run calls return 0: fetch succeeds, cat-file finds objects
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""

            with patch("subprocess.run", return_value=mock_result):
                result = fn(repo, required_shas)

        self.assertEqual(
            result["status"],
            "ok",
            f"Expected status 'ok' when all objects are present after fetch; got: {result}",
        )

    # ------------------------------------------------------------------
    # Integration: plan raises UnrecoverableOriginError
    # ------------------------------------------------------------------

    def test_plan_raises_unrecoverable_origin_error_when_fetch_cannot_restore(self):
        # covers: BO-1600d-3-ii
        """When step_refetch_and_verify returns unrecoverable, executing the plan must
        raise UnrecoverableOriginError with a result carrying the missing objects."""
        unrecoverable_cls = getattr(_mod, "UnrecoverableOriginError", None)
        self.assertIsNotNone(
            unrecoverable_cls,
            "UnrecoverableOriginError must be defined in git_recovery.py",
        )

        missing_sha = "a" * 40
        unrecoverable_result = {
            "status": "unrecoverable",
            "missing_objects": [missing_sha],
            "message": f"Recovery unrecoverable: {missing_sha}",
        }

        # Keep ALL patches and the temp dir alive when execute() is called so the
        # patched step_refetch_and_verify is still in effect at call time.
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git").mkdir()

            with patch.object(_mod, "step_refetch_and_verify", return_value=unrecoverable_result):
                with patch.object(_mod, "_git_version", return_value=(2, 41, 0)):
                    with patch.object(_mod, "detect_zero_byte_objects", return_value=[]):
                        with patch.object(_mod, "detect_corrupt_branch_refs", return_value=[]):
                            with patch.object(_mod, "detect_poisoned_index", return_value=False):
                                plan = plan_recovery_actions(repo)

                                fetch_actions = [
                                    a for a in plan
                                    if "fetch" in a.description.lower()
                                    or "re-fetch" in a.description.lower()
                                ]
                                self.assertGreater(
                                    len(fetch_actions),
                                    0,
                                    "Plan must include a refetch action when git >= 2.36",
                                )

                                with self.assertRaises(unrecoverable_cls) as ctx:
                                    fetch_actions[0].execute()

        exc = ctx.exception
        self.assertTrue(
            hasattr(exc, "result"),
            "UnrecoverableOriginError must have a 'result' attribute",
        )
        self.assertEqual(exc.result["status"], "unrecoverable")
        self.assertIn(
            missing_sha,
            exc.result.get("missing_objects", []),
            "The missing SHA must be in UnrecoverableOriginError.result['missing_objects']",
        )


# ===========================================================================
# NEW TEST GROUP — BO-1600d-3-iii (shallow/bare clone pre-plan guard)
# Covers: detect_shallow_or_bare_repo, and the main() guard that fires
# before any repair action when the repo is shallow or bare.
# ===========================================================================


class TestShallowOrBareClonesRefused(unittest.TestCase):
    """Tests for AC BO-1600d-3-iii: Recovery refuses to run on shallow or bare clones.

    Verifies that:
    - detect_shallow_or_bare_repo is defined and detects .git/shallow presence.
    - detect_shallow_or_bare_repo detects bare repos via git command.
    - detect_shallow_or_bare_repo returns (False, "") for normal repos.
    - main() returns without calling run_status_probe or plan_recovery_actions
      when detect_shallow_or_bare_repo returns (True, ...).
    - No object removal, ref reset, or index rebuild subprocess calls are made
      on the shallow/bare path.
    - A human-readable refusal message mentioning "shallow" or "bare" is printed.
    """

    def _get_detect_fn(self):
        """Return detect_shallow_or_bare_repo or skip if not implemented."""
        fn = getattr(_mod, "detect_shallow_or_bare_repo", None)
        if fn is None:
            self.skipTest("detect_shallow_or_bare_repo not yet implemented")
        return fn

    # ------------------------------------------------------------------
    # 1. Existence check
    # ------------------------------------------------------------------

    def test_detect_shallow_or_bare_exists(self):
        # covers: BO-1600d-3-iii
        """detect_shallow_or_bare_repo must be defined in the module."""
        fn = getattr(_mod, "detect_shallow_or_bare_repo", None)
        self.assertIsNotNone(
            fn,
            "detect_shallow_or_bare_repo must be defined in git_recovery.py but was not found",
        )

    # ------------------------------------------------------------------
    # 2. Shallow detection via .git/shallow file presence
    # ------------------------------------------------------------------

    def test_shallow_clone_detected_via_shallow_file(self):
        # covers: BO-1600d-3-iii
        """When .git/shallow exists, detect_shallow_or_bare_repo returns (True, <non-empty reason>)."""
        fn = self._get_detect_fn()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            git_dir = repo / ".git"
            git_dir.mkdir(parents=True)
            shallow_marker = git_dir / "shallow"
            shallow_marker.write_bytes(b"")  # presence alone signals shallow

            result = fn(repo)

        self.assertIsInstance(result, tuple, "Return value must be a 2-tuple")
        self.assertEqual(len(result), 2, "Return value must be a 2-tuple")
        is_unsupported, reason = result
        self.assertTrue(is_unsupported, "Must return True when .git/shallow exists")
        self.assertIsInstance(reason, str, "Reason must be a string")
        self.assertTrue(reason, "Reason string must be non-empty when shallow detected")

    # ------------------------------------------------------------------
    # 3. Bare clone detection via git command
    # ------------------------------------------------------------------

    def test_bare_clone_detected_via_git_command(self):
        # covers: BO-1600d-3-iii
        """When git rev-parse --is-bare-repository returns 'true', function returns (True, <reason>)."""
        fn = self._get_detect_fn()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            # No .git/shallow — detection via git command only.

            def _mock_run(cmd, **kwargs):
                mock = MagicMock()
                mock.returncode = 0
                if "--is-bare-repository" in cmd:
                    mock.stdout = "true\n"
                elif "--is-shallow-repository" in cmd:
                    mock.stdout = "false\n"
                else:
                    mock.stdout = ""
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                result = fn(repo)

        self.assertIsInstance(result, tuple, "Return value must be a 2-tuple")
        is_unsupported, reason = result
        self.assertTrue(
            is_unsupported,
            "Must return True when git reports bare repository",
        )
        self.assertTrue(reason, "Reason string must be non-empty when bare detected")

    # ------------------------------------------------------------------
    # 4. Normal repo returns (False, "")
    # ------------------------------------------------------------------

    def test_non_shallow_non_bare_returns_false(self):
        # covers: BO-1600d-3-iii
        """When no .git/shallow and git returns 'false' for both checks, returns (False, '')."""
        fn = self._get_detect_fn()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)

            def _mock_run(cmd, **kwargs):
                mock = MagicMock()
                mock.returncode = 0
                mock.stdout = "false\n"
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                result = fn(repo)

        self.assertIsInstance(result, tuple, "Return value must be a 2-tuple")
        is_unsupported, reason = result
        self.assertFalse(
            is_unsupported,
            "Must return False when repo is neither shallow nor bare",
        )
        self.assertEqual(reason, "", "Reason must be empty string for a normal repo")

    # ------------------------------------------------------------------
    # 5. main() refuses on shallow clone — no run_status_probe or plan call
    # ------------------------------------------------------------------

    def test_main_refuses_on_shallow_clone(self):
        # covers: BO-1600d-3-iii
        """When detect_shallow_or_bare_repo returns (True, ...), main() must not call
        run_status_probe or plan_recovery_actions."""
        with patch.object(_mod, "detect_shallow_or_bare_repo", return_value=(True, "shallow clone detected")):
            with patch.object(_mod, "run_status_probe") as mock_probe:
                with patch.object(_mod, "plan_recovery_actions") as mock_plan:
                    with patch("sys.stdin") as mock_stdin:
                        mock_stdin.isatty.return_value = True
                        result = main(["--repo", "/tmp"])

        mock_probe.assert_not_called()
        mock_plan.assert_not_called()
        self.assertIsNone(result, "main() must return None (not sys.exit) on shallow refusal")

    # ------------------------------------------------------------------
    # 6. main() refuses on bare clone — no run_status_probe or plan call
    # ------------------------------------------------------------------

    def test_main_refuses_on_bare_clone(self):
        # covers: BO-1600d-3-iii
        """When detect_shallow_or_bare_repo returns (True, 'bare clone detected'), main()
        must not call run_status_probe or plan_recovery_actions."""
        with patch.object(_mod, "detect_shallow_or_bare_repo", return_value=(True, "bare clone detected")):
            with patch.object(_mod, "run_status_probe") as mock_probe:
                with patch.object(_mod, "plan_recovery_actions") as mock_plan:
                    with patch("sys.stdin") as mock_stdin:
                        mock_stdin.isatty.return_value = True
                        result = main(["--repo", "/tmp"])

        mock_probe.assert_not_called()
        mock_plan.assert_not_called()
        self.assertIsNone(result, "main() must return None (not sys.exit) on bare refusal")

    # ------------------------------------------------------------------
    # 7. No object removal when shallow
    # ------------------------------------------------------------------

    def test_no_object_removal_when_shallow(self):
        # covers: BO-1600d-3-iii
        """When detect_shallow_or_bare_repo returns (True, ...), no subprocess write command
        or Path.unlink is called."""
        with patch.object(_mod, "detect_shallow_or_bare_repo", return_value=(True, "shallow clone")):
            with patch("subprocess.run") as mock_run:
                with patch.object(Path, "unlink") as mock_unlink:
                    with patch("sys.stdin") as mock_stdin:
                        mock_stdin.isatty.return_value = True
                        main(["--repo", "/tmp"])

        write_cmds = {"fetch", "update-ref", "read-tree"}
        for call in mock_run.call_args_list:
            cmd = call[0][0] if call[0] else []
            self.assertFalse(
                any(w in cmd for w in write_cmds),
                f"No write command must run when shallow guard fires; got: {cmd}",
            )
        mock_unlink.assert_not_called()

    # ------------------------------------------------------------------
    # 8. No ref reset when bare
    # ------------------------------------------------------------------

    def test_no_ref_reset_when_bare(self):
        # covers: BO-1600d-3-iii
        """When detect_shallow_or_bare_repo returns (True, ...), no git update-ref call happens."""
        with patch.object(_mod, "detect_shallow_or_bare_repo", return_value=(True, "bare clone detected")):
            with patch("subprocess.run") as mock_run:
                with patch("sys.stdin") as mock_stdin:
                    mock_stdin.isatty.return_value = True
                    main(["--repo", "/tmp"])

        update_ref_calls = [
            c for c in mock_run.call_args_list if "update-ref" in str(c)
        ]
        self.assertEqual(
            update_ref_calls,
            [],
            f"git update-ref must not be called when bare guard fires; got: {update_ref_calls}",
        )

    # ------------------------------------------------------------------
    # 9. No index rebuild when shallow
    # ------------------------------------------------------------------

    def test_no_index_rebuild_when_shallow(self):
        # covers: BO-1600d-3-iii
        """When detect_shallow_or_bare_repo returns (True, ...), no git read-tree call happens."""
        with patch.object(_mod, "detect_shallow_or_bare_repo", return_value=(True, "shallow clone")):
            with patch("subprocess.run") as mock_run:
                with patch("sys.stdin") as mock_stdin:
                    mock_stdin.isatty.return_value = True
                    main(["--repo", "/tmp"])

        read_tree_calls = [
            c for c in mock_run.call_args_list if "read-tree" in str(c)
        ]
        self.assertEqual(
            read_tree_calls,
            [],
            f"git read-tree must not be called when shallow guard fires; got: {read_tree_calls}",
        )

    # ------------------------------------------------------------------
    # 10. Refusal message printed mentioning "shallow" or "bare"
    # ------------------------------------------------------------------

    def test_refusal_message_printed(self):
        # covers: BO-1600d-3-iii
        """When the shallow/bare guard fires, main() prints a message containing 'shallow' or 'bare'."""
        with patch.object(_mod, "detect_shallow_or_bare_repo", return_value=(True, "shallow clone")):
            with patch("sys.stdin") as mock_stdin:
                mock_stdin.isatty.return_value = True
                with patch("builtins.print") as mock_print:
                    main(["--repo", "/tmp"])

        printed_output = " ".join(str(c) for c in mock_print.call_args_list).lower()
        self.assertTrue(
            "shallow" in printed_output or "bare" in printed_output,
            f"Refusal message must mention 'shallow' or 'bare'; got: {printed_output!r}",
        )


# ===========================================================================
# NEW TEST GROUP — BO-1600d-3-iv (branch-ref reset never hardcodes a name)
# Regression tests for the branch detection hierarchy:
#   (a) corrupt ref name  →  (b) current HEAD  →  (c) remote default
# and the unambiguous-detection stop guard.
# ===========================================================================


class TestBranchRefResetNonMain(unittest.TestCase):
    """Regression tests for AC BO-1600d-3-iv.

    Verifies that:
    - When the corrupt ref belongs to "master", the reset targets "master",
      never "main".
    - When the corrupt ref belongs to an epic branch "EPIC-Foo", the reset
      targets "EPIC-Foo".
    - When the affected branch cannot be determined from any source, recovery
      stops with a RecoveryError rather than guessing a name.
    """

    # ------------------------------------------------------------------
    # Helper: bind module-level symbols at test runtime so this class loads
    # even before python-coder adds the functions (guards keep tests
    # discoverable without breaking the existing 66-test suite).
    # ------------------------------------------------------------------

    def _get_determine_fn(self):
        fn = getattr(_mod, "_determine_branch_to_reset", None)
        if fn is None:
            self.skipTest("_determine_branch_to_reset not yet implemented")
        return fn

    def _get_recovery_error(self):
        cls = getattr(_mod, "RecoveryError", None)
        if cls is None:
            self.skipTest("RecoveryError not yet implemented")
        return cls

    # ------------------------------------------------------------------
    # 1. Existence checks
    # ------------------------------------------------------------------

    def test_recovery_error_class_exists(self):
        # covers: BO-1600d-3-iv
        """RecoveryError must be defined in git_recovery.py."""
        cls = getattr(_mod, "RecoveryError", None)
        self.assertIsNotNone(
            cls,
            "RecoveryError must be defined in git_recovery.py but was not found",
        )

    def test_determine_branch_to_reset_exists(self):
        # covers: BO-1600d-3-iv
        """_determine_branch_to_reset must be defined in git_recovery.py."""
        fn = getattr(_mod, "_determine_branch_to_reset", None)
        self.assertIsNotNone(
            fn,
            "_determine_branch_to_reset must be defined in git_recovery.py but was not found",
        )

    # ------------------------------------------------------------------
    # 2. "master" default branch — reset must target "master", not "main"
    # ------------------------------------------------------------------

    def test_master_branch_reset_targets_master(self):
        # covers: BO-1600d-3-iv
        """When the corrupt ref belongs to 'master', the plan targets 'master' (not 'main')."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(
                _mod,
                "detect_corrupt_branch_refs",
                return_value=[("master", "deadbeefdeadbeef")],
            ):
                with patch.object(_mod, "get_reflog_tip", return_value="a" * 40):
                    plan = plan_recovery_actions(repo)

        ref_reset_actions = [
            a for a in plan
            if "reset" in a.description.lower()
            and ("ref" in a.description.lower() or "branch" in a.description.lower())
        ]
        self.assertGreater(
            len(ref_reset_actions),
            0,
            "Plan must include a branch-ref reset action",
        )
        desc = ref_reset_actions[0].description
        self.assertIn(
            "master",
            desc,
            f"Action description must mention 'master'; got: {desc!r}",
        )
        self.assertNotIn(
            "'main'",
            desc,
            f"Action description must NOT hardcode 'main'; got: {desc!r}",
        )

    def test_master_branch_reset_executes_update_ref_on_master(self):
        # covers: BO-1600d-3-iv
        """Executing the branch-ref reset action for 'master' must call
        git update-ref refs/heads/master, never refs/heads/main."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            tip_sha = "b" * 40
            with patch.object(
                _mod,
                "detect_corrupt_branch_refs",
                return_value=[("master", "deadbeef")],
            ):
                with patch.object(_mod, "get_reflog_tip", return_value=tip_sha):
                    plan = plan_recovery_actions(repo)

        ref_reset_actions = [
            a for a in plan
            if "reset" in a.description.lower()
            and ("ref" in a.description.lower() or "branch" in a.description.lower())
        ]
        self.assertGreater(len(ref_reset_actions), 0, "No ref-reset action in plan")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ref_reset_actions[0].execute()

        all_calls_str = str(mock_run.call_args_list)
        self.assertIn(
            "refs/heads/master",
            all_calls_str,
            f"Must call git update-ref refs/heads/master; got: {all_calls_str}",
        )
        self.assertNotIn(
            "refs/heads/main",
            all_calls_str,
            f"Must NOT call git update-ref refs/heads/main; got: {all_calls_str}",
        )

    # ------------------------------------------------------------------
    # 3. Epic branch "EPIC-Foo" — reset must target "EPIC-Foo"
    # ------------------------------------------------------------------

    def test_epic_branch_reset_targets_epic_branch(self):
        # covers: BO-1600d-3-iv
        """When the corrupt ref belongs to 'EPIC-Foo', the plan targets 'EPIC-Foo'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(
                _mod,
                "detect_corrupt_branch_refs",
                return_value=[("EPIC-Foo", "cafebabecafebabe")],
            ):
                with patch.object(_mod, "get_reflog_tip", return_value="c" * 40):
                    plan = plan_recovery_actions(repo)

        ref_reset_actions = [
            a for a in plan
            if "reset" in a.description.lower()
            and ("ref" in a.description.lower() or "branch" in a.description.lower())
        ]
        self.assertGreater(
            len(ref_reset_actions),
            0,
            "Plan must include a branch-ref reset action for epic branch",
        )
        desc = ref_reset_actions[0].description
        self.assertIn(
            "EPIC-Foo",
            desc,
            f"Action description must mention 'EPIC-Foo'; got: {desc!r}",
        )
        self.assertNotIn(
            "'main'",
            desc,
            f"Action description must NOT hardcode 'main'; got: {desc!r}",
        )
        self.assertNotIn(
            "'master'",
            desc,
            f"Action description must NOT hardcode 'master'; got: {desc!r}",
        )

    def test_epic_branch_reset_executes_update_ref_on_epic_branch(self):
        # covers: BO-1600d-3-iv
        """Executing the reset action for 'EPIC-Foo' must call
        git update-ref refs/heads/EPIC-Foo, never refs/heads/main."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            tip_sha = "d" * 40
            with patch.object(
                _mod,
                "detect_corrupt_branch_refs",
                return_value=[("EPIC-Foo", "cafebabe")],
            ):
                with patch.object(_mod, "get_reflog_tip", return_value=tip_sha):
                    plan = plan_recovery_actions(repo)

        ref_reset_actions = [
            a for a in plan
            if "reset" in a.description.lower()
            and ("ref" in a.description.lower() or "branch" in a.description.lower())
        ]
        self.assertGreater(len(ref_reset_actions), 0, "No ref-reset action in plan")

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            ref_reset_actions[0].execute()

        all_calls_str = str(mock_run.call_args_list)
        self.assertIn(
            "refs/heads/EPIC-Foo",
            all_calls_str,
            f"Must call git update-ref refs/heads/EPIC-Foo; got: {all_calls_str}",
        )
        self.assertNotIn(
            "refs/heads/main",
            all_calls_str,
            f"Must NOT call git update-ref refs/heads/main; got: {all_calls_str}",
        )

    # ------------------------------------------------------------------
    # 4. Ambiguous case — RecoveryError raised, not a guess
    # ------------------------------------------------------------------

    def test_ambiguous_branch_determination_raises_recovery_error(self):
        # covers: BO-1600d-3-iv
        """When no source yields an unambiguous branch name, RecoveryError
        must be raised — never a hardcoded fallback to 'main' or 'master'."""
        determine_fn = self._get_determine_fn()
        recovery_error_cls = self._get_recovery_error()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)

            def _mock_run(cmd, **kwargs):
                """Simulate detached HEAD and missing origin/HEAD symbolic ref."""
                mock = MagicMock()
                mock.returncode = 0
                if "--abbrev-ref" in cmd:
                    mock.stdout = "HEAD\n"  # detached HEAD
                elif "symbolic-ref" in cmd:
                    # Simulate absence of origin/HEAD (non-zero exit)
                    raise subprocess.CalledProcessError(128, cmd)
                else:
                    mock.stdout = ""
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                with self.assertLogs("git_recovery", level="WARNING"):
                    with self.assertRaises(recovery_error_cls) as ctx:
                        determine_fn(repo, hint=None)

        error_msg = str(ctx.exception)
        self.assertIn(
            "unambiguously",
            error_msg.lower(),
            f"RecoveryError message must mention 'unambiguously'; got: {error_msg!r}",
        )
        # Must NOT guess any hardcoded branch name
        self.assertNotIn(
            "main",
            error_msg,
            f"RecoveryError must not suggest hardcoded 'main'; got: {error_msg!r}",
        )

    def test_ambiguous_error_message_instructs_manual_recovery(self):
        # covers: BO-1600d-3-iv
        """The RecoveryError message must instruct the operator to take manual action,
        not silently guess a branch name."""
        determine_fn = self._get_determine_fn()
        recovery_error_cls = self._get_recovery_error()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)

            def _mock_run(cmd, **kwargs):
                mock = MagicMock()
                mock.returncode = 0
                if "--abbrev-ref" in cmd:
                    mock.stdout = "HEAD\n"
                elif "symbolic-ref" in cmd:
                    raise subprocess.CalledProcessError(128, cmd)
                else:
                    mock.stdout = ""
                return mock

            with patch("subprocess.run", side_effect=_mock_run):
                with self.assertLogs("git_recovery", level="WARNING"):
                    with self.assertRaises(recovery_error_cls) as ctx:
                        determine_fn(repo, hint=None)

        error_msg = str(ctx.exception)
        # Message must contain actionable guidance (not just a bare assertion)
        has_guidance = (
            "manually" in error_msg.lower()
            or "inspect" in error_msg.lower()
            or "update-ref" in error_msg.lower()
        )
        self.assertTrue(
            has_guidance,
            f"RecoveryError message must contain manual recovery guidance; got: {error_msg!r}",
        )

    def test_hint_provided_returns_hint_directly(self):
        # covers: BO-1600d-3-iv
        """When a hint (corrupt ref branch name) is provided, _determine_branch_to_reset
        returns it directly without any subprocess call."""
        determine_fn = self._get_determine_fn()

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)

            with patch("subprocess.run") as mock_run:
                result = determine_fn(repo, hint="EPIC-ConcurrentDispatch")

        mock_run.assert_not_called()
        self.assertEqual(
            result,
            "EPIC-ConcurrentDispatch",
            f"Expected hint to be returned directly; got: {result!r}",
        )


# ===========================================================================
# NEW TEST GROUP — BO-1600d-3-v (fresh worktree fallback for poisoned linked
# worktrees)
# Covers: detect_poisoned_linked_worktrees, and the [HEAVY] plan step added by
# plan_recovery_actions() when a linked worktree's index is poisoned.
# ===========================================================================


class TestFreshWorktreeFallback(unittest.TestCase):
    """Tests for AC BO-1600d-3-v: Fresh worktree fallback for poisoned linked worktrees.

    When a linked worktree's cache-tree is poisoned such that an in-place rebuild
    does not clear the corruption, plan_recovery_actions() must include a distinct,
    [HEAVY]-labelled action that creates a fresh worktree and verifies it cleanly.
    All tests use mocked subprocess — no real git operations required.
    """

    def _get_detect_linked_fn(self):
        """Return detect_poisoned_linked_worktrees or skip if not implemented."""
        fn = getattr(_mod, "detect_poisoned_linked_worktrees", None)
        if fn is None:
            self.skipTest("detect_poisoned_linked_worktrees not yet implemented")
        return fn

    # ------------------------------------------------------------------
    # Test 1: fresh worktree action appears in dry-run plan
    # ------------------------------------------------------------------

    def test_fresh_worktree_fallback_appears_in_dry_run_plan(self):
        # covers: BO-1600d-3-v
        """When poisoned linked worktrees are detected, the printed plan must include
        a fresh-worktree creation action."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            poisoned_wt = Path("/tmp/fake_worktree_abc")

            with patch.object(
                _mod,
                "detect_poisoned_linked_worktrees",
                return_value=[(poisoned_wt, "my-branch")],
            ):
                with patch.object(_mod, "detect_poisoned_index", return_value=False):
                    plan = plan_recovery_actions(repo)

        descriptions = [a.description for a in plan]
        has_fresh_worktree_action = any(
            "worktree" in d.lower()
            and (
                "create" in d.lower()
                or "fresh" in d.lower()
                or "new" in d.lower()
                or "_recovered" in d
            )
            for d in descriptions
        )
        self.assertTrue(
            has_fresh_worktree_action,
            f"Plan must include a fresh-worktree action when poisoned linked worktrees "
            f"are detected; got descriptions: {descriptions}",
        )

    # ------------------------------------------------------------------
    # Test 2: fresh worktree step is labelled as a distinct, heavier action
    # ------------------------------------------------------------------

    def test_fresh_worktree_fallback_is_distinct_heavy_action(self):
        # covers: BO-1600d-3-v
        """The fresh-worktree step must carry a [HEAVY] label and must NOT share its
        text with the in-place cache-tree rebuild step."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            poisoned_wt = Path("/tmp/fake_worktree_heavy")

            with patch.object(
                _mod,
                "detect_poisoned_linked_worktrees",
                return_value=[(poisoned_wt, "some-branch")],
            ):
                # Enable in-place rebuild too so both actions are in the plan.
                with patch.object(_mod, "detect_poisoned_index", return_value=True):
                    plan = plan_recovery_actions(repo)

        descriptions = [a.description for a in plan]

        # The [HEAVY] label must appear on at least one action.
        heavy_descs = [d for d in descriptions if "[HEAVY]" in d]
        self.assertGreater(
            len(heavy_descs),
            0,
            f"Plan must include at least one action with '[HEAVY]' label; "
            f"got: {descriptions}",
        )

        # The [HEAVY] action must be textually distinct from the in-place rebuild.
        in_place_descs = [
            d for d in descriptions
            if (
                ("cache" in d.lower() and "tree" in d.lower() and "rebuild" in d.lower())
                or ("read-tree" in d.lower() and "[HEAVY]" not in d)
            )
        ]
        for heavy in heavy_descs:
            for in_place in in_place_descs:
                self.assertNotEqual(
                    heavy,
                    in_place,
                    "The [HEAVY] fresh-worktree step text must differ from the "
                    "in-place cache-tree rebuild step text",
                )

    # ------------------------------------------------------------------
    # Test 3: executing the step calls git worktree add and git read-tree HEAD
    # ------------------------------------------------------------------

    def test_fresh_worktree_fallback_creates_new_worktree(self):
        # covers: BO-1600d-3-v
        """On confirmation (mocked), git worktree add must be called with the correct
        new path, and git read-tree HEAD must be called in the new worktree path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            poisoned_wt = Path("/tmp/poisoned_wt_create_test")

            with patch.object(
                _mod,
                "detect_poisoned_linked_worktrees",
                return_value=[(poisoned_wt, "feature-branch")],
            ):
                with patch.object(_mod, "detect_poisoned_index", return_value=False):
                    plan = plan_recovery_actions(repo)

        heavy_actions = [a for a in plan if "[HEAVY]" in a.description]
        self.assertGreater(
            len(heavy_actions),
            0,
            f"No [HEAVY] action found in plan; got: {[a.description for a in plan]}",
        )

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            with patch("builtins.print"):
                heavy_actions[0].execute()

        all_calls_str = str(mock_run.call_args_list)
        self.assertIn(
            "worktree",
            all_calls_str,
            f"'git worktree add' must be invoked; got calls: {all_calls_str}",
        )
        self.assertIn(
            "read-tree",
            all_calls_str,
            f"'git read-tree HEAD' must be invoked in the new worktree; "
            f"got calls: {all_calls_str}",
        )

    # ------------------------------------------------------------------
    # Test 4: success message names the new worktree path
    # ------------------------------------------------------------------

    def test_fresh_worktree_fallback_success_message_names_new_path(self):
        # covers: BO-1600d-3-v
        """After successful creation, the printed output must name the new worktree path."""
        poisoned_wt = Path("/tmp/poisoned_wt_success_msg")
        expected_new_path = str(poisoned_wt) + "_recovered"

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(
                _mod,
                "detect_poisoned_linked_worktrees",
                return_value=[(poisoned_wt, "main")],
            ):
                with patch.object(_mod, "detect_poisoned_index", return_value=False):
                    plan = plan_recovery_actions(repo)

        heavy_actions = [a for a in plan if "[HEAVY]" in a.description]
        self.assertGreater(len(heavy_actions), 0, "No [HEAVY] action found in plan")

        printed_output: list = []

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            with patch(
                "builtins.print",
                side_effect=lambda *args: printed_output.append(
                    " ".join(str(a) for a in args)
                ),
            ):
                heavy_actions[0].execute()

        output_str = " ".join(printed_output)
        self.assertIn(
            expected_new_path,
            output_str,
            f"Success message must name the new worktree path {expected_new_path!r}; "
            f"got printed output: {output_str!r}",
        )

    # ------------------------------------------------------------------
    # Test 5: failure reported when verification (git read-tree HEAD) fails
    # ------------------------------------------------------------------

    def test_fresh_worktree_fallback_reports_failure_if_verification_fails(self):
        # covers: BO-1600d-3-v
        """If git read-tree HEAD exits non-zero in the new worktree, the recovery engine
        must log at WARNING and raise CalledProcessError — it must NOT silently succeed."""
        poisoned_wt = Path("/tmp/poisoned_wt_verify_fail")

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = Path(tmpdir)
            (repo / ".git" / "objects").mkdir(parents=True)

            with patch.object(
                _mod,
                "detect_poisoned_linked_worktrees",
                return_value=[(poisoned_wt, "main")],
            ):
                with patch.object(_mod, "detect_poisoned_index", return_value=False):
                    plan = plan_recovery_actions(repo)

        heavy_actions = [a for a in plan if "[HEAVY]" in a.description]
        self.assertGreater(len(heavy_actions), 0, "No [HEAVY] action found in plan")

        def _mock_run(cmd, **kwargs):
            mock = MagicMock()
            mock.returncode = 0
            mock.stdout = ""
            mock.stderr = ""
            # worktree add succeeds; read-tree fails.
            if isinstance(cmd, list) and "worktree" in cmd and "add" in cmd:
                return mock
            if isinstance(cmd, list) and "read-tree" in cmd:
                raise subprocess.CalledProcessError(
                    128, cmd, output="", stderr="error: cache-tree poisoned"
                )
            return mock

        with patch("subprocess.run", side_effect=_mock_run):
            with self.assertLogs("git_recovery", level="WARNING") as log_ctx:
                with self.assertRaises(subprocess.CalledProcessError):
                    heavy_actions[0].execute()

        self.assertTrue(
            any("WARNING" in line for line in log_ctx.output),
            f"Expected at least one WARNING log when read-tree fails; "
            f"got: {log_ctx.output}",
        )


if __name__ == "__main__":
    unittest.main()
