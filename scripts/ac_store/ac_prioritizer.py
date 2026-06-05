"""
MODULE: ac_prioritizer.py
GOAL: Merge ready ACs from scan_ac_store.py with ready tickets from prioritize.py
      into a unified priority queue, ordered by the same priority rules.
BUSINESS CONTEXT: The `ticket-prioritizer` skill reads ticket files only. The AC store
    also contains ready work items (leaf-level ACs not yet turned into tickets).
    This script bridges the two, producing a single ranked list so the user gets
    one authoritative answer to "what to build next".
ARCHITECTURE: Calls scan_ac_store.py and prioritize.py as subprocesses; pure stdlib.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Priority constants
# ---------------------------------------------------------------------------

PRIORITY_ORDER: dict[str, int] = {"critical": 0, "high": 1, "medium": 2, "low": 3}

COMPLEXITY_TO_PRIORITY: dict[str, str] = {
    "S": "high",
    "M": "medium",
    "L": "low",
    "XL": "low",
}


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class MissingScanScriptError(FileNotFoundError):
    """Raised when scan_ac_store.py is not found at the expected path.

    AC-5: ac_prioritizer exits 1 with an error message naming the missing dependency.
    """


class WorktreeRootNotFoundError(FileNotFoundError):
    """Raised when no .git marker is found while walking up from the script location."""


# ---------------------------------------------------------------------------
# Public API (importable by tests)
# ---------------------------------------------------------------------------


def complexity_to_priority(complexity: str) -> str:
    """Map an estimated_complexity value to a unified priority string.

    AC-4 mapping:
      S  → high
      M  → medium
      L  → low
      XL → low

    Unknown values default to 'medium'.

    Args:
        complexity: The estimated_complexity string from an AC YAML record.

    Returns:
        One of 'critical', 'high', 'medium', or 'low'.
    """
    return COMPLEXITY_TO_PRIORITY.get(complexity, "medium")


def _run_json_script(script_path: Path, extra_args: list[str]) -> dict[str, Any]:
    """Run a Python script with --json flag and parse its stdout as JSON.

    Args:
        script_path: Absolute path to the script.
        extra_args: Additional CLI arguments to pass to the script.

    Returns:
        Parsed JSON dict from the script's stdout.

    Raises:
        FileNotFoundError: When the script does not exist (caller should check).
        subprocess.CalledProcessError: When the script exits non-zero.
        json.JSONDecodeError: When stdout is not valid JSON.
    """
    result = subprocess.run(
        [sys.executable, str(script_path), "--json"] + extra_args,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            [str(script_path)] + extra_args,
            output=result.stdout,
            stderr=result.stderr,
        )
    return json.loads(result.stdout)


def _collect_source_acs(ticket_entries: list[dict[str, Any]]) -> set[str]:
    """Collect all `source_ac` values from ticket entries.

    Used for deduplication: if a ticket has source_ac: ACS-100a-1, then
    the AC entry for ACS-100a-1 is suppressed from the merged list.

    Args:
        ticket_entries: List of ticket dicts from prioritize.py JSON output.

    Returns:
        Set of AC ids that are already represented by a ticket.
    """
    source_acs: set[str] = set()
    for entry in ticket_entries:
        sa = entry.get("source_ac")
        if sa:
            source_acs.add(str(sa))
    return source_acs


def _sort_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort entries by unified priority key (critical < high < medium < low), then path.

    Args:
        entries: List of merged entry dicts, each with a 'priority' field.

    Returns:
        Sorted list with highest-priority entries first.
    """
    def _sort_key(entry: dict[str, Any]) -> tuple[int, str]:
        rank = PRIORITY_ORDER.get(entry.get("priority", ""), 4)
        return (rank, entry.get("path", ""))

    return sorted(entries, key=_sort_key)


