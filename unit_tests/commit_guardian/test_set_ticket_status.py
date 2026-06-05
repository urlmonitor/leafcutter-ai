"""
Tests for scripts/set_ticket_status.py — ticket status transition script.

These tests were written BEFORE the implementation exists (TDD red-baseline).
All tests are expected to fail with ImportError or AssertionError until
python-coder implements scripts/set_ticket_status.py.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Helper — build a minimal ticket file with specified frontmatter
# ---------------------------------------------------------------------------

_TICKET_TEMPLATE = """\
---
title: "Test Ticket"
status: {status}
components:
  - infrastructure
created: 2026-01-01
depends_on: []
agents:
{agents}
---

# Test ticket body
"""

_TICKET_TEMPLATE_NO_STATUS = """\
---
title: "Test Ticket"
components:
  - infrastructure
created: 2026-01-01
depends_on: []
agents:
  python-coder: signed_off
---

# Test ticket body (no status field)
"""


def _make_ticket(tmp_dir: Path, status: str, agents: str = "  python-coder: signed_off") -> Path:
    """Write a ticket file with the specified status and agents map.

    Args:
        tmp_dir: Temporary directory path to write the file into.
        status: The status value to set in frontmatter.
        agents: YAML agents block (indented).

    Returns:
        Path to the written ticket file.
    """
    content = _TICKET_TEMPLATE.format(status=status, agents=agents)
    ticket_path = tmp_dir / "test_ticket.md"
    ticket_path.write_text(content, encoding="utf-8")
    return ticket_path


def _make_ticket_no_status(tmp_dir: Path) -> Path:
    """Write a ticket file with no status field in frontmatter.

    Args:
        tmp_dir: Temporary directory path to write the file into.

    Returns:
        Path to the written ticket file.
    """
    ticket_path = tmp_dir / "test_ticket_no_status.md"
    ticket_path.write_text(_TICKET_TEMPLATE_NO_STATUS, encoding="utf-8")
    return ticket_path


def _run_script(ticket_path: Path, status: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run set_ticket_status.py as a subprocess.

    Args:
        ticket_path: Absolute path to the ticket file.
        status: Target status to set.
        extra_args: Optional additional CLI arguments (e.g. ["--force"]).

    Returns:
        CompletedProcess with returncode, stdout, stderr.
    """
    script = Path(__file__).resolve().parent.parent.parent / "scripts" / "set_ticket_status.py"
    cmd = [sys.executable, str(script), "--ticket", str(ticket_path), "--status", status]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(cmd, capture_output=True, text=True)


