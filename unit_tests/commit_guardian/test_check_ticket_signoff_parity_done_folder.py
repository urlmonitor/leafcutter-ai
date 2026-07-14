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
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

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

# _build_rename_map lives in check_ticket_signoff_parity (same template dir).
# Imported lazily inside the test class to avoid module-level side effects.
_csp_module = None


def _get_csp_module():
    """Return check_ticket_signoff_parity module, importing it lazily."""
    global _csp_module
    if _csp_module is None:
        import importlib
        _csp_module = importlib.import_module("check_ticket_signoff_parity")
    return _csp_module


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


class TestBuildRenameMapProductionPath(unittest.TestCase):
    """BO-400c-3-i: Production path — _build_rename_map must include M-status in-place edits.

    The pre-existing unit tests (TestDoneFolderMoveBlocked) call
    _check_done_folder_prohibition(path, old_path=done_path) directly, which
    bypasses the _build_rename_map() logic.  This class exercises the PRODUCTION
    path: _build_rename_map() must return old_path==new_path for M-status entries
    so that main() passes old_path=done_path when a done/ ticket is edited in place.
    """

    def _make_git_output(self, lines: list[str]) -> str:
        """Join tab-separated git name-status lines into stdout text."""
        return "\n".join(lines) + "\n"

    def test_modified_done_path_maps_to_itself(self):
        """_build_rename_map() must map a modified-in-place done/ path to itself.

        When git diff --cached reports ``M\ttickets/done/03_ticket.md``,
        _build_rename_map() must return {done_path: done_path} (old_path == new_path).
        This enables _check_done_folder_prohibition to detect the in-place edit
        and skip the false-positive prohibition (BO-400c-3-i).
        """
        # covers: BO-400c-3-i
        csp = _get_csp_module()
        done_path = "tickets/00_inbox/epics/EPIC-Foo/done/03_ticket.md"
        fake_stdout = self._make_git_output([f"M\t{done_path}"])
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=fake_stdout, stderr=""
        )
        with patch("subprocess.run", return_value=fake_result):
            rename_map = csp._build_rename_map()
        self.assertIn(
            done_path,
            rename_map,
            msg=(
                f"Expected _build_rename_map() to include '{done_path}' when git "
                f"reports M-status for that path. Got: {rename_map}. "
                "The fix must query --diff-filter=RM (not =R) and map M entries to themselves."
            ),
        )
        self.assertEqual(
            rename_map[done_path],
            done_path,
            msg=(
                f"Expected rename_map['{done_path}'] == '{done_path}' (old_path == new_path "
                "for in-place edit), but got: {rename_map[done_path]!r}."
            ),
        )

    def test_rename_into_done_still_maps_old_to_new(self):
        """_build_rename_map() must still return {new_path: old_path} for R-status renames.

        Renaming a ticket from an inbox path into done/ must be preserved:
        rename_map[new_done_path] == old_inbox_path so that
        _check_done_folder_prohibition fires the genuine-move prohibition.
        """
        # covers: BO-400c-3-i
        csp = _get_csp_module()
        old_path = "tickets/00_inbox/epics/EPIC-Foo/03_ticket.md"
        new_path = "tickets/00_inbox/epics/EPIC-Foo/done/03_ticket.md"
        # R95 is the typical rename-similarity score from git
        fake_stdout = self._make_git_output([f"R95\t{old_path}\t{new_path}"])
        fake_result = subprocess.CompletedProcess(
            args=[], returncode=0, stdout=fake_stdout, stderr=""
        )
        with patch("subprocess.run", return_value=fake_result):
            rename_map = csp._build_rename_map()
        self.assertIn(
            new_path,
            rename_map,
            msg=(
                f"Expected _build_rename_map() to include '{new_path}' for an R-status "
                f"rename. Got: {rename_map}."
            ),
        )
        self.assertEqual(
            rename_map[new_path],
            old_path,
            msg=(
                f"Expected rename_map['{new_path}'] == '{old_path}' (genuine rename), "
                f"but got: {rename_map[new_path]!r}."
            ),
        )

    def test_inplace_done_edit_not_blocked_via_prohibition_with_oldpath(self):
        """When old_path == done_path, _check_done_folder_prohibition must NOT fire.

        This is the final step of the production chain: after _build_rename_map()
        returns {done_path: done_path} for an M-status entry, main() passes
        old_path=done_path to _validate_ticket, which passes it to
        _check_done_folder_prohibition.  The prohibition must NOT fire because
        old_in_done is True (no move occurred).
        """
        # covers: BO-400c-3-i
        done_path = "tickets/00_inbox/epics/EPIC-Foo/done/03_ticket.md"
        # Simulate what _build_rename_map returns for M-status: old_path == new_path
        old_path_from_map = done_path
        violations = _check_done_folder_prohibition(done_path, old_path=old_path_from_map)
        prohibition_violations = [v for v in violations if "Prohibited" in v]
        self.assertEqual(
            prohibition_violations,
            [],
            msg=(
                "Expected no 'Prohibited' violation when old_path == done_path "
                "(in-place edit at a done/ path, no move). "
                f"Got: {prohibition_violations}. "
                "This confirms the production chain is correct end-to-end."
            ),
        )

    def test_genuine_rename_into_done_is_blocked(self):
        """A genuine rename into done/ (old_path NOT in done/) must still be blocked.

        After _build_rename_map() returns {done_path: inbox_path} for an R-status
        rename, main() passes old_path=inbox_path to _validate_ticket.  Since
        old_in_done is False, the prohibition must fire.
        """
        # covers: BO-400c-3-i
        inbox_path = "tickets/00_inbox/epics/EPIC-Foo/03_ticket.md"
        done_path = "tickets/00_inbox/epics/EPIC-Foo/done/03_ticket.md"
        violations = _check_done_folder_prohibition(done_path, old_path=inbox_path)
        prohibition_violations = [v for v in violations if "Prohibited" in v]
        self.assertTrue(
            len(prohibition_violations) > 0,
            msg=(
                "Expected a 'Prohibited' violation when old_path is NOT in done/ "
                f"(genuine rename into done/). Got: {violations}."
            ),
        )


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
