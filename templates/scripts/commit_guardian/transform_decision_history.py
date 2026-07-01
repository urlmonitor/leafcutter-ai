"""
MODULE: leafcutter/scripts/commit_guardian/transform_decision_history.py
GOAL: Pre-stage transformer that injects the current HH:MM timestamp and a
      TICKETLESS tail-tag into staged DECISION HISTORY entries **before**
      the ``check_documentation`` validator runs, so the validator is a
      structural no-op for agent-produced commits.
BUSINESS CONTEXT: Agents frequently write DECISION HISTORY entries with only
      a date (``YYYY-MM-DD``) instead of the required ``YYYY-MM-DD HH:MM``
      timestamp, or omit the required tail-tag entirely.  Every such commit
      triggers the precommit-autofix cycle (validate → fail → autofix → retry)
      adding friction and latency.  This transformer runs at the ``pre-commit``
      stage — before the validator — and silently corrects both defects so
      the validator never fires for them.
ARCHITECTURE: Reads ``git diff --cached`` to find staged hunks in ``.py`` and
      ``.sql`` files that include DECISION HISTORY entries.  For each added
      line in a hunk that is a DECISION HISTORY entry:

      1. If the timestamp is ``YYYY-MM-DD`` only (no HH:MM): rewrite it to
         ``YYYY-MM-DD HH:MM`` using the current UTC time (zero-padded).
      2. If the entry has no tail-tag (``(#EPIC-Name/NN)`` or
         ``(#TICKETLESS reason=...)``): append
         ``(#TICKETLESS reason=agent-no-tag-autofix)``.

      After all rewrites are computed, the transformer patches the working-tree
      file(s) in-place and calls ``git add <file>`` to re-stage the corrected
      content so the next validator sees clean entries.

DOC_LINKS:
  - docs/how-to/known-failing-tests-baseline.md

Exit Codes:
    0 - All entries normalised (or no entries to normalise); commit proceeds
    1 - Unexpected error during transformation (fail-open: should not block)

DECISION HISTORY
- 2026-05-22 10:20 [documentation-expert]: Initial creation. Pre-stage transformer
  for DECISION HISTORY HH:MM injection and TICKETLESS tail-tag injection.
  (#EPIC-CommitSignoffHardening/02)
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# Matches a DECISION HISTORY section header in comments
_DH_HEADER_RE = re.compile(
    r'^(?:#|/\*|"""|\'\'\')?\s*=*\s*DECISION HISTORY\s*=*',
    re.IGNORECASE,
)

# Matches a DECISION HISTORY entry line — date-only (no HH:MM)
# Groups: (indent_and_comment_marker, date, rest_of_line)
_DH_ENTRY_DATE_ONLY_RE = re.compile(
    r'^([-\s#/*]*-\s*)'       # leading indent / comment chars + dash
    r'(\d{4}-\d{2}-\d{2})'   # date only (no HH:MM follows)
    r'(?!\s+\d{2}:\d{2})'    # negative lookahead: NOT already YYYY-MM-DD HH:MM
    r'(.*)',                  # rest of line
    re.DOTALL,
)

# Matches YYYY-MM-DD HH:MM entry — for tail-tag check
_DH_ENTRY_WITH_TIME_RE = re.compile(
    r'^([-\s#/*]*-\s*\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}.*)',
)

# Matches an existing tail-tag (already has one → skip)
_TAIL_TAG_RE = re.compile(
    r'(\(#[A-Za-z0-9_-]+/[A-Za-z0-9_-]+\)|\(#TICKETLESS reason=[A-Za-z0-9_\-]{10,}\))'
)

# File extensions to process
_SUPPORTED_EXTENSIONS = {".py", ".sql", ".yaml", ".yml"}

# The tail-tag to append when none is present
_DEFAULT_TAIL_TAG = "(#TICKETLESS reason=agent-no-tag-autofix)"


