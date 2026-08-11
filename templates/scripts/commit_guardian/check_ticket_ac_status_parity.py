"""
MODULE: check_ticket_ac_status_parity.py
GOAL: Pre-commit hook — block commits when a staged ticket is marked
    status:done but its source acceptance-criterion has not yet reached
    work_status:done in the AC store.
BUSINESS CONTEXT: KI-1 from the BO-2200 retrospective (2026-08-10).
    The BO-2200 finalization required manual repair because tickets had been
    flipped to status:done while their source_ac was left at work_status:todo.
    This hook catches that drift mechanically at pre-commit time so the same
    repair is never needed again.  Scoped strictly to STAGED ticket files so
    it never blocks unrelated commits.
ARCHITECTURE: Reads staged ticket markdown files from ``git diff --cached
    --name-only`` filtered to ``tickets/**/*.md``.  For each staged ticket
    whose YAML frontmatter ``status`` is ``done``: resolves the ``source_ac``
    field to a ``.yaml`` file under ``docs/acceptance-criteria/`` (recursive
    search by filename), reads its ``work_status``, and exits 1 when the AC
    exists and its ``work_status`` is not ``done``.  Fail-closed only on that
    specific case; fail-open (warning, no block) when the AC file cannot be
    found.  Self-contained: stdlib + PyYAML + ``_resolve_root`` (bundled in
    the same commit_guardian directory).  No project-internal imports.

# DECISION HISTORY
# - 2026-08-11 [workflow-architect/KI-1]: Initial implementation.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml

from _resolve_root import find_project_root

# Default AC store root, relative to project root.
_AC_STORE_REL = "docs/acceptance-criteria"


def _get_staged_ticket_paths(project_root: Path) -> list[Path]:
    """Return staged ticket markdown paths from git diff --cached.

    Filters to files whose first path component is ``tickets`` and whose
    extension is ``.md``.  Files that no longer exist on disk are skipped.

    Args:
        project_root: Absolute path to the project (git) root.

    Returns:
        List of absolute Paths for staged ticket ``.md`` files.  Returns an
        empty list when the git command fails or no matching files are staged.
    """
    try:
        proc = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(
            f"WARNING: check_ticket_ac_status_parity: git diff failed: {exc}",
            file=sys.stderr,
        )
        return []

    result: list[Path] = []
    for line in proc.stdout.splitlines():
        rel = line.strip()
        if not rel:
            continue
        p = Path(rel)
        parts = p.parts
        if not parts or parts[0] != "tickets":
            continue
        if p.suffix.lower() != ".md":
            continue
        abs_path = project_root / p
        if abs_path.exists():
            result.append(abs_path)
    return result


def _parse_frontmatter(path: Path) -> dict | None:
    """Parse YAML frontmatter from a markdown file.

    Frontmatter is the YAML block between the first two ``---`` delimiters.
    Unreadable or non-frontmatter files return ``None`` without raising.

    Args:
        path: Absolute path to the markdown file.

    Returns:
        Parsed frontmatter as a dict, or ``None`` if absent or unparseable.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"WARNING: check_ticket_ac_status_parity: cannot read {path}: {exc}",
            file=sys.stderr,
        )
        return None

    if not text.startswith("---"):
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        data = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        print(
            f"WARNING: check_ticket_ac_status_parity: YAML error in {path}: {exc}",
            file=sys.stderr,
        )
        return None

    return data if isinstance(data, dict) else {}


def _find_ac_file(ac_id: str, ac_root: Path) -> Path | None:
    """Search for an AC YAML file by id under ac_root.

    Recursively searches for a file named ``<ac_id>.yaml`` under *ac_root*.
    Returns the first match.

    Args:
        ac_id: AC identifier string (e.g. ``"BP-1100e-1"``).
        ac_root: Root directory of the AC store.

    Returns:
        Absolute path to the AC YAML file, or ``None`` if not found or if
        the search raises an OS error.
    """
    try:
        matches = list(ac_root.rglob(f"{ac_id}.yaml"))
    except OSError as exc:
        print(
            f"WARNING: check_ticket_ac_status_parity: cannot search {ac_root}: {exc}",
            file=sys.stderr,
        )
        return None

    return matches[0] if matches else None


