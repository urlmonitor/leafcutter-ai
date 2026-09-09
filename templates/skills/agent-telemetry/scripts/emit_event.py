#!/usr/bin/env python3
"""
MODULE: emit_event
GOAL: Append one agent-drive telemetry event to the operational JSONL stream,
    resolving the stream's location from the same build-time declaration the
    knowledge-emission sink uses, rather than a per-caller relative default.
BUSINESS CONTEXT: The epic runbook's drive-observability events (supervisor
    dispatch, epic halt/complete, agent start/end, retries) must land in one
    shared operational stream per install so retrospective-agent,
    feedback-analyst, and INF-700b-3's capture-health report can aggregate
    them over time -- a stream that fragments per working directory cannot
    be aggregated by any of them (AC INF-400c-4-iii).
ARCHITECTURE: Entry point for the agent-telemetry skill
    (templates/skills/agent-telemetry/SKILL.md). Distinct from the
    knowledge-emission sink (scripts/knowledge/harvest_learnings.py) and from
    scripts/agent-health/agent_telemetry.py's per-invocation cost metrics.

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

--log PATH
    Path to the JSONL operational-stream sink.
    Default (AC INF-400c-4-iii): the ``operational_telemetry_stream`` value
    recorded in the same build-generated declaration
    (``config/knowledge_sink.json``) the knowledge harvester reads for its
    own sink — found by searching the ancestors of the caller's current
    directory, so an isolated working directory beneath a project root
    resolves to the SAME operational stream as the project root itself,
    rather than fragmenting into one file per working directory. Falls back
    to ``debugging/logs/agent_telemetry.jsonl`` (relative to the caller's
    current directory) only when no declaration is found anywhere above the
    caller (e.g. an un-built source-tree run).

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

# Bound on how many ancestor directories of the caller's current working
# directory are inspected when looking for the build-generated declaration
# (AC INF-400c-4-iii). Generous enough for any realistic nesting depth of an
# isolated working directory beneath a project root, small enough that a
# caller run from an unrelated deep path (e.g. "/") does not walk forever.
_MAX_DECLARATION_SEARCH_DEPTH = 64

# Historical CWD-relative default, used only when no build-generated
# declaration is found anywhere above the caller's current directory (e.g.
# an un-built source-tree run). Kept as the fallback so existing behaviour
# for callers outside a built install is unchanged.
_LEGACY_DEFAULT_LOG_PATH = "debugging/logs/agent_telemetry.jsonl"


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


def _find_declaration(start: Path) -> Path | None:
    """Return the nearest build-generated ``config/knowledge_sink.json``.

    AC INF-400c-4-iii ("ONE STREAM ANCHOR, NOT TWO"): the operational stream
    must be reached by the same build-time-fixed artefact the knowledge sink
    already is, rather than each stream resolving its own directory. This
    script has no ``__file__``-relative route to that artefact -- unlike
    ``harvest_learnings.py``, it is invoked from wherever its skill copy is
    installed, with no fixed depth below a deployed output root -- so it
    looks for the declaration among the ancestors of the CALLER's current
    directory instead, bounded by ``_MAX_DECLARATION_SEARCH_DEPTH`` so a
    caller run far from any install does not walk indefinitely. Returns
    ``None`` when no declaration is found within the bound (e.g. an un-built
    source-tree run, or a caller entirely outside any built install).
    """
    current = start
    for _ in range(_MAX_DECLARATION_SEARCH_DEPTH):
        candidate = current / "config" / "knowledge_sink.json"
        if candidate.is_file():
            return candidate
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def _resolve_default_log_path(cwd: Path) -> Path:
    """Resolve the operational-stream path to use when ``--log`` is omitted.

    Prefers the ``operational_telemetry_stream`` value recorded in the same
    build-generated declaration ``harvest_learnings.py`` reads for the
    knowledge sink (AC INF-400c-4-iii). Falls back to the historical
    CWD-relative default when no declaration is found, or when a declaration
    is found but predates this key (an older or hand-authored declaration
    missing the newer field) -- in which case the declaration's OWN
    directory (never a directory this function computes independently) is
    used as the shared anchor, so the operational stream still lands beside
    the knowledge sink's install rather than beside the caller's own cwd.
    """
    declaration = _find_declaration(cwd)
    if declaration is None:
        return Path(_LEGACY_DEFAULT_LOG_PATH)

    try:
        data = json.loads(declaration.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"emit_event: could not read declaration {declaration}, "
            f"falling back to default: {exc}",
            file=sys.stderr,
        )
        return Path(_LEGACY_DEFAULT_LOG_PATH)

    declared = data.get("operational_telemetry_stream")
    if isinstance(declared, str) and declared:
        return Path(declared)

    # Declaration exists but lacks the operational key -- anchor on the
    # declaration's own location (the shared artefact both streams read),
    # not on the caller's cwd, and not on any directory recomputed from
    # scratch.
    anchor = declaration.parent.parent
    return anchor / "debugging" / "logs" / "agent_telemetry.jsonl"


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
    parser.add_argument(
        "--log",
        default=None,
        help=(
            "JSONL sink path. Default (AC INF-400c-4-iii): the "
            "operational_telemetry_stream recorded in the same "
            "build-generated declaration the knowledge harvester reads, "
            f"falling back to {_LEGACY_DEFAULT_LOG_PATH!r} (relative to the "
            "caller's current directory) when no declaration is found."
        ),
    )
    args = parser.parse_args(argv)

    log_path = Path(args.log) if args.log is not None else _resolve_default_log_path(Path.cwd())

    record = build_record(
        event=args.event,
        agent=args.agent,
        ticket=args.ticket,
        phase=args.phase,
        outcome=args.outcome,
        retry_count=args.retry_count,
    )
    append_record(record, log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-09-09 [python-coder]: Added _find_declaration()/_resolve_default_log_path()
#   and changed --log's default from a hardcoded CWD-relative string to None,
#   resolved dynamically (AC INF-400c-4-iii). When --log is omitted, the
#   operational stream now resolves via the SAME build-generated declaration
#   (config/knowledge_sink.json) harvest_learnings.py already reads for the
#   knowledge sink -- read by searching the ancestors of the caller's current
#   directory for that file (this script has no fixed __file__-relative depth
#   below a deployed output root the way harvest_learnings.py does), preferring
#   the new operational_telemetry_stream key and falling back to the
#   declaration's own directory when that key is absent. Closes the gap where
#   a caller inside an isolated working directory wrote a SEPARATE operational
#   stream file than one at the project root, fragmenting the stream every
#   working directory instead of sharing one per install. No behaviour change
#   for existing callers that pass --log explicitly.
#   (#TICKETLESS reason=ac-scoped-fastlane-build-INF-400c-4-iii)
