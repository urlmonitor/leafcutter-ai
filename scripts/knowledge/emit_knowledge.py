"""
MODULE: emit_knowledge
GOAL: Validate an agent-supplied ``entry_kind`` against the single declared
    vocabulary and append a ``knowledge_captured`` event to the
    knowledge-emission sink -- or decline non-fatally when the entry_kind is
    out of vocabulary.
BUSINESS CONTEXT: AC INF-400c-5 requires enforcement to live at the point an
    event is emitted, not only at the harvester: "a free-hand JSON append by
    an agent is how the 15 uncontrolled values arose" (it_requirements). This
    CLI is the emission helper the four shipped emit sites (signoff SKILL.md
    Section 7, and the product-owner/business-analyst/it-po v3 templates)
    call instead of hand-writing a ``knowledge_captured`` JSON line.
    AC INF-400c-5-iii additionally requires a rejection to be reported to the
    agent (naming the rejected value and candidate members) without failing
    the agent's run, and to be counted distinctly from a run that emitted
    nothing (via a separate ``--rejection-log`` sink).
ARCHITECTURE: Self-contained CLI script (stdlib only, no project imports) for
    the Knowledge System component (docs/architecture/components/
    knowledge-system.md), mirroring the existing standalone-script convention
    of ``harvest_learnings.py`` and
    ``templates/skills/agent-telemetry/scripts/emit_event.py``. Reads its
    vocabulary from ``config/entry_kind_vocabulary.json`` via the shared
    ``entry_kind_vocabulary`` module so validation logic lives in one place
    (AC INF-400c-5-i).

Usage
-----
    python scripts/knowledge/emit_knowledge.py \\
        --agent AGENT --component COMPONENT --destination PATH \\
        --entry-kind KIND --text TEXT [--ticket TICKET] \\
        --sink SINK_PATH [--vocabulary VOCAB_PATH] [--rejection-log PATH]

Exit codes
----------
0   Always, in both the accepted and the rejected case. This helper is
    best-effort and must never be fatal to the calling agent (AC
    INF-400c-5-iii): an out-of-vocabulary entry_kind is reported on stdout,
    counted (when ``--rejection-log`` is given), and the run continues.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from entry_kind_vocabulary import (
    default_vocabulary_path,
    load_vocabulary,
    resolve_canonical,
)

logger = logging.getLogger("emit_knowledge")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="emit_knowledge",
        description=(
            "Validate an entry_kind against the declared vocabulary and "
            "append a knowledge_captured event to the emission sink."
        ),
    )
    parser.add_argument("--agent", required=True, help="Name of the emitting agent.")
    parser.add_argument("--component", required=True, help="Component the learning concerns.")
    parser.add_argument(
        "--destination", required=True, help="The knowledge surface path the event targets."
    )
    parser.add_argument(
        "--entry-kind", required=True, dest="entry_kind", help="The entry_kind to validate."
    )
    parser.add_argument("--text", required=True, help="The learning body text.")
    parser.add_argument("--ticket", default=None, help="Optional ticket reference.")
    parser.add_argument(
        "--sink", required=True, type=Path, help="Path to the JSONL knowledge-emission sink."
    )
    parser.add_argument(
        "--vocabulary",
        type=Path,
        default=None,
        help="Path to the declared entry_kind vocabulary JSON (default: build-time location).",
    )
    parser.add_argument(
        "--rejection-log",
        dest="rejection_log",
        type=Path,
        default=None,
        help=(
            "Optional path to a separate rejection-count sink. A run that "
            "rejects nothing never creates this file."
        ),
    )
    return parser.parse_args(argv)


def _select_candidates(members: dict[str, object], destination: str) -> list[str]:
    """Return the vocabulary members to offer as candidates for *destination*.

    Prefers members whose declared ``destination_pattern`` directory matches
    *destination*'s parent directory (AC INF-400c-5-iii: "lists the canonical
    members whose routing destination matches the destination the agent
    supplied"). Falls back to every vocabulary member when nothing matches --
    an empty candidate list on a genuine rejection would be a worse outcome
    than an over-inclusive one.

    Pure function: no I/O, no shared-state mutation.
    """
    dest_dir = str(Path(destination).parent)
    matches = []
    for name in sorted(members):
        meta = members[name]
        pattern = meta.get("destination_pattern") if isinstance(meta, dict) else None
        if isinstance(pattern, str) and str(Path(pattern).parent) == dest_dir:
            matches.append(name)
    return matches or sorted(members)


def _append_jsonl(path: Path, record: dict[str, object]) -> None:
    """Append *record* as one JSON line to *path*, creating parent dirs.

    External I/O, wrapped per the project error-handling policy: logs a
    WARNING and re-raises so the caller (at the CLI boundary) decides how to
    proceed rather than silently losing the write.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError as exc:
        logger.warning("Failed to append to %s: %s", path, exc)
        raise


def _handle_rejection(args: argparse.Namespace, members: dict[str, object]) -> None:
    """Report a rejected entry_kind and record it in the rejection log.

    Never writes to the knowledge-emission sink. Never raises: a failure to
    persist the rejection-log entry is logged and swallowed here, since the
    calling agent's run must not be blocked by this best-effort helper (AC
    INF-400c-5-iii).
    """
    candidates = _select_candidates(members, args.destination)
    print(
        f"REJECTED entry_kind {args.entry_kind!r}: not a member of the "
        "declared vocabulary. Candidate canonical members for this "
        f"destination: {candidates}",
        file=sys.stderr,
    )
    if args.rejection_log is not None:
        record = {
            "event": "knowledge_rejected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": args.agent,
            "component": args.component,
            "destination": args.destination,
            "rejected_entry_kind": args.entry_kind,
            "candidates": candidates,
        }
        try:
            _append_jsonl(args.rejection_log, record)
        except OSError:
            # Already logged by _append_jsonl. A rejection-log write failure
            # must not escalate into a failed run for the calling agent.
            pass


def _handle_acceptance(args: argparse.Namespace, canonical_entry_kind: str) -> None:
    """Write the validated event to the sink.

    A sink-write failure is logged and swallowed: this helper's own contract
    is best-effort / non-fatal to the calling agent, and a lost knowledge
    write is preferable to aborting the agent's primary task.
    """
    event: dict[str, object] = {
        "event": "knowledge_captured",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": args.agent,
        "component": args.component,
        "destination": args.destination,
        "entry_kind": canonical_entry_kind,
        "text": args.text,
    }
    if args.ticket:
        event["ticket"] = args.ticket
    try:
        _append_jsonl(args.sink, event)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Always returns 0 (see module docstring exit codes)."""
    args = _parse_args(argv)

    vocab_path = args.vocabulary or default_vocabulary_path()
    members = load_vocabulary(vocab_path)

    canonical_entry_kind = resolve_canonical(args.entry_kind, members)
    if canonical_entry_kind is None:
        _handle_rejection(args, members)
        return 0

    _handle_acceptance(args, canonical_entry_kind)
    return 0


if __name__ == "__main__":
    # Python automatically puts this script's own directory at sys.path[0]
    # when invoked as `python .../emit_knowledge.py`, so the top-level
    # `from entry_kind_vocabulary import ...` resolves without needing a
    # package `__init__.py` -- mirroring the standalone-script convention
    # already used by harvest_learnings.py's sibling modules.
    sys.exit(main())
