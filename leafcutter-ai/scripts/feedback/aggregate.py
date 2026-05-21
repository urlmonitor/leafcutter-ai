"""
MODULE: leafcutter/scripts/feedback/aggregate.py
GOAL: Read-only query script for feedback.jsonl. Filters entries by
      ticket, category, phase, date range, and source; returns filtered
      rows and summary counts in JSON or table format.
BUSINESS CONTEXT: Enables retrospective-agent and ad-hoc human queries
      over structured feedback data without requiring manual log parsing.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - docs/how-to/feedback-collection.md
  - docs/explanation/why-feedback-system.md

Usage:
    aggregate.py [--ticket <path>] [--category <id>] [--phase <agent>]
                 [--since <YYYY-MM-DD>] [--until <YYYY-MM-DD>]
                 [--source {agent,hook}] [--hook-name <name>]
                 [--jsonl <path>]
                 [--format {json,table}]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_JSONL_DEFAULT = Path(__file__).resolve().parents[3] / "debugging" / "logs" / "feedback.jsonl"


# ---------------------------------------------------------------------------
# JSONL reading and filtering
# ---------------------------------------------------------------------------


def _read_jsonl(jsonl_path: Path) -> list[dict]:
    """Read and parse all valid JSON lines from the feedback JSONL file.

    Silently skips malformed lines (backward compatibility with partial writes).

    Args:
        jsonl_path: Path to the feedback.jsonl file.

    Returns:
        list[dict]: List of parsed entry dicts.
    """
    if not jsonl_path.exists():
        return []
    entries: list[dict] = []
    with open(jsonl_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                pass  # skip malformed lines
    return entries


def _parse_date(date_str: str) -> datetime:
    """Parse a YYYY-MM-DD date string to a timezone-aware datetime at midnight UTC.

    Args:
        date_str: Date string in YYYY-MM-DD format.

    Returns:
        datetime: Timezone-aware datetime at midnight UTC.

    Raises:
        ValueError: When the string is not a valid YYYY-MM-DD date.
    """
    return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)


def _entry_date(entry: dict) -> datetime | None:
    """Extract the timestamp field from an entry as a timezone-aware datetime.

    Args:
        entry: Feedback JSONL entry dict.

    Returns:
        datetime | None: Parsed datetime, or None when the field is missing/malformed.
    """
    ts = entry.get("timestamp")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _matches_date_window(
    entry: dict,
    since_dt: datetime | None,
    until_dt: datetime | None,
) -> bool:
    """Return True if the entry falls within the given date window.

    Args:
        entry: Feedback JSONL entry dict.
        since_dt: Inclusive lower bound (timezone-aware), or None for no lower bound.
        until_dt: Inclusive upper bound at day granularity, or None for no upper bound.

    Returns:
        bool: True when the entry's timestamp is within the window.
    """
    if since_dt is None and until_dt is None:
        return True
    entry_dt = _entry_date(entry)
    if entry_dt is None:
        return False
    if since_dt and entry_dt < since_dt:
        return False
    if until_dt:
        entry_day = entry_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if entry_day > until_dt:
            return False
    return True


def _matches_scalar_filters(
    entry: dict,
    ticket: str | None,
    category: str | None,
    phase: str | None,
    source: str | None,
    hook_name: str | None,
) -> bool:
    """Return True if the entry matches all provided scalar field filters.

    Entries without a 'source' field are treated as source='agent'.

    Args:
        entry: Feedback JSONL entry dict.
        ticket: Required ticket path value, or None.
        category: Required category id value, or None.
        phase: Required phase value, or None.
        source: Required source value ('agent' or 'hook'), or None (all sources).
        hook_name: Required hook_name value, or None.

    Returns:
        bool: True when all provided filters match.
    """
    if ticket and entry.get("ticket") != ticket:
        return False
    if category and entry.get("category") != category:
        return False
    if phase and entry.get("phase") != phase:
        return False
    # Treat missing 'source' as 'agent' for backward compatibility
    if source and entry.get("source", "agent") != source:
        return False
    if hook_name and entry.get("hook_name") != hook_name:
        return False
    return True


def filter_entries(
    entries: list[dict],
    ticket: str | None = None,
    category: str | None = None,
    phase: str | None = None,
    since: str | None = None,
    until: str | None = None,
    source: str | None = None,
    hook_name: str | None = None,
) -> list[dict]:
    """Filter a list of feedback entries by the given criteria.

    All filters are AND-combined. Absent filters are not applied.
    Entries without a 'source' field are treated as source='agent'.

    Args:
        entries: List of parsed feedback entry dicts.
        ticket: Filter to entries whose 'ticket' field matches this value.
        category: Filter to entries whose 'category' field matches this value.
        phase: Filter to entries whose 'phase' field matches this value.
        since: ISO date string YYYY-MM-DD; include entries on or after this date.
        until: ISO date string YYYY-MM-DD; include entries on or before this date.
        source: Filter by 'source' field ('agent' or 'hook'). None = all sources.
        hook_name: Filter by 'hook_name' field (only meaningful for source=hook).

    Returns:
        list[dict]: Filtered list of entries.
    """
    since_dt = _parse_date(since) if since else None
    until_dt = _parse_date(until) if until else None

    result: list[dict] = []
    for entry in entries:
        if not _matches_scalar_filters(entry, ticket, category, phase, source, hook_name):
            continue
        if not _matches_date_window(entry, since_dt, until_dt):
            continue
        result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Summary building
# ---------------------------------------------------------------------------


def _build_summary(entries: list[dict]) -> dict:
    """Build a summary dict with total count, per-category, and per-phase counts.

    Also builds per-hook-name counts when the filtered set contains hook entries.

    Args:
        entries: Filtered list of feedback entry dicts.

    Returns:
        dict: Summary with 'total', 'by_category', 'by_phase', and optionally
              'by_hook_name' keys.
    """
    by_category: dict[str, int] = {}
    by_phase: dict[str, int] = {}
    by_hook_name: dict[str, int] = {}
    has_hooks = False

    for entry in entries:
        cat = entry.get("category", "unknown")
        ph = entry.get("phase", "unknown")
        by_category[cat] = by_category.get(cat, 0) + 1
        by_phase[ph] = by_phase.get(ph, 0) + 1
        if entry.get("source") == "hook":
            has_hooks = True
            hn = entry.get("hook_name", "unknown")
            by_hook_name[hn] = by_hook_name.get(hn, 0) + 1

    summary: dict = {
        "total": len(entries),
        "by_category": dict(sorted(by_category.items())),
        "by_phase": dict(sorted(by_phase.items())),
    }
    if has_hooks:
        summary["by_hook_name"] = dict(sorted(by_hook_name.items()))
    return summary


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _format_table(entries: list[dict], summary: dict) -> str:
    """Format filtered entries and summary as a human-readable table.

    Args:
        entries: Filtered feedback entry dicts.
        summary: Summary dict from _build_summary.

    Returns:
        str: Human-readable table string.
    """
    lines: list[str] = []
    for entry in entries:
        ts = entry.get("timestamp", "?")[:19]
        fid = entry.get("feedback_id", "?")
        cat = entry.get("category", "?")
        ph = entry.get("phase", "?")
        note = entry.get("note", "")[:60]
        lines.append(f"  {ts}  {fid}  {cat:<22}  {ph:<20}  {note}")

    lines.append("")
    lines.append(f"Total: {summary['total']}")
    lines.append("By category: " + ", ".join(
        f"{k}={v}" for k, v in summary["by_category"].items()
    ))
    lines.append("By phase:    " + ", ".join(
        f"{k}={v}" for k, v in summary["by_phase"].items()
    ))
    if "by_hook_name" in summary:
        lines.append("By hook:     " + ", ".join(
            f"{k}={v}" for k, v in summary["by_hook_name"].items()
        ))
    return "\n".join(lines)


def _format_json(entries: list[dict], summary: dict) -> str:
    """Format filtered entries and summary as a JSON array + summary object.

    Args:
        entries: Filtered feedback entry dicts.
        summary: Summary dict from _build_summary.

    Returns:
        str: JSON string with 'entries' array and 'summary' object.
    """
    output = {"entries": entries, "summary": summary}
    return json.dumps(output, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for aggregate.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 always — read-only, no validation failures).
    """
    parser = argparse.ArgumentParser(
        description="Query and aggregate feedback.jsonl entries.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ticket", default=None, help="Filter by ticket path.")
    parser.add_argument("--category", default=None, help="Filter by category id.")
    parser.add_argument("--phase", default=None, help="Filter by phase (agent name).")
    parser.add_argument("--since", default=None, metavar="YYYY-MM-DD", help="Include entries on or after date.")
    parser.add_argument("--until", default=None, metavar="YYYY-MM-DD", help="Include entries on or before date.")
    parser.add_argument(
        "--source",
        choices=("agent", "hook"),
        default=None,
        help="Filter by source ('agent' or 'hook'). Absent = all sources.",
    )
    parser.add_argument("--hook-name", default=None, help="Filter by hook name (hook source only).")
    parser.add_argument(
        "--jsonl",
        default=None,
        help=f"Override JSONL input path. Default: {_JSONL_DEFAULT}",
    )
    parser.add_argument(
        "--format",
        choices=("json", "table"),
        default="table",
        help="Output format (default: table).",
    )

    args = parser.parse_args(argv)

    jsonl_path = Path(args.jsonl) if args.jsonl else _JSONL_DEFAULT
    all_entries = _read_jsonl(jsonl_path)

    filtered = filter_entries(
        all_entries,
        ticket=args.ticket,
        category=args.category,
        phase=args.phase,
        since=args.since,
        until=args.until,
        source=args.source,
        hook_name=args.hook_name,
    )

    summary = _build_summary(filtered)

    if args.format == "json":
        print(_format_json(filtered, summary))
    else:
        print(_format_table(filtered, summary))

    return 0


if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-18 12:45 [EPIC-AgentSystemFrictionReduction/04]: Convert _JSONL_DEFAULT to __file__-relative path. (#EPIC-AgentSystemFrictionReduction/04)
#   CWD-relative Path("debugging/logs/feedback.jsonl") resolves incorrectly when
#   invoked from a worktree. Fix: Path(__file__).resolve().parents[3] / "debugging" / "logs" / "feedback.jsonl".
# - 2026-05-15 10:50 [EPIC-FeedbackCollection/ticket-03]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Pure read-only query script over feedback.jsonl. filter_entries() is the
#   public API used by retrospective-agent (ticket 06). Includes --source and
#   --hook-name filters (ticket 09 design) from the start so ticket 09 only
#   needs to extend aggregate.py minimally. by_hook_name appears in summary
#   only when hook entries are present in the filtered set.
# ====================================================================