def _read_ac_work_status(ac_path: Path) -> str | None:
    """Read the ``work_status`` field from an AC YAML file.

    Args:
        ac_path: Absolute path to the AC YAML file.

    Returns:
        The ``work_status`` string value, or ``None`` if absent or unreadable.
    """
    try:
        with open(ac_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        print(
            f"WARNING: check_ticket_ac_status_parity: cannot read {ac_path}: {exc}",
            file=sys.stderr,
        )
        return None

    if not isinstance(data, dict):
        return None
    return data.get("work_status")


def check_ticket_ac_parity(
    staged_ticket_paths: list[Path],
    *,
    ac_root: Path,
) -> list[dict]:
    """Check staged done-tickets against their source AC work_status.

    For each staged ticket whose frontmatter ``status`` is ``"done"``:

    - If ``source_ac`` field is absent: skip silently (epic / composite /
      scaffold ticket — no source AC relationship).
    - If the AC file cannot be found under *ac_root*: emit a WARNING to
      stderr but do NOT return a violation (warn-only, no hard block).
    - If the AC file exists and ``work_status`` is not ``"done"``: record a
      violation.  This is the only fail-closed case.

    Args:
        staged_ticket_paths: Absolute paths of staged ticket ``.md`` files.
        ac_root: Root directory of the AC store (``docs/acceptance-criteria``).

    Returns:
        List of violation dicts; each has keys ``"ticket"`` (filename str),
        ``"source_ac"`` (AC id str), and ``"work_status"`` (current status
        str).  An empty list means no violations.
    """
    violations: list[dict] = []

    for ticket_path in staged_ticket_paths:
        fm = _parse_frontmatter(ticket_path)
        if fm is None:
            continue

        if fm.get("status") != "done":
            continue

        source_ac = fm.get("source_ac")
        if not source_ac:
            # No source_ac — epics, composites, scaffolds; skip.
            continue

        source_ac_str = str(source_ac).strip()
        if not source_ac_str:
            continue

        ac_path = _find_ac_file(source_ac_str, ac_root)
        if ac_path is None:
            print(
                f"WARNING: check_ticket_ac_status_parity: source_ac "
                f"'{source_ac_str}' not found under {ac_root} "
                f"(ticket: {ticket_path.name}) — skipping",
                file=sys.stderr,
            )
            continue

        work_status = _read_ac_work_status(ac_path)
        if work_status is None:
            print(
                f"WARNING: check_ticket_ac_status_parity: cannot read "
                f"work_status from {ac_path.name} "
                f"(ticket: {ticket_path.name}) — skipping",
                file=sys.stderr,
            )
            continue

        if work_status != "done":
            violations.append(
                {
                    "ticket": ticket_path.name,
                    "source_ac": source_ac_str,
                    "work_status": work_status,
                }
            )

    return violations


def main() -> int:
    """Pre-commit hook entry point.

    Reads staged ticket markdown files via ``git diff --cached``, checks each
    done-ticket's ``source_ac`` against the AC store, and exits 1 when any
    done-ticket's AC is not yet done.

    Returns:
        0 when no violations; 1 when at least one violation is found.
    """
    project_root = find_project_root()
    ac_root = project_root / _AC_STORE_REL

    staged_tickets = _get_staged_ticket_paths(project_root)
    if not staged_tickets:
        return 0

    violations = check_ticket_ac_parity(staged_tickets, ac_root=ac_root)

    if not violations:
        return 0

    print(
        "[check-ticket-ac-status-parity] BLOCKED — done ticket(s) whose "
        "source_ac is not yet done:",
        file=sys.stderr,
    )
    for v in violations:
        print(
            f"  ticket:     {v['ticket']}\n"
            f"  source_ac:  {v['source_ac']}\n"
            f"  work_status: {v['work_status']} (expected: done)\n",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError) as exc:
        print(
            f"[check-ticket-ac-status-parity] unexpected error, skipping: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
