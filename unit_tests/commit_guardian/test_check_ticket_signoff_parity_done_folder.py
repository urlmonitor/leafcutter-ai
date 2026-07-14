"""
Tests for the done-folder move prohibition check in check_ticket_signoff_parity.py.

These tests verify BO-400c-3 and sub-ACs: the pre-commit hook must block any staged
commit that MOVES a ticket into a done/ or tickets/99_done/ subfolder, and must NOT
block commits that merely edit files already residing at such a path in-place.

The check must be MOVE-BASED (detect old_path → new_path path change), not
PRESENCE-BASED (any path containing done/).  The existing _check_done_folder_prohibition
is presence-based and misses tickets/99_done/ entirely — this file establishes the
red baseline for those two defects plus the missing finalize env-flag carve-out.

TDD red-baseline: all three tests will fail until python-coder:
  1. Extends _check_done_folder_prohibition to accept an ``old_path`` keyword argument
     so callers can supply the pre-move path for move detection.
  2. Adds tickets/99_done/ detection (current check for '/done/' never matches '/99_done/').
  3. Adds the LEAFCUTTER_FINALIZE_ARCHIVE env-flag carve-out that exempts the finalize
     archive step from the 99_done prohibition.
  4. Fixes the pytest_ac_enforcement XFAIL masking so these assertions actually run.

Import path note: the canonical source lives at
  templates/scripts/commit_guardian/_signoff_parity_checks.py
NOT scripts/commit_guardian/ (which contains only commit_guardian.json and hook wrappers
in this worktree).  The path below is the corrected import path.
"""

import os
import sys
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Import path — canonical template directory (NOT scripts/commit_guardian/)
# ---------------------------------------------------------------------------

_COMMIT_GUARDIAN_DIR = (
    Path(__file__).resolve().parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
)
if str(_COMMIT_GUARDIAN_DIR) not in sys.path:
    sys.path.insert(0, str(_COMMIT_GUARDIAN_DIR))

from _signoff_parity_checks import _check_done_folder_prohibition  # noqa: E402


