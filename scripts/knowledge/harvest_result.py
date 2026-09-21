"""
MODULE: harvest_result
GOAL: Define ``HarvestResult`` — the per-run outcome record the knowledge
    harvester accumulates while draining the emission sink, and the
    human-readable summary line derived from it.
BUSINESS CONTEXT: This is a reporting/data concern distinct from the act of
    draining the sink: ``harvest_learnings.py``'s ``harvest()`` function
    mutates one ``HarvestResult`` instance as it classifies each record, and
    ``main()`` prints its ``summary()`` unconditionally so an operator can
    always distinguish "nothing to do" from "nothing eligible to do" from
    "a broken run" (see the field-level docstrings below for the exact
    counting rules each of those distinctions depends on).
ARCHITECTURE: Plain-data module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md). Loaded by
    ``harvest_learnings.py`` as a required sibling module (see that file's
    ``_load_required_sibling_module``) rather than a bare top-level import,
    since ``harvest_learnings.py`` is itself loaded via
    ``importlib.util.spec_from_file_location`` by several pre-existing tests
    that do not add ``scripts/knowledge/`` to ``sys.path`` first.

# DECISION HISTORY
# - 2026-09-14 [python-coder/GE-127b-1 fix]: Extracted verbatim from
#   harvest_learnings.py (no behaviour change) to relieve the GE-127b-1
#   file-size ratchet, which refused a legitimate INF-400c-5-i fix because it
#   left that already-oversized file longer than it stood before. HarvestResult
#   is a reporting/data concern distinct from draining the sink, so it is a
#   natural, self-contained seam: no dependency on harvest_learnings's other
#   module state (sink resolution, entry_kind routing), so no circular-import
#   hazard and no monkeypatch-visibility concern of the kind that keeps
#   ``_KNOWN_ENTRY_KINDS`` in harvest_learnings.py itself.
#   (#INF-400c-5, GE-127b-1)
"""

from __future__ import annotations

import dataclasses


