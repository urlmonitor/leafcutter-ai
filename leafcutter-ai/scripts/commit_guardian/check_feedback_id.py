"""
MODULE: leafcutter/scripts/commit_guardian/check_feedback_id.py
GOAL: Pre-commit guard that verifies every new signoff-comment heading in staged
      ticket diffs carries a ``feedback-id:`` line, enforcing the CFCS contract.
BUSINESS CONTEXT: ticket 04 (signoff-integration) updated the signoff skill to
      emit a feedback-id in every comment. This hook is the commit-time safety net
      that catches any comment headings added without the required line — whether
      from a stale agent, a manual edit, or a pre-epoch ticket that was incorrectly
      updated. Only newly-added lines are inspected so old headings are never
      flagged.
ARCHITECTURE: Reads ``git diff --cached`` directly (subprocess) to get only the
      staged diff, then splits by file hunk. For each file, collects the added-line
      bodies and scans for comment-heading lines (``### YYYY-MM-DD HH:MM — ...``).
      When a heading is found, the next two added lines are inspected for a
      ``feedback-id:`` prefix. The escape hatch ``[NO-FEEDBACK-CHECK]`` in the
      commit message (read from ``COMMIT_EDITMSG`` env or ``--commit-msg-file``
      arg) skips all checks. Registered via
      ``scripts/commit_guardian/run_hook.py`` in ``.pre-commit-config.yaml``.
DOC_LINKS:
  - docs/how-to/feedback-collection.md

Exit Codes:
    0 - All staged headings carry feedback-id, or escape hatch active
    1 - One or more headings are missing feedback-id

Usage:
    python scripts/commit_guardian/check_feedback_id.py
    python scripts/commit_guardian/check_feedback_id.py --commit-msg-file .git/COMMIT_EDITMSG
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches: ### 2026-05-15 14:30 — agent-name (status: ok)
_HEADING_RE = re.compile(
    r"^### \d{4}-\d{2}-\d{2} \d{2}:\d{2} — "
)

# Matches: feedback-id: fb_YYYY-MM-DD_xxxxxxxx  (leading whitespace OK)
_FEEDBACK_ID_RE = re.compile(r"^\s*feedback-id:\s*\S")

_ESCAPE_TOKEN = "[NO-FEEDBACK-CHECK]"


# ---------------------------------------------------------------------------
# Escape hatch
# ---------------------------------------------------------------------------


def _should_skip(commit_msg_file: str | None) -> bool:
    """Return True when the commit message contains the escape token.

    Checks (in order):
    1. ``--commit-msg-file`` argument
    2. ``GIT_COMMIT_MSG`` environment variable
    3. ``COMMIT_EDITMSG`` environment variable (absolute path to the file set by git)
    4. ``.git/COMMIT_EDITMSG`` resolved via ``git rev-parse --git-dir`` — the only
       reliable path at the pre-commit stage when the user runs
       ``git commit -m "msg [NO-FEEDBACK-CHECK]"``.  Git writes the message to
       ``COMMIT_EDITMSG`` before running pre-commit hooks but does NOT set env
       vars.  In a git worktree, ``git rev-parse --git-dir`` resolves to the
       worktree-specific gitdir (e.g. ``.git/worktrees/<branch>/``), so
       ``COMMIT_EDITMSG`` is found correctly regardless of worktree nesting.

    Args:
        commit_msg_file: Path to the commit-message file supplied by
            ``--commit-msg-file``, or None when not provided.

    Returns:
        bool: True when the escape token is found in any commit-message source.
    """
    sources: list[str | None] = [commit_msg_file]
    sources.append(os.environ.get("GIT_COMMIT_MSG"))
    sources.append(os.environ.get("COMMIT_EDITMSG"))

    for source in sources:
        if source is None:
            continue
        # Treat as a file path when it looks like one (contains path separator or exists).
        if os.sep in source or "/" in source or Path(source).exists():
            try:
                text = Path(source).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
        else:
            text = source  # treat as the raw message string

        if _ESCAPE_TOKEN in text:
            return True

    # Fourth source: read COMMIT_EDITMSG directly via git rev-parse --git-dir.
    # This is the only reliable path at the pre-commit stage when the user runs
    # git commit -m "msg [NO-FEEDBACK-CHECK]" — git writes the message to
    # COMMIT_EDITMSG before running pre-commit hooks, but does NOT set env vars.
    # In a worktree, git rev-parse --git-dir returns the worktree-specific gitdir
    # (e.g. .git/worktrees/<branch>/), so COMMIT_EDITMSG is resolved correctly.
    try:
        git_dir_result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if git_dir_result.returncode == 0:
            git_dir = git_dir_result.stdout.strip()
            commit_editmsg = Path(git_dir) / "COMMIT_EDITMSG"
            if commit_editmsg.exists():
                text = commit_editmsg.read_text(encoding="utf-8", errors="replace")
                if _ESCAPE_TOKEN in text:
                    return True
    except OSError:
        pass  # fail-open: if git is unavailable, don't block

    return False


# ---------------------------------------------------------------------------
# Diff parsing
# ---------------------------------------------------------------------------


def _get_cached_diff() -> str:
    """Run ``git diff --cached`` and return stdout as a string.

    Returns:
        str: Raw unified diff of the staged changes, or empty string on error.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout
    except OSError:
        return ""


