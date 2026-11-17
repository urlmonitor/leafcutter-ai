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
     "payload": {"phase": ..., "outcome": ..., "retry_count": ...,
                 "missing_target": ...}}
Absent optional values are written as JSON null rather than omitted, so every
line has the same keys and a reader never needs to test for key presence.

``capture_attempt`` (ADR-034 Amendment 2, A2.2) is the capture-attempt ledger
event: its ``--outcome`` must be one of recorded, nothing-to-record, failed,
and ``failed`` also requires ``--missing-target`` (which any other outcome must
omit). A violation writes nothing,
warns on stderr and still exits 0. Other event types keep free-text outcomes.

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
    The stream is usable only when the declaration also records an absolute
    ``operational_log_root`` with the stream directly under it (INF-500d-4-i).
    When the declaration is absent, unreadable, unparseable, lacks either key,
    holds a relative value or the stream is outside the root, the script warns
    on stderr naming the declaration and ``operational_log_root``, writes
    NOTHING (no workspace-relative fallback) and still exits 0.

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
    missing_target: str | None = None,
    timestamp: str | None = None,
) -> dict:
    """Return the telemetry record for one event.

    Optional values are preserved as None (serialised as JSON null) so every
    emitted line carries an identical key set, ``missing_target`` included.
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
            "missing_target": missing_target,
        },
    }


CAPTURE_ATTEMPT = "capture_attempt"
CAPTURE_OUTCOMES = ("recorded", "nothing-to-record", "failed")


def _refusal_reason(event: str, outcome: str | None, missing_target: str | None) -> str | None:
    """Return why a ``capture_attempt`` call must be refused, or None when it is valid.

    Only ``capture_attempt`` is validated (ADR-034 A2.2): its outcome must be a
    member of the closed set, ``failed`` must name the missing target, and any
    other outcome must NOT carry one (``missing_target`` is null unless failed).
    Every other event type keeps free-text outcomes. Pure function: no I/O.
    """
    if event != CAPTURE_ATTEMPT:
        return None
    if outcome not in CAPTURE_OUTCOMES:
        return f"capture_attempt outcome {outcome!r} is not one of {list(CAPTURE_OUTCOMES)}"
    if outcome == "failed" and not missing_target:
        return "capture_attempt outcome 'failed' requires --missing-target"
    if outcome != "failed" and missing_target is not None:
        return f"capture_attempt outcome {outcome!r} must not carry --missing-target"
    return None


def append_record(record: dict, log_path: Path) -> bool:
    """Append *record* to *log_path* as one JSON line. Return True on success.

    Creates missing parent directories and the file itself when absent (for a
    declared stream ``_declared_stream`` has already established that the
    enduring root holding the log directory is live, so at most ``debugging``
    and the log directory appear). The line goes
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
    follows the workspace). The Gemini copy sits one directory deeper
    (``<output_root>/gemini/skills/...``, reached through ``.gemini``), so a
    ``gemini`` directory is stepped out of.
    """
    install = Path(__file__).resolve().parents[3]
    if install.name == "gemini":
        install = install.parent
    return install / "config" / "knowledge_sink.json"


def _declared_stream(declaration: Path) -> tuple[Path | None, str]:
    """Return ``(stream, "")`` from *declaration*, or ``(None, why it is unusable)``.

    Standard library only (this script imports nothing from the package).
    An inline copy of ``scripts/knowledge/sink_resolution.read_usable_stream``,
    the one usable-stream rule (INF-500d-4-i): the declaration must record an
    absolute ``operational_log_root`` AND an absolute
    ``operational_telemetry_stream`` sitting directly under it. It also mirrors
    ``enduring_root_exists``: the directory holding the root (its parent, or the
    project above ``debugging``) must exist, so a vanished project is refused
    rather than recreated; a missing log directory under a live one is a first
    write. Keep the two in step.
    """
    try:
        data = json.loads(declaration.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, "absent: no such file"
    except (OSError, ValueError) as exc:
        return None, f"unreadable or unparseable: {exc}"
    if not isinstance(data, dict):
        return None, "unparseable: the declaration is not a JSON object"
    values: dict[str, str] = {}
    for key in ("operational_log_root", "operational_telemetry_stream"):
        value = data.get(key)
        if not isinstance(value, str) or not value:
            return None, f"missing: no '{key}' entry"
        if not Path(value).is_absolute():
            return None, f"not absolute: '{key}' is {value!r}"
        values[key] = value
    stream, root = values["operational_telemetry_stream"], values["operational_log_root"]
    if Path(stream).parent != Path(root):
        return None, (f"'operational_telemetry_stream' is {stream}, which is not "
                      f"directly under operational_log_root {root}")
    holder = Path(root).parent
    if holder.name == "debugging":
        holder = holder.parent
    if not holder.is_dir():
        return None, (f"stale: {holder} (the enduring root that should hold {root}) "
                      "no longer exists")
    return Path(stream), ""


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
    parser.add_argument("--missing-target", dest="missing_target", default=None,
                        help="Literal path of the script that could not run "
                             "(required for capture_attempt outcome failed).")
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

    refusal = _refusal_reason(args.event, args.outcome, args.missing_target)
    if refusal is not None:
        print(f"emit_event: WARNING: {refusal}; event dropped, nothing written",
              file=sys.stderr)
        return 0

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
        missing_target=args.missing_target,
    )
    append_record(record, log_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-10-21 15:00 [python-coder]: capture_attempt with --missing-target on an outcome other than `failed` is refused (nothing written, stderr warning, exit 0), so missing_target is null unless failed (pr-reviewer M-1). (#EPIC-ALearningAnAgentHasTodayActuallyGets/02) (ADR-034)
# - 2026-10-21 12:00 [python-coder]: Added the capture_attempt event (closed
#   outcome set, validated for that event only) and --missing-target, carried as
#   payload.missing_target on every record (null by default). No new copy of the
#   usable-stream rule: stream resolution is unchanged. (#EPIC-ALearningAnAgentHasTodayActuallyGets/02) (ADR-034)
# - 2026-10-12 [python-coder/INF-500d-4-i gap fix]: _declared_stream now also
#   requires an absolute operational_log_root with the stream directly under it,
#   so a --no-log-root or legacy two-key declaration (streams recorded under the
#   disposable worktree) warns and drops the event instead of writing there.
#   The rule lives in scripts/knowledge/sink_resolution.read_usable_stream; this
#   is a deliberate inline copy because the standard-library-only rule is KEPT
#   (importing sink_resolution would need the deploy manifest to carry it).
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
