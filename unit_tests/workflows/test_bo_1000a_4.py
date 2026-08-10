"""
MODULE: test_bo_1000a_4
GOAL: Verify AC BO-1000a-4 — the delivered architecture diagram
    docs/architecture/diagrams/finalize-progress-narration-sequence.md is a
    Mermaid sequenceDiagram of the START-OF-STEP narration emission path.

    Static-analysis coverage backfill for an already-shipped DOC artifact
    (EPIC-InFlightVisibility, PR #360). The tests read the diagram as text and
    assert on its ACTUAL content, following the pattern established in
    test_bo_1000a_1.py / test_bo_1000a_3.py.

    AC BO-1000a-4 requires the diagram to:
      - be a Mermaid sequenceDiagram (fenced ```mermaid block);
      - name the emission-path participants: the finalize workflow step, the
        narration helper / progress channel, and the live progress view;
      - depict the start-of-step signal emitted BEFORE the step's own work
        (ordering is load-bearing);
      - reference the "Step X of N" framing and the skip-still-narrates case
        (BO-1000a-3) at least in a note.

TICKET: 06_TICKET-20260720-BO-1000a-4.md
AC: BO-1000a-4
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
    / "finalize-progress-narration-sequence.md"
)


def _diagram_text() -> str:
    """Return the full text of the narration-sequence diagram."""
    return _DIAGRAM_PATH.read_text(encoding="utf-8")


def _mermaid_block(text: str) -> str:
    """Return the contents of the first ```mermaid fenced block, or ''."""
    match = re.search(r"```mermaid\s*(.*?)```", text, re.DOTALL)
    return match.group(1) if match else ""


class TestNarrationSequenceDiagram(unittest.TestCase):
    """AC BO-1000a-4: the start-of-step narration emission path is documented
    as a Mermaid sequenceDiagram with the emission-path participants, correct
    ordering, and the Step X of N + skip-still-narrates references.
    """

    def test_diagram_file_exists(self):
        # covers: BO-1000a-4
        """The delivered artifact must exist on disk."""
        self.assertTrue(
            _DIAGRAM_PATH.is_file(),
            msg=(
                f"AC BO-1000a-4 artifact missing: {_DIAGRAM_PATH} does not "
                f"exist. The start-of-step narration sequence diagram is a "
                f"required deliverable."
            ),
        )

    def test_contains_mermaid_sequencediagram(self):
        # covers: BO-1000a-4
        """The diagram must be a Mermaid sequenceDiagram inside a fenced
        ```mermaid block (not a flowchart, not prose)."""
        block = _mermaid_block(_diagram_text())
        self.assertTrue(
            block,
            msg="No ```mermaid fenced block found in the diagram file.",
        )
        self.assertIn(
            "sequenceDiagram",
            block,
            msg=(
                "The ```mermaid block must declare a `sequenceDiagram` — "
                "AC BO-1000a-4 specifies a sequence diagram of the emission "
                "path."
            ),
        )

    def test_names_emission_path_participants(self):
        # covers: BO-1000a-4
        """The diagram must name the three emission-path participant concepts:
        the finalize workflow step, the narration helper / progress channel,
        and the live progress view. Asserts on the actual participant
        declarations present in the mermaid block."""
        block = _mermaid_block(_diagram_text())
        # The finalize workflow step (phase body).
        self.assertRegex(
            block,
            r"participant\s+\w+\s+as\s+Finalize step body",
            msg="Missing the finalize workflow step participant.",
        )
        # The narration helper AND the progress/narration channel (narrate/log).
        self.assertIn(
            "narrate()",
            block,
            msg="Missing the narrate() narration-helper participant.",
        )
        self.assertRegex(
            block,
            r"participant\s+\w+\s+as\s+log\(\)",
            msg="Missing the log() narration-channel participant.",
        )
        # The live progress view.
        self.assertRegex(
            block,
            r"participant\s+\w+\s+as\s+Live progress view",
            msg="Missing the live progress view participant.",
        )

    def test_start_of_step_signal_precedes_step_work(self):
        # covers: BO-1000a-4
        """Ordering is load-bearing: the start-of-step narration signal must be
        depicted as emitted BEFORE the step dispatches its own work. Assert the
        Step->>Narrate emission message appears earlier in the diagram source
        than the Step->>Agent (await agent) work-dispatch message, and that the
        diagram states the 'BEFORE the step's own work' ordering explicitly."""
        block = _mermaid_block(_diagram_text())
        narrate_pos = block.find("->>Narrate")
        agent_dispatch_pos = block.find("await agent")
        self.assertNotEqual(
            narrate_pos, -1, msg="No start-of-step narrate message found."
        )
        self.assertNotEqual(
            agent_dispatch_pos, -1, msg="No agent work-dispatch message found."
        )
        self.assertLess(
            narrate_pos,
            agent_dispatch_pos,
            msg=(
                "The start-of-step narration message must appear BEFORE the "
                "agent work-dispatch in the sequence — the diagram currently "
                "orders the work dispatch first, contradicting BO-1000a-4."
            ),
        )
        self.assertRegex(
            _diagram_text(),
            r"[Bb]efore the step'?s own work",
            msg=(
                "The diagram must state the ordering explicitly (start-of-step "
                "line emitted BEFORE the step's own work is dispatched)."
            ),
        )

    def test_references_step_x_of_n_and_skip_still_narrates(self):
        # covers: BO-1000a-4
        """The diagram must reference the 'Step X of N' framing and the
        skip-still-narrates case (BO-1000a-3) at least in a note."""
        text = _diagram_text()
        self.assertRegex(
            text,
            r"Step X of \d+",
            msg="The diagram must carry the 'Step X of N' framing.",
        )
        # Skip-still-narrates must be referenced and tied to BO-1000a-3.
        self.assertIn(
            "BO-1000a-3",
            text,
            msg=(
                "The diagram must reference the skip-still-narrates case "
                "(BO-1000a-3)."
            ),
        )
        block = _mermaid_block(text)
        self.assertRegex(
            block,
            r"skip",
            msg=(
                "The mermaid block must depict the skip case (a step whose "
                "outcome is already satisfied still narrates)."
            ),
        )


if __name__ == "__main__":
    unittest.main()
