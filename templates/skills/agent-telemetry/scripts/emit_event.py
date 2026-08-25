#!/usr/bin/env python3
"""
emit_event.py — append one agent-drive telemetry event to a JSONL sink.

Records the drive-observability events the epic runbook emits: supervisor
dispatch, epic halt, epic complete, agent start/end, retries. One invocation
appends exactly one JSON line.

Deliberately self-contained: standard library only, and it imports NOTHING from
the package. The script runs from the DEPLOYED layout
(``.claude/skills/agent-telemetry/scripts/emit_event.py``), where a project
import would have to be carried by the build's deploy manifest — the failure
class that has already produced several silent breakages here (a deployed hook
whose dependency was never deployed). A file with no project imports cannot
acquire that defect.

Write failures are NON-FATAL by design (BP-400a-1-i): every call site in
``building-epics`` invokes this with a trailing ``|| true`` because losing a
telemetry line must never halt a build. The script warns on stderr and still
exits 0, so the caller's ``|| true`` is belt-and-braces rather than the only
thing keeping the drive alive.

Record shape (BP-400a-1):
    {"event_type": ..., "timestamp": ..., "agent_name": ..., "ticket_path": ...,
     "payload": {"phase": ..., "outcome": ..., "retry_count": ...}}
Absent optional values are written as JSON null rather than omitted, so every
line has the same keys and a reader never needs to test for key presence.

NOTE: this is a different surface from ``scripts/agent-health/agent_telemetry.py``,
which records per-invocation cost metrics (lane, duration, token counts) for
fast-lane comparison. Same word, different record — do not merge them.

Usage:
    python emit_event.py --agent "ticket-supervisor" --event agent_start \
      --ticket "/path/to/01_schema.md" --phase "python-coder" \
      --log debugging/logs/agent_telemetry.jsonl

Exit codes:
    0 - always, including on write failure (telemetry is best-effort)
    2 - argument parsing failure (argparse default; a malformed call is a bug
        in the caller, not a runtime condition to swallow)
"""

from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path


def build_record(
    *,
    event: str,
    agent: str,
    ticket: str | None = None,
    phase: str | None = None,
    outcome: str | None = None,
    retry_count: int | None = None,
    timestamp: str | None = None,
) -> dict:
    """Return the telemetry record for one event.

    Optional values are preserved as None (serialised as JSON null) so every
    emitted line carries an identical key set.
    """
    return {
        "event_type": event,
        "timestamp": timestamp or datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "agent_name": agent,
        "ticket_path": ticket,
        "payload": {
            "phase": phase,
            "outcome": outcome,
            "retry_count": retry_count,
        },
    }


def append_record(record: dict, log_path: Path) -> bool:
    """Append *record* to *log_path* as one JSON line. Return True on success.

    Creates parent directories and the file itself when absent. Never raises:
    a telemetry sink that cannot be written is reported and dropped, because
    the drive it is observing must not fail on account of being observed
    (BP-400a-1-i).
    """
    try:
        line = json.dumps(record, ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as exc:
        print(f"emit_event: record is not JSON-serialisable, dropped: {exc}",
              file=sys.stderr)
        return False

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError as exc:
        print(f"emit_event: could not write telemetry to {log_path}, "
              f"event dropped: {exc}", file=sys.stderr)
        return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Entry point. Always returns 0 — telemetry emission is best-effort."""
    parser = argparse.ArgumentParser(
        description="Append one agent-drive telemetry event to a JSONL sink.")
    parser.add_argument("--event", required=True,
                        help="Event type, e.g. agent_start, epic_complete.")
    parser.add_argument("--agent", required=True,
                        help="Emitting agent name, e.g. ticket-supervisor.")
    parser.add_argument("--ticket", default=None, help="Ticket path, when scoped to one.")
    parser.add_argument("--phase", default=None, help="Phase name, e.g. python-coder.")
    parser.add_argument("--outcome", default=None, help="Outcome, e.g. ok, blocked.")
    parser.add_argument("--retry-count", type=int, default=None,
                        help="Retry attempt number, when this event is a retry.")
    parser.add_argument("--log", default="debugging/logs/agent_telemetry.jsonl",
                        help="JSONL sink path. Default: %(default)s")
    args = parser.parse_args(argv)

    record = build_record(
        event=args.event,
        agent=args.agent,
        ticket=args.ticket,
        phase=args.phase,
        outcome=args.outcome,
        retry_count=args.retry_count,
    )
    append_record(record, Path(args.log))
    return 0


if __name__ == "__main__":
    sys.exit(main())