def _parse_added_lines_by_file(diff_text: str) -> dict[str, list[str]]:
    """Extract added lines from a unified diff, grouped by file path.

    Only lines with a ``+`` prefix are collected (``+++`` header lines are
    excluded). The file key is the ``b/`` path from the ``+++ b/...`` header.

    Args:
        diff_text: Raw unified diff string from ``git diff --cached``.

    Returns:
        dict[str, list[str]]: Mapping from file path to list of added line
            bodies (``+`` prefix stripped).
    """
    result: dict[str, list[str]] = {}
    current_file: str | None = None

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            if current_file not in result:
                result[current_file] = []
        elif line.startswith("+++ /dev/null"):
            current_file = None
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file is not None:
                result.setdefault(current_file, []).append(line[1:])

    return result


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------


def _find_violations(file_path: str, added_lines: list[str]) -> list[str]:
    """Scan a list of added lines for comment headings without feedback-id.

    A heading is any added line that matches ``_HEADING_RE``. The next two
    added lines after a heading are checked for ``feedback-id:``. If neither
    contains it, the heading is a violation.

    Args:
        file_path: The file path string (used in violation messages only).
        added_lines: List of added line bodies (``+`` prefix already stripped).

    Returns:
        list[str]: Human-readable violation strings, one per missing feedback-id.
    """
    violations: list[str] = []
    for idx, line in enumerate(added_lines):
        if not _HEADING_RE.match(line):
            continue
        heading_text = line.strip()
        # Look at the next two added lines for feedback-id:
        found = _check_next_lines_for_feedback_id(added_lines, idx)
        if not found:
            violations.append(
                f"{file_path}: new comment heading missing feedback-id:\n"
                f"  heading: {heading_text}"
            )
    return violations


def _check_next_lines_for_feedback_id(added_lines: list[str], heading_idx: int) -> bool:
    """Check the two lines after heading_idx for a feedback-id: marker.

    Args:
        added_lines: Full list of added line bodies for the file.
        heading_idx: Index of the heading line in added_lines.

    Returns:
        bool: True when a feedback-id: line is found within two positions after.
    """
    for offset in range(1, 3):
        next_idx = heading_idx + offset
        if next_idx >= len(added_lines):
            break
        if _FEEDBACK_ID_RE.match(added_lines[next_idx]):
            return True
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser for this hook.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Pre-commit guard: every new signoff-comment heading in staged ticket diffs "
            "must carry a feedback-id: line.\n\n"
            "Escape hatch: include [NO-FEEDBACK-CHECK] in the commit message to skip."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--commit-msg-file",
        default=None,
        metavar="PATH",
        help="Path to the commit-message file (e.g. .git/COMMIT_EDITMSG).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for check_feedback_id.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: 0 when all checks pass or escape hatch is active, 1 on violations.
    """
    args = _build_parser().parse_args(argv)

    if _should_skip(args.commit_msg_file):
        print("[check-feedback-id] skipped via [NO-FEEDBACK-CHECK] escape hatch.")
        return 0

    diff_text = _get_cached_diff()
    added_by_file = _parse_added_lines_by_file(diff_text)

    all_violations: list[str] = []
    for file_path, added_lines in added_by_file.items():
        # Only inspect ticket files (markdown under tickets/)
        if not _is_ticket_file(file_path):
            continue
        all_violations.extend(_find_violations(file_path, added_lines))

    if all_violations:
        print(
            "[check-feedback-id] BLOCK: new comment headings found without feedback-id:",
            file=sys.stderr,
        )
        for v in all_violations:
            print(f"  {v}", file=sys.stderr)
        print(
            "\nAdd 'feedback-id: <id>' on the line immediately after each heading,\n"
            "or include [NO-FEEDBACK-CHECK] in the commit message to bypass.",
            file=sys.stderr,
        )
        return 1

    return 0


def _is_ticket_file(file_path: str) -> bool:
    """Return True when the file path looks like a ticket markdown file.

    Args:
        file_path: Relative file path from the diff header.

    Returns:
        bool: True when the path is under ``tickets/`` and ends with ``.md``.
    """
    norm = file_path.replace("\\", "/")
    return norm.startswith("tickets/") and norm.endswith(".md")


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-15 14:40 [EPIC-FeedbackCollection/ticket-05]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Pre-commit guard for feedback-id enforcement. Inspects only added lines
#   (git diff --cached) so pre-existing headings are never flagged. The two-line
#   lookahead covers the signoff-skill body structure where feedback-id: is the
#   first body line after the heading. Escape hatch [NO-FEEDBACK-CHECK] is
#   checked in commit message file, GIT_COMMIT_MSG env, and COMMIT_EDITMSG env.
#   Only ticket files (tickets/**/*.md) are inspected — non-ticket diffs pass
#   through silently. Registered in both commit_guardian.json instances (scripts
#   and templates directories).
# - 2026-05-17 10:30 [TICKET-20260517-Surface_Step5_Residuals_Feedback_Fix_NoFeedbackCheck]: (#EPIC-LeafcutterMVP/01)
#   Fixed _should_skip() to add a fourth fallback source: read COMMIT_EDITMSG from
#   the gitdir resolved via `git rev-parse --git-dir`. This is the only reliable
#   path at the pre-commit stage when the user runs `git commit -m "msg
#   [NO-FEEDBACK-CHECK]"` because git writes the message to COMMIT_EDITMSG before
#   running pre-commit hooks but does NOT set env vars at this stage. The fix
#   also correctly handles git worktrees: `git rev-parse --git-dir` returns the
#   worktree-specific gitdir (e.g. .git/worktrees/<branch>/), so COMMIT_EDITMSG
#   is found at the correct location. Any OSError or non-zero git return is
#   suppressed (fail-open) so the hook never blocks on git unavailability.
# ====================================================================
