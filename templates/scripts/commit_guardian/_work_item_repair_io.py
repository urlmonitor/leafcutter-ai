"""
Ticket text I/O helpers for the work-item duplicate repair.

MODULE: _work_item_repair_io
GOAL: Own every read, write, move, and delete the work-item duplicate repair
    performs -- reading a ticket's frontmatter status, merging a losing
    copy's unique body content into the survivor, recording the resolution
    and reason on the survivor's own text, and performing the actual
    filesystem move/delete. Split out of repair_work_item_duplicates.py to
    keep every new file in this directory under the project's
    400-line-per-new-file limit, following the _work_items_scanner.py /
    check_identifier_uniqueness.py precedent already established here.
BUSINESS CONTEXT: GE-122e-2's own it_requirements bind two behaviours this
    module implements: (1) "before deleting either copy, diff the two and
    record the diff on the surviving file" -- two copies that have drifted
    may each hold something the other lacks, so the deletion this module
    performs must never discard content found nowhere else; (2) "use git mv
    / git rm so the deletions and moves are tracked" -- a ticket file removed
    with a plain filesystem delete loses the history that would let the
    decision be reviewed.
ARCHITECTURE: Every filesystem-crossing call here is wrapped per CLAUDE.md
    Rules 1-4: a read failure fails open (returns None, logs WARNING) since
    the caller can still report "could not repair this one", but a write,
    move, or delete failure re-raises after logging, since silently
    continuing past a failed mutation would leave the collection in an
    inconsistent, half-repaired state. git operations (``_run_git``) are the
    one deliberate exception to "log and re-raise": a git failure here is the
    EXPECTED path when this module runs against a bare tempdir fixture (this
    module's own unit tests never call ``git init``), so it is logged at
    WARNING and the caller falls back to a plain filesystem move/delete
    instead of treating "not a git repository" as fatal.

DOC_LINKS:
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122e-2.yaml

DECISION HISTORY:
  - 2026-08-18 [python-coder/GE-122e-2]: Extracted from
    repair_work_item_duplicates.py to keep every new file in this directory
    under the check-file-size 400-line limit for new files.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

_HOOK_PREFIX = "[repair_work_item_duplicates]"
_TICKET_STATUS_RE = re.compile(r"^status:\s*(.+)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------


def read_text(path: Path) -> str | None:
    """Read a ticket file's full text, failing open with a WARNING.

    Args:
        path: Path to the ticket Markdown file.

    Returns:
        The file's text, or None if it could not be read.
    """
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"{_HOOK_PREFIX} WARNING: cannot read {path}: {exc}", file=sys.stderr)
        return None


def split_frontmatter(text: str) -> tuple[str, str]:
    """Split ticket text into its frontmatter block and body.

    Args:
        text: Full ticket file text.

    Returns:
        (frontmatter_text, body_text) tuple. frontmatter_text is empty when
        the file has no leading ``---`` block.
    """
    if not text.startswith("---"):
        return "", text
    end = text.find("---", 3)
    if end == -1:
        return text[3:], ""
    return text[3:end], text[end + 3 :]


def read_status(text: str) -> str | None:
    """Extract the declared ``status:`` value from ticket text.

    Args:
        text: Full ticket file text.

    Returns:
        The raw declared status string, or None if absent.
    """
    frontmatter, _body = split_frontmatter(text)
    match = _TICKET_STATUS_RE.search(frontmatter)
    return match.group(1).strip() if match else None


# ---------------------------------------------------------------------------
# Content merge
# ---------------------------------------------------------------------------


def find_unique_lines(loser_body: str, winner_body: str) -> list[str]:
    """Return non-blank loser body lines absent from the winner's body.

    Args:
        loser_body: Body text (post-frontmatter) of the losing copy.
        winner_body: Body text (post-frontmatter) of the surviving copy.

    Returns:
        Ordered, de-duplicated list of lines unique to the loser -- content
        the winner does not already carry, which must not be discarded.
    """
    winner_lines = {line for line in winner_body.splitlines() if line.strip()}
    unique: list[str] = []
    for line in loser_body.splitlines():
        if line.strip() and line not in winner_lines and line not in unique:
            unique.append(line)
    return unique


def compose_survivor_content(winner_text: str, loser_text: str, resolution: str, reason: str) -> str:
    """Assemble the survivor's final on-disk content.

    Appends a resolution-record section (always) and a recovered-content
    section (only when the loser held body content the winner lacks) after
    the winner's own unchanged text, so folder position, declared state, and
    the survivor's frontmatter are never touched by this merge.

    Args:
        winner_text: The surviving copy's original full text.
        loser_text: The deleted copy's original full text.
        resolution: The resolution label to record.
        reason: The reason text to record (must appear verbatim in output).

    Returns:
        The full text to write to the survivor's final path.
    """
    _winner_fm, winner_body = split_frontmatter(winner_text)
    _loser_fm, loser_body = split_frontmatter(loser_text)
    recovered_lines = find_unique_lines(loser_body, winner_body)

    sections = [winner_text.rstrip("\n"), "", "## Repair Resolution (GE-122e-2)", ""]
    sections.append(f"- resolution: {resolution}")
    sections.append(f"- reason: {reason}")
    if recovered_lines:
        sections.extend(["", "### Recovered content from the deleted copy", ""])
        sections.extend(recovered_lines)
    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# Filesystem operations (git-first, plain-filesystem fallback)
# ---------------------------------------------------------------------------


def run_git(args: list[str], repo_root: Path) -> bool:
    """Run a git subcommand in *repo_root*; return whether it succeeded.

    A failure here (not a git repository, git not installed) is expected
    when this module runs against a bare tempdir fixture -- logged at
    WARNING, never raised, so callers can fall back to a plain filesystem
    operation.

    Args:
        args: git subcommand and arguments (e.g. ``["mv", src, dst]``).
        repo_root: Directory to run git in (``-C`` target).

    Returns:
        True if the git command exited zero.
    """
    try:
        subprocess.run(
            ["git", "-C", str(repo_root), *args],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: git {' '.join(args)} failed ({exc}); "
            "falling back to a plain filesystem operation.",
            file=sys.stderr,
        )
        return False
    return True


def relocate_file(src: Path, dst: Path, repo_root: Path) -> None:
    """Move *src* to *dst*, preferring ``git mv`` to preserve history.

    Args:
        src: Current file path.
        dst: Destination file path.
        repo_root: Repository root for the ``git -C`` invocation.
    """
    dst.parent.mkdir(parents=True, exist_ok=True)
    if run_git(["mv", str(src), str(dst)], repo_root):
        return
    try:
        shutil.move(str(src), str(dst))
    except OSError as exc:
        print(f"{_HOOK_PREFIX} WARNING: could not move {src} to {dst}: {exc}", file=sys.stderr)
        raise


def remove_file(path: Path, repo_root: Path) -> None:
    """Delete *path*, preferring ``git rm`` to preserve history.

    Args:
        path: File to delete.
        repo_root: Repository root for the ``git -C`` invocation.
    """
    if run_git(["rm", "-f", str(path)], repo_root):
        return
    try:
        path.unlink()
    except OSError as exc:
        print(f"{_HOOK_PREFIX} WARNING: could not delete {path}: {exc}", file=sys.stderr)
        raise


def write_survivor(path: Path, content: str) -> None:
    """Write the merged survivor content to *path*.

    Args:
        path: Destination file path.
        content: Full text to write.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        print(f"{_HOOK_PREFIX} WARNING: could not write {path}: {exc}", file=sys.stderr)
        raise
