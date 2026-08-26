"""
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
0   Success — drained cleanly (no unroutable events left behind).
1   Sink file not found or unreadable.
2   State file exists but cannot be parsed (corrupted).
3   Drained with unroutable events left behind (see summary for the
    per-entry_kind breakdown). Distinct from 0 so a caller cannot mistake a
    run that routed nothing because there was unroutable input for a run
    that had nothing to route.
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger("harvest_learnings")


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class HarvestResult:
    """Outcome of a single harvester run."""

    routed: int = 0
    previously_processed: int = 0
    skipped_unknown: int = 0
    by_kind: dict[str, int] = dataclasses.field(default_factory=dict)
    unroutable_by_kind: dict[str, int] = dataclasses.field(default_factory=dict)

    def summary(self) -> str:
        """Return the human-readable one-line summary.

        Format: ``"N learnings routed: K1 kind1, K2 kind2 (M previously
        processed); P unroutable: K3 kind3, K4 kind4"``. The unroutable
        segment is present only when ``skipped_unknown`` is nonzero, and
        names each distinct unroutable ``entry_kind`` with its count so the
        backlog is visible on every run (INF-400c-2-ii).
        """
        parts = [f"{count} {kind}" for kind, count in sorted(self.by_kind.items())]
        breakdown = ", ".join(parts) if parts else "none"
        base = f"{self.routed} learnings routed: {breakdown}"
        if self.previously_processed:
            base += f" ({self.previously_processed} previously processed)"
        if self.skipped_unknown:
            unroutable_parts = [
                f"{count} {kind}" for kind, count in sorted(self.unroutable_by_kind.items())
            ]
            base += f"; {self.skipped_unknown} unroutable: {', '.join(unroutable_parts)}"
        return base


# ---------------------------------------------------------------------------
# State helpers (hash-based idempotency, per ADR-011)
# ---------------------------------------------------------------------------


def _event_hash(event: dict[str, Any]) -> str:
    """Return a stable SHA-256 hex digest for a knowledge_captured event.

    The hash key is the tuple (ticket, timestamp, destination, entry_kind).
    This is stable across file rotation and compaction.
    """
    key = json.dumps(
        {
            "ticket": event.get("ticket", ""),
            "timestamp": event.get("timestamp", ""),
            "destination": event.get("destination", ""),
            "entry_kind": event.get("entry_kind", ""),
        },
        sort_keys=True,
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


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
        plus a per-kind breakdown.

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

    for line in raw_lines:
        line = line.strip()
        if not line:
            continue

        # Parse JSON line
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            logger.warning("Skipping malformed JSON line: %s — %s", line[:80], exc)
            continue

        # Filter: only knowledge_captured events
        if event.get("event") != "knowledge_captured":
            if verbose:
                logger.debug("Skipping non-knowledge event: %s", event.get("event"))
            continue

        h = _event_hash(event)

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
            # Intentionally NOT added to new_hashes / seen: per INF-400c-2-ii
            # an unroutable event must remain retryable, not be silently
            # discarded via the idempotency record.
            continue

        # Build the learning text (minimal — harvester writes destination text)
        # The production path would load the event's `text` field if present;
        # for events emitted by signoff §7 the text is the learning body.
        learning_text = event.get("text", f"[{entry_kind}] Learning from {ticket}")

        if not dry_run:
            try:
                capture_fn(learning_text, destination)
            except OSError:
                # capture_fn already logged the error; continue to next event
                continue

        result.routed += 1
        result.by_kind[entry_kind] = result.by_kind.get(entry_kind, 0) + 1
        new_hashes.add(h)

    # 3. Persist updated state
    if not dry_run:
        try:
            _save_state(state_path, seen | new_hashes)
        except OSError:
            # _save_state already warned; do not abort the run
            pass

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
        ``0`` if the run drained cleanly (no unroutable events left behind),
        ``3`` if unroutable events remain in the sink (see the printed
        summary for the per-entry_kind breakdown). ``harvest()`` itself may
        also ``sys.exit(1)``/``sys.exit(2)`` for sink/state I/O failures
        before this function returns.
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

    return 3 if result.skipped_unknown else 0


if __name__ == "__main__":
    sys.exit(main())