def merge_and_prioritize(
    scan_script: Path,
    prioritize_script: Path,
    scan_extra_args: list[str] | None = None,
    prioritize_extra_args: list[str] | None = None,
) -> dict[str, Any]:
    """Merge ready ACs and ready tickets into a unified priority queue.

    Steps:
    1. Call scan_script (scan_ac_store.py) with --json flag; parse ready AC list.
    2. Call prioritize_script (prioritize.py) with --all --json; parse ready ticket list.
    3. Map AC estimated_complexity to priority via COMPLEXITY_TO_PRIORITY.
    4. Deduplicate: suppress AC entries whose id matches a ticket's source_ac field.
    5. Add `source` field ('ticket' or 'ac') to every entry.
    6. Merge and sort by unified priority key.

    Args:
        scan_script: Path to scan_ac_store.py.
        prioritize_script: Path to prioritize.py.
        scan_extra_args: Extra args for scan_ac_store.py (default: none).
        prioritize_extra_args: Extra args for prioritize.py (default: --all).

    Returns:
        Dict with keys:
          - 'ready': sorted list of merged entry dicts (each has 'source' field).
          - 'blocked': combined blocked lists from both scripts (informational).

    Raises:
        FileNotFoundError: If scan_script does not exist (AC-5).
        subprocess.CalledProcessError: If either script exits non-zero.
        json.JSONDecodeError: If either script produces non-JSON output.
    """
    if not scan_script.exists():
        raise MissingScanScriptError(str(scan_script))

    scan_args = list(scan_extra_args or [])
    prio_args = list(prioritize_extra_args or ["--all"])

    scan_data = _run_json_script(scan_script, scan_args)
    prio_data = _run_json_script(prioritize_script, prio_args)

    ticket_entries: list[dict[str, Any]] = prio_data.get("ready", [])
    ac_entries: list[dict[str, Any]] = scan_data.get("ready", [])

    # Collect source_ac ids from tickets (for deduplication)
    source_acs = _collect_source_acs(ticket_entries)

    merged: list[dict[str, Any]] = []

    # Add ticket entries with source field
    for entry in ticket_entries:
        ticket_entry = dict(entry)
        ticket_entry["source"] = "ticket"
        merged.append(ticket_entry)

    # Add AC entries with source field, deduplicating when a ticket covers the AC
    for ac in ac_entries:
        ac_id = ac.get("ac_id", "")
        if ac_id in source_acs:
            continue  # Suppressed: a ticket already represents this AC

        priority = complexity_to_priority(ac.get("estimated_complexity", ""))
        ac_entry: dict[str, Any] = {
            "path": ac.get("path", ""),
            "title": ac.get("title", ""),
            "priority": priority,
            "source": "ac",
            "ac_id": ac_id,
            "assigned_agent": ac.get("assigned_agent", ""),
            "estimated_complexity": ac.get("estimated_complexity", ""),
        }
        merged.append(ac_entry)

    # Collect blocked entries (informational — not sorted)
    blocked: list[dict[str, Any]] = []
    for b in prio_data.get("blocked", []):
        entry = dict(b)
        entry["source"] = "ticket"
        blocked.append(entry)
    for b in scan_data.get("blocked", []):
        blocked.append({"ac_id": b.get("ac_id", ""), "blocked_by": b.get("blocked_by", []), "source": "ac"})

    return {
        "ready": _sort_entries(merged),
        "blocked": blocked,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _resolve_script(
    script_arg: str | None,
    default_relative: str,
    worktree_root: Path,
) -> Path:
    """Resolve a script path from a CLI argument or a default relative path.

    Args:
        script_arg: CLI-provided path string, or None to use default.
        default_relative: Default path relative to worktree_root.
        worktree_root: Repository root for relative path resolution.

    Returns:
        Resolved absolute Path.
    """
    if script_arg:
        return Path(script_arg).resolve()
    return (worktree_root / default_relative).resolve()


def _find_worktree_root() -> Path:
    """Walk up from this script until a .git marker is found.

    Returns:
        Worktree root path.

    Raises:
        FileNotFoundError: When no .git is found.
    """
    current = Path(__file__).resolve().parent
    for parent in [current, *current.parents]:
        if (parent / ".git").exists():
            return parent
    raise WorktreeRootNotFoundError(str(Path(__file__).resolve()))


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ac_prioritizer.py.

    Args:
        argv: Argument list (default: sys.argv[1:]).

    Returns:
        Exit code: 0 on success, 1 on error.
    """
    # Windows UTF-8 stdout fix
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    parser = argparse.ArgumentParser(
        description="Merge AC store ready items with ready tickets into a unified priority queue.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--scan-script",
        dest="scan_script",
        default=None,
        help="Path to scan_ac_store.py (default: scripts/ac_store/scan_ac_store.py).",
    )
    parser.add_argument(
        "--prioritize-script",
        dest="prioritize_script",
        default=None,
        help="Path to prioritize.py (default: templates/skills/ticket-prioritizer/scripts/prioritize.py).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="output_json",
        help="Emit machine-readable JSON to stdout (default: human-readable text).",
    )

    args = parser.parse_args(argv)

    try:
        worktree_root = _find_worktree_root()
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    scan_script = _resolve_script(
        args.scan_script,
        "scripts/ac_store/scan_ac_store.py",
        worktree_root,
    )
    prioritize_script = _resolve_script(
        args.prioritize_script,
        "templates/skills/ticket-prioritizer/scripts/prioritize.py",
        worktree_root,
    )

    try:
        result = merge_and_prioritize(
            scan_script=scan_script,
            prioritize_script=prioritize_script,
        )
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as exc:
        cmd_name = Path(exc.cmd[1]).name if len(exc.cmd) > 1 else "script"
        print(
            f"ERROR: {cmd_name} exited with code {exc.returncode}. "
            f"stderr: {exc.stderr or '(none)'}",
            file=sys.stderr,
        )
        return 1
    except json.JSONDecodeError as exc:
        print(f"ERROR: Failed to parse JSON output: {exc}", file=sys.stderr)
        return 1

    if args.output_json:
        print(json.dumps(result, indent=2))
    else:
        _print_human(result)

    return 0


def _print_human(result: dict[str, Any]) -> None:
    """Print the merged result in human-readable format.

    Args:
        result: Dict with 'ready' and 'blocked' lists.
    """
    ready = result.get("ready", [])
    blocked = result.get("blocked", [])

    print(f"READY ({len(ready)})  — tickets and ACs sorted by priority:")
    if ready:
        for entry in ready:
            source = entry.get("source", "?")
            pri = entry.get("priority", "?")
            label = entry.get("title") or entry.get("ac_id") or entry.get("path", "?")
            print(f"  [{source:<6}] [{pri:<8}]  {label}")
    else:
        print("  (none)")

    print()
    print(f"BLOCKED ({len(blocked)}):")
    if blocked:
        for entry in blocked:
            source = entry.get("source", "?")
            label = entry.get("ac_id") or entry.get("title") or entry.get("path", "?")
            blockers = entry.get("blocked_by", [])
            print(f"  [{source:<6}] {label}  blocked by: {', '.join(blockers)}")
    else:
        print("  (none)")


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-05 10:10 [Agent]: Initial implementation by python-coder phase of ticket 02
  (EPIC-ACDrivenDevelopment). Merges scan_ac_store.py ready ACs with prioritize.py
  ready tickets. Uses subprocess.run for both scripts to stay dependency-free.
  complexity_to_priority mapping: S→high, M→medium, L/XL→low (AC-4).
  Deduplication: suppresses AC entries when ticket.source_ac matches (AC-2).
  Exits 1 with named dependency when scan_ac_store.py is missing (AC-5).
  (#EPIC-ACDrivenDevelopment/02)
====================================================================
"""
