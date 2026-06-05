"""
MODULE: prioritize.py
GOAL: Dependency-aware ticket selector — builds a DAG from depends_on frontmatter,
      detects cycles, and surfaces only unblocked tickets sorted by priority.
BUSINESS CONTEXT: Agents need to know which ticket to pick up next. Priority-only
    sorting is insufficient when tickets have depends_on chains; this script resolves
    those chains and returns only genuinely workable tickets.
ARCHITECTURE: Not needed.

New flag (ticket 02 — EPIC-ACDrivenDevelopment):
  --include-acs  When set, delegates to ac_prioritizer.py which merges ready ACs
                 from the AC store with ready tickets into a unified priority queue.
                 Default is off (False) for backward compatibility — callers that
                 do not pass the flag see identical output to prior versions.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Priority ordering
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
DONE_DIR_NAMES = {"done", "09_done", "99_done", "99_rejected"}


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict:
    """Parse YAML-style frontmatter delimited by --- lines.

    Supports only the minimal subset used by ticket files: string scalars,
    lists, and nested dicts. Full YAML parsing is intentionally avoided to
    keep this script dependency-free.

    Args:
        text: Full file content as a string.

    Returns:
        Dict of parsed frontmatter fields, or an empty dict if none found.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    fm_lines: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        fm_lines.append(line)

    return _parse_yaml_block(fm_lines)


def _parse_yaml_block(lines: list[str]) -> dict:
    """Parse a minimal YAML block into a Python dict.

    Handles: string scalars, null, booleans, and sequence blocks (- item).
    Nested mappings are supported one level deep.

    Args:
        lines: Lines of the YAML block (no leading/trailing --- delimiters).

    Returns:
        A dict with parsed key/value pairs.
    """
    result: dict = {}
    current_key: str | None = None
    current_list: list | None = None

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- ") and current_key is not None and current_list is not None:
            current_list.append(stripped[2:].strip())
            continue

        if ":" in stripped:
            if current_key is not None and current_list is not None:
                result[current_key] = current_list
                current_list = None
            current_key, current_list = _handle_key_line(stripped, result)

    if current_key is not None and current_list is not None:
        result[current_key] = current_list

    return result


def _handle_key_line(
    stripped: str,
    result: dict,
) -> tuple[str | None, list | None]:
    """Parse a single key: value line and write the value into result.

    Returns the new (current_key, current_list) state so the caller can
    accumulate subsequent list items.

    Args:
        stripped: The stripped line text containing a colon.
        result: The mutable output dict to write scalar/list values into.

    Returns:
        Tuple of (current_key, current_list) for continued list accumulation,
        or (None, None) when the value was a scalar or inline list.
    """
    key, _, value = stripped.partition(":")
    key = key.strip()
    value = value.strip()

    if not value:
        result[key] = []
        return key, []

    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        result[key] = [item.strip().strip("'\"") for item in inner.split(",")] if inner else []
        return None, None

    result[key] = _coerce_scalar(value)
    return None, None


def _coerce_scalar(value: str) -> str | bool | None:
    """Convert a YAML scalar string to an appropriate Python type.

    Args:
        value: Raw string from after the colon in a YAML key-value line.

    Returns:
        bool, None, or stripped string depending on the content.
    """
    if value in ("true", "True", "yes"):
        return True
    if value in ("false", "False", "no"):
        return False
    if value in ("null", "~", ""):
        return None
    return value.strip("'\"")


# ---------------------------------------------------------------------------
# Ticket discovery
# ---------------------------------------------------------------------------


def is_done_path(path: Path) -> bool:
    """Return True if the path lives inside a done/ directory.

    Args:
        path: Absolute or relative path to a ticket file.

    Returns:
        True when any parent directory component is a done-directory name.
    """
    return any(part in DONE_DIR_NAMES for part in path.parts)


