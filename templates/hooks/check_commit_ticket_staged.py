"""
MODULE: check_commit_ticket_staged.py
GOAL: PreToolUse hook that blocks a ``git commit`` call when the active
    ticket file has unstaged modifications. This catches the regression
    pattern where a phase agent (commit or pull-request) writes sign-off
    edits to the ticket file but calls ``git commit`` before staging them,
    leaving the ticket file in the working tree as an unstaged delta.
BUSINESS CONTEXT: Every phase-agent sign-off writes bytes to the ticket file
    (frontmatter status flip, Sign-offs checkbox tick, Comments entry). If
    those bytes are not staged before ``git commit``, the commit lands without
    the sign-off and Step 5 of build-single-ticket catches a residual —
    requiring a manual ``git add`` + amend or re-run. This PreToolUse hook
    makes that failure structural (the commit cannot proceed) rather than
    detectable only after the fact.
ARCHITECTURE: PreToolUse hook on ``Bash`` tool calls containing ``git commit``.
    Reads the current TICKET_PATH env var (set by ticket-supervisor when
    invoking phase agents). If the ticket file is ``M`` (modified in working
    tree) but absent from the staged set, exits non-zero with a blocking message
    so the agent self-corrects by running ``git add <ticket_path>`` first.
    When TICKET_PATH is unset or empty, exits 0 silently (interactive sessions
    where no ticket is active).
DOC_LINKS:
  - docs/how-to/agent-commit-discipline.md

PreToolUse hook contract (Bash tool):
- Exit 0 with no output = silently allow
- Exit 0 with {"decision": "block", "reason": "..."} = block the tool call
- Exit 1 = allow (non-zero exit is not blocking for PreToolUse on Bash)

This hook emits JSON and exits 0 to leverage the block-decision contract.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _get_ticket_path() -> str | None:
    """Read TICKET_PATH from the environment.

    Returns:
        The ticket path string when set and non-empty, or None otherwise.
    """
    ticket_path = os.environ.get("TICKET_PATH", "").strip()
    return ticket_path if ticket_path else None


def _is_git_commit_call(payload: dict) -> bool:
    """Return True when the Bash tool input contains ``git commit``.

    Only exact ``git commit`` calls are intercepted — ``git add``,
    ``git status``, etc. are ignored.

    Args:
        payload: Parsed PreToolUse JSON payload.

    Returns:
        True when the ``command`` field contains ``git commit``.
    """
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or tool_input.get("cmd") or "")
    # Match "git commit" but not "git commit --amend" suppression check, etc.
    return "git commit" in command


def _ticket_has_unstaged_changes(ticket_path: str) -> bool:
    """Return True when *ticket_path* has working-tree modifications not staged.

    Uses ``git status --porcelain <path>`` and checks whether the first
    character (working-tree status) is ``M`` — modified but not staged.

    Args:
        ticket_path: Absolute or repo-relative path to the ticket file.

    Returns:
        True when the file is modified in the working tree (not staged).
        False on any subprocess error (fail-open: don't block on git errors).
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", ticket_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return False  # fail-open

        for line in result.stdout.splitlines():
            if len(line) < 2:
                continue
            # Porcelain format: XY PATH
            # X = staged status, Y = working-tree status
            wt_status = line[1]  # working-tree column
            staged_status = line[0]  # staged column
            if wt_status == "M":
                # File is modified in working tree
                # Check whether it is ALSO staged (i.e. would be captured
                # by git commit even without explicit re-add).
                # If staged_status is not ' ' (space), it's already in the index.
                # But we want: staged AND has unstaged changes = partial stage.
                # For our purposes, any 'M' in column 2 (wt) with ' ' in
                # column 1 (staged) means ENTIRELY unstaged — the whole file
                # is missing from the index.
                if staged_status == " ":
                    return True  # completely unstaged
        return False
    except OSError:
        return False  # fail-open: if git is unavailable, don't block


def _is_ticket_in_staged_set(ticket_path: str) -> bool:
    """Return True when *ticket_path* appears in ``git diff --cached --name-only``.

    A supplementary check for when ``git status --porcelain`` reports a
    complex state (e.g. partially staged file). When the file IS in the
    cached diff, the commit will capture the staged portion.

    Args:
        ticket_path: Absolute or repo-relative path to the ticket file.

    Returns:
        True when the file has staged changes. False on error (fail-open).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return False

        # Normalise both sides: resolve to POSIX paths for comparison
        staged_files = {line.strip() for line in result.stdout.splitlines() if line.strip()}
        ticket_posix = Path(ticket_path).as_posix()
        # Check both the raw path and any trailing-slash-stripped form
        return (
            ticket_posix in staged_files
            or any(sf.endswith(Path(ticket_path).name) for sf in staged_files)
        )
    except OSError:
        return False


def _build_block_message(ticket_path: str) -> str:
    """Build the human-readable blocking reason.

    Args:
        ticket_path: Absolute or repo-relative path to the ticket file.

    Returns:
        Multi-line string injected back to the agent as a blocking reason.
    """
    return (
        "PreToolUse blocked: ticket file has unstaged modifications.\n"
        f"  Ticket: {ticket_path}\n"
        "\n"
        "The ticket file has edits in the working tree that are NOT in the staged set.\n"
        "These edits (sign-off checkbox ticks, Comments entries, frontmatter status)\n"
        "would be MISSING from the commit if you proceed now.\n"
        "\n"
        "Fix: stage the ticket file first, then retry git commit:\n"
        f"  git add {ticket_path}\n"
        "  git commit -m \"...\""
    )


def main() -> None:
    """Entry point. Reads the PreToolUse payload from stdin and emits a decision."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        # Malformed payload — fail-open, do not block
        sys.exit(0)

    # Only intercept Bash tool calls containing "git commit"
    if not _is_git_commit_call(payload):
        sys.exit(0)

    # Only active when a ticket is being driven
    ticket_path = _get_ticket_path()
    if not ticket_path:
        sys.exit(0)

    # Check whether the ticket file has unstaged changes
    if not _ticket_has_unstaged_changes(ticket_path):
        # Either file is staged, clean, or doesn't exist — allow
        sys.exit(0)

    # Double-check: is the file already in the staged set (partial stage)?
    if _is_ticket_in_staged_set(ticket_path):
        # Staged portion exists — allow (the commit will capture it)
        sys.exit(0)

    # Ticket file has unstaged changes and is not in the staged set — block
    print(json.dumps({"decision": "block", "reason": _build_block_message(ticket_path)}))
    sys.exit(0)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-22 00:00 [EPIC-CommitSignoffHardening/01]: Initial implementation.
  PreToolUse hook on Bash tool calls containing "git commit". Checks
  TICKET_PATH env var for the active ticket file; if the file has unstaged
  modifications (git status --porcelain col 2 == 'M', col 1 == ' '), emits
  a block decision with an actionable error. Fail-open on all subprocess
  errors and on missing TICKET_PATH. Companion to the existing
  "Commit-Agent Sign-off Step" in templates/agents/commit.md — the hook is
  the structural backstop, the agent instruction is the primary mechanism.
  Belt-and-suspenders: together they eliminate the regression pattern where
  sign-off edits land in the working tree but miss the commit.
====================================================================
"""
