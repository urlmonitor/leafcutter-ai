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
      --ticket "/path/to/01_schema.md" --phase "python-coder"

--log PATH
    Path to the JSONL operational-stream sink.
    Default (AC INF-400c-4-iii, INF-500d-4-iv): the
    ``operational_telemetry_stream`` value recorded in the build-time
    declaration (``config/knowledge_sink.json``) of THIS script's own deployed
    workspace -- found relative to the script's resolved location, not the
    caller's current directory, so every working directory (the project root,
    a nested directory, an isolated worktree) resolves to the SAME stream.
    When the declaration is absent, unreadable, unparseable, lacks the key or
    holds a relative value, the script warns on stderr naming the declaration,
    writes NOTHING (no workspace-relative fallback) and still exits 0.

Exit codes:
    0 - always, including on write failure (telemetry is best-effort)
    2 - argument parsing failure (argparse default; a malformed call is a bug
        in the caller, not a runtime condition to swallow)
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
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

    Creates parent directories and the file itself when absent. The line goes
    out in ONE ``os.write`` on an ``O_APPEND`` descriptor, so records from
    simultaneous drives sharing one stream are neither lost, truncated nor
    interleaved (AC INF-500d-4-iv). Never raises: a telemetry sink that cannot
    be written is reported and dropped, because the drive it is observing must
    not fail on account of being observed (BP-400a-1-i).
    """
    try:
        line = json.dumps(record, ensure_ascii=False) + "\n"
    except (TypeError, ValueError) as exc:
        print(f"emit_event: record is not JSON-serialisable, dropped: {exc}",
              file=sys.stderr)
        return False

    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(log_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, line.encode("utf-8"))
        finally:
            os.close(fd)
    except OSError as exc:
        print(f"emit_event: could not write telemetry to {log_path}, "
              f"event dropped: {exc}", file=sys.stderr)
        return False
    return True


def _declaration_path() -> Path:
    """Return the build-time declaration of THIS script's own deployed workspace.

    The skill deploys to ``<output_root>/skills/agent-telemetry/scripts/`` and
    is reached through the ``.claude/skills`` symlink, so the resolved file
    sits three directories below ``<output_root>``, whose ``config/`` holds
    ``knowledge_sink.json``. The answer does not depend on the caller's
    current directory (AC INF-500d-4-iv; ADR-069 rule (a): configuration
    follows the workspace).
    """
    return Path(__file__).resolve().parents[3] / "config" / "knowledge_sink.json"


def _declared_stream(declaration: Path) -> tuple[Path | None, str]:
    """Return ``(stream, "")`` from *declaration*, or ``(None, why it is unusable)``.

    Standard library only (this script imports nothing from the package).
    Mirrors ``scripts/knowledge/sink_resolution.py``: the value of
    ``operational_telemetry_stream`` must be a non-empty absolute path.
    """
    try:
        data = json.loads(declaration.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "absent: no such file"
    except (OSError, ValueError) as exc:
        return None, f"unreadable or unparseable: {exc}"
    declared = data.get("operational_telemetry_stream") if isinstance(data, dict) else None
    if not isinstance(declared, str) or not declared:
        return None, "missing: no 'operational_telemetry_stream' entry"
    if not Path(declared).is_absolute():
        return None, f"not absolute: 'operational_telemetry_stream' is {declared!r}"
    return Path(declared), ""


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
            "JSONL sink path. Default (AC INF-500d-4-iv): the "
            "operational_telemetry_stream recorded in this install's "
            "build-time declaration (config/knowledge_sink.json); when that "
            "declaration is unusable the event is dropped with a warning."
        ),
    )
    args = parser.parse_args(argv)

    if args.log is not None:
        log_path = Path(args.log)
    else:
        declaration = _declaration_path()
        log_path, problem = _declared_stream(declaration)
        if log_path is None:
            print(f"emit_event: WARNING: no usable build-time declaration {declaration} "
                  f"({problem}); event dropped, nothing written", file=sys.stderr)
            return 0

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
# - 2026-10-12 [python-coder/INF-500d-4-iv]: The default stream is now read from
#   THIS script's own workspace declaration (Path(__file__).resolve().parents[3]
#   / "config" / "knowledge_sink.json"), replacing _find_declaration's ancestor
#   search of the caller's cwd for <dir>/config/knowledge_sink.json. That search
#   never matched the deployed layout (<project>/.leafcutter/config/) and fell
#   back to the bare relative debugging/logs/agent_telemetry.jsonl, i.e. a log
#   inside the disposable workspace. The workspace-relative fallback is gone: an
#   unusable declaration now warns (naming it) and drops the event, exit 0. The
#   append is one os.write on an O_APPEND descriptor. The standard-library-only
#   rule is KEPT: the declaration is read with json here (mirroring
#   scripts/knowledge/sink_resolution.py) rather than importing that module.
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
