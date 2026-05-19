"""
MODULE: leafcutter/scripts/retrospective/extract_epic_facts.py
GOAL: Deterministic extractor that reads an epic folder (ticket files, git log,
      and optional telemetry JSONL) and produces a structured JSON blob for the
      retrospective-agent synthesis step.
BUSINESS CONTEXT: retrospective-agent previously parsed ## Comments sections
      inline to count retries, blockers, and phase outcomes. This script offloads
      all counting to deterministic Python so the agent does synthesis only. The
      output is stable across runs (same inputs → same output) and testable
      without an LLM.
ARCHITECTURE: Three data sources: (1) ticket .md files under the epic folder
      — YAML frontmatter parsed for agents: map, ## Comments heading lines parsed
      for status tags; (2) git log subprocess (git log --oneline -- <path>) for
      commit count and date range; (3) optional agent_telemetry.jsonl filtered
      by epic_path prefix. JSON emitted to stdout.
DOC_LINKS:
  - docs/how-to/feedback-collection.md

Output schema:
    {
      "epic_name": "EPIC-FeedbackCollection",
      "epic_path": "tickets/00_inbox/epics/EPIC-FeedbackCollection",
      "extracted_at": "2026-05-15T14:32:00Z",
      "ticket_count": 9,
      "completed_ticket_count": 5,
      "phase_agent_counts": {
        "python-coder": {"signed_off": 3, "failed": 0, "needed": 0, "not_needed": 2}
      },
      "git_commit_count": 12,
      "git_first_commit_date": "2026-05-14",
      "git_last_commit_date": "2026-05-28",
      "blocker_comment_count": 2,
      "handoff_comment_count": 1,
      "telemetry_events": {"knowledge_captured": 4}
    }

Usage:
    extract_epic_facts.py <epic_folder_path> [--telemetry <path>] [--format json]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches:  ### YYYY-MM-DD HH:MM — agent-name (status: ok|blocker|question|handoff)
_COMMENT_HEADING_RE = re.compile(
    r"^### \d{4}-\d{2}-\d{2} \d{2}:\d{2} — [^(]+ \(status: (?P<status>\w+)\)"
)

_VALID_AGENT_STATUSES = frozenset({"signed_off", "failed", "needed", "not_needed"})


# ---------------------------------------------------------------------------
# Ticket parsing
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> dict | None:
    """Extract and parse the YAML frontmatter block from ticket content.

    Args:
        content: Full text content of a markdown ticket file.

    Returns:
        Parsed frontmatter dict, or None if absent or unparseable.
    """
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    raw = content[3:end].strip()
    try:
        import yaml  # type: ignore[import]
        parsed = yaml.safe_load(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _extract_agent_status(raw_value: object) -> str | None:
    """Extract the effective status string from a frontmatter agent entry.

    Accepts both scalar (``signed_off``) and nested-map
    (``{status: signed_off, grandfathered: true}``) forms.

    Args:
        raw_value: Raw value from the agents: YAML map.

    Returns:
        Status string or None when unrecognised.
    """
    if isinstance(raw_value, str):
        return raw_value
    if isinstance(raw_value, dict):
        status = raw_value.get("status")
        if isinstance(status, str):
            return status
    return None


def _count_comment_statuses(content: str) -> dict[str, int]:
    """Count blocker and handoff comment headings in a ticket's ## Comments section.

    Args:
        content: Full text content of a ticket markdown file.

    Returns:
        Dict with keys ``blocker`` and ``handoff``, each mapping to a count.
    """
    counts = {"blocker": 0, "handoff": 0}
    in_comments = False
    for line in content.splitlines():
        if re.match(r"^## Comments\s*$", line):
            in_comments = True
            continue
        if in_comments and re.match(r"^##\s+", line):
            break
        if in_comments:
            m = _COMMENT_HEADING_RE.match(line.strip())
            if m:
                status = m.group("status")
                if status == "blocker":
                    counts["blocker"] += 1
                elif status == "handoff":
                    counts["handoff"] += 1
    return counts


def _read_tickets(epic_path: Path) -> tuple[int, int, dict, int, int]:
    """Read all ticket files and extract phase agent counts and comment stats.

    Args:
        epic_path: Absolute path to the epic folder.

    Returns:
        Tuple of (ticket_count, completed_ticket_count, phase_agent_counts,
        blocker_comment_count, handoff_comment_count).
    """
    phase_agents: dict[str, dict[str, int]] = {}
    ticket_count = 0
    completed_count = 0
    total_blockers = 0
    total_handoffs = 0

    ticket_files = _collect_ticket_files(epic_path)
    for path in ticket_files:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        fm = _parse_frontmatter(content)
        if fm is None:
            continue

        ticket_count += 1
        if fm.get("status") == "done":
            completed_count += 1

        agents = fm.get("agents")
        if isinstance(agents, dict):
            _accumulate_agents(agents, phase_agents)

        comment_counts = _count_comment_statuses(content)
        total_blockers += comment_counts["blocker"]
        total_handoffs += comment_counts["handoff"]

    return ticket_count, completed_count, phase_agents, total_blockers, total_handoffs


def _collect_ticket_files(epic_path: Path) -> list[Path]:
    """Collect all ticket markdown files under an epic folder.

    Excludes Master_Plan.md and non-markdown files.

    Args:
        epic_path: Path to the epic folder.

    Returns:
        Sorted list of ticket .md file Paths.
    """
    files: list[Path] = []
    for candidate in epic_path.rglob("*.md"):
        if candidate.name == "Master_Plan.md":
            continue
        if candidate.name == "README.md":
            continue
        files.append(candidate)
    return sorted(files)


def _accumulate_agents(agents: dict, phase_agents: dict[str, dict[str, int]]) -> None:
    """Accumulate agent status counts from one ticket into the running totals.

    Args:
        agents: The agents: map from one ticket's frontmatter.
        phase_agents: Running tally dict to update in-place.
    """
    for agent_name, raw_value in agents.items():
        status = _extract_agent_status(raw_value)
        if status not in _VALID_AGENT_STATUSES:
            continue
        if agent_name not in phase_agents:
            phase_agents[agent_name] = {s: 0 for s in _VALID_AGENT_STATUSES}
        phase_agents[agent_name][status] += 1


# ---------------------------------------------------------------------------
# Git log
# ---------------------------------------------------------------------------


def _run_git_log(epic_path: Path) -> list[str]:
    """Run git log for the epic path and return oneline entries.

    Args:
        epic_path: Path to the epic folder (used as pathspec).

    Returns:
        List of oneline git log strings (empty on error or no commits).
    """
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "--", str(epic_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return lines
    except OSError:
        return []


def _git_date_from_log(epic_path: Path, extra_flags: list[str]) -> str | None:
    """Get a single date from git log with extra_flags appended.

    Args:
        epic_path: Path to the epic folder (used as pathspec).
        extra_flags: Extra flags to pass to git log (e.g. [``--reverse``]).

    Returns:
        Date string in YYYY-MM-DD format, or None when no commits exist.
    """
    try:
        result = subprocess.run(
            ["git", "log", "--format=%as"] + extra_flags + ["--", str(epic_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        return lines[0] if lines else None
    except OSError:
        return None


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


def _read_telemetry(telemetry_path: Path, epic_path_str: str) -> dict[str, int]:
    """Count telemetry events whose ticket path is under the epic folder.

    Args:
        telemetry_path: Path to agent_telemetry.jsonl.
        epic_path_str: String representation of the epic folder path (used
            as a prefix filter on the ``ticket`` field).

    Returns:
        Dict mapping event type to count. Empty dict when file is absent.
    """
    if not telemetry_path.exists():
        return {}

    counts: dict[str, int] = {}
    try:
        with open(telemetry_path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ticket = entry.get("ticket", "")
                if not isinstance(ticket, str):
                    continue
                if not _ticket_under_epic(ticket, epic_path_str):
                    continue
                event_type = entry.get("event_type", "unknown")
                counts[event_type] = counts.get(event_type, 0) + 1
    except OSError:
        return {}

    return counts


def _ticket_under_epic(ticket_path: str, epic_path_str: str) -> bool:
    """Return True when ticket_path is under epic_path_str.

    Normalises both to forward-slash paths for platform safety.

    Args:
        ticket_path: Ticket path string from telemetry entry.
        epic_path_str: Epic folder path string.

    Returns:
        bool: True when ticket_path starts with epic_path_str.
    """
    norm_ticket = ticket_path.replace("\\", "/")
    norm_epic = epic_path_str.replace("\\", "/").rstrip("/")
    return norm_ticket.startswith(norm_epic + "/") or norm_ticket == norm_epic


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def extract_facts(
    epic_path: Path,
    telemetry_path: Path | None = None,
) -> dict:
    """Extract all quantitative facts from an epic folder.

    This is the public API for use by retrospective-agent and tests.

    Args:
        epic_path: Absolute or relative path to the epic folder.
        telemetry_path: Path to agent_telemetry.jsonl, or None to skip.

    Returns:
        Facts dict matching the documented output schema.
    """
    epic_path = Path(epic_path)
    epic_name = epic_path.name

    ticket_count, completed_count, phase_agents, blockers, handoffs = _read_tickets(epic_path)

    git_lines = _run_git_log(epic_path)
    git_commit_count = len(git_lines)
    git_first = _git_date_from_log(epic_path, ["--reverse", "-1"])
    git_last = _git_date_from_log(epic_path, ["-1"])

    telemetry_events: dict[str, int] = {}
    if telemetry_path is not None:
        telemetry_events = _read_telemetry(Path(telemetry_path), str(epic_path))

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return {
        "epic_name": epic_name,
        "epic_path": str(epic_path).replace("\\", "/"),
        "extracted_at": now,
        "ticket_count": ticket_count,
        "completed_ticket_count": completed_count,
        "phase_agent_counts": phase_agents,
        "git_commit_count": git_commit_count,
        "git_first_commit_date": git_first,
        "git_last_commit_date": git_last,
        "blocker_comment_count": blockers,
        "handoff_comment_count": handoffs,
        "telemetry_events": telemetry_events,
    }


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        description="Extract deterministic quantitative facts from an epic folder.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("epic_path", help="Path to the epic folder.")
    parser.add_argument(
        "--telemetry",
        default=None,
        metavar="PATH",
        help="Path to agent_telemetry.jsonl. Default: debugging/logs/agent_telemetry.jsonl",
    )
    parser.add_argument(
        "--format",
        choices=("json",),
        default="json",
        help="Output format (only json is supported).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for extract_epic_facts.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 on success, 1 on error).
    """
    args = _build_parser().parse_args(argv)

    epic_path = Path(args.epic_path)
    if not epic_path.exists():
        print(f"ERROR: Epic path does not exist: {epic_path}", file=sys.stderr)
        return 1

    telemetry_path: Path | None = None
    if args.telemetry:
        telemetry_path = Path(args.telemetry)
    else:
        default_telemetry = Path("debugging") / "logs" / "agent_telemetry.jsonl"
        if default_telemetry.exists():
            telemetry_path = default_telemetry

    facts = extract_facts(epic_path, telemetry_path)
    print(json.dumps(facts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-15 14:50 [EPIC-FeedbackCollection/ticket-07]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Deterministic facts extractor for retrospective pipeline. Three data sources:
#   ticket frontmatter (YAML via PyYAML), git log (subprocess), optional telemetry
#   JSONL. _count_comment_statuses() scans only the ## Comments section for status
#   tags to avoid false positives in other sections. _accumulate_agents() supports
#   both scalar and nested-map frontmatter agent value forms. Cyclomatic complexity
#   kept under 15 by extracting per-source helpers. telemetry_events is always
#   present (empty dict when no telemetry). git dates use --format=%as (short date)
#   to avoid locale issues.
# ====================================================================
