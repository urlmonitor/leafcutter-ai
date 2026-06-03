"""
MODULE: check_ticket_state_integrity.py
GOAL: Post-merge hook that scans all ticket files under ``tickets/`` for
    basename duplicates across lifecycle folders and for
    status-folder inconsistencies (e.g. ``status: done`` in ``00_inbox/``).
    Prints a formatted warning report to stdout and always exits 0
    (non-blocking, informational).
BUSINESS CONTEXT: Even with pre-commit guards in place, ticket duplicates and
    status mismatches can still arise from branches created before this epic
    landed, ``git merge --no-verify`` operations, or external contributors who
    haven't installed the hook. A post-merge watchdog that fires after every
    ``git merge`` catches these violations immediately without blocking work,
    giving operators a clear action to take. Duplicate and mismatch detection
    closes the gap between the pre-commit guard (which fires at author time)
    and the human review (which may not inspect ticket YAML).
ARCHITECTURE: Post-merge hook. Reads no stdin. Uses only ``pathlib``, ``re``,
    ``subprocess`` (for ``git rev-parse --show-toplevel`` to find the repo
    root), ``sys``, ``time``, and ``json`` (stdlib only). Scans the
    ``tickets/`` tree via ``pathlib.Path.rglob``. Reads ``ticket_lifecycle.json``
    for the allowed-status-per-folder mapping. Exits 0 regardless of findings
    (post-merge hooks cannot abort a merge, and blocking post-merge hooks cause
    user confusion).

Post-merge hook contract:
- Reads nothing from stdin; scans the working tree directly.
- exit 0 always (informational, non-blocking).

DECISION HISTORY
- 2026-06-03 12:05 [EPIC-MoveOnMainOnly/05]: Initial implementation.
  Post-merge watchdog that prints duplicate-ticket and status-folder-mismatch
  warnings after every ``git merge``. Pure stdlib, exits 0 always. Reads
  ``ticket_lifecycle.json`` for allowed-status-per-folder mapping; graceful
  fallback when config is missing. Designed to run in < 2 seconds on repos
  with up to 200 ticket files.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

# Files to exclude from ticket scanning
_EXCLUDED_NAMES = frozenset({"README.md", "Master_Plan.md", "MASTER_PLAN.md"})

# Regex to extract the ``status:`` value from YAML frontmatter
_STATUS_RE = re.compile(r"^status:\s*(.+)$", re.MULTILINE)

# Fallback allowed statuses per folder label when ticket_lifecycle.json
# is missing. Maps folder-name fragment → set of allowed statuses.
_FALLBACK_ALLOWED: dict[str, list[str]] = {
    "00_inbox": ["todo", "blocked", "deferred"],
    "01_todo": ["todo", "in_progress", "blocked"],
    "99_done": ["done", "deferred"],
    "99_rejected": ["done", "deferred"],
}


def _find_repo_root() -> Path:
    """Return the repository root as an absolute Path.

    Uses ``git rev-parse --show-toplevel``. Falls back to the current working
    directory on any error so the hook remains usable outside git.

    Returns:
        The repository root path.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return Path.cwd()
    else:
        if result.returncode == 0:
            return Path(result.stdout.strip())
        return Path.cwd()