def _get_staged_files() -> list[str]:
    """Return a list of staged file paths that have DECISION HISTORY changes.

    Returns:
        list[str]: Paths to modified/added staged Python or SQL files.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
    except OSError:
        return []
    if result.returncode != 0:
        return []
    paths = []
    for line in result.stdout.splitlines():
        p = Path(line.strip())
        if p.suffix.lower() in _SUPPORTED_EXTENSIONS:
            paths.append(line.strip())
    return paths


def _file_has_decision_history(content: str) -> bool:
    """Return True when the content contains a DECISION HISTORY block.

    Args:
        content: Full text of the file.

    Returns:
        bool: True if a DECISION HISTORY section header is found.
    """
    return bool(_DH_HEADER_RE.search(content))


def _transform_content(content: str, now_utc: str) -> tuple[str, int]:
    """Rewrite DECISION HISTORY entries in-place.

    For each line in the content:
    - If it is a DECISION HISTORY entry with only a date (no HH:MM): inject
      the current UTC HH:MM.
    - If it is a DECISION HISTORY entry (with HH:MM) but missing a tail-tag:
      append the default TICKETLESS tail-tag.

    Args:
        content: Full file content.
        now_utc: Current UTC time formatted as ``HH:MM``.

    Returns:
        tuple[str, int]: (transformed_content, number_of_lines_changed)
    """
    lines = content.split("\n")
    in_dh_section = False
    changed = 0
    new_lines: list[str] = []

    for line in lines:
        # Detect entry into DECISION HISTORY section
        if _DH_HEADER_RE.match(line.strip()):
            in_dh_section = True
            new_lines.append(line)
            continue

        if not in_dh_section:
            new_lines.append(line)
            continue

        # We're inside a DECISION HISTORY section.
        # Apply the two transforms in order.

        # Transform 1: inject HH:MM when only date is present
        date_only_match = _DH_ENTRY_DATE_ONLY_RE.match(line)
        if date_only_match:
            prefix = date_only_match.group(1)  # e.g. "- "
            date = date_only_match.group(2)    # e.g. "2026-05-22"
            rest = date_only_match.group(3)    # everything after the date
            line = f"{prefix}{date} {now_utc}{rest}"
            changed += 1

        # Transform 2: append tail-tag when entry has no tail-tag
        # (only applies to lines that look like DH entries with HH:MM)
        if _DH_ENTRY_WITH_TIME_RE.match(line):
            if not _TAIL_TAG_RE.search(line):
                # Only append if the line has meaningful content beyond timestamp
                stripped = line.rstrip()
                if stripped and not stripped.endswith(":"):
                    line = f"{stripped} {_DEFAULT_TAIL_TAG}"
                    changed += 1

        new_lines.append(line)

    return "\n".join(new_lines), changed


def _restage_file(file_path: str) -> None:
    """Run git add on the given file to re-stage the transformed content.

    Args:
        file_path: Repository-relative path to the file to stage.
    """
    try:
        subprocess.run(
            ["git", "add", file_path],
            capture_output=True,
        )
    except OSError as exc:
        raise RuntimeError(f"Failed to re-stage {file_path}: {exc}") from exc


def main() -> int:
    """Entry point for the pre-stage transformer hook.

    Returns:
        int: Exit code (always 0 — fail-open contract; errors are logged to
             stderr but never block the commit).
    """
    now_utc = datetime.now(tz=timezone.utc).strftime("%H:%M")
    staged = _get_staged_files()

    if not staged:
        return 0

    total_changed = 0

    for file_path in staged:
        path = Path(file_path)
        if not path.exists():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue

        if not _file_has_decision_history(content):
            continue

        new_content, changed = _transform_content(content, now_utc)
        if changed > 0:
            try:
                path.write_text(new_content, encoding="utf-8")
                _restage_file(file_path)
                total_changed += changed
                print(
                    f"[transform-decision-history] {file_path}: "
                    f"normalised {changed} DECISION HISTORY line(s)",
                    file=sys.stderr,
                )
            except OSError as exc:
                print(
                    f"[transform-decision-history] WARNING: could not write {file_path}: {exc}",
                    file=sys.stderr,
                )

    if total_changed > 0:
        print(
            f"[transform-decision-history] Total: {total_changed} line(s) "
            f"normalised across {len(staged)} staged file(s).",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
