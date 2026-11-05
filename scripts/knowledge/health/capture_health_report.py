"""
MODULE: capture_health_report
GOAL: Tell a reader, for a reporting period, which kind of quiet it was -- no
    capture attempt at all, attempts that all had nothing to record, attempts
    that recorded learnings, or a broken capture path (naming what was missing)
    -- from the durable capture-attempt ledger alone.
BUSINESS CONTEXT: AC INF-700b-3. A period with no captured learnings used to
    look the same whether agents had nothing to record, the capture step never
    ran, or the capture path was failing. This report counts ``capture_attempt``
    records (the unit is the ATTEMPT, never the agent run: the ledger has no run
    id) and gives exactly one of four verdicts per period. It fails closed: when
    it cannot locate the ledger it exits non-zero and prints no verdict, because
    a dead ledger must not read as a quiet week (ADR-034 Amendment 3, A3.4).
ARCHITECTURE: CLI-only reader in the Knowledge System / Agent Telemetry
    components (docs/architecture/adrs/amendments/ADR-034/
    amendment-3-capture-health-reader-contract.md). Pure ``build_report(lines,
    since, until)`` plus ``main(argv)``. Standard library only, apart from the
    parent-folder ``sink_resolution`` module (``scripts/knowledge/``), whose ``read_usable_stream``,
    ``enduring_root_exists`` and ``refusal_message`` are the one usable-stream
    rule (not copied here). It reads the operational telemetry stream and
    nothing else: not the harvester, not the knowledge-emission sink, no
    backlog figure. Deployed to ``<output_root>/scripts/knowledge/health/`` through
    both hand-kept lists in ``scripts/build_phases_knowledge.py``.

# DECISION HISTORY
# - 2026-10-23 [python-coder/INF-700b-3]: Created. Four verdicts in the order
#   no attempts, any failed, any recorded, else nothing-to-record; half-open
#   window [since, until) with naive times read as UTC; bad timestamps and
#   out-of-set outcomes are counted as malformed, non-attempt lines as
#   unrecognised, neither is fatal; an unlocatable stream exits 1 with no
#   verdict while a usable declaration with no stream file yet is
#   no-run-reached-the-step. (#EPIC-ALearningAnAgentHasTodayActuallyGets/06)
# - 2026-10-23 [python-coder/INF-700b-3]: Moved from scripts/knowledge/ into the
#   health/ sub-folder (check-folder-density, 15 non-markdown files per folder);
#   sink_resolution is now imported from the parent folder and the output root is
#   parents[3]. (#EPIC-ALearningAnAgentHasTodayActuallyGets/06)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

OUTCOMES = ("recorded", "nothing-to-record", "failed")
VERDICT_NO_RUN = "no-run-reached-the-step"
VERDICT_BROKEN = "capture-path-broken"
VERDICT_RECORDED = "learnings-recorded"
VERDICT_NOTHING = "nothing-to-record"
NOT_RECORDED = "(not recorded)"
_TELEMETRY_KEY = "operational_telemetry_stream"
_MEANINGS = {
    VERDICT_NO_RUN: "no capture attempt was recorded in this period",
    VERDICT_BROKEN: "at least one attempt to record a learning failed; the capture path is broken",
    VERDICT_RECORDED: "attempts recorded learnings and none failed",
    VERDICT_NOTHING: "attempts were made and every one found nothing to record",
}
_LIMITS = (
    "limit A2.6: a failed attempt can only exist where telemetry was still writable; "
    "a failure that also broke the telemetry writer leaves no record.",
    "limit A2.4: when the knowledge record is written but the emit_event.py subprocess "
    "cannot run, no recorded attempt exists, so such a period can read as nothing-to-record "
    "(or no-run-reached-the-step when it was the only attempt).",
)


@dataclass
class Report:
    """Figures for one period; ``attempts`` is always recorded + nothing + failed."""

    since: datetime
    until: datetime
    recorded: int = 0
    nothing: int = 0
    failed: int = 0
    malformed: int = 0
    unrecognised: int = 0
    targets: set[str] = field(default_factory=set)

    @property
    def attempts(self) -> int:
        """Return the number of in-window attempts."""
        return self.recorded + self.nothing + self.failed

    @property
    def verdict(self) -> str:
        """Return the one verdict, decided in the fixed A3.2 order."""
        if self.attempts == 0:
            return VERDICT_NO_RUN
        if self.failed:
            return VERDICT_BROKEN
        return VERDICT_RECORDED if self.recorded else VERDICT_NOTHING


def as_utc(moment: datetime) -> datetime:
    """Return *moment* as an aware datetime, reading a naive one as UTC."""
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=timezone.utc)


def parse_time(text: object) -> datetime | None:
    """Parse an ISO-8601 *text* into an aware UTC-defaulted datetime, or ``None`` when it is not one."""
    if not isinstance(text, str) or not text.strip():
        return None
    try:
        return as_utc(datetime.fromisoformat(text.strip().replace("Z", "+00:00")))
    except ValueError:
        return None


def _attempt_or_kind(line: str) -> tuple[str, dict | None]:
    """Classify one stream *line* as ``blank``, ``unrecognised`` or ``attempt`` (with its record)."""
    text = line.strip()
    if not text:
        return "blank", None
    try:
        record = json.loads(text)
    except ValueError:
        return "unrecognised", None
    if not isinstance(record, dict) or record.get("event_type") != "capture_attempt":
        return "unrecognised", None
    return "attempt", record


def _read_attempt(record: dict) -> tuple[datetime, str, str] | None:
    """Return ``(when, outcome, target)`` for a valid attempt *record*, or ``None`` when it is malformed.

    ``missing_target`` is read with a default because records written before A2.2 lack the key.
    """
    payload = record.get("payload")
    payload = payload if isinstance(payload, dict) else {}
    when = parse_time(record.get("timestamp"))
    outcome = payload.get("outcome")
    if when is None or outcome not in OUTCOMES:
        return None
    target = payload.get("missing_target")
    shown = target.strip() if isinstance(target, str) and target.strip() else NOT_RECORDED
    return when, outcome, shown


def build_report(lines: list[str], since: datetime, until: datetime) -> Report:
    """Count the capture attempts of the half-open window ``[since, until)`` in stream *lines*.

    Args:
        lines: Raw telemetry stream lines; garbage never raises.
        since: Window start (inclusive); a naive value is read as UTC.
        until: Window end (exclusive); a naive value is read as UTC.

    Returns:
        The period's :class:`Report`. Malformed attempts (bad or absent timestamp,
        outcome outside the closed set) and unrecognised lines are counted apart
        from every period figure.

    Pure function: no I/O, no shared-state mutation.
    """
    start, end = as_utc(since), as_utc(until)
    report = Report(since=start, until=end)
    for line in lines:
        kind, record = _attempt_or_kind(line)
        if kind == "unrecognised":
            report.unrecognised += 1
        elif record is not None:
            _count_attempt(report, record)
    return report


def _count_attempt(report: Report, record: dict) -> None:
    """Add one attempt *record* to *report*, or count it as malformed or out of window."""
    parsed = _read_attempt(record)
    if parsed is None:
        report.malformed += 1
        return
    when, outcome, target = parsed
    if not report.since <= when < report.until:
        return
    if outcome == "failed":
        report.failed += 1
        report.targets.add(target)
    elif outcome == "recorded":
        report.recorded += 1
    else:
        report.nothing += 1


def format_report(report: Report) -> str:
    """Render *report* as the text a reader sees; every figure is printed, zeros included."""
    out = [
        "capture-health report",
        f"period: {report.since.isoformat()} to {report.until.isoformat()} (half-open, UTC)",
        "unit: attempts (one capture_attempt record each)",
        f"attempts={report.attempts} recorded={report.recorded} "
        f"nothing-to-record={report.nothing} failed={report.failed}",
        f"malformed={report.malformed} unrecognised={report.unrecognised}",
        f"verdict: {report.verdict}",
        f"meaning: {_MEANINGS[report.verdict]}",
    ]
    if report.verdict == VERDICT_BROKEN:
        out += [f"missing-target: {target}" for target in sorted(report.targets)]
    out += _LIMITS
    return "\n".join(out) + "\n"


def _refusal(output_root: Path) -> str | None:
    """Return why the declared telemetry stream cannot be used, or ``None`` when it can."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import sink_resolution

    stream, why = sink_resolution.read_usable_stream(output_root, _TELEMETRY_KEY)
    if stream is None:
        return sink_resolution.refusal_message(output_root, "telemetry stream", why)
    if not sink_resolution.enduring_root_exists(output_root):
        declaration = output_root / "config" / "knowledge_sink.json"
        return f"the enduring root recorded in {declaration} no longer exists (stale declaration)"
    return None