def _read_lifecycle_config(repo_root: Path) -> dict[str, list[str]]:
    """Read ``ticket_lifecycle.json`` and return a folder-label → allowed-statuses map.

    Falls back to ``_FALLBACK_ALLOWED`` if the file is missing or malformed,
    printing a warning to stdout.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        A dict mapping folder path fragment (e.g. ``"00_inbox"``) to a list of
        allowed status strings.
    """
    config_path = repo_root / "config" / "ticket_lifecycle.json"
    if not config_path.exists():
        # Try the leafcutter package path as a secondary location
        config_path = repo_root / "leafcutter" / "config" / "ticket_lifecycle.json"
    if not config_path.exists():
        print(
            "[ticket-integrity] WARNING: ticket_lifecycle.json not found; "
            "using built-in fallback for folder/status mapping."
        )
        return dict(_FALLBACK_ALLOWED)

    try:
        with open(config_path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(
            f"[ticket-integrity] WARNING: could not parse ticket_lifecycle.json "
            f"({exc}); using built-in fallback."
        )
        return dict(_FALLBACK_ALLOWED)

    folders = data.get("folders", [])
    mapping: dict[str, list[str]] = {}
    for entry in folders:
        path_str = entry.get("path", "")
        allowed = entry.get("allowed_statuses", [])
        # Use the final path component (e.g. "00_inbox") as the key
        label = Path(path_str).name
        if label and allowed:
            mapping[label] = allowed
    if not mapping:
        print(
            "[ticket-integrity] WARNING: ticket_lifecycle.json has no folder entries; "
            "using built-in fallback."
        )
        return dict(_FALLBACK_ALLOWED)
    return mapping


def _collect_tickets(repo_root: Path) -> list[Path]:
    """Collect all ticket Markdown files under ``tickets/``.

    Uses ``pathlib.Path.rglob`` to walk the tree. Excludes ``README.md``,
    ``Master_Plan.md``, and ``MASTER_PLAN.md``.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        List of absolute Path objects for each ticket file found.
    """
    tickets_dir = repo_root / "tickets"
    if not tickets_dir.exists():
        return []
    return [
        p for p in tickets_dir.rglob("*.md")
        if p.name not in _EXCLUDED_NAMES
    ]


def _read_frontmatter_status(path: Path) -> str | None:
    """Extract the ``status:`` value from a ticket file's YAML frontmatter.

    Reads only the first 50 lines to stay fast on large files. Returns ``None``
    if no frontmatter block is found or the status field is absent.

    Args:
        path: Absolute path to the ticket Markdown file.

    Returns:
        The raw status string (e.g. ``"done"``), or ``None`` if not found.
    """
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            # Read up to 50 lines — frontmatter is always near the top
            lines = []
            for i, line in enumerate(fh):
                if i >= 50:
                    break
                lines.append(line)
    except OSError:
        return None

    content = "".join(lines)
    # Only search within the frontmatter block (between the first two ``---``)
    if not content.startswith("---"):
        return None
    # Find the closing ``---``
    end_idx = content.find("---", 3)
    if end_idx == -1:
        frontmatter = content
    else:
        frontmatter = content[3:end_idx]

    match = _STATUS_RE.search(frontmatter)
    if match:
        return match.group(1).strip()
    return None


def _detect_duplicates(
    tickets: list[Path],
) -> list[tuple[str, list[Path]]]:
    """Detect ticket files that share the same basename across multiple folders.

    Args:
        tickets: List of ticket file paths.

    Returns:
        List of (basename, [paths]) tuples where len(paths) > 1.
    """
    by_basename: dict[str, list[Path]] = defaultdict(list)
    for ticket in tickets:
        by_basename[ticket.name].append(ticket)
    return [
        (name, paths)
        for name, paths in by_basename.items()
        if len(paths) > 1
    ]


def _detect_folder_mismatches(
    tickets: list[Path],
    lifecycle: dict[str, list[str]],
) -> list[dict[str, object]]:
    """Detect tickets whose frontmatter status conflicts with their folder.

    For each ticket, maps its physical parent folder name to the allowed
    statuses from ``lifecycle``. Reports a violation when the ticket's actual
    ``status:`` value is not in the allowed list.

    Args:
        tickets: List of ticket file paths.
        lifecycle: Mapping from folder-name fragment to allowed status list.

    Returns:
        List of violation dicts, each with keys ``file``, ``status``,
        ``folder``, and ``allowed``.
    """
    violations: list[dict[str, object]] = []
    for ticket in tickets:
        # Walk up the parent chain to find the first folder that matches
        # a lifecycle key (to handle nested paths like 00_inbox/epics/EPIC-*/...)
        folder_label: str | None = None
        allowed_statuses: list[str] = []
        for parent in ticket.parents:
            label = parent.name
            if label in lifecycle:
                folder_label = label
                allowed_statuses = lifecycle[label]
                break

        if folder_label is None:
            # Ticket is outside any known lifecycle folder — skip
            continue

        status = _read_frontmatter_status(ticket)
        if status is None:
            continue

        if status not in allowed_statuses:
            violations.append(
                {
                    "file": ticket,
                    "status": status,
                    "folder": folder_label,
                    "allowed": allowed_statuses,
                }
            )
    return violations


def main() -> None:
    """Orchestrate duplicate and mismatch detection; print a report; exit 0.

    Scans all tickets in the repository, detects duplicates and
    status-folder mismatches, and prints a structured warning report.
    Always exits 0 (post-merge hooks are non-blocking by policy).
    """
    t_start = time.monotonic()

    repo_root = _find_repo_root()
    lifecycle = _read_lifecycle_config(repo_root)
    tickets = _collect_tickets(repo_root)

    duplicates = _detect_duplicates(tickets)
    mismatches = _detect_folder_mismatches(tickets, lifecycle)

    if not duplicates and not mismatches:
        elapsed = time.monotonic() - t_start
        print(
            f"[ticket-integrity] OK: no integrity violations found "
            f"({len(tickets)} tickets scanned in {elapsed:.2f}s)"
        )
        sys.exit(0)

    for basename, paths in duplicates:
        copies_text = "\n".join(f"    - {p}" for p in paths)
        print(
            f"[ticket-integrity] WARNING: duplicate ticket detected\n"
            f"  Basename: {basename}\n"
            f"  Copies:\n{copies_text}\n"
            f"  Action: Remove the stale copy (usually the 00_inbox/ version) "
            f"and commit."
        )

    for violation in mismatches:
        allowed_str = ", ".join(str(s) for s in violation["allowed"])
        print(
            f"[ticket-integrity] WARNING: status-folder mismatch\n"
            f"  File: {violation['file']}\n"
            f"  Frontmatter status: {violation['status']}\n"
            f"  Folder: {violation['folder']} (allowed: {allowed_str})\n"
            f"  Action: Move the file to the correct lifecycle folder "
            f"or correct the frontmatter status."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