def discover_tickets(scope_paths: list[Path]) -> list[dict]:
    """Discover all ticket .md files under the given scope paths.

    Args:
        scope_paths: List of directories to scan recursively.

    Returns:
        List of ticket dicts with keys: path, frontmatter, done.
    """
    tickets: list[dict] = []
    seen: set[Path] = set()

    for scope in scope_paths:
        if not scope.is_dir():
            continue
        for md_file in sorted(scope.rglob("*.md")):
            if md_file in seen:
                continue
            # Skip README files
            if md_file.name.lower() == "readme.md":
                continue
            seen.add(md_file)

            content = md_file.read_text(encoding="utf-8", errors="replace")
            fm = parse_frontmatter(content)
            if not fm:
                continue

            tickets.append({
                "path": md_file,
                "frontmatter": fm,
                "done": _is_done(md_file, fm),
            })

    return tickets


def _is_done(path: Path, fm: dict) -> bool:
    """Determine whether a ticket is already done.

    Args:
        path: Path to the ticket file.
        fm: Parsed frontmatter dict.

    Returns:
        True if the ticket is in a done state.
    """
    status = str(fm.get("status", "")).lower()
    if status in ("done", "deferred"):
        return True
    return is_done_path(path)


# ---------------------------------------------------------------------------
# Dependency graph
# ---------------------------------------------------------------------------


def build_graph(tickets: list[dict]) -> dict[str, dict]:
    """Build a dependency graph keyed by ticket filename (basename).

    Args:
        tickets: List of ticket dicts from discover_tickets().

    Returns:
        Dict mapping filename -> {path, frontmatter, done, depends_on}.
    """
    graph: dict[str, dict] = {}
    for t in tickets:
        name = t["path"].name
        depends_on_raw: list = t["frontmatter"].get("depends_on") or []
        depends_on: list[str] = [
            str(d).strip()
            for d in depends_on_raw
            if str(d).strip()
        ]
        graph[name] = {
            "path": t["path"],
            "frontmatter": t["frontmatter"],
            "done": t["done"],
            "depends_on": depends_on,
        }
    return graph


def detect_cycle(graph: dict[str, dict]) -> list[str] | None:
    """Detect a cycle in the dependency graph using DFS.

    Args:
        graph: Dependency graph from build_graph().

    Returns:
        A list of node names forming the cycle path, or None if no cycle exists.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {name: WHITE for name in graph}
    parent: dict[str, str | None] = {name: None for name in graph}

    def dfs(node: str) -> list[str] | None:
        """Perform DFS from a node, returning cycle path if found.

        Args:
            node: Starting node name.

        Returns:
            Cycle path as a list of node names, or None.
        """
        color[node] = GRAY
        for dep in graph.get(node, {}).get("depends_on", []):
            if dep not in graph:
                continue
            if color[dep] == GRAY:
                # Found cycle — reconstruct path
                cycle = [dep]
                cur = node
                while cur != dep and cur is not None:
                    cycle.append(cur)
                    cur = parent.get(cur)
                cycle.append(dep)
                cycle.reverse()
                return cycle
            if color[dep] == WHITE:
                parent[dep] = node
                result = dfs(dep)
                if result is not None:
                    return result
        color[node] = BLACK
        return None

    for name in graph:
        if color[name] == WHITE:
            cycle = dfs(name)
            if cycle is not None:
                return cycle

    return None


def compute_ready(graph: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Partition tickets into ready (unblocked) and blocked lists.

    A ticket is ready iff it is not done AND all its depends_on entries
    are either done or absent from the graph (assumed satisfied).

    Args:
        graph: Dependency graph from build_graph().

    Returns:
        Tuple of (ready_tickets, blocked_tickets), each a list of dicts
        with keys: path, title, priority, blocked_by.
    """
    ready: list[dict] = []
    blocked: list[dict] = []

    for name, node in graph.items():
        if node["done"]:
            continue

        fm = node["frontmatter"]
        title = str(fm.get("title", name))
        priority = str(fm.get("priority", "")).lower()

        unmet: list[str] = []
        for dep in node["depends_on"]:
            dep_node = graph.get(dep)
            if dep_node is None:
                continue  # Unknown dependency — treat as satisfied
            if not dep_node["done"]:
                unmet.append(dep)

        entry = {
            "path": str(node["path"]),
            "title": title,
            "priority": priority,
        }

        if unmet:
            entry["blocked_by"] = unmet
            blocked.append(entry)
        else:
            ready.append(entry)

    def _sort_key(ticket: dict) -> tuple[int, str]:
        """Sort key: priority rank ascending, then path ascending.

        Args:
            ticket: Ticket dict with priority and path keys.

        Returns:
            Tuple for sorting: (priority_rank, path_string).
        """
        rank = PRIORITY_ORDER.get(ticket["priority"], 4)
        return (rank, ticket["path"])

    ready.sort(key=_sort_key)
    blocked.sort(key=_sort_key)

    return ready, blocked


