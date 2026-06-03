"""
MODULE: check_ticket_no_branch_move.py
GOAL: Pre-commit hook that blocks ``git mv`` of ticket files on non-main/master
    branches. Inspects the staged index for R (rename) entries whose source or
    destination paths fall under the ``tickets/`` directory tree. If running on
    a non-main/master branch and a ticket rename is detected, exits non-zero with
    a descriptive error message directing the author to edit frontmatter status
    instead.
BUSINESS CONTEXT: The move-on-main-only pattern requires that branches never
    rename ticket files between lifecycle folders. Tickets 01 and 02 remove the
    automated ``git mv`` calls from the tooling, but a developer (or an agent
    writing custom bash) could still manually run ``git mv
    tickets/00_inbox/TICKET-X.md tickets/01_todo/TICKET-X.md`` and commit it.
    This hook closes that gap by acting as a policy gate at pre-commit time,
    complementing ``check_ticket_rename_tracking.py`` (PostToolUse guard) and
    enforcing the EPIC-MoveOnMainOnly pattern.
ARCHITECTURE: Pre-commit hook. Reads no stdin. Uses only subprocess and sys
    (no external dependencies). Detects current branch via ``git rev-parse
    --abbrev-ref HEAD``. Inspects ``git diff --cached --name-status -M`` for
    ``R<score>\t<src>\t<dst>`` lines. Exits 0 on main/master or when no ticket
    renames are found; exits 1 with a structured error message when a ticket
    rename is detected on a non-main branch.

Pre-commit hook contract:
- Reads nothing from stdin; inspects staged index directly.
- exit 0 = allow the commit.
- exit non-zero = block the commit; error message is printed to stdout.

DECISION HISTORY
- 2026-06-03 10:10 [EPIC-MoveOnMainOnly/04]: Initial implementation.
  Pre-commit hook enforcing the move-on-main-only pattern. Blocks any commit
  that stages a rename (R entry) of a file under ``tickets/`` on a branch
  other than main or master. Exits 0 on main/master or when no ticket renames
  are staged.
"""
from __future__ import annotations

import subprocess
import sys

_MAIN_BRANCHES = frozenset({"main", "master"})


def _current_branch() -> str:
    """Return the current git branch name.

    Returns:
        The branch name from ``git rev-parse --abbrev-ref HEAD``, or ``"main"``
        on any error (fail-open so the hook does not block in detached-HEAD or
        non-git contexts).
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return "main"
    else:
        if result.returncode == 0:
            return result.stdout.strip()
        return "main"


def _get_staged_renames() -> list[tuple[str, str]]:
    """Return a list of (src, dst) rename pairs from the staged index.

    Runs ``git diff --cached --name-status -M`` and parses lines that start
    with ``R`` (rename entries, e.g. ``R100\\told_path\\tnew_path``).

    Returns:
        List of (source, destination) path tuples for all staged renames.
        Returns an empty list on any error (fail-open).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "-M"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return []
    else:
        if result.returncode != 0:
            return []
        renames: list[tuple[str, str]] = []
        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) >= 3 and parts[0].startswith("R"):
                src = parts[1].strip()
                dst = parts[2].strip()
                renames.append((src, dst))
        return renames


def _is_ticket_path(path: str) -> bool:
    """Return True if ``path`` is under the tickets/ directory tree.

    Args:
        path: A file path (relative to the repository root).

    Returns:
        True when the path starts with ``tickets/``, False otherwise.
    """
    return path.startswith("tickets/")


def main() -> None:
    """Orchestrate branch detection, staged rename inspection, and exit logic.

    Exits 0 (allow) when:
    - The current branch is main or master.
    - No staged renames involve paths under ``tickets/``.

    Exits 1 (block) when the current branch is not main/master and at least
    one staged rename has a source or destination path under ``tickets/``.
    """
    branch = _current_branch()
    if branch in _MAIN_BRANCHES:
        sys.exit(0)

    renames = _get_staged_renames()
    ticket_renames = [
        (src, dst)
        for src, dst in renames
        if _is_ticket_path(src) or _is_ticket_path(dst)
    ]

    if not ticket_renames:
        sys.exit(0)

    for src, dst in ticket_renames:
        print(
            f"[no-branch-ticket-move] ERROR: ticket file renamed on a non-main branch.\n"
            f"Source: {src}\n"
            f"Dest:   {dst}\n"
            f"Branch: {branch}\n"
            f"\n"
            f"Branches must NOT move ticket files between lifecycle folders (move-on-main-only\n"
            f"pattern, EPIC-MoveOnMainOnly). Instead:\n"
            f"  - Edit the ticket's frontmatter `status:` field to reflect the new state.\n"
            f"  - The folder move happens automatically on main after merge via\n"
            f"    finalize-feature.js Step 5.\n"
            f"\n"
            f"If you intentionally need to commit this rename (e.g. fixing a duplicate),\n"
            f"switch to main or use git commit --no-verify with explicit justification."
        )
    sys.exit(1)


if __name__ == "__main__":
    main()
