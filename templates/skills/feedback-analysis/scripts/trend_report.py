"""
MODULE: templates/skills/feedback-analysis/scripts/trend_report.py
GOAL: Orchestrate aggregate.py and list_tags.py to produce a prioritized,
      cross-category feedback analysis report with optional trend indicators.
BUSINESS CONTEXT: Enables operators to invoke /feedback-report and receive a
      prioritized, actionable summary of accumulated agent feedback data,
      without requiring a completed epic (contrast with retrospective-agent).
ARCHITECTURE: Read-only script. Imports aggregate.filter_entries and
      aggregate._build_summary when available; falls back to subprocess.
      Imports list_tags.count_tags directly. Never writes to feedback.jsonl
      or any other data file.
DOC_LINKS:
  - templates/skills/feedback-analysis/SKILL.md
  - docs/how-to/feedback-collection.md

Usage:
    python trend_report.py
      [--jsonl <path>]          override feedback.jsonl path
      [--since <YYYY-MM-DD>]    pass-through to aggregate.py
      [--until <YYYY-MM-DD>]    pass-through to aggregate.py
      [--category <id>]         limit report to one category
      [--trend week|month|none] emit trend indicators; default: none
      [--format text|json]      output format; default: text
      [--top-tags N]            top-N tags per category in text report; default: 5
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Closed vocabulary of feedback categories with severity weights.
# Must stay in sync with config/feedback_categories.yaml.
_CATEGORIES: list[dict[str, Any]] = [
    {"id": "complete", "default_severity": "low"},
    {"id": "knowledge-gap", "default_severity": "medium"},
    {"id": "quality-concern", "default_severity": "high"},
    {"id": "tooling-issue", "default_severity": "medium"},
    {"id": "convention-ambiguity", "default_severity": "medium"},
    {"id": "blocker", "default_severity": "high"},
    {"id": "subagent-quality", "default_severity": "medium"},
    {"id": "success-pattern", "default_severity": "low"},
    {"id": "process-finding", "default_severity": "low"},
]

_ACTIONABLE_CATEGORIES = {
    "knowledge-gap",
    "convention-ambiguity",
    "tooling-issue",
    "quality-concern",
    "blocker",
    "subagent-quality",
}

_SEVERITY_WEIGHT = {"high": 3, "medium": 2, "low": 1}

_CATEGORY_SEVERITY: dict[str, str] = {c["id"]: c["default_severity"] for c in _CATEGORIES}

_ACTIONABLE_RECOMMENDATIONS: dict[str, str] = {
    "knowledge-gap": "Open doc tickets for these topics",
    "convention-ambiguity": "Clarify the ambiguous rules in the relevant SKILL.md or CLAUDE.md",
    "tooling-issue": "Fix the identified hook or script failures",
    "quality-concern": "Flag quality regressions for pr-reviewer follow-up",
    "blocker": "Surface recurring external dependencies to the project owner",
    "subagent-quality": "Review the agent trust ladder for the flagged phase agents",
}


# ---------------------------------------------------------------------------
# JSONL path resolution
# ---------------------------------------------------------------------------


def _find_default_jsonl() -> Path:
    """Walk up from this file to find debugging/logs/feedback.jsonl.

    Returns:
        Path: Resolved path to feedback.jsonl (may not exist).
    """
    current = Path(__file__).resolve().parent
    for _ in range(8):
        candidate = current / "debugging" / "logs" / "feedback.jsonl"
        if candidate.exists():
            return candidate
        # Also check for .claude/ marker (project root)
        if (current / ".claude").is_dir():
            return current / "debugging" / "logs" / "feedback.jsonl"
        current = current.parent
    # Fallback: relative to CWD
    return Path("debugging") / "logs" / "feedback.jsonl"


# ---------------------------------------------------------------------------
# Direct import with subprocess fallback
# ---------------------------------------------------------------------------


def _import_aggregate():
    """Try to import aggregate.filter_entries and aggregate._build_summary.

    Returns:
        module or None: The aggregate module, or None when import fails.
    """
    try:
        # Try the known relative path from this script's location
        scripts_feedback = Path(__file__).resolve().parents[4] / "scripts" / "feedback"
        if scripts_feedback.exists() and str(scripts_feedback) not in sys.path:
            sys.path.insert(0, str(scripts_feedback))
        import aggregate as _agg  # type: ignore[import]
    except ImportError:
        return None
    else:
        return _agg


def _import_list_tags():
    """Try to import list_tags.count_tags.

    Returns:
        module or None: The list_tags module, or None when import fails.
    """
    try:
        scripts_feedback = Path(__file__).resolve().parents[4] / "scripts" / "feedback"
        if scripts_feedback.exists() and str(scripts_feedback) not in sys.path:
            sys.path.insert(0, str(scripts_feedback))
        import list_tags as _lt  # type: ignore[import]
    except ImportError:
        return None
    else:
        return _lt


# ---------------------------------------------------------------------------
# JSONL reading (fallback when aggregate import is unavailable)
# ---------------------------------------------------------------------------


def _read_jsonl_fallback(jsonl_path: Path) -> list[dict]:
    """Read JSONL entries when aggregate module is unavailable.

    Args:
        jsonl_path: Path to feedback.jsonl.

    Returns:
        list[dict]: Parsed entries, skipping malformed lines.
    """
    if not jsonl_path.exists():
        return []
    entries: list[dict] = []
    try:
        with open(jsonl_path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    except OSError as exc:
        print(f"Warning: could not read {jsonl_path}: {exc}", file=sys.stderr)
    return entries


# ---------------------------------------------------------------------------
# Entry filtering (for trend windows)
# ---------------------------------------------------------------------------


def _entry_timestamp(entry: dict) -> datetime | None:
    """Extract a timezone-aware datetime from an entry's 'timestamp' field.

    Args:
        entry: Feedback JSONL entry dict.

    Returns:
        datetime | None: Parsed datetime, or None when absent or malformed.
    """
    ts = entry.get("timestamp")
    if not ts:
        return None
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _filter_by_date_range(
    entries: list[dict],
    since: str | None,
    until: str | None,
) -> list[dict]:
    """Filter entries to those within [since, until] (inclusive).

    Args:
        entries: All parsed feedback entries.
        since: YYYY-MM-DD lower bound (inclusive), or None for no lower bound.
        until: YYYY-MM-DD upper bound (inclusive), or None for no upper bound.

    Returns:
        list[dict]: Filtered entries.
    """
    since_dt: datetime | None = None
    until_dt: datetime | None = None

    if since:
        try:
            since_dt = datetime.strptime(since, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    if until:
        try:
            # until is inclusive at end-of-day
            until_dt = datetime.strptime(until, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            pass

    result: list[dict] = []
    for entry in entries:
        entry_dt = _entry_timestamp(entry)
        if entry_dt is None:
            # Include entries without timestamps when no date filter is active
            if since_dt is None and until_dt is None:
                result.append(entry)
            continue
        if since_dt is not None and entry_dt < since_dt:
            continue
        if until_dt is not None and entry_dt > until_dt:
            continue
        result.append(entry)
    return result


def _filter_by_date_window(entries: list[dict], window_start: date, window_end: date) -> list[dict]:
    """Filter entries to a specific calendar date window (inclusive).

    Args:
        entries: All parsed feedback entries.
        window_start: First date (inclusive) of the window.
        window_end: Last date (inclusive) of the window.

    Returns:
        list[dict]: Entries whose timestamp falls within [window_start, window_end].
    """
    start_dt = datetime.combine(window_start, datetime.min.time()).replace(tzinfo=timezone.utc)
    end_dt = datetime.combine(window_end, datetime.max.time()).replace(tzinfo=timezone.utc)

    result: list[dict] = []
    for entry in entries:
        entry_dt = _entry_timestamp(entry)
        if entry_dt is None:
            continue
        if start_dt <= entry_dt <= end_dt:
            result.append(entry)
    return result


# ---------------------------------------------------------------------------
# Load all entries
# ---------------------------------------------------------------------------


def _load_entries(
    jsonl_path: Path,
    since: str | None,
    until: str | None,
    category: str | None,
) -> list[dict]:
    """Load feedback entries from JSONL, optionally filtered.

    Prefers direct import of aggregate.filter_entries for consistency;
    falls back to local JSONL reading when the module is unavailable.

    Args:
        jsonl_path: Path to feedback.jsonl.
        since: YYYY-MM-DD lower bound.
        until: YYYY-MM-DD upper bound.
        category: Restrict to this category, or None for all.

    Returns:
        list[dict]: Filtered entries.
    """
    agg = _import_aggregate()
    if agg is not None:
        try:
            all_entries = agg._read_jsonl(jsonl_path)
            return agg.filter_entries(
                all_entries,
                category=category,
                since=since,
                until=until,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: aggregate import failed ({exc}), falling back to local read.", file=sys.stderr)

    # Fallback
    all_entries = _read_jsonl_fallback(jsonl_path)
    filtered = _filter_by_date_range(all_entries, since, until)
    if category:
        filtered = [e for e in filtered if e.get("category") == category]
    return filtered


# ---------------------------------------------------------------------------
# Per-category analysis
# ---------------------------------------------------------------------------


def _build_category_counts(entries: list[dict]) -> dict[str, int]:
    """Count entries per category, sorted descending by count.

    Args:
        entries: Filtered feedback entries.

    Returns:
        dict[str, int]: Category -> count, sorted descending by value.
    """
    counts: dict[str, int] = {}
    for entry in entries:
        cat = entry.get("category", "unknown")
        counts[cat] = counts.get(cat, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))


def _get_top_tags(entries: list[dict], category: str, top_n: int) -> list[tuple[str, int]]:
    """Get the top-N most frequent tags for a given category.

    Args:
        entries: All filtered entries.
        category: Category to filter by.
        top_n: Number of top tags to return.

    Returns:
        list[tuple[str, int]]: (tag, count) pairs sorted by count descending.
    """
    lt = _import_list_tags()
    if lt is not None:
        try:
            cat_entries = [e for e in entries if e.get("category") == category]
            counter = lt.count_tags(cat_entries, category=None)
            return counter.most_common(top_n)
        except Exception as exc:  # noqa: BLE001
            print(f"Warning: list_tags import failed ({exc}), using fallback.", file=sys.stderr)

    # Fallback
    counter: Counter = Counter()
    for entry in entries:
        if entry.get("category") != category:
            continue
        for tag in entry.get("tags", []):
            counter[tag] += 1
    return counter.most_common(top_n)


def _get_recent_notes(entries: list[dict], category: str, n: int = 3) -> list[str]:
    """Get the N most recent entry notes for a category, truncated to 120 chars.

    Args:
        entries: All filtered entries.
        category: Category to filter by.
        n: Number of recent notes to return.

    Returns:
        list[str]: Recent note strings.
    """
    cat_entries = [e for e in entries if e.get("category") == category]
    # Sort by timestamp descending; entries without timestamp go to the end
    def _ts_key(e: dict) -> datetime:
        dt = _entry_timestamp(e)
        return dt if dt is not None else datetime.min.replace(tzinfo=timezone.utc)

    cat_entries.sort(key=_ts_key, reverse=True)
    notes = []
    for e in cat_entries[:n]:
        note = str(e.get("note", "")).strip()
        if note:
            notes.append(note[:120])
    return notes


# ---------------------------------------------------------------------------
# Trend computation
# ---------------------------------------------------------------------------


def _compute_trend(
    all_entries: list[dict],
    category: str,
    mode: str,
) -> str:
    """Compute rising/stable/falling trend indicator for a category.

    Compares entry count in the current window vs the previous window.
    >20% increase = rising; >20% decrease = falling; otherwise stable.

    Args:
        all_entries: ALL entries from JSONL (no date pre-filter applied here).
        category: Category ID to compute trend for.
        mode: "week" or "month".

    Returns:
        str: "rising", "falling", or "stable".
    """
    today = date.today()

    if mode == "week":
        current_start = today - timedelta(days=6)
        current_end = today
        prev_start = today - timedelta(days=13)
        prev_end = today - timedelta(days=7)
    elif mode == "month":
        current_start = today - timedelta(days=29)
        current_end = today
        prev_start = today - timedelta(days=59)
        prev_end = today - timedelta(days=30)
    else:
        return "stable"

    current_entries = _filter_by_date_window(all_entries, current_start, current_end)
    prev_entries = _filter_by_date_window(all_entries, prev_start, prev_end)

    current_count = sum(1 for e in current_entries if e.get("category") == category)
    prev_count = sum(1 for e in prev_entries if e.get("category") == category)

    if prev_count == 0:
        # No previous data: if there's current data, it's "rising"
        return "rising" if current_count > 0 else "stable"

    change_ratio = (current_count - prev_count) / prev_count
    if change_ratio > 0.20:
        return "rising"
    if change_ratio < -0.20:
        return "falling"
    return "stable"


# ---------------------------------------------------------------------------
# Priority score and action items
# ---------------------------------------------------------------------------


def _compute_priority_score(category: str, count: int) -> float:
    """Compute combined priority score = count * severity_weight.

    Args:
        category: Category ID.
        count: Entry count for the category.

    Returns:
        float: Priority score (higher = more urgent).
    """
    severity = _CATEGORY_SEVERITY.get(category, "low")
    weight = _SEVERITY_WEIGHT.get(severity, 1)
    return count * weight


def _build_action_items(
    category_counts: dict[str, int],
    entries: list[dict],
    top_n: int,
    top_tags_n: int,
) -> list[dict[str, Any]]:
    """Build prioritized action items list (top-N by priority score).

    Args:
        category_counts: Category -> count mapping.
        entries: All filtered entries.
        top_n: Number of top action items to include.
        top_tags_n: Number of tags to include per item.

    Returns:
        list[dict]: Sorted list of action item dicts with category, count, score,
                    recommendation, and top_tags.
    """
    items = []
    for cat, count in category_counts.items():
        if cat not in _ACTIONABLE_CATEGORIES:
            continue
        score = _compute_priority_score(cat, count)
        top_tags = _get_top_tags(entries, cat, top_tags_n)
        recommendation = _ACTIONABLE_RECOMMENDATIONS.get(cat, f"Review {cat} entries")
        if top_tags:
            tag_str = ", ".join(t for t, _ in top_tags[:3])
            recommendation = f"{recommendation}: {tag_str}"
        items.append(
            {
                "category": cat,
                "count": count,
                "score": score,
                "recommendation": recommendation,
                "top_tags": [{"tag": t, "count": c} for t, c in top_tags],
            }
        )

    items.sort(key=lambda x: -x["score"])
    return items[:top_n]


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def _format_text_report(
    entries: list[dict],
    category_counts: dict[str, int],
    action_items: list[dict[str, Any]],
    trends: dict[str, str] | None,
    top_tags_n: int,
) -> str:
    """Format the analysis as a human-readable Markdown-flavoured text report.

    Args:
        entries: All filtered entries.
        category_counts: Category -> count sorted by count descending.
        action_items: Pre-built action items list.
        trends: Category -> trend indicator dict, or None when no trend was computed.
        top_tags_n: Number of tags to show per category.

    Returns:
        str: Formatted text report.
    """
    lines = ["# Feedback Analysis Report", ""]

    # Summary
    total = sum(category_counts.values())
    lines += [f"**Total entries:** {total}", ""]

    # Category Breakdown
    lines += ["## Category Breakdown", ""]
    lines += ["| Category | Count | Severity | Trend |"]
    lines += ["|---|---|---|---|"]
    for cat, count in category_counts.items():
        severity = _CATEGORY_SEVERITY.get(cat, "?")
        trend_col = trends.get(cat, "-") if trends else "-"
        lines.append(f"| {cat} | {count} | {severity} | {trend_col} |")
    lines.append("")

    # Actionable sections
    for cat, count in category_counts.items():
        if cat not in _ACTIONABLE_CATEGORIES:
            continue
        lines += [f"## {cat} ({count} entries)", ""]
        top_tags = _get_top_tags(entries, cat, top_tags_n)
        if top_tags:
            lines.append(f"Top tags: {', '.join(t for t, _ in top_tags)}")
        recent = _get_recent_notes(entries, cat, n=3)
        if recent:
            lines.append("Recent notes:")
            for note in recent:
                lines.append(f"  - {note}")
        lines.append("")

    # Prioritized Action Items
    lines += ["## Prioritized Action Items", ""]
    if not action_items:
        lines.append("*(no actionable findings in the filtered date range)*")
    else:
        for i, item in enumerate(action_items, 1):
            lines.append(f"{i}. **{item['category']}** (count={item['count']}, score={item['score']:.0f}): {item['recommendation']}")
    lines.append("")

    return "\n".join(lines)


def _format_json_report(
    entries: list[dict],
    category_counts: dict[str, int],
    action_items: list[dict[str, Any]],
    trends: dict[str, str] | None,
) -> str:
    """Format the analysis as a JSON object.

    Args:
        entries: All filtered entries (used for total count).
        category_counts: Category -> count dict.
        action_items: Pre-built action items list.
        trends: Category -> trend indicator dict, or None.

    Returns:
        str: JSON-serialized analysis object.
    """
    total = sum(category_counts.values())
    output: dict[str, Any] = {
        "summary": {
            "total_entries": total,
            "categories_found": len(category_counts),
            "actionable_categories": sum(
                1 for c in category_counts if c in _ACTIONABLE_CATEGORIES
            ),
        },
        "by_category": category_counts,
        "action_items": action_items,
    }
    if trends is not None:
        output["trends"] = trends
    return json.dumps(output, indent=2)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for trend_report.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 on success; non-zero on unrecoverable error).
    """
    parser = argparse.ArgumentParser(
        description="Generate a prioritized feedback analysis report.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--jsonl", default=None, help="Override feedback.jsonl path.")
    parser.add_argument("--since", default=None, metavar="YYYY-MM-DD", help="Include entries from this date.")
    parser.add_argument("--until", default=None, metavar="YYYY-MM-DD", help="Include entries up to this date.")
    parser.add_argument("--category", default=None, help="Limit report to one category.")
    parser.add_argument(
        "--trend",
        default="none",
        choices=["week", "month", "none"],
        help="Emit trend indicators (default: none).",
    )
    parser.add_argument(
        "--format",
        default="text",
        choices=["text", "json"],
        dest="output_format",
        help="Output format (default: text).",
    )
    parser.add_argument(
        "--top-tags",
        type=int,
        default=5,
        metavar="N",
        help="Top-N tags per category in text report (default: 5).",
    )

    args = parser.parse_args(argv)

    jsonl_path = Path(args.jsonl) if args.jsonl else _find_default_jsonl()

    # Load entries (possibly empty)
    try:
        entries = _load_entries(jsonl_path, args.since, args.until, args.category)
    except OSError as exc:
        print(f"Error reading {jsonl_path}: {exc}", file=sys.stderr)
        return 1

    if not entries:
        print("(no feedback data found)")
        return 0

    # Build category counts
    category_counts = _build_category_counts(entries)

    # Compute trends if requested
    trends: dict[str, str] | None = None
    if args.trend != "none":
        # Load ALL entries for trend computation (ignore since/until filters)
        try:
            all_entries_for_trend = _load_entries(jsonl_path, None, None, args.category)
        except OSError as exc:
            print(f"Warning: could not load all entries for trend: {exc}", file=sys.stderr)
            all_entries_for_trend = entries
        trends = {}
        for cat in category_counts:
            trends[cat] = _compute_trend(all_entries_for_trend, cat, args.trend)

    # Build action items
    action_items = _build_action_items(
        category_counts,
        entries,
        top_n=5,
        top_tags_n=args.top_tags,
    )

    # Render output
    if args.output_format == "json":
        print(_format_json_report(entries, category_counts, action_items, trends))
    else:
        print(_format_text_report(entries, category_counts, action_items, trends, args.top_tags))

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-03 14:00 [TICKET-20260603-FeedbackAnalysisPipeline/python-coder]:
#   Initial implementation of trend_report.py.
#   Imports aggregate.filter_entries and list_tags.count_tags directly;
#   falls back to local JSONL reading via subprocess on import failure.
#   Trend computation uses raw date windows (current 7-day vs previous 7-day);
#   >20% change threshold matches the acceptance criteria specification.
#   No external deps beyond stdlib. Follow project error-handling policy (Rules 1-4).
# ====================================================================
