"""
MODULE: harvest_learnings
GOAL: Read unprocessed knowledge_captured events from the emission sink and
    route each to the knowledge surface it names, without ever inventing
    content the emitting agent did not actually write.
BUSINESS CONTEXT: Agents emit learnings via the signoff Sec7 knowledge-capture
    step; this harvester is the batch process that drains those emissions
    into durable, curated knowledge files. A record with no learning text is
    a receipt of a past write, not new knowledge, and must never become a
    placeholder line on a real file (INF-700c-1); a line that is not a valid
    JSON object must never derail the read of the records around it
    (INF-700c-1-i).
ARCHITECTURE: Entry point for the Knowledge System component
    (docs/architecture/components/knowledge-system.md). Reads
    ``debugging/logs/knowledge_emissions.jsonl`` (retained sink per ADR-011)
    and writes via the capture-learning write protocol
    (docs/architecture/adrs/ADR-034-knowledge-write-ownership.md).

harvest_learnings.py — Knowledge emission harvester for leafcutter-ai.

Reads unprocessed ``knowledge_captured`` events from
``debugging/logs/knowledge_emissions.jsonl`` (per ADR-011), invokes the
capture-learning write protocol for each event, marks processed events via
a hash-based state file so re-runs are idempotent, and prints a summary.

Usage
-----
    python scripts/knowledge/harvest_learnings.py [--sink PATH] [--dry-run] [--verbose]

Options
-------
--sink PATH
    Path to the JSONL sink file.
    Default: debugging/logs/knowledge_emissions.jsonl (relative to CWD).

--state PATH
    Path to the JSON state file tracking processed event hashes.
    Default: debugging/logs/harvest_state.json (relative to CWD).

--dry-run
    Read events and decide routing but do not write to any knowledge surface.

--verbose
    Print each event as it is processed.

Exit codes
----------
0   Drained with nothing left to ROUTE. Read this literally: it does NOT mean
    the sink is empty and it does NOT mean every record was written. Records
    classified `no learning text` are deliberately not written and are NOT
    counted as unroutable, so a run over a corpus that is entirely textless
    exits 0 while writing nothing at all -- which is the current state of the
    real 28-record sink. Always read the summary's `no learning text` segment
    alongside this code; the count is the only thing that distinguishes
    "nothing to do" from "nothing eligible to do".
1   Sink file not found or unreadable.
2   State file exists but cannot be parsed (corrupted).
3   Drained with unroutable events left behind (see summary for the
    per-entry_kind breakdown). Distinct from 0 so a caller cannot mistake a
    run that routed nothing because there was unroutable input for a run
    that had nothing to route.
4   The run was not clean: at least one destination write failed, and/or the
    state file could not be persisted. Outranks 3 -- a broken run is more
    urgent than a retained backlog. Both conditions leave the affected events
    retryable, but a state-persist failure additionally means the learnings
    routed by this run WILL be routed (and re-appended) again next run.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, cast

logger = logging.getLogger("harvest_learnings")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


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
    digest requires (see ``_event_hash``). This is deliberately a distinct
    bucket from ``malformed_lines`` — the line itself is well-formed JSON;
    it is the record's content that is short a required key. Such a record
    is never hashed, routed, or added to the idempotency state, so it is
    retried on a later run once the producer is fixed.

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


# ---------------------------------------------------------------------------
# State helpers (hash-based idempotency, per ADR-011)
# ---------------------------------------------------------------------------


# The idempotency key, per INF-400b-2-i / INF-400b-2-ii: exactly the fields
# the reconciled record shape requires of every producer. `ticket` and
# `text` are optional and MUST NOT appear here under any spelling -- not
# even as a defaulted-to-empty lookup, which is the substitution path that
# produced the original defect (a constant key component that silently
# discriminated nothing).
_REQUIRED_DIGEST_FIELDS: tuple[str, ...] = (
    "timestamp",
    "agent",
    "component",
    "destination",
    "entry_kind",
)


def _event_hash(event: dict[str, Any]) -> str:
    """Return a stable SHA-256 hex digest for a knowledge_captured event.

    The hash key is built from exactly ``_REQUIRED_DIGEST_FIELDS`` --
    ``(timestamp, agent, component, destination, entry_kind)`` -- the set of
    fields the reconciled record shape requires of every producer
    (INF-400b-2-ii). Optional fields (``ticket``, ``text``) are deliberately
    excluded: they must never contribute to identity, either because they
    carry no discriminating information (``ticket`` is absent from every
    real record) or because they carry content rather than identity
    (``text``). This is stable across file rotation and compaction.

    Pure function: no I/O, no shared-state mutation, so per the project
    error-handling policy it is not wrapped in try/except here. A record
    missing one of the required fields raises ``KeyError`` naming that
    field; the caller (``harvest()``, at the I/O boundary) is responsible
    for catching it, reporting the record's line number, and leaving the
    record unprocessed rather than silently substituting an empty string.

    Raises
    ------
    KeyError
        If *event* is missing any field in ``_REQUIRED_DIGEST_FIELDS``.
    """
    key = json.dumps(
        {field: event[field] for field in _REQUIRED_DIGEST_FIELDS},
        sort_keys=True,
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _is_no_learning_text(event: dict[str, Any]) -> bool:
    """Return ``True`` if *event* carries no real learning content.

    A record is ineligible to be written to any knowledge surface when its
    ``text`` field is absent, ``null``, empty (after whitespace
    normalisation), or is merely a restatement of the record's own
    descriptive fields in the exact shape the deleted harvester placeholder
    used to compose (``"[<entry_kind>] Learning from <ticket>"``). The
    restatement check exists so an emitter cannot undo the deletion of that
    placeholder by inlining the same string as if it were real ``text``
    (INF-700c-1 it_requirements #3).

    Pure function: no I/O, no shared-state mutation.
    """
    text = event.get("text")
    if text is None or not isinstance(text, str):
        return True
    normalized = text.strip()
    if not normalized:
        return True
    entry_kind = event.get("entry_kind", "")
    ticket = event.get("ticket", "")
    placeholder = f"[{entry_kind}] Learning from {ticket}".strip()
    return normalized == placeholder


def _load_state(state_path: Path) -> set[str]:
    """Load the set of already-processed event hashes from *state_path*.

    Returns an empty set if the file does not exist.

    Raises
    ------
    ValueError
        If the file exists but cannot be parsed as a JSON list of strings.
    """
    if not state_path.exists():
        return set()
    try:
        with open(state_path, encoding="utf-8") as fh:
            raw = json.load(fh)
        if not isinstance(raw, list):
            raise TypeError("State file must contain a JSON list of strings")  # noqa: TRY003
        return set(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("State file is not valid JSON") from exc  # noqa: TRY003


def _save_state(state_path: Path, hashes: set[str]) -> None:
    """Persist *hashes* to *state_path* (atomic-style: write then rename).

    The list is sorted so diffs are deterministic.
    """
    tmp_path = state_path.with_suffix(".json.tmp")
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(sorted(hashes), fh, indent=2)
        tmp_path.replace(state_path)
    except OSError as exc:
        logger.warning("Failed to persist harvest state: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Default capture function (production wiring via capture-learning protocol)
# ---------------------------------------------------------------------------

# The _known_entry_kinds set enumerates the entry_kind values that the
# harvester can route.  Any value not in this set triggers a WARNING log and
# capture_fn is NOT called.  Per INF-400c-2-ii, the event is NOT marked
# processed — it is left out of the idempotency record so a later run (after
# the routing rules are extended) reads and retries it. The backlog stays
# visible via HarvestResult.unroutable_by_kind / skipped_unknown rather than
# growing an unbounded reprocessing loop silently: every run reports it.
_KNOWN_ENTRY_KINDS: frozenset[str] = frozenset(
    {
        "memory-project",
        "per-folder-readme",
        "agent-frontmatter",
        "code-comment",
        "adr",
        "skill-context",
        "per-agent-memory",
        "explanation-doc",
        "reference-doc",
        "claude-md",
        "retrospective",
    }
)


def _default_capture(learning_text: str, destination_path: str) -> None:
    """Write *learning_text* to *destination_path* (append-only).

    This is the production capture-learning write protocol.  In tests, this
    function is replaced by a lightweight stub so the test suite does not
    write to the real filesystem.
    """
    dest = Path(destination_path)
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "a", encoding="utf-8") as fh:
            fh.write(learning_text + "\n")
    except OSError as exc:
        logger.warning(
            "Failed to write learning to %s: %s",
            destination_path,
            exc,
        )
        raise


# ---------------------------------------------------------------------------
# Core harvest function
# ---------------------------------------------------------------------------


def harvest(
    sink_path: Path,
    state_path: Path,
    capture_fn: Callable[[str, str], None] = _default_capture,
    dry_run: bool = False,
    verbose: bool = False,
) -> HarvestResult:
    """Process unhandled ``knowledge_captured`` events from *sink_path*.

    Parameters
    ----------
    sink_path:
        Path to the JSONL sink file (``knowledge_emissions.jsonl``).
    state_path:
        Path to the JSON file that persists processed event hashes.
    capture_fn:
        Callable invoked for each routable event.  Signature:
        ``(learning_text: str, destination_path: str) -> None``.
        Defaults to ``_default_capture`` (production path).
    dry_run:
        When ``True``, decisions are logged but ``capture_fn`` is not called
        and state is not updated.
    verbose:
        When ``True``, log each event at DEBUG level.

    Returns
    -------
    HarvestResult
        Counts of routed, previously processed, and skipped-unknown events,
        plus a per-kind breakdown and the derived ``outstanding`` count
        (INF-700c-2) of text-bearing records not yet durably written.

    Raises
    ------
    SystemExit(1)
        If *sink_path* does not exist or cannot be read.
    SystemExit(2)
        If *state_path* exists but is corrupted.
    """
    result = HarvestResult()

    # 1. Read sink file
    if not sink_path.exists():
        logger.error("Sink file not found: %s", sink_path)
        sys.exit(1)

    try:
        raw_lines = sink_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        logger.exception("Cannot read sink file %s", sink_path)
        sys.exit(1)

    # 2. Load previously processed hashes
    try:
        seen: set[str] = _load_state(state_path)
    except ValueError:
        logger.exception("State file corrupted (%s)", state_path)
        sys.exit(2)

    new_hashes: set[str] = set()

    # enumerate() over raw_lines (from splitlines(), so no trailing newline
    # entry) gives the 1-based line number exactly as it appears on disk,
    # including blank lines -- required so a reported malformed-line number
    # can be used to open the real file at that line (INF-700c-1-i).
    for line_no, raw_line in enumerate(raw_lines, start=1):
        line = raw_line.strip()
        if not line:
            continue

        # Parse JSON line. Two distinct ways a line can fail to be a usable
        # record: it is not valid JSON at all (JSONDecodeError), or it parses
        # but is not a JSON object (e.g. a bare string/number/list/null),
        # which would otherwise raise AttributeError on the .get() calls
        # below. Both are "malformed line" (INF-700c-1-i) -- a line-level
        # condition, never written to a knowledge surface, and the read does
        # not stop: subsequent lines are still processed.
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning(
                "Skipping malformed line %d (not valid JSON): %s — %s",
                line_no,
                line[:80],
                exc,
            )
            result.malformed_lines += 1
            result.malformed_line_numbers.append(line_no)
            continue

        if not isinstance(event, dict):
            logger.warning(
                "Skipping malformed line %d (valid JSON but not an object): %s",
                line_no,
                line[:80],
            )
            result.malformed_lines += 1
            result.malformed_line_numbers.append(line_no)
            continue

        # Filter: only knowledge_captured events
        if event.get("event") != "knowledge_captured":
            if verbose:
                logger.debug("Skipping non-knowledge event: %s", event.get("event"))
            continue

        # The record parsed as a valid JSON object and is a genuine
        # knowledge_captured event, but it may still lack a field the
        # idempotency digest requires (INF-400b-2-i). This is distinct from
        # a malformed line -- the line itself is well-formed JSON -- so it
        # is counted in its own bucket, reported with its line number, and
        # the record is left unprocessed (never hashed, routed, or added to
        # the idempotency state) rather than silently hashed on a
        # defaulted-to-empty substitute, which is the mechanism that
        # produced the original defect.
        try:
            h = _event_hash(event)
        except KeyError as exc:
            missing_field = exc.args[0] if exc.args else "<unknown>"
            logger.warning(
                "Skipping event at line %d: missing required digest field %r. "
                "Event stays unprocessed and will be retried once the "
                "producer emits it.",
                line_no,
                missing_field,
            )
            result.missing_required_field_count += 1
            result.missing_required_field_lines.append(line_no)
            # A record that carries a REAL learning and was not written is
            # outstanding, whatever the reason it could not be written.
            # INF-700c-2-ii states the figure admits "no floor, no cap, no
            # exclusion by age, agent, kind or destination" -- and a missing
            # digest field is exactly such an exclusion if we let this
            # `continue` skip the count. Without this the one number the
            # feature exists to make truthful reads 0 while a genuine
            # unwritten learning sits in the sink.
            if not _is_no_learning_text(event):
                result.outstanding += 1
            continue

        # Already processed?
        if h in seen:
            result.previously_processed += 1
            continue

        entry_kind = event.get("entry_kind", "")
        destination = event.get("destination", "")
        ticket = event.get("ticket", "")

        if verbose:
            logger.debug(
                "Processing event: entry_kind=%s destination=%s ticket=%s",
                entry_kind,
                destination,
                ticket,
            )

        # Eligibility check MUST run before entry_kind routing (INF-700c-1
        # it_requirements: classification order is load-bearing). All 28
        # retained real records are simultaneously textless AND
        # unknown-entry_kind; a kind-first check would route every one of
        # them into skipped_unknown and pin the exit code non-zero forever.
        if _is_no_learning_text(event):
            result.no_learning_text += 1
            result.no_learning_by_kind[entry_kind] = (
                result.no_learning_by_kind.get(entry_kind, 0) + 1
            )
            # Log at WARNING like every sibling branch. Without this the
            # bucket is the only classification in the module that is
            # silent on stderr, and over the real 28-record corpus that
            # takes the run from 28 warnings to zero while the exit code
            # goes 3 -> 0. A record deliberately not written is still a
            # record not written, and an operator reading only stderr
            # would see a clean run.
            logger.warning(
                "No learning text in event (entry_kind: %r, destination: %r). "
                "Nothing written; the record is left unprocessed so a later "
                "run re-derives it once a real learning body is emitted.",
                entry_kind,
                destination,
            )
            # NOT added to new_hashes / seen: the classification must be
            # re-derived from the record on every run, per INF-700c-1 (the
            # idempotency state file lives under gitignored debugging/logs/
            # and is not durable across a fresh clone or install).
            continue

        # Route based on entry_kind
        if entry_kind not in _KNOWN_ENTRY_KINDS:
            logger.warning(
                "Unrecognised entry_kind %r in event from ticket %r (destination: %r). "
                "Event stays unprocessed and will be retried on a later run.",
                entry_kind,
                ticket,
                destination,
            )
            result.skipped_unknown += 1
            result.unroutable_by_kind[entry_kind] = (
                result.unroutable_by_kind.get(entry_kind, 0) + 1
            )
            # Outstanding per INF-700c-2-ii: this record carries real text
            # and has not been written anywhere, regardless of whether the
            # routing table can currently place its entry_kind. Counting it
            # here (rather than deriving "outstanding" from
            # skipped_unknown/unroutable_by_kind after the fact) is what
            # keeps a text-bearing-but-unroutable record from being able to
            # hide in either bucket alone.
            result.outstanding += 1
            # Intentionally NOT added to new_hashes / seen: per INF-400c-2-ii
            # an unroutable event must remain retryable, not be silently
            # discarded via the idempotency record.
            continue

        # By this point `_is_no_learning_text` has already confirmed `text`
        # is present and carries real content, so it is used verbatim. Per
        # INF-700c-1 it_requirements, there is deliberately NO fallback here
        # — a default that synthesises a stand-in string from the record's
        # descriptive fields is exactly the defect this AC closes.
        # cast, not a runtime check: `_is_no_learning_text` above has already
        # rejected absent / null / blank / self-restating values and issued a
        # `continue`, so by here `text` is necessarily a non-empty str. mypy
        # cannot see across that helper, and adding an `isinstance` branch
        # would be unreachable code asserting an invariant the helper owns.
        # If that helper's contract ever changes, this cast is the line to
        # revisit.
        learning_text = cast(str, event.get("text"))

        if not dry_run:
            try:
                capture_fn(learning_text, destination)
            except OSError:
                # capture_fn already logged the specific error. Record the
                # failure and move on to the next event: one unwritable
                # destination must not abort the whole drain. The event's
                # hash is deliberately NOT added to new_hashes, so the write
                # is retried on the next run — same retention rule as an
                # unroutable event (INF-400c-2-ii).
                result.write_failures += 1
                result.failed_by_kind[entry_kind] = (
                    result.failed_by_kind.get(entry_kind, 0) + 1
                )
                # Outstanding per INF-700c-2-ii: the count follows the
                # write, not the attempt. A write that raised was not
                # persisted, so the record remains unwritten and must stay
                # outstanding on this and every subsequent run until a
                # write actually succeeds.
                result.outstanding += 1
                continue

        result.routed += 1
        result.by_kind[entry_kind] = result.by_kind.get(entry_kind, 0) + 1
        new_hashes.add(h)
        if dry_run:
            # A dry run never calls capture_fn and never persists state (see
            # the persistence step below), so this record is still
            # genuinely unwritten. Only a real (non-dry-run) write that
            # reaches this line has actually captured the learning, so only
            # the dry-run case counts toward `outstanding` here.
            result.outstanding += 1

    # 3. Persist updated state
    #
    # Only when there is something new to record. With new_hashes empty the
    # write is a no-op (seen | {} == seen), so attempting it can only
    # manufacture a failure that costs nothing: nothing was routed, so
    # nothing can be re-routed. Reporting that as a failed run would raise
    # the exit code to 4 and mask the exit-3 backlog signal on precisely the
    # run that most needs it -- an all-unroutable sink, which is today's
    # real corpus.
    if not dry_run and new_hashes:
        try:
            _save_state(state_path, seen | new_hashes)
        except OSError:
            # _save_state already warned with the specific errno. Do not abort
            # -- the learnings were written and that work is real -- but the
            # run is NOT clean: without the state file every hash in
            # new_hashes is forgotten, so the next run re-routes all of them
            # and appends each learning to its destination a second time.
            # Recording this is what stops the caller reading a duplicating
            # run as a successful one.
            result.state_persist_failed = True
            logger.warning(
                "Harvest state was not persisted; the %d learnings routed by "
                "this run will be routed again (and re-appended to their "
                "destinations) on the next run.",
                result.routed,
            )

    return result


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="harvest_learnings",
        description="Route knowledge_captured events from the emission sink.",
    )
    parser.add_argument(
        "--sink",
        type=Path,
        default=Path("debugging/logs/knowledge_emissions.jsonl"),
        metavar="PATH",
        help="Path to the JSONL sink (default: debugging/logs/knowledge_emissions.jsonl).",
    )
    parser.add_argument(
        "--state",
        type=Path,
        default=Path("debugging/logs/harvest_state.json"),
        metavar="PATH",
        help="Path to the processed-event state file (default: debugging/logs/harvest_state.json).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log routing decisions but do not write to knowledge surfaces.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Log each event as it is processed.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the knowledge harvester.

    Returns
    -------
    int
        ``0`` if the run drained cleanly, ``3`` if unroutable events remain
        in the sink (see the printed summary for the per-entry_kind
        breakdown), ``4`` if any destination write failed or the state file
        could not be persisted. ``4`` outranks ``3``: a broken run is more
        urgent than a retained backlog. ``harvest()`` itself may also
        ``sys.exit(1)``/``sys.exit(2)`` for sink/state read failures before
        this function returns.
    """
    args = _parse_args(argv)

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s %(name)s: %(message)s")

    result = harvest(
        sink_path=args.sink,
        state_path=args.state,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    print(result.summary())

    if result.write_failures or result.state_persist_failed:
        return 4
    return 3 if result.skipped_unknown else 0


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-08-31 12:00 [python-coder]: Deleted the placeholder-synthesis default for
#   learning_text and added a no-learning-text eligibility bucket, evaluated
#   BEFORE entry_kind routing so a record that is both textless and
#   unknown-kinded (the shape of all 28 retained real records) is never
#   double-counted into skipped_unknown. Also added a malformed-line counter
#   with 1-based line numbers and a not-a-JSON-object guard so a bare JSON
#   scalar line no longer crashes the run with AttributeError. Neither change
#   introduces a new exit code. (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700c-1)
# - 2026-08-31 [python-coder]: Re-keyed `_event_hash` on the reconciled
#   required-field set (timestamp, agent, component, destination, entry_kind)
#   per INF-400b-2-ii's contract, dropping the always-absent `ticket` field
#   that made the digest effectively three-fields-wide (INF-400b-2-i /
#   KI-KM-010). A record missing a required field now raises `KeyError` from
#   `_event_hash` instead of being silently hashed on a defaulted-to-empty
#   substitute; `harvest()` catches it per-record, reports the 1-based line
#   number via new `HarvestResult.missing_required_field_count` /
#   `missing_required_field_lines` counters (distinct from `malformed_lines`
#   per KI-KM-011's separate territory), and leaves the record unprocessed
#   so it is retried once the producer is fixed. No new exit code.
#   CONSEQUENCE (documented per this AC's own it_requirements): changing the
#   key invalidates every digest computed under the old (ticket, timestamp,
#   destination, entry_kind) key -- any state file persisted before this
#   change will no longer recognise its own entries as processed. Harmless
#   for the current real corpus (INF-700c establishes all 28 records are
#   ineligible-to-write, so nothing was ever actually routed under the old
#   key), but deliberate and called out here rather than discovered later.
#   KNOWN COLLATERAL: 15 pre-existing tests in
#   tests/knowledge/test_harvest_learnings.py (all tagged for INF-400c-2 /
#   INF-400c-2-ii, none for this AC) construct events via the `_make_event`
#   helper, which predates INF-400b-2-ii's reconciled record shape and
#   supplies `ticket` but never `agent`/`component`. Those fixtures are now
#   stale relative to the shape INF-400b-2-ii made authoritative (classify:
#   test_drift -- production is correct per the now-`done` INF-400b-2-ii
#   contract; the fixtures were never updated to match it). Per this
#   project's Test Delegation rule, test files are not touched here; flagged
#   for test-writer to update `_make_event` call sites (or migrate them to
#   `_make_bare_event`) to include `agent`/`component`. The fast-lane gate
#   scoped to INF-400b-2-i's own `# covers:` tags is unaffected (verified
#   green + coverage_ok). (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400b-2-i)
# - 2026-09-01 [python-coder]: Added `HarvestResult.outstanding` -- the "still
#   waiting to be written" count INF-700c-2 / INF-700c-2-ii require -- and
#   always print it in `summary()` (including when zero), since "visible is
#   not the same as outstanding" (INF-700c-2 it_requirements #5). The count is
#   derived per-record inside the existing loop, never stored: a record
#   contributes 1 unless it is eligibility-excluded (`no_learning_text`, per
#   INF-700c-1), already watermarked (`previously_processed`), or actually
#   written by this exact (non-dry-run) invocation. Deliberately NOT derived
#   from `skipped_unknown`/`unroutable_by_kind`, so a text-bearing record with
#   an unrecognised `entry_kind` still counts as outstanding -- the
#   anti-cheat boundary INF-700c-2-ii exists to pin. A write that raises
#   OSError leaves the record outstanding (the count follows the write, not
#   the attempt); a dry-run "route" never persists, so it also leaves the
#   record outstanding. No new exit code: `main()`'s 0/3/4 vocabulary is
#   still derived solely from `skipped_unknown` / `write_failures` /
#   `state_persist_failed`. Introduces no corpus identifier, no new runtime
#   state file, and mutates neither the sink nor any destination -- the 28
#   real records reach `outstanding == 0` because the definition of
#   outstanding is corrected, not because they were disposed of.
#   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700c-2)
