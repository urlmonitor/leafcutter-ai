"""
MODULE: commit_guardian._file_size_measure.backstop
GOAL: Decide whether an already-oversized file's change has the shape the
    GE-127d-4 backstop refuses -- its MEASURED length fell while its TOTAL
    physical line count rose -- and render the refusal block that names it.
BUSINESS CONTEXT: KI-CG-20261013: restyling ``//`` runs into ``/* */`` blocks
    cleared the growth ratchet on five workflow templates while every one
    grew raw. This is a canary for any future gap in the measure: it compares
    the measured length with a count the measure cannot influence (the total
    line count). It applies only to a file whose previous version already
    stood over its limit (BrainCandy, 2026-10-16); the honest shape there is
    refused at a bounded cost -- the reduction and the commenting go in
    separate commits and each passes on its own.
ARCHITECTURE: Pure functions over numbers the caller already holds -- the
    previous length the ratchet resolved, the content it already fetched, the
    staged content it already read -- so no second git lookup happens here.
    During a merge the shape must hold against EVERY parent that has the file,
    mirroring the ratchet's most-permissive reasoning, so a merge that adopts
    one already-vetted parent's version is never refused.
"""

from __future__ import annotations

from typing import NamedTuple


class BackstopFinding(NamedTuple):
    """The four numbers a backstop refusal states."""

    previous_measured: int
    current_measured: int
    previous_total: int
    current_total: int


def evaluate_backstop(
    limit: int, current_measured: int, current_total: int, parents: list[tuple[int, int]]
) -> BackstopFinding | None:
    """Return the finding when the file's change has the refused shape against every parent.

    Args:
        limit: The permitted length for the file's extension.
        current_measured: The staged version's measured length.
        current_total: The staged version's total physical line count.
        parents: ``(measured, total)`` of the file at every parent that has it.

    Returns:
        A finding when, against every parent, the previous measured length
        strictly exceeded *limit*, the measured length strictly fell and the
        total strictly rose; otherwise None (also None for a new file).
    """
    if not parents:
        return None
    for measured, total in parents:
        if not (measured > limit and current_measured < measured and current_total > total):
            return None
    previous_measured, previous_total = max(parents)
    return BackstopFinding(previous_measured, current_measured, previous_total, current_total)


def format_backstop_block(filepath: str, finding: BackstopFinding) -> list[str]:
    """Render the refusal block for *finding*, under its own heading."""
    return [
        "❌ MEASURED LENGTH FELL WHILE TOTAL LINES ROSE (FILE ALREADY OVER ITS LIMIT):",
        f"   {filepath}",
        (
            f"   Its measured length fell from {finding.previous_measured} to {finding.current_measured} "
            f"while its total line count rose from {finding.previous_total} to {finding.current_total}."
        ),
        "   This combination is refused for a file already over its limit: it is the shape of a change that",
        "   moves content into forms the measure does not count rather than shortening the file.",
        "   A reduction in counted lines and an addition of uncounted lines (comments and standalone strings)",
        "   are accepted when made in separate commits.",
        "",
    ]


"""
DECISION HISTORY
========================================================================
- 2026-10-20 15:19 [python-coder]: Initial authoring of the GE-127d-4 backstop as pure functions
  so check_file_size.py (itself over its limit) only gains a call; the finding is reported
  alongside, never instead of, a crossing or growth refusal, and under its own heading.
  (#EPIC-FilesStayWorkable/GE-127d-4)
"""
