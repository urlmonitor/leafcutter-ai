"""
MODULE: test_bo_400e_5_close_path_diagram
GOAL: Make BO-400e-5's AC-7 mechanically checkable instead of merely asserted —
    exactly one path in the close-path diagram ends in the finished state being
    written, and that path passes through the checking mechanism.

BUSINESS CONTEXT: The record's own constraint says the count must be stated on the
    diagram "rather than left for the reader to count", because "a diagram a later
    second door could be added under, without contradicting anything drawn, would have
    failed at the one job this one exists for". Prose alone cannot enforce that: the
    diagram was drawn, a second door WAS found in finalize-feature.js
    (KI-BO-20260923-0630, fixed by BO-400e-3-i), and nothing but a human reading would
    have noticed if it had been drawn straight to the record again. These tests make a
    re-added second writer fail.

ARCHITECTURE: Parses the mermaid sequence block out of the diagram and reasons about
    its arrows, rather than matching prose. The load-bearing invariant is structural:
    the record participant (REC) may be reached only by the two drivers reading it back
    and by the checking mechanism (CHK). Any other lifeline drawing an arrow INTO REC is
    a second door by construction, whatever the label says — which is exactly how the
    original defect looked (`FF->>REC: raw frontmatter line replacement`).
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
_DIAGRAM = (
    _REPO_ROOT
    / "docs"
    / "architecture"
    / "diagrams"
    / "c3-008-ticket-close-paths-sequence.md"
)

# The record's lifeline, and the only lifelines permitted to address it: the two
# drivers (which read it back) and the checking mechanism (which alone writes it).
_RECORD = "REC"
_ALLOWED_SOURCES = {"BF", "BT", "CHK"}
_WRITER = "CHK"

_ARROW_TO_RECORD = re.compile(rf"^\s*([A-Za-z_][A-Za-z0-9_]*)->>{_RECORD}:\s*(.*)$")


def _mermaid_block() -> str:
    """The diagram's mermaid sequence block."""
    text = _DIAGRAM.read_text(encoding="utf-8")
    match = re.search(r"```mermaid\n(.*?)\n```", text, re.DOTALL)
    assert match, "the close-path diagram must contain a mermaid block"
    return match.group(1)


def _arrows_into_the_record() -> list[tuple[str, str]]:
    """Every (source, label) pair for an arrow addressed to the record lifeline."""
    return [
        (m.group(1), m.group(2))
        for m in (_ARROW_TO_RECORD.match(line) for line in _mermaid_block().splitlines())
        if m
    ]


class TestOnlyOneDoorReachesTheRecord:
    """BO-400e-5 AC-7, enforced structurally rather than by reading the prose."""

    def test_no_lifeline_other_than_the_drivers_and_the_mechanism_addresses_the_record(
        self,
    ) -> None:
        # covers: BO-400e-5
        # angle: criterion
        """A second door is a second lifeline drawing an arrow into the record.

        This is the shape the real defect had: `FF->>REC: raw frontmatter line
        replacement`. Catching it by source rather than by label means a re-added
        writer fails however it is worded.
        """
        offenders = sorted(
            {src for src, _ in _arrows_into_the_record() if src not in _ALLOWED_SOURCES}
        )
        assert offenders == [], (
            "only the two drivers (reading back) and the checking mechanism may address "
            f"the record; these lifelines reach it directly: {offenders}"
        )

    def test_exactly_one_arrow_writes_the_finished_state_and_it_is_the_mechanism(
        self,
    ) -> None:
        # covers: BO-400e-5
        # angle: criterion
        """AC-7's count, as a count rather than a sentence."""
        writes = [
            (src, label)
            for src, label in _arrows_into_the_record()
            if "write the finished state" in label
        ]
        assert len(writes) == 1, (
            f"exactly one arrow must write the finished state; found {len(writes)}: {writes}"
        )
        assert writes[0][0] == _WRITER, (
            f"the writing arrow must come from the checking mechanism, not {writes[0][0]}"
        )

    def test_both_drivers_and_the_refusal_are_drawn(self) -> None:
        # covers: BO-400e-5
        # angle: boundary
        """AC-4 and AC-5: a diagram of one driver cannot show a divergence between two,
        and a happy-path-only diagram documents the half that was never in doubt.
        """
        block = _mermaid_block()
        for lifeline in ("BF", "BT"):
            assert re.search(rf"^\s*{lifeline}->>", block, re.MULTILINE), (
                f"both drivers must appear as actors; {lifeline} draws no arrow"
            )
        assert "UNCHANGED" in block, (
            "the refusal path must terminate with the recorded state unchanged"
        )
