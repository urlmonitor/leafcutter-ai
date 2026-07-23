"""
MODULE: leafcutter/scripts/agent-health/generate_health_report.py
GOAL: Join agent_telemetry.jsonl (invocation volume + success rates) with
      feedback.jsonl (subagent-quality failure-mode classifications) to produce
      a per-agent quality table: invocations, success rate, top-3 failure
      archetypes by tag.
BUSINESS CONTEXT: Provides a single command to answer "how is <agent> doing?"
      in terms of both volume and failure-mode distribution. Used by the
      retrospective-agent to populate the Subagent Quality Trends section and
      by operators performing ad-hoc quality investigations.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - .claude/skills/agent-health/SKILL.md
  - docs/how-to/feedback-collection.md

Usage:
    python generate_health_report.py [--telemetry PATH] [--feedback PATH]
        [--agent AGENT_ID] [--format markdown|json]

    Defaults:
        --telemetry  debugging/logs/agent_telemetry.jsonl
        --feedback   debugging/logs/feedback.jsonl
        --format     markdown

Exit codes:
    0: success (table printed to stdout)
    1: unrecoverable error (e.g. malformed JSONL, filesystem error)
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DEFAULT_TELEMETRY = Path("debugging") / "logs" / "agent_telemetry.jsonl"
_DEFAULT_FEEDBACK = Path("debugging") / "logs" / "feedback.jsonl"

# Archetype tags that appear in subagent-quality entries (canonical set)
ARCHETYPE_TAGS = {"mechanical-retry", "cross-agent-rework", "brainstorm-escalation", "halt"}

# Prefix used by ticket-supervisor to tag the failing agent
_AGENT_TAG_PREFIX = "agent-"


# ---------------------------------------------------------------------------
# JSONL loading helpers
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict]:
    """Load all JSON lines from a JSONL file, skipping malformed lines.

    Args:
        path: Path to the JSONL file.

    Returns:
        list[dict]: Parsed entries; empty list when the file is absent or empty.
    """
    if not path.exists():
        return []
    entries: list[dict] = []
    try:
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    print(
                        f"WARNING: Skipping malformed JSON on line {lineno} of {path}: {exc}",
                        file=sys.stderr,
                    )
    except OSError as exc:
        print(
            f"WARNING: Could not read {path}: {exc}",
            file=sys.stderr,
        )
        return []
    return entries


# ---------------------------------------------------------------------------
# Data extraction helpers
# ---------------------------------------------------------------------------


def _build_telemetry_table(entries: list[dict]) -> dict[str, dict]:
    """Build per-agent invocation and success counts from telemetry entries.

    Args:
        entries: Parsed JSONL entries from agent_telemetry.jsonl.

    Returns:
        dict: Keyed by agent id; values have 'invocations' and 'successes'.
    """
    table: dict[str, dict] = {}
    for entry in entries:
        agent = entry.get("agent") or entry.get("phase")
        if not agent:
            continue
        if agent not in table:
            table[agent] = {"invocations": 0, "successes": 0}
        table[agent]["invocations"] += 1
        # Success: status field is 'ok', 'success', 'signed_off', or absent (assume success)
        status = entry.get("status", "ok")
        if status in {"ok", "success", "signed_off", "complete"}:
            table[agent]["successes"] += 1
    return table


def _build_archetype_table(
    entries: list[dict],
) -> dict[str, Counter]:
    """Build per-agent archetype counts from subagent-quality feedback entries.

    Args:
        entries: Parsed JSONL entries from feedback.jsonl.

    Returns:
        dict: Keyed by agent id (extracted from 'agent-<id>' tag);
              values are Counter objects mapping archetype tag to count.
    """
    table: dict[str, Counter] = defaultdict(Counter)
    for entry in entries:
        if entry.get("category") != "subagent-quality":
            continue
        tags: list[str] = entry.get("tags", [])
        # Find the agent tag
        failing_agent = None
        for tag in tags:
            if tag.startswith(_AGENT_TAG_PREFIX):
                failing_agent = tag[len(_AGENT_TAG_PREFIX):]
                break
        if not failing_agent:
            continue
        # Count archetype tags
        for tag in tags:
            if tag in ARCHETYPE_TAGS:
                table[failing_agent][tag] += 1
    return dict(table)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _success_rate(tele: dict | None) -> str:
    """Format success rate as a percentage string.

    Args:
        tele: Telemetry dict with 'invocations' and 'successes', or None.

    Returns:
        str: Formatted percentage (e.g. '88%') or 'N/A'.
    """
    if not tele or tele["invocations"] == 0:
        return "N/A"
    rate = tele["successes"] / tele["invocations"]
    return f"{round(rate * 100)}%"


def _top_failures(archetype_counter: Counter | None, n: int = 3) -> list[str]:
    """Return the top N failure archetype strings.

    Args:
        archetype_counter: Counter of archetype tags, or None.
        n: Number of top entries to return.

    Returns:
        list[str]: Strings like 'mechanical-retry (4)'; padded with 'N/A' to length n.
    """
    if not archetype_counter:
        return ["N/A"] * n
    top = archetype_counter.most_common(n)
    result = [f"{tag} ({count})" for tag, count in top]
    while len(result) < n:
        result.append("N/A")
    return result


def _render_markdown(rows: list[dict[str, Any]]) -> str:
    """Render the per-agent quality table as a Markdown string.

    Args:
        rows: List of row dicts with keys: agent, invocations, success_rate,
              top_failure_archetypes.

    Returns:
        str: Markdown table.
    """
    if not rows:
        return "No data available — both agent_telemetry.jsonl and feedback.jsonl are absent or empty."

    lines = [
        "| Agent | Invocations | Success Rate | Top Failure 1 | Top Failure 2 | Top Failure 3 |",
        "|---|---|---|---|---|---|",
    ]
    for row in rows:
        tele = row.get("telemetry")
        inv = str(tele["invocations"]) if tele else "N/A"
        sr = _success_rate(tele)
        tops = _top_failures(row.get("archetypes"))
        lines.append(
            f"| {row['agent']} | {inv} | {sr} | {tops[0]} | {tops[1]} | {tops[2]} |"
        )
    return "\n".join(lines)


def _render_json(rows: list[dict[str, Any]]) -> str:
    """Render the per-agent quality table as a JSON string.

    Args:
        rows: List of row dicts (same shape as _render_markdown input).

    Returns:
        str: Pretty-printed JSON.
    """
    output = []
    for row in rows:
        tele = row.get("telemetry")
        archetypes = row.get("archetypes") or Counter()
        entry: dict = {
            "agent": row["agent"],
            "invocations": tele["invocations"] if tele else None,
            "success_rate": (
                round(tele["successes"] / tele["invocations"], 4)
                if tele and tele["invocations"] > 0
                else None
            ),
            "top_failure_archetypes": [
                {"tag": tag, "count": count}
                for tag, count in archetypes.most_common(3)
            ],
        }
        output.append(entry)
    return json.dumps(output, indent=2)


# ---------------------------------------------------------------------------
# Lane comparison report (BO-2400d-3)
# ---------------------------------------------------------------------------


def build_lane_comparison_report(sink_path: Path) -> dict:
    """Read telemetry JSONL records and return per-lane aggregates side by side.

    Groups records by their "lane" field and computes for each lane:
    count, total_duration_ms, avg_duration_ms, total_tokens_in,
    total_tokens_out, total_cache_read_tokens, avg_total_tokens (mean of the
    per-invocation token sum: tokens_in + tokens_out + cache_read_tokens).

    A lane with no records is absent from the result (not an empty sub-dict),
    letting callers detect the single-lane case and report it gracefully.
    An absent or empty sink file returns an empty dict without raising.

    Args:
        sink_path: Path to the JSONL file produced by emit_agent_telemetry.

    Returns:
        dict: Keys are lane strings present in the data (e.g. "fast", "heavy");
            values are aggregate sub-dicts with the keys described above.
            Returns {} when the sink is absent or contains no valid records.
    """
    records = _load_jsonl(sink_path)
    if not records:
        return {}

    lanes: dict[str, list[dict]] = {}
    for rec in records:
        lane = rec.get("lane")
        if lane:
            lanes.setdefault(lane, []).append(rec)

    result: dict = {}
    for lane, recs in lanes.items():
        count = len(recs)
        total_dur = sum(r.get("duration_ms", 0) for r in recs)
        total_in = sum(r.get("tokens_in", 0) for r in recs)
        total_out = sum(r.get("tokens_out", 0) for r in recs)
        total_cache = sum(r.get("cache_read_tokens", 0) for r in recs)
        per_rec_totals = [
            r.get("tokens_in", 0) + r.get("tokens_out", 0) + r.get("cache_read_tokens", 0)
            for r in recs
        ]
        result[lane] = {
            "count": count,
            "total_duration_ms": total_dur,
            "avg_duration_ms": total_dur / count,
            "total_tokens_in": total_in,
            "total_tokens_out": total_out,
            "total_cache_read_tokens": total_cache,
            "avg_total_tokens": sum(per_rec_totals) / count,
        }

    return result


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Join agent_telemetry.jsonl and feedback.jsonl to produce a "
            "per-agent quality table (invocations, success rate, top failure archetypes)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--telemetry",
        default=None,
        help=f"Path to agent_telemetry.jsonl. Default: {_DEFAULT_TELEMETRY}",
    )
    parser.add_argument(
        "--feedback",
        default=None,
        help=f"Path to feedback.jsonl. Default: {_DEFAULT_FEEDBACK}",
    )
    parser.add_argument(
        "--agent",
        default=None,
        help="Filter output to a single agent id (e.g. python-coder).",
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format: 'markdown' (default) or 'json'.",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for generate_health_report.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 on success, 1 on unrecoverable error).
    """
    args = _build_parser().parse_args(argv)

    telemetry_path = Path(args.telemetry) if args.telemetry else _DEFAULT_TELEMETRY
    feedback_path = Path(args.feedback) if args.feedback else _DEFAULT_FEEDBACK

    tele_entries = _load_jsonl(telemetry_path)
    fb_entries = _load_jsonl(feedback_path)

    tele_table = _build_telemetry_table(tele_entries)
    archetype_table = _build_archetype_table(fb_entries)

    # Union of all known agent ids
    all_agents = sorted(set(tele_table.keys()) | set(archetype_table.keys()))

    # Apply --agent filter
    if args.agent:
        all_agents = [a for a in all_agents if a == args.agent]
        if not all_agents:
            print(
                f"No data found for agent '{args.agent}'. "
                "Check that the agent id matches entries in telemetry or feedback files.",
                file=sys.stderr,
            )
            return 0

    rows = [
        {
            "agent": agent,
            "telemetry": tele_table.get(agent),
            "archetypes": archetype_table.get(agent),
        }
        for agent in all_agents
    ]

    if args.format == "json":
        print(_render_json(rows))
    else:
        print(_render_markdown(rows))

    return 0


if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-15 10:30 [EPIC-SupervisorFeedback/05_agent_health_skill]: Initial creation. (#EPIC-LeafcutterMVP/01)
#   Joins agent_telemetry.jsonl (volume/success) with feedback.jsonl (subagent-quality
#   failure archetypes) into a per-agent quality table. Uses agent-<id> tag convention
#   from ticket-supervisor CFCS emits to identify the failing agent in feedback entries.
#   Fallback: either JSONL absent -> N/A for that dimension. Both absent -> empty message.
# ====================================================================