# ---------------------------------------------------------------------------
# Output formatters
# ---------------------------------------------------------------------------


def format_human(
    ready: list[dict],
    blocked: list[dict],
    done: list[dict],
) -> str:
    """Format results as human-readable text.

    Args:
        ready: List of ready ticket dicts.
        blocked: List of blocked ticket dicts.
        done: List of done ticket dicts (paths as strings).

    Returns:
        Formatted multi-line string for console output.
    """
    lines: list[str] = []

    lines.append("READY TICKETS  (unblocked, sorted by priority):")
    if ready:
        for t in ready:
            pri = t["priority"] or "unlabelled"
            lines.append(f"  [{pri:<10}]  {Path(t['path']).name}")
    else:
        lines.append("  (none)")

    lines.append("")
    lines.append("BLOCKED TICKETS  (has unresolved depends_on):")
    if blocked:
        for t in blocked:
            pri = t["priority"] or "unlabelled"
            lines.append(f"  [{pri:<10}]  {Path(t['path']).name}")
            for blocker in t.get("blocked_by", []):
                lines.append(f"    blocked by: {blocker}")
    else:
        lines.append("  (none)")

    return "\n".join(lines)


def format_json(
    ready: list[dict],
    blocked: list[dict],
    done: list[dict],
) -> str:
    """Format results as a JSON string.

    Args:
        ready: List of ready ticket dicts.
        blocked: List of blocked ticket dicts.
        done: List of done ticket paths (strings).

    Returns:
        JSON-formatted string.
    """
    payload = {
        "ready": [
            {
                "path": t["path"],
                "title": t["title"],
                "priority": t["priority"],
            }
            for t in ready
        ],
        "blocked": [
            {
                "path": t["path"],
                "title": t["title"],
                "priority": t["priority"],
                "blocked_by": t.get("blocked_by", []),
            }
            for t in blocked
        ],
        "done": [str(p) for p in done],
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def build_scope(args: argparse.Namespace) -> list[Path]:
    """Resolve the list of scope directories from parsed CLI arguments.

    Args:
        args: Parsed argument namespace with epic and all attributes.

    Returns:
        List of Path objects to scan.
    """
    if args.epic:
        epic_path = Path(args.epic).resolve()
        return [epic_path]

    # Default / --all: scan tickets/00_inbox and tickets/01_todo
    repo_root = Path.cwd()
    inbox = repo_root / "tickets" / "00_inbox"
    todo = repo_root / "tickets" / "01_todo"
    return [inbox, todo]


def _find_worktree_root_from(start: Path) -> Path | None:
    """Walk up from *start* to find the nearest directory containing a .git marker.

    Args:
        start: Starting path for the upward search.

    Returns:
        The worktree root Path, or None when no .git marker is found.
    """
    current = start.resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    return None


def _delegate_to_ac_prioritizer(args: "argparse.Namespace") -> int:
    """Delegate to ac_prioritizer.py when --include-acs is set.

    Locates ac_prioritizer.py relative to the worktree root and invokes it as
    a subprocess, forwarding --json when set. Returns its exit code.

    Args:
        args: Parsed argument namespace (must have output_json attribute).

    Returns:
        Exit code from ac_prioritizer.py, or 1 on location failure.
    """
    import subprocess  # noqa: PLC0415 — local import to keep module-level imports minimal

    # Locate ac_prioritizer.py relative to the worktree root
    script_dir = Path(__file__).resolve().parent
    worktree_root = _find_worktree_root_from(script_dir)
    if worktree_root is None:
        print(
            "ERROR: --include-acs: could not locate worktree root to find ac_prioritizer.py",
            file=sys.stderr,
        )
        return 1

    ac_prio_script = worktree_root / "scripts" / "ac_store" / "ac_prioritizer.py"
    if not ac_prio_script.exists():
        print(
            f"ERROR: --include-acs: ac_prioritizer.py not found at {ac_prio_script}",
            file=sys.stderr,
        )
        return 1

    cmd = [sys.executable, str(ac_prio_script)]
    if args.output_json:
        cmd.append("--json")

    result = subprocess.run(cmd)
    return result.returncode


def main(argv: list[str] | None = None) -> int:
    """Entry point for the ticket prioritizer CLI.

    Parses arguments, discovers tickets, builds the dependency graph,
    detects cycles, computes the ready/blocked split, and prints results.

    Args:
        argv: Argument list (defaults to sys.argv[1:] when None).

    Returns:
        Exit code: 0 on success, 1 on cycle detected or other error.
    """
    # Windows UTF-8 stdout fix
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    parser = argparse.ArgumentParser(
        description="Dependency-aware ticket selector.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--epic",
        metavar="PATH",
        help="Scope to a single epic folder (scans sub-tickets only).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Scan all tickets across 00_inbox and 01_todo (default when no flag given).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Emit machine-readable JSON instead of human-readable text.",
    )
    parser.add_argument(
        "--include-acs",
        action="store_true",
        dest="include_acs",
        default=False,
        help=(
            "Merge ready ACs from the AC store with ready tickets into a unified "
            "priority queue. Delegates to scripts/ac_store/ac_prioritizer.py. "
            "Default: off (backward-compatible — existing callers are unaffected)."
        ),
    )

    args = parser.parse_args(argv)

    # --include-acs: delegate entirely to ac_prioritizer.py
    if args.include_acs:
        return _delegate_to_ac_prioritizer(args)

    scope_paths = build_scope(args)

    tickets = discover_tickets(scope_paths)
    graph = build_graph(tickets)

    cycle = detect_cycle(graph)
    if cycle is not None:
        cycle_str = " -> ".join(cycle)
        print(f"CYCLE DETECTED: {cycle_str}", file=sys.stderr)
        return 1

    ready, blocked = compute_ready(graph)
    done_paths = [node["path"] for node in graph.values() if node["done"]]

    if args.output_json:
        print(format_json(ready, blocked, done_paths))
    else:
        print(format_human(ready, blocked, done_paths))

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-13 13:00 [Agent]: Created as part of ticket 17 (EPIC-PortableDevWorkflow). (#TICKETLESS reason=initial-dag-implementation)
  Rewrote the previous priority-only script to resolve depends_on chains via
  a DAG with cycle detection. Kept dependency-free (stdlib only) so it can
  be copied into any project without Poetry/pip requirements.
- 2026-05-13 17:00 [Agent]: Ticket 19 — added 99_done to DONE_DIR_NAMES to match
  the renamed done folder (09_done → 99_done per ticket lifecycle manifest update). (#TICKETLESS reason=99-done-dir-name-alignment)
- 2026-06-03 00:00 [Agent]: Appended missing tail-tags to both DECISION HISTORY entries
  so check_documentation pre-commit hook passes on downstream installs. (#EPIC-TemplateDocViolations/02)
- 2026-06-05 10:10 [Agent]: Added --include-acs flag (default off) that delegates to
  ac_prioritizer.py when set. Backward-compatible: callers without the flag get identical
  output. Added _delegate_to_ac_prioritizer() and _find_worktree_root_from() helpers.
  (#EPIC-ACDrivenDevelopment/02)
====================================================================
"""
