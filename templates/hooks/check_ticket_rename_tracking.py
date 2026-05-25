"""
MODULE: check_ticket_rename_tracking.py
GOAL: PostToolUse hook that verifies a ``git mv`` on a ticket path under
    ``tickets/00_inbox/`` is recorded as an ``R`` (rename) in the staged
    index — not as separate ``A`` (add) + ``D`` (delete) entries. If the
    rename is not detected, the hook emits a warning and attempts to
    re-stage the files correctly.
BUSINESS CONTEXT: When build-single-ticket moves a ticket to ``99_done/``
    via ``git mv``, a subsequent bare ``git add`` on the destination path
    can break git's rename detection. The ticket then appears as a new file
    (``A``) in the done folder with a stale copy lingering in the inbox.
    This hook fires after the ``git mv`` and catches the defect before it
    reaches a commit.
ARCHITECTURE: PostToolUse hook on ``Bash`` tool calls containing ``git mv``
    with a source path matching ``tickets/00_inbox/``. Inspects
    ``git diff --cached --name-status`` for the expected ``R`` entry.
    If the rename is not detected, attempts to re-stage via
    ``git rm --cached <old_path> && git add <new_path>``.

PostToolUse hook contract (Bash tool):
- stdout is shown to the agent as informational feedback
- exit code is ignored (PostToolUse hooks cannot block)
- the hook should be idempotent and safe to run multiple times

DECISION HISTORY
- 2026-05-22 14:30 [EPIC-CommitSignoffHardening/05]: Initial implementation.
  PostToolUse hook on Bash tool calls containing ``git mv tickets/00_inbox/``.
  Verifies rename tracking in the staged index and attempts self-correction
  when the rename is not detected.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys


def _extract_git_mv_paths(command: str) -> tuple[str, str] | None:
    """Extract source and destination paths from a ``git mv`` command.

    Args:
        command: The full bash command string.

    Returns:
        (source, destination) tuple if a ``git mv`` on a ticket inbox path
        is found, or None otherwise.
    """
    pattern = re.compile(
        r'git\s+(?:-C\s+\S+\s+)?mv\s+'
        r'["\']?(tickets/00_inbox/\S+?)["\']?\s+'
        r'["\']?(\S+?)["\']?\s*(?:$|[;&|])',
    )
    match = pattern.search(command)
    if match:
        return match.group(1).rstrip("'\""), match.group(2).rstrip("'\"")
    return None


def _check_rename_in_index(old_path: str, new_path: str) -> bool:
    """Check whether the staged index shows an R (rename) for the ticket move.

    Args:
        old_path: The original ticket path (source of git mv).
        new_path: The destination ticket path.

    Returns:
        True if the rename is detected (R entry), False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status", "-M"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            return True  # fail-open

        for line in result.stdout.splitlines():
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            status = parts[0].strip()
            src = parts[1].strip()
            dst = parts[2].strip()
            if status.startswith("R") and (
                src.endswith(old_path.split("/")[-1])
                or dst.endswith(new_path.split("/")[-1])
            ):
                return True
        return False
    except OSError:
        return True  # fail-open


def _attempt_restage(old_path: str, new_path: str) -> bool:
    """Attempt to re-stage the rename correctly.

    Runs ``git rm --cached <old_path>`` and ``git add <new_path>`` to
    fix the index so git detects the rename.

    Args:
        old_path: The original ticket path.
        new_path: The destination ticket path.

    Returns:
        True if re-staging succeeded and rename is now detected.
    """
    try:
        subprocess.run(
            ["git", "rm", "--cached", old_path],
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "add", new_path],
            capture_output=True,
            text=True,
        )
        return _check_rename_in_index(old_path, new_path)
    except OSError:
        return False


def main() -> None:
    """Entry point. Reads PostToolUse payload from stdin."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or tool_input.get("cmd") or "")

    if "git mv" not in command or "tickets/00_inbox/" not in command:
        sys.exit(0)

    paths = _extract_git_mv_paths(command)
    if not paths:
        sys.exit(0)

    old_path, new_path = paths

    if _check_rename_in_index(old_path, new_path):
        print(
            f"[rename-tracking] OK: git mv {old_path} -> {new_path} "
            f"recorded as R (rename) in staged index."
        )
        sys.exit(0)

    print(
        f"[rename-tracking] WARNING: git mv {old_path} -> {new_path} "
        f"NOT recorded as R (rename). Attempting re-stage correction..."
    )

    if _attempt_restage(old_path, new_path):
        print(
            f"[rename-tracking] FIXED: re-staged {old_path} -> {new_path} "
            f"as rename. Verified R entry in index."
        )
    else:
        print(
            f"[rename-tracking] ERROR: could not fix rename tracking for "
            f"{old_path} -> {new_path}.\n"
            f"Manual fix: git rm --cached {old_path} && git add {new_path}\n"
            f"Then verify: git diff --cached --name-status -M | grep {new_path.split('/')[-1]}"
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
