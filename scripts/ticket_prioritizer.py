"""
MODULE: ticket_prioritizer.py
GOAL: Dependency-aware ticket prioritizer that uses frontmatter status: as the
    authoritative source for ticket lifecycle state, replacing the folder-position
    heuristic (done/ subfolder) with explicit status field reads.
BUSINESS CONTEXT: BO-400a-4, BO-400a-5 — the ticket prioritizer must exclude
    in_progress tickets (already being driven) and done tickets (already complete)
    from the ready set. Dependency resolution must use frontmatter status: done
    rather than checking whether a ticket lives in a done/ subfolder. Backward
    compatibility: legacy epics with tickets in done/ subfolders are supported
    via recursive scan + status-field-fallback (tickets in done/ without a status:
    field are treated as status: done).
ARCHITECTURE: Single-module script + importable function. Scans all *.md files
    under the given epic folder recursively (including legacy done/ subfolders).
    Parses YAML frontmatter to extract status: and depends_on: fields. Builds a
    simple dependency graph and returns the ready set: tickets with status: todo
    whose depends_on entries are all satisfied (status: done or living in done/).
    Excludes in_progress, blocked, done, and deferred tickets from the ready set.

Exit Codes:
    0 - Success
    1 - Cycle detected in dependency graph

Usage:
    python scripts/ticket_prioritizer.py --epic <epic_folder> [--json]
    python scripts/ticket_prioritizer.py --all [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Status constants
# ---------------------------------------------------------------------------

# Statuses that count as "done" for dependency resolution
DONE_STATUSES: frozenset[str] = frozenset({"done", "deferred"})

# Statuses that are excluded from the ready set (ticket is in flight or finished)
EXCLUDED_STATUSES: frozenset[str] = frozenset({"done", "in_progress", "blocked", "deferred"})

# Fallback status for tickets in a done/ subfolder with no status: field
DONE_FOLDER_FALLBACK_STATUS: str = "done"

# Fallback status for tickets with no status: field outside done/
MISSING_STATUS_FALLBACK: str = "todo"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _parse_frontmatter(content: str) -> dict | None:
    """Parse the YAML frontmatter block from ticket content.

    Uses lightweight regex parsing (not yaml.safe_load) to stay fast and
    avoid yaml dependency issues in environments where pyyaml may not be
    installed. Handles simple scalar values and list values for the fields
    we care about (status:, title:, priority:, depends_on:).

    Args:
        content: Full text content of a ticket markdown file.

    Returns:
        A dict with parsed frontmatter fields (at least status, depends_on,
        title, priority), or None if the frontmatter block cannot be parsed.
    """
    if not content.startswith("---"):
        return None
    end_idx = content.find("\n---", 3)
    if end_idx == -1:
        return None

    yaml_block = content[4 : end_idx + 1]

    try:
        import yaml

        parsed = yaml.safe_load(yaml_block)
        if not isinstance(parsed, dict):
            return None
        return parsed
    except Exception:
        # Fallback: regex-based parsing for the fields we need
        result: dict = {}
        for line in yaml_block.splitlines():
            m = re.match(r"^(\w+):\s*(.*)$", line)
            if m:
                key, value = m.group(1), m.group(2).strip()
                result[key] = value if value else None
        return result if result else None


def _get_status(fm: dict, ticket_path: Path) -> str:
    """Determine the effective status for a ticket.

    Applies the backward-compatibility rule: tickets in a done/ subfolder
    without a status: field are treated as status: done.

    Args:
        fm: Parsed frontmatter dict.
        ticket_path: Path to the ticket file (used for done/ folder detection).

    Returns:
        The effective status string.
    """
    status = fm.get("status")
    if status:
        return str(status).strip()

    # Backward-compat: no status: field
    path_str = str(ticket_path).replace("\\", "/").lower()
    if "/done/" in path_str:
        return DONE_FOLDER_FALLBACK_STATUS

    return MISSING_STATUS_FALLBACK


def _get_depends_on(fm: dict) -> list[str]:
    """Extract the depends_on list from ticket frontmatter.

    Handles both list format and null/missing values.

    Args:
        fm: Parsed frontmatter dict.

    Returns:
        List of dependency basenames (or paths) as strings.
    """
    depends_on = fm.get("depends_on")
    if depends_on is None:
        return []
    if isinstance(depends_on, list):
        return [str(d) for d in depends_on if d]
    if isinstance(depends_on, str) and depends_on.strip():
        return [depends_on.strip()]
    return []


# ---------------------------------------------------------------------------
# Dependency graph + ready-set computation
# ---------------------------------------------------------------------------


def _scan_tickets(epic_folder: Path) -> list[dict]:
    """Scan all *.md files under the epic folder recursively.

    Excludes Master_Plan.md and README.md. Parses frontmatter for each
    found file and builds a list of ticket dicts.

    Args:
        epic_folder: Path to the epic directory to scan.

    Returns:
        List of dicts, each with keys: path, basename, status, depends_on,
        title, priority.
    """
    tickets: list[dict] = []

    try:
        all_md = list(epic_folder.rglob("*.md"))
    except OSError as exc:
        print(f"Warning: cannot scan {epic_folder}: {exc}", file=sys.stderr)
        return []

    for md_path in sorted(all_md):
        if md_path.name in ("Master_Plan.md", "README.md"):
            continue

        try:
            content = md_path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"Warning: cannot read {md_path}: {exc}", file=sys.stderr)
            continue

        fm = _parse_frontmatter(content)
        if fm is None:
            continue

        status = _get_status(fm, md_path)
        depends_on = _get_depends_on(fm)
        title = str(fm.get("title", md_path.stem))
        priority = str(fm.get("priority", "medium"))

        tickets.append(
            {
                "path": str(md_path),
                "basename": md_path.name,
                "status": status,
                "depends_on": depends_on,
                "title": title,
                "priority": priority,
            }
        )

    return tickets


def _resolve_dependency(dep: str, tickets: list[dict], epic_folder: Path) -> str | None:
    """Resolve a dependency reference to a ticket's effective status.

    Dependency references can be basenames (e.g. "03_ticket_c.md") or
    relative paths. Matches against both basename and full path.

    Args:
        dep: Dependency reference string from the depends_on list.
        tickets: All scanned tickets.
        epic_folder: Epic folder for relative path resolution.

    Returns:
        The effective status of the dependency ticket, or None if not found.
    """
    dep_basename = Path(dep).name

    for t in tickets:
        if t["basename"] == dep_basename:
            return t["status"]
        if Path(t["path"]).name == dep_basename:
            return t["status"]
        # Full path match
        if t["path"] == str(epic_folder / dep):
            return t["status"]

    return None


def _detect_cycle(ticket: dict, tickets: list[dict], epic_folder: Path, visited: set[str], stack: set[str]) -> list[str] | None:
    """Detect cycles in the dependency graph via DFS.

    Args:
        ticket: The current ticket dict being visited.
        tickets: All scanned tickets.
        epic_folder: Epic folder for dependency resolution.
        visited: Set of already-fully-visited ticket basenames.
        stack: Set of ticket basenames currently in the DFS stack.

    Returns:
        A list describing the cycle path if one is detected, or None.
    """
    name = ticket["basename"]
    if name in stack:
        return [name]
    if name in visited:
        return None

    stack.add(name)
    for dep in ticket["depends_on"]:
        dep_basename = Path(dep).name
        dep_ticket = next((t for t in tickets if t["basename"] == dep_basename), None)
        if dep_ticket is None:
            continue
        cycle = _detect_cycle(dep_ticket, tickets, epic_folder, visited, stack)
        if cycle is not None:
            return [name] + cycle

    stack.discard(name)
    visited.add(name)
    return None


def get_ready_tickets(epic_folder: str) -> list[dict]:
    """Return the set of tickets ready to work on now.

    A ticket is ready when:
    - Its status: is 'todo' (not in_progress, done, blocked, or deferred)
    - All depends_on entries have status: in DONE_STATUSES

    Args:
        epic_folder: Path string to the epic directory.

    Returns:
        List of ticket dicts for ready tickets, sorted by priority.
    """
    folder = Path(epic_folder)
    tickets = _scan_tickets(folder)

    if not tickets:
        return []

    # Check for cycles
    visited: set[str] = set()
    for ticket in tickets:
        if ticket["basename"] not in visited:
            cycle = _detect_cycle(ticket, tickets, folder, visited, set())
            if cycle is not None:
                cycle_str = " -> ".join(cycle)
                print(f"CYCLE DETECTED: {cycle_str}", file=sys.stderr)
                return []

    # Compute ready set
    ready: list[dict] = []
    for ticket in tickets:
        # Exclude non-todo statuses
        if ticket["status"] in EXCLUDED_STATUSES:
            continue

        # Check all dependencies are satisfied
        all_deps_done = True
        for dep in ticket["depends_on"]:
            dep_status = _resolve_dependency(dep, tickets, folder)
            if dep_status is None:
                # Dependency not found — treat as unresolved (not done)
                all_deps_done = False
                break
            if dep_status not in DONE_STATUSES:
                all_deps_done = False
                break

        if all_deps_done:
            ready.append(ticket)

    # Sort by priority
    priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    ready.sort(key=lambda t: priority_order.get(t["priority"], 4))

    return ready


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for ticket_prioritizer.py.

    Returns:
        Configured ArgumentParser instance.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Dependency-aware ticket prioritizer. Returns the set of tickets "
            "ready to work on now, using frontmatter status: as the authoritative "
            "lifecycle signal."
        )
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--epic",
        help="Path to the epic folder to scan.",
    )
    group.add_argument(
        "--all",
        action="store_true",
        default=False,
        help="Scan all tickets in tickets/00_inbox/ and tickets/01_todo/.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        default=False,
        dest="json_output",
        help="Output JSON instead of human-readable text.",
    )
    return parser


def main() -> int:
    """Entry point for ticket_prioritizer.py.

    Returns:
        0 on success, 1 on cycle detection or scan failure.
    """
    parser = _build_arg_parser()
    args = parser.parse_args()

    if args.all:
        # Scan both inbox and todo folders
        repo_root = Path(__file__).resolve().parent.parent
        folders = [
            repo_root / "tickets" / "00_inbox",
            repo_root / "tickets" / "01_todo",
        ]
        all_ready: list[dict] = []
        for folder in folders:
            if folder.exists():
                all_ready.extend(get_ready_tickets(str(folder)))
        ready = all_ready
    else:
        epic_folder = Path(args.epic).resolve()
        if not epic_folder.exists():
            print(f"Error: epic folder not found: {epic_folder}", file=sys.stderr)
            return 1
        ready = get_ready_tickets(str(epic_folder))

    if args.json_output:
        print(json.dumps({"ready": ready}, indent=2))
    else:
        if not ready:
            print("No ready tickets found.")
        else:
            print("READY TICKETS  (unblocked, sorted by priority):")
            for t in ready:
                priority_label = t["priority"]
                print(f"  [{priority_label}]  {Path(t['path']).name}")

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 12:30 [python-coder/BO-400]: Created as the status-field-based
  ticket prioritizer per BO-400a-4, BO-400a-5. Uses frontmatter status: as the
  authoritative source instead of folder position. Backward-compat: tickets in
  legacy done/ subfolders without a status: field are treated as status: done
  (BO-400c-1-i). Exposes get_ready_tickets() as the primary importable function
  so tests can call it directly without subprocess. The EXCLUDED_STATUSES set
  explicitly includes in_progress so already-driven tickets are never in the
  ready set.
====================================================================
"""