class TestDoneFolderMoveBlocked(unittest.TestCase):
    """BO-400c-3, BO-400c-3-i, BO-400c-3-ii: Move-based done-folder prohibition."""

    def test_done_folder_move_blocked(self) -> None:
        """BO-400c-3: A staged move from an inbox path into a done/ path must be blocked.

        Given a staged rename from EPIC-Foo/03_ticket.md to EPIC-Foo/done/03_ticket.md,
        the done-folder prohibition must detect the path change (old_path != new_path
        where new_path contains /done/) and return a 'Prohibited' violation.

        Python-coder must extend _check_done_folder_prohibition to accept an ``old_path``
        keyword argument.  When old_path does NOT contain /done/ but the new ticket_path
        DOES, the function must fire the prohibition.

        Red baseline: calling with old_path kwarg raises TypeError until the signature
        is updated.
        """
        # covers: BO-400c-3
        old_path = "tickets/00_inbox/epics/EPIC-Foo/03_ticket.md"
        new_path = "tickets/00_inbox/epics/EPIC-Foo/done/03_ticket.md"

        # After the fix, the function will accept old_path and detect the move.
        # Currently: TypeError — _check_done_folder_prohibition() got an unexpected
        # keyword argument 'old_path'.
        violations = _check_done_folder_prohibition(new_path, old_path=old_path)
        prohibition_violations = [
            v for v in violations if "Prohibited" in v or "done/" in v.lower()
        ]
        self.assertTrue(
            len(prohibition_violations) > 0,
            f"Expected a done-folder-move prohibition violation for move "
            f"from '{old_path}' to '{new_path}', but got: {violations}",
        )

    def test_in_place_done_edit_not_blocked(self) -> None:
        """BO-400c-3-i: Editing a file already residing at done/ (no move) must NOT be blocked.

        Given a ticket already committed at EPIC-Foo/done/03_ticket.md (i.e. old_path ==
        new_path, no path change), the prohibition must NOT fire.  The current presence-
        based implementation fires for ANY path containing /done/, which is a false
        positive for in-place edits.

        Python-coder must ensure the prohibition only fires when old_path (the HEAD path)
        differs from ticket_path (the staged path) AND the new path is in a done/ folder.

        Red baseline: calling with old_path kwarg raises TypeError until the signature
        is updated, so the assertion about no violations never runs.
        """
        # covers: BO-400c-3-i
        # Simulate an in-place edit: the file already lived at done/ before this commit.
        done_path = "tickets/00_inbox/epics/EPIC-Foo/done/03_ticket.md"

        # old_path == new_path → no move → no prohibition expected.
        # Currently: TypeError — unexpected keyword argument 'old_path'.
        violations = _check_done_folder_prohibition(done_path, old_path=done_path)
        prohibition_violations = [v for v in violations if "Prohibited" in v]
        self.assertEqual(
            prohibition_violations,
            [],
            f"Expected no 'Prohibited' violation for an in-place edit of a done/ "
            f"file (path unchanged), but got: {prohibition_violations}",
        )

    def test_99_done_move_caught(self) -> None:
        """BO-400c-3-ii: A move into tickets/99_done/ must be blocked; the finalize env-flag exempts it.

        Given a staged commit on a branch that moves a ticket from an epic folder into
        tickets/99_done/, the prohibition must fire.  The current '/done/' substring check
        never matches '/99_done/' (99_done does not contain the bare '/done/' sequence), so
        this case is silently missed.

        Part A — ordinary branch commit: prohibited (no LEAFCUTTER_FINALIZE_ARCHIVE flag).
        Part B — finalize archive step: exempted (LEAFCUTTER_FINALIZE_ARCHIVE=1 is set).

        Red baseline: calling with old_path kwarg raises TypeError until the signature
        is updated, so neither Part A nor Part B assertion can run.
        """
        # covers: BO-400c-3-ii
        old_path = "tickets/00_inbox/epics/EPIC-Foo/03_ticket.md"
        new_path = "tickets/99_done/03_ticket.md"

        # Ensure the finalize env-flag is absent for Part A.
        saved_flag = os.environ.pop("LEAFCUTTER_FINALIZE_ARCHIVE", None)
        try:
            # --- Part A: 99_done move must be blocked on an ordinary branch commit ---
            # Currently: TypeError — unexpected keyword argument 'old_path'.
            violations = _check_done_folder_prohibition(new_path, old_path=old_path)
            prohibition_violations = [
                v for v in violations if "Prohibited" in v or "99_done" in v.lower()
            ]
            self.assertTrue(
                len(prohibition_violations) > 0,
                f"Expected a prohibition violation for a move into tickets/99_done/ "
                f"(ordinary branch commit), but got: {violations}",
            )

            # --- Part B: finalize carve-out — exempted when LEAFCUTTER_FINALIZE_ARCHIVE=1 ---
            os.environ["LEAFCUTTER_FINALIZE_ARCHIVE"] = "1"
            violations_with_flag = _check_done_folder_prohibition(new_path, old_path=old_path)
            prohibition_with_flag = [
                v for v in violations_with_flag
                if "Prohibited" in v or "99_done" in v.lower()
            ]
            self.assertEqual(
                prohibition_with_flag,
                [],
                f"Expected no prohibition violation for a tickets/99_done/ move when "
                f"LEAFCUTTER_FINALIZE_ARCHIVE=1 (finalize carve-out), but got: "
                f"{prohibition_with_flag}",
            )
        finally:
            # Restore the env to its original state.
            os.environ.pop("LEAFCUTTER_FINALIZE_ARCHIVE", None)
            if saved_flag is not None:
                os.environ["LEAFCUTTER_FINALIZE_ARCHIVE"] = saved_flag


if __name__ == "__main__":
    unittest.main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-14 [test-writer/BO-400c-3]: Rewrote to cover the three required tests
  from the ticket: test_done_folder_move_blocked (BO-400c-3), test_in_place_done_edit_not_blocked
  (BO-400c-3-i), test_99_done_move_caught (BO-400c-3-ii).  Fixed import path from
  scripts/commit_guardian/ (wrong: only contains JSON + hook wrappers) to
  templates/scripts/commit_guardian/ (canonical Python source).  All three tests are
  red-baseline: TypeError from the unsupported old_path kwarg until python-coder
  extends _check_done_folder_prohibition.
- 2026-06-05 12:00 [test-writer/BO-400]: Original red-baseline tests written for the
  done-folder-move prohibition check (BO-400c-3).  The check did not yet exist in
  _signoff_parity_checks.py — tests expected to fail with AssertionError until
  python-coder added the prohibition check.
====================================================================
"""
