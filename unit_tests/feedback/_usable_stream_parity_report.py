"""
MODULE: _usable_stream_parity_report
GOAL: The outcome of one usable-stream parity run (AC INF-500d-4-ix): what was compared,
    what disagreed on the verdict, what reported another location, what wrote something
    it must not, and what could not be run.
BUSINESS CONTEXT: A run is only worth trusting when it names the copy and the row of every
    failure: a verdict disagreement, a location disagreement on a row the canonical rule
    finds usable (both paths in the message), a stray write, or a copy / canonical probe /
    row install that could not be run.
ARCHITECTURE: Plain data plus read-only properties; ``_usable_stream_parity_copies`` builds
    it and re-exports it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from unit_tests.feedback._usable_stream_parity_core import Verdict


@dataclass(frozen=True)
class Disagreement:
    """One (copy, row) where the copy's usable answer differs from the canonical rule's."""

    copy: str
    row: str
    canonical: Verdict
    observed: Verdict


@dataclass(frozen=True)
class LocationMismatch:
    """One (copy, row) the canonical rule finds usable where the copy reports another absolute location."""

    copy: str
    row: str
    canonical: Path
    observed: Path


def _word(verdict: Verdict) -> str:
    return "usable" if verdict.usable else "unusable"


@dataclass
class ParityReport:
    """The outcome of one run: what was compared, what disagreed, what could not be run."""

    verdicts: dict[tuple[str, str], Verdict]
    canonical_verdicts: dict[tuple[str, str], Verdict]
    errors: list[str]

    @property
    def copies_compared(self) -> int:
        """Number of copies that produced verdicts (a copy that could not be found or run is not counted)."""
        return len({copy for copy, _row in self.verdicts})

    @property
    def rows_compared(self) -> int:
        """Number of distinct rows any copy was compared on."""
        return len({row for _copy, row in self.verdicts})

    @property
    def disagreements(self) -> list[Disagreement]:
        """Every (copy, row) whose usable answer differs from the canonical rule's."""
        return [Disagreement(copy, row, self.canonical_verdicts[(copy, row)], verdict)
                for (copy, row), verdict in self.verdicts.items()
                if verdict.usable != self.canonical_verdicts[(copy, row)].usable]

    @property
    def location_mismatches(self) -> list[LocationMismatch]:
        """Every (copy, row) both call usable where the copy reports a location other than the canonical one."""
        found = []
        for (copy, row), verdict in self.verdicts.items():
            canonical = self.canonical_verdicts[(copy, row)]
            if (verdict.usable and canonical.usable and verdict.location is not None
                    and canonical.location is not None and Path(verdict.location) != Path(canonical.location)):
                found.append(LocationMismatch(copy, row, Path(canonical.location), Path(verdict.location)))
        return found

    @property
    def stray_writes(self) -> list[tuple[str, str, str]]:
        """Every (copy, row, detail) where running the copy changed more than the declared stream's one line."""
        return [(copy, row, verdict.detail) for (copy, row), verdict in self.verdicts.items() if verdict.stray]

    @property
    def vacuous(self) -> bool:
        """True when, for some compared copy, the canonical rule answers the same for every row."""
        answers: dict[str, set[bool]] = {}
        for (copy, _row), verdict in self.canonical_verdicts.items():
            answers.setdefault(copy, set()).add(verdict.usable)
        return any(len(seen) == 1 for seen in answers.values())

    @property
    def ok(self) -> bool:
        """True only when something was compared and nothing erred, disagreed, mislocated, strayed or was vacuous."""
        return (self.copies_compared > 0 and self.rows_compared > 0 and not self.errors
                and not self.disagreements and not self.location_mismatches and not self.stray_writes
                and not self.vacuous)

    def summary(self) -> str:
        """One line stating how many copies and rows were compared."""
        return (f"copies_compared={self.copies_compared} rows_compared={self.rows_compared} "
                f"disagreements={len(self.disagreements)} location_mismatches={len(self.location_mismatches)} "
                f"stray_writes={len(self.stray_writes)} errors={len(self.errors)}")

    def message(self) -> str:
        """The failure text: summary, errors, one line per finding, and any vacuity or emptiness."""
        lines = [self.summary(), *(f"error: {error}" for error in self.errors)]
        for d in self.disagreements:
            lines.append(f"{d.copy} disagrees on row {d.row}: canonical={_word(d.canonical)} "
                         f"copy={_word(d.observed)} (copy said: {d.observed.detail or 'n/a'})")
        for m in self.location_mismatches:
            lines.append(f"{m.copy} reports a different location on row {m.row}: "
                         f"canonical={m.canonical} copy={m.observed}")
        for copy, row, detail in self.stray_writes:
            lines.append(f"{copy} wrote something it must not on row {row}: {detail}")
        if self.copies_compared == 0:
            lines.append("no copy was compared: a run that compared nothing proves nothing")
        if self.rows_compared == 0:
            lines.append("no row was compared: a run that compared nothing proves nothing")
        if self.vacuous:
            lines.append("vacuous: the canonical rule answers the same for every row, so "
                         "agreement proves nothing")
        return "\n".join(lines)


# DECISION HISTORY
# ================================================================================
# - 2026-10-14 16:00 [python-coder]: Split the report out of the copies module; added location mismatches and stray writes to ok/message. (#TICKET-INF-500d-4-ix)