@dataclasses.dataclass
class HarvestResult:
    """Outcome of a single harvester run.

    Six record-level buckets — ``routed``, ``previously_processed``,
    ``skipped_unknown``, ``write_failures``, ``no_learning_text``,
    ``missing_required_field_count`` — partition every ``knowledge_captured``
    record read from the sink; they always sum to the number of such
    records. ``malformed_lines`` is a separate, line-level counter (a
    malformed line never parses into a record at all) and is intentionally
    excluded from that sum (INF-700c-1-i).

    ``missing_required_field_count`` / ``missing_required_field_lines``
    (INF-400b-2-i) count records that parsed as a valid JSON object and are
    genuine ``knowledge_captured`` events but lack a field the idempotency
    digest requires (see ``_event_hash`` in ``harvest_learnings.py``). This
    is deliberately a distinct bucket from ``malformed_lines`` — the line
    itself is well-formed JSON; it is the record's content that is short a
    required key. Such a record is never hashed, routed, or added to the
    idempotency state, so it is retried on a later run once the producer is
    fixed.

    ``outstanding`` (INF-700c-2 / INF-700c-2-ii) is the "still waiting to be
    written" count: the number of records carrying non-empty ``text`` that
    have not yet been durably written to their destination. It is derived,
    never stored — a record contributes to it only for the run(s) in which
    the record is neither eligibility-excluded (``no_learning_text``) nor
    already watermarked as processed (``previously_processed``) nor
    successfully written by *this* run. This includes a record that is
    *also* counted in ``missing_required_field_count``: such a record can
    never be hashed, so it can never be watermarked, and it never reaches
    the write step — so a text-bearing one always contributes here too.
    ``outstanding`` is not one of the six partitioning buckets; it overlaps
    them by design, and reading it as a seventh bucket is the mistake that
    let a text-bearing record with a missing digest field report
    ``outstanding: 0``. It is deliberately NOT derived from
    ``skipped_unknown`` / ``unroutable_by_kind``: those describe records the
    routing table cannot place, which is a different condition from a
    record waiting to be written, and a text-bearing record can be both at
    once (INF-700c-2-ii it_requirements).
    """

    routed: int = 0
    previously_processed: int = 0
    skipped_unknown: int = 0
    by_kind: dict[str, int] = dataclasses.field(default_factory=dict)
    unroutable_by_kind: dict[str, int] = dataclasses.field(default_factory=dict)
    write_failures: int = 0
    failed_by_kind: dict[str, int] = dataclasses.field(default_factory=dict)
    state_persist_failed: bool = False
    no_learning_text: int = 0
    no_learning_by_kind: dict[str, int] = dataclasses.field(default_factory=dict)
    malformed_lines: int = 0
    malformed_line_numbers: list[int] = dataclasses.field(default_factory=list)
    missing_required_field_count: int = 0
    missing_required_field_lines: list[int] = dataclasses.field(default_factory=list)
    outstanding: int = 0

    def summary(self) -> str:
        """Return the human-readable one-line summary.

        Format: ``"N learnings routed: K1 kind1, K2 kind2 (M previously
        processed); P unroutable: K3 kind3, K4 kind4; Q write failures: ...;
        state NOT persisted; R no learning text: ...; S malformed line(s):
        [...]; T record(s) missing a required digest field at line(s)
        [...]"``. Each trailing segment appears only when the condition it
        reports is present.

        The unroutable segment names each distinct unroutable ``entry_kind``
        with its count so the backlog is visible on every run
        (INF-400c-2-ii).

        The write-failure and state segments exist because a run in which
        every write failed otherwise renders as ``"0 learnings routed:
        none"`` — textually identical to a run that had nothing to do. The
        counters are what let the caller tell an empty queue from a broken
        one.

        The no-learning-text segment (INF-700c-1) and the malformed-line
        segment (INF-700c-1-i) never include the record's or line's raw
        content — only counts and, for malformed lines, 1-based line
        numbers — so a corrupt or content-free record cannot leak its bytes
        into the run's own output.

        The ``outstanding`` count (INF-700c-2) is always printed, including
        when it is zero: "visible is not the same as outstanding"
        (INF-700c-2 it_requirements #5) — a reader must be able to see that
        the honoured 28 are known about without them being reported as
        still waiting to be written.
        """
        parts = [f"{count} {kind}" for kind, count in sorted(self.by_kind.items())]
        breakdown = ", ".join(parts) if parts else "none"
        base = f"{self.routed} learnings routed: {breakdown}"
        base += f"; {self.outstanding} outstanding"
        if self.previously_processed:
            base += f" ({self.previously_processed} previously processed)"
        if self.skipped_unknown:
            unroutable_parts = [
                f"{count} {kind}" for kind, count in sorted(self.unroutable_by_kind.items())
            ]
            base += f"; {self.skipped_unknown} unroutable: {', '.join(unroutable_parts)}"
        if self.write_failures:
            failed_parts = [
                f"{count} {kind}" for kind, count in sorted(self.failed_by_kind.items())
            ]
            base += f"; {self.write_failures} write failures: {', '.join(failed_parts)}"
        if self.state_persist_failed:
            base += (
                f"; state NOT persisted ({self.routed} routed learnings will be"
                " re-applied on the next run)"
            )
        if self.no_learning_text:
            no_text_parts = [
                f"{count} {kind}" for kind, count in sorted(self.no_learning_by_kind.items())
            ]
            base += f"; {self.no_learning_text} no learning text: {', '.join(no_text_parts)}"
        if self.malformed_lines:
            base += (
                f"; {self.malformed_lines} malformed line(s) at "
                f"{self.malformed_line_numbers}"
            )
        if self.missing_required_field_count:
            base += (
                f"; {self.missing_required_field_count} record(s) missing a "
                f"required digest field at line(s) {self.missing_required_field_lines}"
            )
        return base
