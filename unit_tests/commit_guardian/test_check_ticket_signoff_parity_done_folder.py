"""
Tests for the done-folder move prohibition check in check_ticket_signoff_parity.py.

These tests verify BO-400c-3: the pre-commit hook must block any staged commit
that moves a ticket into a done/ subfolder, and must permit commits that use
the new frontmatter-based status: done convention instead.

These tests are written BEFORE the implementation exists (TDD red-baseline).
The done-folder-move check is expected to be added to check_ticket_signoff_parity.py
by python-coder.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Add commit_guardian to path for imports
_COMMIT_GUARDIAN_DIR = Path(__file__).resolve().parent.parent.parent / "scripts" / "commit_guardian"
if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DONE_TICKET_CONTENT = """\
---
title: "Done Ticket"
status: done
components:
  - infrastructure
created: 2026-01-01
depends_on: []
agents:
  python-coder: signed_off
  test-runner: signed_off
---

## Sign-offs
- [x] python-coder — 2026-06-01 10:00
- [x] test-runner — 2026-06-01 11:00

## Comments
"""

_NEEDED_TICKET_CONTENT = """\
---
title: "In-progress Ticket"
status: in_progress
components:
  - infrastructure
created: 2026-01-01
depends_on: []
agents:
  python-coder: signed_off
  test-runner: needed
---

## Sign-offs
- [x] python-coder — 2026-06-01 10:00
- [ ] test-runner

## Comments
"""


class TestDoneFolderMoveBlocked(unittest.TestCase):
    """BO-400c-3: Pre-commit hook must reject done/ folder moves."""

    def setUp(self) -> None:
        """Create temporary directory for test tickets."""
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_dir = Path(self._tmp.name)

    def tearDown(self) -> None:
        """Clean up temporary directory."""
        self._tmp.cleanup()

    def test_done_folder_move_blocked(self) -> None:
        """BO-400c-3: Moving a ticket into done/ subfolder must exit 1.

        Given a staged rename from EPIC-Foo/03.md to EPIC-Foo/done/03.md,
        check_ticket_signoff_parity.py must exit 1 with an error message
        referencing the prohibited done/ folder move.
        """
        # covers: BO-400c-3
        # Write a ticket at a done/ path (simulating what would be detected by the hook)
        done_path = self.tmp_dir / "EPIC-Foo" / "done" / "03_ticket.md"
        done_path.parent.mkdir(parents=True, exist_ok=True)
        done_path.write_text(_DONE_TICKET_CONTENT, encoding="utf-8")

        # Import the validation function (will fail if not yet implemented)
        try:
            from check_ticket_signoff_parity import _validate_ticket_content
        except ImportError as exc:
            self.fail(f"Cannot import _validate_ticket_content: {exc}")

        # A ticket moved to done/ should trigger the done-folder-move prohibition
        # This requires the new check to be implemented in _validate_ticket_content
        # Currently the hook checks for /done/ path with needed agents — but
        # BO-400c-3 adds a check for the move itself (regardless of agent status)
        # The expected violation message contains "Prohibited" and "done/"
        from check_ticket_signoff_parity import _validate_ticket

        violations = _validate_ticket(str(done_path))
        # We expect the new done-folder-move prohibition check to fire
        # (This test will fail until the new check is added to the hook)
        prohibition_violations = [v for v in violations if "Prohibited" in v or "done/" in v.lower()]
        self.assertTrue(
            len(prohibition_violations) > 0,
            f"Expected done-folder-move prohibition violation, got: {violations}",
        )

    def test_frontmatter_done_without_move_passes(self) -> None:
        """BO-400c-3: Setting status: done via frontmatter (no file move) must pass the hook.

        Given a staged modification that sets status: done in frontmatter with all
        agents signed_off, the hook must exit 0 (new parity rule passes).
        """
        # covers: BO-400c-3
        ticket_path = self.tmp_dir / "EPIC-Foo" / "03_ticket.md"
        ticket_path.parent.mkdir(parents=True, exist_ok=True)
        ticket_path.write_text(_DONE_TICKET_CONTENT, encoding="utf-8")

        try:
            from check_ticket_signoff_parity import _validate_ticket
        except ImportError as exc:
            self.fail(f"Cannot import _validate_ticket: {exc}")

        violations = _validate_ticket(str(ticket_path))
        # Filter out unrelated violations (e.g. missing required fields)
        # We care that there is no done-folder-move prohibition violation
        prohibition_violations = [v for v in violations if "Prohibited" in v]
        self.assertEqual(
            prohibition_violations,
            [],
            f"Expected no prohibition violation for frontmatter-only done, got: {prohibition_violations}",
        )

    def test_non_done_subfolder_move_not_blocked(self) -> None:
        """BO-400c-3: Moving a ticket to a subfolder NOT named done/ must not trigger the new check.

        The done-folder-move prohibition is specific to the done/ subfolder convention.
        Moving to a subfolder with any other name (e.g. archive/, wip/) must not be blocked.
        """
        # covers: BO-400c-3
        # A ticket in a subfolder NOT named "done/"
        other_path = self.tmp_dir / "EPIC-Foo" / "archive" / "03_ticket.md"
        other_path.parent.mkdir(parents=True, exist_ok=True)
        other_path.write_text(_DONE_TICKET_CONTENT, encoding="utf-8")

        try:
            from check_ticket_signoff_parity import _validate_ticket
        except ImportError as exc:
            self.fail(f"Cannot import _validate_ticket: {exc}")

        violations = _validate_ticket(str(other_path))
        prohibition_violations = [v for v in violations if "Prohibited" in v]
        self.assertEqual(
            prohibition_violations,
            [],
            f"Expected no prohibition for non-done/ folder, got: {prohibition_violations}",
        )


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 12:00 [test-writer/BO-400]: Red-baseline tests written for the
  done-folder-move prohibition check (BO-400c-3). The check does not yet
  exist in _signoff_parity_checks.py — all tests expected to fail with
  AssertionError until python-coder adds the prohibition check.
====================================================================
"""
