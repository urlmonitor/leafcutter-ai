"""
MODULE: test_bo_1000c_2_i
GOAL: Verify AC BO-1000c-2-i — on a mid-flight HALT, the /finalize-feature
    launcher command doc (templates/commands/finalize-feature.md) instructs the
    launcher to FLUSH any remaining unrelayed journal lines so the halting
    step's line reaches the conversation BEFORE/independently of the terminal
    halt payload.

    Static-analysis coverage backfill for an already-shipped DOC/PROSE artifact
    (EPIC-InFlightVisibility, PR #360). The tests read the command doc as text
    and assert on the ACTUAL instruction phrases and their ORDERING, following
    the pattern established in test_bo_1000a_1.py.

    AC BO-1000c-2-i requires the doc to instruct that, on detecting a halt, the
    launcher performs a final journal read, relays all remaining unrelayed lines
    (including the halting step's start-of-step line) FIRST, and only THEN
    presents the terminal halt payload — so the last conversation line reflects
    the halting step from the live stream, not only the returned halt result.

TICKET: 15_TICKET-20260720-BO-1000c-2-i.md
AC: BO-1000c-2-i
"""

from __future__ import annotations

import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DOC_PATH = _REPO_ROOT / "templates" / "commands" / "finalize-feature.md"


def _doc_text() -> str:
    """Return the full text of the finalize-feature command doc."""
    return _DOC_PATH.read_text(encoding="utf-8")


class TestFinalizeHaltFlush(unittest.TestCase):
    """AC BO-1000c-2-i: the command doc instructs the launcher to flush
    remaining unrelayed journal lines on a mid-flight halt so the halting step's
    line reaches the conversation before the terminal halt payload.
    """

    def test_doc_file_exists(self):
        # covers: BO-1000c-2-i
        """The delivered command-doc artifact must exist on disk."""
        self.assertTrue(
            _DOC_PATH.is_file(),
            msg=f"AC BO-1000c-2-i artifact missing: {_DOC_PATH} does not exist.",
        )

    def test_halt_flush_protocol_present(self):
        # covers: BO-1000c-2-i
        """The doc must define a halt-flush behaviour tied to BO-1000c-2-i:
        on detecting a halt, perform a final journal read and relay all
        remaining unrelayed lines."""
        text = _doc_text()
        self.assertRegex(
            text,
            r"Halt-Flush Protocol",
            msg="The doc must define a Halt-Flush Protocol section.",
        )
        self.assertIn(
            "BO-1000c-2-i",
            text,
            msg="The halt-flush behaviour must be tied to AC BO-1000c-2-i.",
        )
        self.assertRegex(
            text,
            r"final journal read",
            msg=(
                "The doc must instruct a final journal read on halt detection "
                "to capture the halting step's line."
            ),
        )
        self.assertRegex(
            text,
            r"Relay all remaining lines first|remaining unrelayed",
            msg=(
                "The doc must instruct relaying all remaining unrelayed lines "
                "on halt."
            ),
        )

    def test_halting_step_line_reaches_conversation_before_halt_payload(self):
        # covers: BO-1000c-2-i
        """The doc must guarantee the halting step's start-of-step line reaches
        the conversation as the most recent line BEFORE the terminal halt
        payload is presented. Assert both the requirement text and the ORDERING:
        the flush instruction appears before the 'present the halt summary'
        instruction in the doc source."""
        text = _doc_text()
        # The halting step's line must be relayed and named.
        self.assertRegex(
            text,
            r"halting step",
            msg="The doc must name the halting step's line explicitly.",
        )
        self.assertRegex(
            text,
            r"halting step'?s start-of-step",
            msg=(
                "The doc must guarantee the halting step's start-of-step line "
                "reaches the conversation."
            ),
        )
        # Ordering: relay-first must precede present-the-halt-summary.
        relay_pos = text.find("Relay all remaining lines first")
        present_pos = text.find("Present the halt summary only after")
        self.assertNotEqual(
            relay_pos, -1, msg="Missing 'Relay all remaining lines first' step."
        )
        self.assertNotEqual(
            present_pos,
            -1,
            msg="Missing 'Present the halt summary only after' ordering step.",
        )
        self.assertLess(
            relay_pos,
            present_pos,
            msg=(
                "The flush (relay remaining lines) must be instructed BEFORE "
                "presenting the halt summary — ordering is the observable "
                "contract for BO-1000c-2-i."
            ),
        )

    def test_anti_pattern_halt_first_is_prohibited(self):
        # covers: BO-1000c-2-i
        """The doc must explicitly prohibit the anti-pattern of presenting the
        halt summary first and relaying remaining journal lines afterward — the
        halt-flush must precede the halt summary so the last progress line the
        user reads is the halting step's own line."""
        text = _doc_text()
        self.assertRegex(
            text,
            r"Anti-pattern to avoid",
            msg="The doc must call out the halt-first anti-pattern.",
        )
        self.assertRegex(
            text,
            r"halt-flush must precede the halt\s+summary",
            msg=(
                "The doc must state the halt-flush precedes the halt summary "
                "(halting-step line surfaces before the terminal payload)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
