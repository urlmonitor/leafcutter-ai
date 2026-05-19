"""
MODULE: roadmap_query
GOAL: CLI tool that reads docs/roadmap.json and scans tickets/ to produce
    three queryable views of ticket-to-roadmap alignment.
BUSINESS CONTEXT: After tickets have roadmap_phase and advances_current_outcome
    fields, this script is the read layer — agents and humans can quickly answer
    "which open tickets advance the current phase outcome?" and "which tickets
    have no phase assigned?"
ARCHITECTURE: Six output modes driven by --rollup, --current-outcome,
    --unassigned, --starved, --off-roadmap, and --audit flags. Reads
    docs/roadmap.json for phase metadata then globs tickets/00_inbox/**/*.md
    and tickets/01_todo/**/*.md, parses YAML frontmatter, and aggregates
    results. Output is human-readable (default) or JSON (--format json).
    Exits with a clean error message (not traceback) when docs/roadmap.json
    is absent. --audit produces the full audit_result JSON for the
    product-owner-agent (ADR-039).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Audit modes live in a sibling module to keep this file under 400 lines.
import importlib.util as _ilu
_aud = _ilu.module_from_spec(_s := _ilu.spec_from_file_location("roadmap_query_audit", Path(__file__).resolve().parent / "roadmap_query_audit.py"))  # type: ignore[arg-type]
_s.loader.exec_module(_aud)  # type: ignore[union-attr]
_starved = _aud._starved
_off_roadmap = _aud._off_roadmap
_audit = _aud._audit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SKIP_FILENAMES = {"Master_Plan.md", "README.md"}

_OPEN_STATUSES = {"todo", "in_progress"}


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _find_frontmatter_end(lines: list[str]) -> int:
    """Return the index of the closing ``---`` delimiter, or -1 if absent.

    Args:
        lines: All lines of the file. Assumes ``lines[0]`` is ``---``.

    Returns:
        Line index of the closing delimiter, or -1 if not found.
    """
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            return i
    return -1


def _parse_scalar_value(raw: str) -> Any:
    """Parse an inline scalar YAML value string to a Python type.

    Handles booleans, null, quoted strings, and bare strings. Does not
    handle numeric types — all unrecognised values are returned as strings.

    Args:
        raw: The trimmed right-hand side of a ``key: value`` YAML line.

    Returns:
        True, False, None, or a string.
    """
    lower = raw.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if lower in ("null", "~"):
        return None
    if len(raw) >= 2 and raw[0] in ('"', "'") and raw[-1] == raw[0]:
        return raw[1:-1]
    return raw


def _parse_block_children(lines: list[str], start: int, end: int) -> tuple[list[str], int]:
    """Collect YAML list items from indented lines following a bare ``key:`` line.

    Args:
        lines: All lines of the file.
        start: Index of the first line after the bare ``key:`` line.
        end: Index of the closing ``---`` delimiter.

    Returns:
        A tuple of (list_of_items, next_line_index) where list_of_items
        contains the text of each ``- item`` child line (without the ``- ``
        prefix), and next_line_index is the first non-indented line index
        after the block.
    """
    children: list[str] = []
    j = start
    while j < end and (lines[j].startswith("  ") or lines[j].strip() == ""):
        stripped = lines[j].strip()
        if stripped.startswith("- "):
            children.append(stripped[2:].strip())
        j += 1
    return children, j


def _parse_frontmatter(text: str) -> dict[str, Any]:
    """Extract YAML frontmatter fields from a ticket file's text.

    Uses a minimal line-by-line parser that handles the subset of YAML used
    in ticket frontmatter: string scalars, boolean scalars, and simple
    lists. Complex nested structures (e.g. ``agents:`` mapping) are skipped.

    Args:
        text: Full text content of a ticket file.

    Returns:
        A dict of frontmatter field names to their parsed values. Returns an
        empty dict when no frontmatter block (``---`` delimiters) is found.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = _find_frontmatter_end(lines)
    if end == -1:
        return {}
    fm: dict[str, Any] = {}
    i = 1
    while i < end:
        line = lines[i]
        if not line.strip() or line.startswith("  "):
            i += 1
            continue
        m = re.match(r"^(\w[\w_-]*):\s*(.*)", line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        raw = m.group(2).strip()
        if raw == "":
            children, i = _parse_block_children(lines, i + 1, end)
            if children:
                fm[key] = children
            continue
        fm[key] = _parse_scalar_value(raw)
        i += 1
    return fm


# ---------------------------------------------------------------------------
# Ticket discovery
# ---------------------------------------------------------------------------


def _discover_tickets(project_root: Path) -> list[dict[str, Any]]:
    """Glob tickets/00_inbox and tickets/01_todo for ticket files.

    Skips ``Master_Plan.md`` and ``README.md``. Returns a list of dicts with
    keys: ``path`` (Path), ``rel_path`` (str), ``fm`` (frontmatter dict).

    Args:
        project_root: Absolute path to the project root containing a
            ``tickets/`` directory.

    Returns:
        List of ticket dicts, each with ``path``, ``rel_path``, and ``fm``.
    """
    tickets: list[dict[str, Any]] = []
    for pattern in (
        "tickets/00_inbox/**/*.md",
        "tickets/01_todo/**/*.md",
    ):
        for p in sorted(project_root.glob(pattern)):
            if p.name in _SKIP_FILENAMES:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except OSError:
                continue
            fm = _parse_frontmatter(text)
            tickets.append(
                {
                    "path": p,
                    "rel_path": str(p.relative_to(project_root)).replace("\\", "/"),
                    "fm": fm,
                }
            )
    return tickets


# ---------------------------------------------------------------------------
# Roadmap loading
# ---------------------------------------------------------------------------


def _load_roadmap(project_root: Path) -> dict[str, Any]:
    """Load and return the parsed docs/roadmap.json.

    Args:
        project_root: Absolute path to the project root.

    Returns:
        Parsed roadmap dict.

    Raises:
        SystemExit: With a human-readable error message when the file is absent
            or not valid JSON.
    """
    roadmap_path = project_root / "docs" / "roadmap.json"
    if not roadmap_path.exists():
        print(
            "ERROR: docs/roadmap.json not found.\n"
            "Run `build.py` to create it from the template, or create it manually.",
            file=sys.stderr,
        )
        sys.exit(1)
    try:
        return json.loads(roadmap_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        print(f"ERROR: docs/roadmap.json is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(1)


# ---------------------------------------------------------------------------
# Output modes
# ---------------------------------------------------------------------------


def _rollup(
    tickets: list[dict[str, Any]],
    roadmap: dict[str, Any],
    fmt: str,
) -> int:
    """Print a per-phase rollup of ticket counts and status breakdown.

    Args:
        tickets: List of ticket dicts from ``_discover_tickets``.
        roadmap: Parsed roadmap dict from ``_load_roadmap``.
        fmt: ``"text"`` for human-readable table; ``"json"`` for JSON output.

    Returns:
        0 always (success).
    """
    phases = {p["id"]: p["title"] for p in roadmap.get("phases", [])}
    # Group tickets by phase
    by_phase: dict[str, list[dict[str, Any]]] = {}
    unassigned: list[dict[str, Any]] = []
    for t in tickets:
        phase = t["fm"].get("roadmap_phase")
        if not phase:
            unassigned.append(t)
        else:
            by_phase.setdefault(phase, []).append(t)

    if fmt == "json":
        result: dict[str, Any] = {"phases": {}, "unassigned_count": len(unassigned)}
        for phase_id, title in phases.items():
            phase_tickets = by_phase.get(phase_id, [])
            status_counts: dict[str, int] = {}
            for t in phase_tickets:
                s = t["fm"].get("status", "unknown")
                status_counts[s] = status_counts.get(s, 0) + 1
            result["phases"][phase_id] = {
                "title": title,
                "total": len(phase_tickets),
                "status_breakdown": status_counts,
            }
        print(json.dumps(result, indent=2))
        return 0

    # Human-readable
    current_phase = roadmap.get("current_phase", "")
    print("Roadmap Phase Rollup")
    print("=" * 60)
    for phase_id, title in phases.items():
        marker = " [CURRENT]" if phase_id == current_phase else ""
        phase_tickets = by_phase.get(phase_id, [])
        print(f"\n{phase_id}: {title}{marker}")
        print(f"  Tickets: {len(phase_tickets)}")
        if phase_tickets:
            status_counts: dict[str, int] = {}
            for t in phase_tickets:
                s = t["fm"].get("status", "unknown")
                status_counts[s] = status_counts.get(s, 0) + 1
            for s, count in sorted(status_counts.items()):
                print(f"    {s}: {count}")
    print(f"\nUnassigned (no roadmap_phase): {len(unassigned)}")
    return 0


def _current_outcome(
    tickets: list[dict[str, Any]],
    roadmap: dict[str, Any],
    fmt: str,
) -> int:
    """Print tickets that advance the current-phase outcome.

    Filters to tickets where ``advances_current_outcome is True`` AND
    ``roadmap_phase == current_phase`` AND ``status`` is an open status
    (todo or in_progress).

    Args:
        tickets: List of ticket dicts from ``_discover_tickets``.
        roadmap: Parsed roadmap dict from ``_load_roadmap``.
        fmt: ``"text"`` or ``"json"``.

    Returns:
        0 always (success).
    """
    current_phase = roadmap.get("current_phase", "")
    current_outcome_text = roadmap.get("current_outcome", "")

    filtered = [
        t
        for t in tickets
        if t["fm"].get("advances_current_outcome") is True
        and t["fm"].get("roadmap_phase") == current_phase
        and t["fm"].get("status") in _OPEN_STATUSES
    ]

    if fmt == "json":
        print(
            json.dumps(
                {
                    "current_phase": current_phase,
                    "current_outcome": current_outcome_text,
                    "tickets": [
                        {
                            "path": t["rel_path"],
                            "title": t["fm"].get("title", t["path"].stem),
                            "status": t["fm"].get("status", "unknown"),
                        }
                        for t in filtered
                    ],
                },
                indent=2,
            )
        )
        return 0

    print(f"Current phase: {current_phase}")
    print(f"Current outcome: {current_outcome_text}")
    print(f"\nTickets advancing current outcome ({len(filtered)}):")
    print("=" * 60)
    if not filtered:
        print("  (none — no open tickets marked advances_current_outcome: true)")
        return 0
    for t in filtered:
        title = t["fm"].get("title", t["path"].stem)
        status = t["fm"].get("status", "unknown")
        print(f"  [{status}] {t['rel_path']}")
        print(f"    {title}")
    return 0


def _unassigned(
    tickets: list[dict[str, Any]],
    fmt: str,
) -> int:
    """Print tickets missing a roadmap_phase field (warning list).

    Args:
        tickets: List of ticket dicts from ``_discover_tickets``.
        fmt: ``"text"`` or ``"json"``.

    Returns:
        0 always (success).
    """
    unassigned = [t for t in tickets if not t["fm"].get("roadmap_phase")]

    if fmt == "json":
        print(
            json.dumps(
                {
                    "unassigned": [
                        {
                            "path": t["rel_path"],
                            "title": t["fm"].get("title", t["path"].stem),
                        }
                        for t in unassigned
                    ]
                },
                indent=2,
            )
        )
        return 0

    print(f"Unassigned tickets (missing roadmap_phase): {len(unassigned)}")
    print("=" * 60)
    if not unassigned:
        print("  (none — all tickets have a roadmap_phase assigned)")
        return 0
    for t in unassigned:
        title = t["fm"].get("title", t["path"].stem)
        print(f"  WARNING: {t['rel_path']}")
        print(f"    Title: {title}")
        print(f"    Status: {t['fm'].get('status', 'unknown')}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for roadmap_query CLI.

    Args:
        argv: Argument list to parse. Defaults to ``sys.argv[1:]`` when None.

    Returns:
        Exit code: 0 on success, 1 on fatal error (e.g. missing roadmap.json).
    """
    parser = argparse.ArgumentParser(
        description="Query ticket alignment against docs/roadmap.json.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  roadmap_query.py --rollup\n"
            "  roadmap_query.py --current-outcome\n"
            "  roadmap_query.py --unassigned\n"
            "  roadmap_query.py --starved\n"
            "  roadmap_query.py --off-roadmap\n"
            "  roadmap_query.py --audit\n"
            "  roadmap_query.py --rollup --format json\n"
        ),
    )
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--rollup",
        action="store_true",
        help="List all tickets grouped by roadmap phase with status breakdown.",
    )
    mode_group.add_argument(
        "--current-outcome",
        action="store_true",
        dest="current_outcome",
        help=(
            "List only tickets where advances_current_outcome=true AND "
            "roadmap_phase==current_phase AND status is open."
        ),
    )
    mode_group.add_argument(
        "--unassigned",
        action="store_true",
        help="List tickets with no roadmap_phase (warning list).",
    )
    mode_group.add_argument(
        "--starved",
        action="store_true",
        help="List roadmap phases with no open tickets advancing them.",
    )
    mode_group.add_argument(
        "--off-roadmap",
        action="store_true",
        dest="off_roadmap",
        help="List open tickets with no valid roadmap_phase (off-roadmap).",
    )
    mode_group.add_argument(
        "--audit",
        action="store_true",
        help=(
            "Produce full audit_result JSON for the product-owner-agent: "
            "all_items, starved_items, off_roadmap_tickets."
        ),
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format: 'text' (default) or 'json'.",
    )
    parser.add_argument(
        "--project-root",
        metavar="DIR",
        help=(
            "Root of the project to scan. Defaults to the current working directory."
        ),
    )
    args = parser.parse_args(argv)

    project_root = (
        Path(args.project_root).resolve() if args.project_root else Path.cwd()
    )

    roadmap = _load_roadmap(project_root)
    tickets = _discover_tickets(project_root)

    if args.rollup:
        return _rollup(tickets, roadmap, args.format)
    if args.current_outcome:
        return _current_outcome(tickets, roadmap, args.format)
    if args.unassigned:
        return _unassigned(tickets, args.format)
    if args.starved:
        return _starved(tickets, roadmap, args.format)
    if args.off_roadmap:
        return _off_roadmap(tickets, roadmap, args.format)
    if args.audit:
        return _audit(tickets, roadmap, args.format)
    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-19 12:45 [EPIC-RoadmapStewardship/05]: Added --starved, --off-roadmap, --audit flags. (#EPIC-RoadmapStewardship/05)
  _starved() lists roadmap phases with no open tickets. _off_roadmap() lists
  open tickets with no valid roadmap_phase. _audit() produces the full
  audit_result JSON (all_items, starved_items, off_roadmap_tickets) for the
  product-owner-agent (ADR-039). roadmap-steward SKILL.md documents invocation.
- 2026-05-18 00:00 [EPIC-ProjectRoadmap/ticket 05]: Initial implementation. (#EPIC-ProjectRoadmap/05)
  Three output modes: --rollup, --current-outcome, --unassigned.
  Minimal YAML frontmatter parser (no PyYAML dependency) handles the subset
  used in ticket files. Graceful sys.exit(1) when docs/roadmap.json is absent.
  --format json for machine-readable output. Scans tickets/00_inbox and
  tickets/01_todo only (not 99_done, as done tickets are not actionable).
====================================================================
"""
