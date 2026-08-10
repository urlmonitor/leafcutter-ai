"""
MODULE: test_bo_1000c_1b
GOAL: Verify AC BO-1000c-1b — the /finalize-feature launcher command doc
    (templates/commands/finalize-feature.md) instructs the launcher to poll the
    run-progress journal and relay each new line into the main conversation.

    Static-analysis coverage backfill for an already-shipped DOC/PROSE artifact
    (EPIC-InFlightVisibility, PR #360). The tests read the command doc as text
    and assert on the ACTUAL instruction phrases present, following the pattern
    established in test_bo_1000a_1.py.

    AC BO-1000c-1b requires the command doc to instruct:
      (a) after starting the background run, POLL the run-progress journal while
          the run is in flight;
      (b) RELAY each new progress line into the main conversation (not requiring
          the user to open the live-workflows view);
      (c) relay is INCREMENTAL (new lines only, no duplicates) and STOPS cleanly
          when the run terminates;
      (d) DEGRADE gracefully if the journal is absent/unreadable.

TICKET: 14/15_TICKET-20260720-BO-1000c-1b.md
AC: BO-1000c-1b
"""

from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOC_PATH = _REPO_ROOT / "templates" / "commands" / "finalize-feature.md"


def _doc_text() -> str:
    """Return the full text of the finalize-feature command doc."""
    return _DOC_PATH.read_text(encoding="utf-8")


class TestFinalizeLauncherPollAndRelay(unittest.TestCase):
    """AC BO-1000c-1b: the /finalize-feature command doc instructs the launcher
    to poll the run-progress journal and incrementally relay new lines into the
    main conversation, stopping cleanly and degrading gracefully.
    """

    def test_doc_file_exists(self):
        # covers: BO-1000c-1b
        """The delivered command-doc artifact must exist on disk."""
        self.assertTrue(
            _DOC_PATH.is_file(),
            msg=f"AC BO-1000c-1b artifact missing: {_DOC_PATH} does not exist.",
        )

    def test_a_poll_journal_while_in_flight(self):
        # covers: BO-1000c-1b
        """(a) The doc must instruct the launcher to POLL the run-progress
        journal while the run is in flight, AFTER starting the background run."""
        text = _doc_text()
        self.assertRegex(
            text,
            r"poll the run-progress journal",
            msg=(
                "The doc must instruct the launcher to poll the run-progress "
                "journal."
            ),
        )
        # Polling must be tied to the in-flight window and start after launch.
        self.assertRegex(
            text,
            r"while the run is in flight",
            msg=(
                "The doc must scope polling to while the run is in flight."
            ),
        )
        self.assertRegex(
            text,
            r"[Bb]egin polling immediately",
            msg=(
                "The doc must instruct the launcher to begin polling "
                "immediately after the background run is launched."
            ),
        )

    def test_b_relay_each_new_line_into_main_conversation(self):
        # covers: BO-1000c-1b
        """(b) The doc must instruct the launcher to relay each new progress
        line into the main conversation, explicitly without requiring the user
        to open the live-workflows view."""
        text = _doc_text()
        self.assertRegex(
            text,
            r"relay new progress lines into the main conversation",
            msg=(
                "The doc must instruct the launcher to relay new progress "
                "lines into the main conversation."
            ),
        )
        self.assertRegex(
            text,
            r"without\s+opening the live-workflows view",
            msg=(
                "The doc must state the user gets progress in the main "
                "conversation without opening the live-workflows view."
            ),
        )

    def test_c_incremental_no_duplicates_and_stops_cleanly(self):
        # covers: BO-1000c-1b
        """(c) The relay must be incremental (new lines only, no duplicates)
        and stop cleanly when the run terminates."""
        text = _doc_text()
        # Incremental: track last position, only lines added since last read.
        self.assertRegex(
            text,
            r"track the last line position relayed",
            msg="The doc must instruct tracking the last relayed line position.",
        )
        self.assertRegex(
            text,
            r"new lines only, no duplicates",
            msg=(
                "The doc must specify emitting only new lines with no "
                "duplicates (incremental relay)."
            ),
        )
        self.assertRegex(
            text,
            r"No re-delivery",
            msg=(
                "The doc must state already-relayed lines are not re-emitted."
            ),
        )
        # Stops cleanly when the run terminates.
        self.assertRegex(
            text,
            r"[Ss]top when the run terminates|stop polling when the workflow exits",
            msg=(
                "The doc must instruct the launcher to stop polling cleanly "
                "when the run terminates."
            ),
        )

    def test_d_graceful_degradation_when_journal_absent(self):
        # covers: BO-1000c-1b
        """(d) The doc must instruct graceful degradation if the journal is
        absent or unreadable — do NOT error the launch, emit an informational
        note, and bound the retry."""
        text = _doc_text()
        self.assertRegex(
            text,
            r"[Gg]raceful degradation",
            msg="The doc must include a graceful-degradation instruction.",
        )
        self.assertRegex(
            text,
            r"journal file is absent or unreadable",
            msg=(
                "The doc must cover the journal-absent/unreadable case "
                "explicitly."
            ),
        )
        self.assertRegex(
            text,
            r"Do NOT error the launch",
            msg=(
                "Graceful degradation must not error the launch when the "
                "journal is unavailable."
            ),
        )


if __name__ == "__main__":
    unittest.main()
