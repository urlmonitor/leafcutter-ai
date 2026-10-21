"""
MODULE: _setup_ticket_branch_record.py
GOAL: Record which ticket a branch is being built for (git config
    ``branch.<branch>.leafcutterTicket``) and refuse a second, different ticket
    that maps to the same branch name.
BUSINESS CONTEXT: BO-400e-3-ix. Finalization reads the record instead of
    guessing which ticket a branch belongs to. Split out of
    ``setup_ticket_worktree.py`` to keep that file under its file-size ratchet.
ARCHITECTURE: Pure stdlib. Lives in ``scripts/build_orchestration/``; the build's
    build-orchestration phase deploys every ``*.py`` there to the consumer's
    ``scripts/build_orchestration/``, next to the deployed ``scripts/setup_ticket_worktree.py``.
    ``setup_ticket_worktree.py`` imports this module lazily (``_load_sibling``), from its own
    directory, its ``build_orchestration/`` subdirectory, and then the located repository's
    ``scripts/build_orchestration/``.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_TICKET_RECORD_KEY = "leafcutterTicket"


def _ticket_record_rel(main_repo: Path, ticket_path: Path) -> str | None:
    """Repo-relative POSIX path of *ticket_path*, or None (with a warning) when it is outside *main_repo*."""
    rel = Path(os.path.relpath(ticket_path, main_repo)).as_posix()
    if rel.startswith(".."):
        print(
            f"WARNING: {ticket_path} is outside {main_repo}; the branch will carry no "
            f"built-for-ticket record (finalization will report it cannot tell which ticket).",
            file=sys.stderr,
        )
        return None
    return rel


def _recorded_ticket(main_repo: Path, branch: str) -> str | None:
    """The ticket path recorded against *branch* (git config branch.<branch>.leafcutterTicket), or None."""
    try:
        result = subprocess.run(
            ["git", "-C", str(main_repo), "config", "--get-all", f"branch.{branch}.{_TICKET_RECORD_KEY}"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to read the ticket record for '{branch}': {exc}"
        ) from exc
    values = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return values[0] if values else None


def _refuse_conflicting_record(main_repo: Path, branch: str, rel: str) -> None:
    """Exit 1 when *branch* is already recorded as built for a DIFFERENT ticket (BO-400e-3-ix).

    Two tickets whose titles share a slug map to the same branch name; letting the second
    overwrite the first record would make finalization close the wrong ticket. The same
    ticket after it moved lanes (00_inbox -> 01_todo -> done) has the same file name and
    is NOT a conflict; the caller's ``_record_built_for_ticket`` then rewrites the stored
    path to the new location.
    """
    recorded = _recorded_ticket(main_repo, branch)
    if recorded is not None and Path(recorded).name != Path(rel).name:
        print(
            f"ERROR: branch '{branch}' is already recorded as built for {recorded}; "
            f"refusing to set up {rel} on the same branch. Pass --branch <name> to use a "
            f"different branch for this ticket.",
            file=sys.stderr,
        )
        sys.exit(1)


def _record_built_for_ticket(main_repo: Path, branch: str, rel: str) -> None:
    """Record, in the clone's shared git config, which ticket *branch* is being built for.

    Stored as ``branch.<branch>.leafcutterTicket`` (not as a file in the tree, so recording
    never makes the branch "change" its own ticket). Idempotent: one value under the key.
    """
    try:
        subprocess.run(
            ["git", "-C", str(main_repo), "config", "--replace-all", f"branch.{branch}.{_TICKET_RECORD_KEY}", rel],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise subprocess.SubprocessError(  # noqa: TRY003
            f"Failed to record the built-for ticket for '{branch}': {exc}"
        ) from exc


"""
DECISION HISTORY
====================================================================
- 2026-10-16 [restructuring-specialist]: Moved the BO-400e-3-ix built-for-ticket
  record helpers out of setup_ticket_worktree.py verbatim to keep it under its
  file-size ratchet; no behaviour change. (#BO-400e/3-ix)
====================================================================
"""
