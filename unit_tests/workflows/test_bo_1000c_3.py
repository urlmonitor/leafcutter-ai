"""
MODULE: test_bo_1000c_3
GOAL: Verify AC BO-1000c-3 — the delivered architecture diagram
    docs/architecture/diagrams/finalize-progress-relay-sequence.md is a Mermaid
    sequenceDiagram of live progress delivery from the background workflow to
    the conversation.

    Static-analysis coverage backfill for an already-shipped DOC artifact
    (EPIC-InFlightVisibility, PR #360). The tests read the diagram as text and
    assert on its ACTUAL content, following the pattern established in
    test_bo_1000a_1.py.

    AC BO-1000c-3 requires the diagram to:
      - be a Mermaid sequenceDiagram (fenced ```mermaid block);
      - have MORE THAN TWO participants covering the relay path (background
        finalize workflow, run-progress journal, /finalize-feature launcher /
        poller, main conversation, user);
      - depict in-flight ordering via a `loop` (updates during the run, not
        only at the end);
      - include the halt case (BO-1000c-2-i) at least as a note.

TICKET: 16_TICKET-20260720-BO-1000c-3.md
AC: BO-1000c-3
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DIAGRAM_PATH = (
    _REPO_ROOT
    / "docs"
    / "architecture"
    / "diagrams"
    / "finalize-progress-relay-sequence.md"
)


def _diagram_text() -> str:
    """Return the full text of the relay-sequence diagram."""
    return _DIAGRAM_PATH.read_text(encoding="utf-8")


def _mermaid_block(text: str) -> str:
    """Return the contents of the first ```mermaid fenced block, or ''."""
    match = re.search(r"```mermaid\s*(.*?)```", text, re.DOTALL)
    return match.group(1) if match else ""


class TestRelaySequenceDiagram(unittest.TestCase):
    """AC BO-1000c-3: live progress delivery from the background workflow to
    the conversation is documented as a Mermaid sequenceDiagram with >2 relay
    participants, in-flight loop ordering, and the halt case.
    """

    def test_diagram_file_exists(self):
        # covers: BO-1000c-3
        """The delivered artifact must exist on disk."""
        self.assertTrue(
            _DIAGRAM_PATH.is_file(),
            msg=(
                f"AC BO-1000c-3 artifact missing: {_DIAGRAM_PATH} does not "
                f"exist. The progress-relay sequence diagram is a required "
                f"deliverable."
            ),
        )

    def test_contains_mermaid_sequencediagram(self):
        # covers: BO-1000c-3
        """The diagram must be a Mermaid sequenceDiagram inside a fenced
        ```mermaid block."""
        block = _mermaid_block(_diagram_text())
        self.assertTrue(
            block, msg="No ```mermaid fenced block found in the diagram file."
        )
        self.assertIn(
            "sequenceDiagram",
            block,
            msg="The ```mermaid block must declare a `sequenceDiagram`.",
        )

    def test_more_than_two_participants_on_relay_path(self):
        # covers: BO-1000c-3
        """The diagram must declare MORE THAN TWO participants (>=3 distinct
        `participant`/`actor` declarations) so it spans the full relay path,
        not just a two-party hand-off. Count the declarations in the mermaid
        block."""
        block = _mermaid_block(_diagram_text())
        declarations = re.findall(r"^\s*(?:participant|actor)\s+(\w+)", block, re.M)
        distinct = set(declarations)
        self.assertGreater(
            len(distinct),
            2,
            msg=(
                f"AC BO-1000c-3 requires MORE THAN TWO participants; found "
                f"only {len(distinct)}: {sorted(distinct)}. The relay path "
                f"spans background workflow -> journal -> launcher -> "
                f"conversation -> user."
            ),
        )

    def test_relay_path_concepts_present(self):
        # covers: BO-1000c-3
        """The five relay-path concepts must appear as participant declarations:
        background finalize workflow, run-progress journal, /finalize-feature
        launcher/poller, main conversation, and the user."""
        block = _mermaid_block(_diagram_text())
        required_concepts = {
            "background finalize workflow": r"[Bb]ackground finalize workflow",
            "run-progress journal": r"[Rr]un-progress journal",
            "/finalize-feature launcher": r"/finalize-feature launcher",
            "main conversation": r"[Mm]ain conversation",
            "user": r"actor\s+User",
        }
        missing = [
            name
            for name, pattern in required_concepts.items()
            if re.search(pattern, block) is None
        ]
        self.assertEqual(
            missing,
            [],
            msg=(
                "The relay-path diagram is missing participant concept(s): "
                f"{missing}. All of background workflow, run-progress journal, "
                "the /finalize-feature launcher/poller, the main conversation, "
                "and the user must appear."
            ),
        )

    def test_in_flight_ordering_uses_loop(self):
        # covers: BO-1000c-3
        """In-flight ordering must be depicted with a `loop` so updates arrive
        during the run (not only at the end). Assert a loop exists and its
        label references the in-flight / polling nature of the relay."""
        block = _mermaid_block(_diagram_text())
        self.assertRegex(
            block,
            r"\bloop\b",
            msg=(
                "The diagram must use a `loop` construct to show updates "
                "arriving during the run (in-flight), not a single end-of-run "
                "message."
            ),
        )
        self.assertRegex(
            block,
            r"loop[^\n]*(in flight|in-flight|Poll|each)",
            msg=(
                "The loop must be labelled to convey in-flight polling/relay "
                "(e.g. 'Poll while run is in flight' / 'For each in-flight "
                "step')."
            ),
        )

    def test_halt_case_included(self):
        # covers: BO-1000c-3
        """The halt case (BO-1000c-2-i) must be included at least as a note or
        alt branch — the halting step's line reaching the conversation live."""
        text = _diagram_text()
        self.assertIn(
            "BO-1000c-2-i",
            text,
            msg=(
                "The diagram must reference the mid-flight halt case "
                "(BO-1000c-2-i)."
            ),
        )
        block = _mermaid_block(text)
        self.assertRegex(
            block,
            r"[Hh]alt",
            msg=(
                "The mermaid block must depict the halt case (halting step's "
                "line relayed before the terminal halt result)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