def _declared_stream(output_root: Path) -> tuple[Path | None, str]:
    """Return ``(stream, "")`` from the install's declaration, or ``(None, reason)`` when unusable."""
    reason = _refusal(output_root)
    if reason is not None:
        return None, reason
    import sink_resolution

    stream, _why = sink_resolution.read_usable_stream(output_root, _TELEMETRY_KEY)
    return stream, ""


def _read_lines(stream: Path) -> list[str]:
    """Read *stream*'s lines; a stream file that does not exist yet is an empty ledger."""
    if not stream.exists():
        return []
    try:
        return stream.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        print(f"ERROR: cannot read the telemetry stream {stream}: {exc}", file=sys.stderr)
        raise


def _moment(text: str) -> datetime:
    """Parse a ``--since`` / ``--until`` argument (date-only means midnight UTC).

    argparse reports a ``ValueError`` as ``invalid _moment value: <text>`` (exit 2).
    """
    parsed = parse_time(text)
    if parsed is None:
        raise ValueError(text)
    return parsed


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: print the capture-health report, or refuse when the ledger cannot be located.

    Args:
        argv: Arguments after the program name; ``None`` reads ``sys.argv``.

    Returns:
        0 with a report on stdout; 1 with the reason on stderr and nothing on
        stdout when the stream is unlocatable or unreadable.
    """
    parser = argparse.ArgumentParser(prog="capture_health_report", description=__doc__.split("\n")[2].strip())
    parser.add_argument("--since", required=True, type=_moment, help="ISO-8601 window start (inclusive)")
    parser.add_argument("--until", required=True, type=_moment, help="ISO-8601 window end (exclusive)")
    parser.add_argument("--stream", type=Path, default=None, help="telemetry stream override")
    args = parser.parse_args(argv)
    stream = args.stream
    if stream is None:
        stream, reason = _declared_stream(Path(__file__).resolve().parents[3])
        if stream is None:
            print(f"ERROR: {reason}. No verdict is given from a ledger that cannot be found.", file=sys.stderr)
            return 1
    try:
        lines = _read_lines(stream)
    except OSError:
        return 1
    sys.stdout.write(format_report(build_report(lines, args.since, args.until)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
