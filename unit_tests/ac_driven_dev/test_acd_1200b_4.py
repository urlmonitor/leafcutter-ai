"""
MODULE: unit_tests/ac_driven_dev/test_acd_1200b_4.py
GOAL: Failing stubs for ACD-1200b-4 — goal_to_epic.py non-interactive readiness gate.
BUSINESS CONTEXT: The readiness gate in goal_to_epic.py currently blocks non-interactive
  runs by calling input() regardless of TTY state. ACD-1200b-4 requires:
  (1) --yes flag: non-interactive runs with --yes proceed past the gate without prompting.
  (2) --approved-only flag: generate epic using only already-approved leaf ACs.
  (3) No TTY + no flag: exit non-zero with clear message naming the flag to pass.
  (4) Backward compat: TTY present + no flag still prompts interactively (unchanged).
ARCHITECTURE: Tests 1-3 use subprocess (goal_to_epic.py CLI) to avoid import side-effects.
  Test 4 is a unit test that imports _build_parser directly to check arg registration.
  All tests are RED before implementation:
    - Tests 1-2: argparse rejects --yes/--approved-only ("unrecognized arguments"), exits 2.
    - Test 3: EOFError traceback from input(), not a clear user-readable message naming flag.
    - Test 4: parsed args missing 'yes' attribute (_build_parser() doesn't define it yet).
DECISION HISTORY
- 2026-07-20 [ACD-1200b-4/test-writer]: Initial failing stubs — all 4 tests RED.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_AC_STORE_DIR = _SCRIPTS_DIR / "ac_store"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))
if str(_AC_STORE_DIR) not in sys.path:
    sys.path.insert(0, str(_AC_STORE_DIR))


def _run_goal_to_epic(
    extra_args: list[str],
    stdin_devnull: bool = False,
    timeout: int = 15,
) -> subprocess.CompletedProcess:
    """Run goal_to_epic.py as a subprocess and return the completed process."""
    cmd = [sys.executable, str(_SCRIPTS_DIR / "goal_to_epic.py")] + extra_args
    env = dict(os.environ)
    env["PYTHONPATH"] = str(_SCRIPTS_DIR)
    return subprocess.run(
        cmd,
        stdin=subprocess.DEVNULL if stdin_devnull else None,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )


def _write_minimal_ac(store_dir: Path, ac_id: str, readiness: str, level: str = "L2") -> None:
    """Write a minimal AC YAML file into store_dir."""
    (store_dir / f"{ac_id}.yaml").write_text(
        f"id: {ac_id}\nreadiness: {readiness}\nlevel: {level}\ntitle: {ac_id} AC\n",
        encoding="utf-8",
    )


class TestAcd1200b4(unittest.TestCase):
    """Tests for ACD-1200b-4: non-interactive readiness gate."""

    def test_no_tty_with_flag_proceeds(self) -> None:
        # covers: ACD-1200b-4
        """AC-1 / AC-2: When --yes is passed with stdin redirected from /dev/null (no TTY),
        the command must proceed past the readiness gate and exit zero.

        Uses --dry-run to avoid needing generate_ticket_from_ac.py or a real inbox.
        The AC has readiness 'approved' so the all-approved fast-path is triggered;
        with --yes the gate must not call input() and must not exit non-zero.

        MUST be RED before implementation:
          --yes is not a recognised argparse flag, so goal_to_epic.py exits 2
          ("unrecognized arguments: --yes") and never reaches the readiness gate.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir) / "ac-store"
            inbox_dir = Path(tmpdir) / "inbox"
            store_root.mkdir()
            inbox_dir.mkdir()
            _write_minimal_ac(store_root, "FAKE-APPROVED-1", "approved")

            result = _run_goal_to_epic(
                [
                    "--ac", "FAKE-APPROVED-1",
                    "--store-root", str(store_root),
                    "--inbox-dir", str(inbox_dir),
                    "--yes",      # NEW FLAG — does not exist yet → argparse exit 2
                    "--dry-run",
                ],
                stdin_devnull=True,
            )

        # After implementation: proceeds past gate, exits 0.
        # FAILS RED: argparse exits 2 for unrecognised --yes before any gate logic runs.
        self.assertEqual(
            result.returncode,
            0,
            f"Expected exit 0 with --yes flag and no TTY, got {result.returncode}.\n"
            f"stderr: {result.stderr!r}\nstdout: {result.stdout!r}",
        )

    def test_approved_only_excludes_unapproved(self) -> None:
        # covers: ACD-1200b-4
        """AC-3: When --approved-only is passed, generation proceeds with only the
        already-approved leaf ACs and excludes unapproved ones.

        Sets up a store with two leaf ACs — one approved, one draft.
        With --approved-only the dry-run output must name APPROVED-ONLY-1
        but must NOT name UNAPPROVED-ONLY-1.

        MUST be RED before implementation:
          --approved-only is not a recognised argparse flag, so goal_to_epic.py
          exits 2 ("unrecognized arguments: --approved-only") before the readiness
          gate is reached.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir) / "ac-store"
            inbox_dir = Path(tmpdir) / "inbox"
            store_root.mkdir()
            inbox_dir.mkdir()
            _write_minimal_ac(store_root, "APPROVED-ONLY-1", "approved")
            _write_minimal_ac(store_root, "UNAPPROVED-ONLY-1", "draft")

            result = _run_goal_to_epic(
                [
                    "--ac", "APPROVED-ONLY-1",
                    "--store-root", str(store_root),
                    "--inbox-dir", str(inbox_dir),
                    "--approved-only",  # NEW FLAG — does not exist yet → argparse exit 2
                    "--dry-run",
                ],
                stdin_devnull=True,
            )

        # After implementation: exits 0 and output contains only approved ACs.
        # FAILS RED: argparse exits 2 for unrecognised --approved-only.
        self.assertEqual(
            result.returncode,
            0,
            f"Expected exit 0 with --approved-only flag, got {result.returncode}.\n"
            f"stderr: {result.stderr!r}\nstdout: {result.stdout!r}",
        )
        self.assertNotIn(
            "UNAPPROVED-ONLY-1",
            result.stdout,
            "Generation must exclude unapproved ACs when --approved-only is passed. "
            f"stdout: {result.stdout!r}",
        )

    def test_no_tty_no_flag_fails_clearly(self) -> None:
        # covers: ACD-1200b-4
        """AC-4: When no TTY is available (stdin=/dev/null) and no approval flag is
        passed, the command must exit non-zero and print a clear message that names
        the approval flag to pass — never hang waiting for input.

        Uses a DRAFT (unapproved) leaf AC so the readiness gate is reached.

        MUST be RED before implementation:
          The current code calls input() at the gate. With stdin=/dev/null,
          input() raises EOFError. The unhandled exception prints a traceback to
          stderr; the exit code is 1 (non-zero) but the output contains
          'EOFError', not a user-readable message naming '--yes' or
          '--approved-only'. The second assertion below catches this.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            store_root = Path(tmpdir) / "ac-store"
            inbox_dir = Path(tmpdir) / "inbox"
            store_root.mkdir()
            inbox_dir.mkdir()
            # Level L2 so traverse_ac_tree recognises it as a leaf.
            _write_minimal_ac(store_root, "DRAFT-GATE-1", "draft", level="L2")

            result = _run_goal_to_epic(
                [
                    "--ac", "DRAFT-GATE-1",
                    "--store-root", str(store_root),
                    "--inbox-dir", str(inbox_dir),
                    # No --yes or --approved-only intentionally
                ],
                stdin_devnull=True,  # No controlling TTY
            )

        # Must exit non-zero (must not hang or exit 0).
        self.assertNotEqual(
            result.returncode,
            0,
            f"Expected non-zero exit when no TTY and no approval flag, "
            f"got returncode={result.returncode}.",
        )

        # Must emit a clear, user-readable message naming the flag to pass.
        # FAILS RED: current output is an EOFError traceback, not a flag-naming message.
        combined_output = result.stdout + result.stderr
        has_flag_mention = (
            "--yes" in combined_output
            or "--approved-only" in combined_output
        )
        self.assertTrue(
            has_flag_mention,
            f"Expected output to name the approval flag (--yes or --approved-only) "
            f"when run with no TTY and no flag, but the message did not contain it.\n"
            f"stdout: {result.stdout!r}\n"
            f"stderr: {result.stderr!r}",
        )

    def test_tty_no_flag_prompts_as_before(self) -> None:
        # covers: ACD-1200b-4
        """AC-5: When a controlling TTY is present and no approval flag is supplied,
        the existing interactive prompt behaviour is unchanged (backward compatibility).

        Verifies that _build_parser() defines the --yes argument with a default of
        False, so that a caller who does NOT pass --yes gets the interactive prompt
        path (args.yes == False → fall through to input()-based gate).

        MUST be RED before implementation:
          _build_parser() does not define --yes. The parsed Namespace therefore
          has no 'yes' attribute. The hasattr(args, 'yes') assertion below fails.
        """
        from goal_to_epic import _build_parser

        parser = _build_parser()
        # Simulate a TTY user who omits the new --yes flag entirely.
        args = parser.parse_args([
            "--ac", "FAKE-BACK-COMPAT-1",
            "--store-root", "/tmp",
            "--inbox-dir", "/tmp",
            # No --yes flag
        ])

        # After implementation: args.yes must exist and default to False so that
        # the interactive prompt path is the default when no flag is passed.
        # FAILS RED: _build_parser() does not define --yes; args has no 'yes' attribute.
        self.assertTrue(
            hasattr(args, "yes"),
            "Expected _build_parser() to define --yes (args.yes attribute absent — "
            "implementation not yet landed).",
        )
        # With --yes absent from the command line, the default must be False,
        # ensuring the interactive prompt path remains the default for TTY users.
        self.assertFalse(
            args.yes,
            f"Expected args.yes to default to False when --yes is not passed, "
            f"got {getattr(args, 'yes', '<missing>')!r}.",
        )


if __name__ == "__main__":
    unittest.main()