class TestSetTicketStatusTransitions(unittest.TestCase):
    """Tests for basic status transition behavior of set_ticket_status.py."""

    def setUp(self) -> None:
        """Create a temporary directory for test ticket files."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        """Clean up the temporary directory."""
        self._tmp.cleanup()

    def test_todo_to_in_progress_updates_frontmatter(self) -> None:
        """BO-400b-1: Script updates frontmatter status from todo to in_progress.

        Given a ticket with status: todo, invoking with --status in_progress
        must rewrite the frontmatter status field and preserve all other content.
        """
        # covers: BO-400b-1
        ticket = _make_ticket(self.tmp_dir, "todo")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        content = ticket.read_text(encoding="utf-8")
        self.assertIn("status: in_progress", content)
        self.assertNotIn("status: todo", content)
        self.assertIn("# Test ticket body", content)  # body preserved

    def test_same_status_is_noop(self) -> None:
        """BO-400b-2: Invoking with the current status is an idempotent no-op.

        Given status: in_progress, invoking with --status in_progress must exit 0,
        print "(no change)", and not modify the file.
        """
        # covers: BO-400b-2
        ticket = _make_ticket(self.tmp_dir, "in_progress")
        mtime_before = ticket.stat().st_mtime
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        self.assertIn("no change", result.stdout.lower())
        mtime_after = ticket.stat().st_mtime
        self.assertEqual(mtime_before, mtime_after, "File should not be modified for no-op transition")

    def test_done_transition_blocked_by_needed_agents(self) -> None:
        """BO-400b-1-i: Script refuses done transition when agents have needed status.

        Given a ticket with test-runner: needed and commit: needed, invoking
        --status done without --force must exit 1 and not modify the file.
        """
        # covers: BO-400b-1-i
        agents = "  test-runner: needed\n  commit: needed"
        ticket = _make_ticket(self.tmp_dir, "in_progress", agents=agents)
        content_before = ticket.read_text(encoding="utf-8")
        result = _run_script(ticket, "done")
        self.assertEqual(result.returncode, 1, f"Expected exit 1, got {result.returncode}")
        self.assertIn("Cannot set done", result.stdout + result.stderr)
        content_after = ticket.read_text(encoding="utf-8")
        self.assertEqual(content_before, content_after, "File must not be modified on rejected transition")

    def test_done_transition_forced_bypasses_parity(self) -> None:
        """BO-400b-1-i (--force): --force bypasses the parity check for done transition.

        Given a ticket with needed agents, --status done --force must exit 0
        and update status to done.
        """
        # covers: BO-400b-1-i
        agents = "  test-runner: needed\n  commit: needed"
        ticket = _make_ticket(self.tmp_dir, "in_progress", agents=agents)
        result = _run_script(ticket, "done", extra_args=["--force"])
        self.assertEqual(result.returncode, 0, f"Expected exit 0 with --force, got {result.returncode}. stderr: {result.stderr}")
        content = ticket.read_text(encoding="utf-8")
        self.assertIn("status: done", content)

    def test_invalid_transition_rejected_without_force(self) -> None:
        """BO-400b-2: Invalid transitions (done -> in_progress) are rejected without --force.

        Script must exit 1 and print an error message about invalid transition.
        """
        # covers: BO-400b-2
        ticket = _make_ticket(self.tmp_dir, "done")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 1, f"Expected exit 1, got {result.returncode}")
        self.assertIn("Invalid transition", result.stdout + result.stderr)

    def test_missing_status_field_treated_as_todo(self) -> None:
        """BO-400b-2-i: Missing status field is treated as todo.

        Given a ticket with no status: field, invoking --status in_progress must
        insert status: in_progress and print the '(absent, treated as todo)' variant.
        """
        # covers: BO-400b-2-i
        ticket = _make_ticket_no_status(self.tmp_dir)
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        content = ticket.read_text(encoding="utf-8")
        self.assertIn("status: in_progress", content)
        output = result.stdout + result.stderr
        self.assertIn("absent", output.lower())

    def test_git_staging_on_success(self) -> None:
        """BO-400b-3: Successful update stages the modified file via git add.

        After a successful status update, git status --porcelain must show the
        ticket file as staged-modified (M in the index column).
        """
        # covers: BO-400b-3
        # This test requires a git repo context; skip if running outside git
        try:
            git_check = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True,
                text=True,
                cwd=str(self.tmp_dir.parent.parent.parent),
            )
            if git_check.returncode != 0:
                self.skipTest("Not running inside a git repository")
        except FileNotFoundError:
            self.skipTest("git not available")

        ticket = _make_ticket(self.tmp_dir, "todo")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        git_status = subprocess.run(
            ["git", "status", "--porcelain", str(ticket)],
            capture_output=True,
            text=True,
            cwd=str(self.tmp_dir.parent.parent.parent),
        )
        # File should be staged (M in first column) after a successful update
        self.assertIn("M", git_status.stdout[:2], f"Expected staged file, got: {git_status.stdout!r}")

    def test_no_staging_on_noop(self) -> None:
        """BO-400b-3 (no-op): No staging on same-status no-op call.

        When the transition is a no-op (same status), git add must NOT be called
        and the file must not appear as staged.
        """
        # covers: BO-400b-3
        ticket = _make_ticket(self.tmp_dir, "in_progress")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 0, f"Expected exit 0, got {result.returncode}. stderr: {result.stderr}")
        # On a no-op, the file is unchanged — it should not appear as staged
        # (if it was previously staged, it would appear as ' M'; if untracked, '??')
        git_status = subprocess.run(
            ["git", "status", "--porcelain", str(ticket)],
            capture_output=True,
            text=True,
            cwd=str(self.tmp_dir.parent.parent.parent),
        )
        # Either not staged (empty output) or untracked — not M in index column
        if git_status.stdout.strip():
            self.assertNotEqual("M", git_status.stdout[0], "File must not be staged on no-op")

    def test_no_staging_on_rejection(self) -> None:
        """BO-400b-3 (rejection): No staging on a rejected transition.

        When the transition is rejected (invalid), git add must NOT be called.
        """
        # covers: BO-400b-3
        ticket = _make_ticket(self.tmp_dir, "done")
        result = _run_script(ticket, "in_progress")
        self.assertEqual(result.returncode, 1, "Expected exit 1 for invalid transition")
        # File must not be staged after rejection
        git_status = subprocess.run(
            ["git", "status", "--porcelain", str(ticket)],
            capture_output=True,
            text=True,
            cwd=str(self.tmp_dir.parent.parent.parent),
        )
        if git_status.stdout.strip():
            self.assertNotEqual("M", git_status.stdout[0], "File must not be staged on rejection")


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 12:00 [test-writer/BO-400]: Red-baseline tests written before
  set_ticket_status.py exists. All tests expected to fail with FileNotFoundError
  (script absent) or non-zero returncode assertions until python-coder implements
  scripts/set_ticket_status.py per BO-400b spec.
====================================================================
"""
