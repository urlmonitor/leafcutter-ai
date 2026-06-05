"""
context_file_maintenance.py — Context file maintenance for leafcutter-ai.

Provides functions for creating and maintaining component README.md files and
skill-scoped PROJECT_CONTEXT.md files. Both file types accumulate entries in
reverse-chronological order (newest first) with date headings and agent
attribution. A summary section is auto-generated when an entry count threshold
is exceeded.

Called by harvest_learnings.py during its write phase for entry_kinds:
  - "per-folder-readme"  → component README.md files
  - "skill-context"      → skill PROJECT_CONTEXT.md files

Usage
-----
    from scripts.knowledge.context_file_maintenance import (
        create_readme,
        append_entry,
        generate_summary,
        CONTEXT_FILENAME,
    )
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("context_file_maintenance")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Canonical filename for skill-scoped context files.
#: MUST be uppercase with underscore separator per agent_knowledge_system.md §2.1.
CONTEXT_FILENAME: str = "PROJECT_CONTEXT.md"

#: Entry count threshold above which a summary section is generated / refreshed.
SUMMARY_THRESHOLD: int = 15

#: Regex that matches an entry heading line of the form "## YYYY-MM-DD — <agent>"
_ENTRY_HEADING_RE = re.compile(r"^## \d{4}-\d{2}-\d{2} — .+$", re.MULTILINE)

#: Sentinel marker for the summary section heading
_SUMMARY_HEADING = "## Summary"

#: Separator used between the header block and the first entry
_SECTION_SEP = "\n\n---\n\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def create_readme(path: Path, component: str) -> None:
    """Create a component README.md with the standard header if it does not exist.

    If the file already exists, this function is a no-op (idempotent).

    Args:
        path:       Destination path for the README.md file.
        component:  Component name used in the standard header line, e.g.
                    "infrastructure".

    Raises:
        OSError: If the directory cannot be created or the file cannot be written.
    """
    if path.exists():
        return

    header = f"# {component} — domain conventions"
    content = f"{header}\n\nThis file accumulates domain conventions, naming patterns, and standing rules\nobserved by agents working in the {component!r} component.\n"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    except OSError as exc:
        logger.warning("Failed to create README at %s: %s", path, exc)
        raise


def append_entry(path: Path, date: str, agent: str, text: str) -> None:
    """Append a dated, agent-attributed entry to a context file.

    Entries are stored in reverse-chronological order — the newest entry is
    inserted immediately after the file header block (before any existing entries).
    Each entry is limited to 5 lines of text.

    If the destination file does not yet exist, it is created with a minimal
    header before the entry is appended.

    Args:
        path:   Path to the context file (README.md or PROJECT_CONTEXT.md).
        date:   ISO-8601 date string for the entry heading, e.g. "2026-06-05".
        agent:  Name of the agent that discovered the learning, e.g. "python-coder".
        text:   Learning text (must be at most 5 lines).

    Raises:
        ValueError: If *text* exceeds 5 lines.
        OSError:    If the file cannot be read or written.
    """
    text_lines = text.strip().splitlines()
    if len(text_lines) > 5:
        raise ValueError(  # noqa: TRY003
            f"Entry text exceeds 5-line limit ({len(text_lines)} lines)"
        )

    entry_text = text.strip()
    new_entry = f"## {date} — {agent}\n{entry_text}\n"

    if not path.exists():
        # Auto-create with a minimal header rather than failing
        component = path.stem  # best-effort: use filename without extension
        try:
            create_readme(path=path, component=component)
        except OSError as exc:
            logger.warning("Cannot auto-create context file at %s: %s", path, exc)
            raise

    try:
        existing = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read context file %s: %s", path, exc)
        raise

    updated = _insert_entry_after_header(existing, new_entry)

    entry_count = len(_ENTRY_HEADING_RE.findall(updated))
    if entry_count > SUMMARY_THRESHOLD:
        updated = _regenerate_summary(updated, entry_count)

    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot write context file %s: %s", path, exc)
        raise


def generate_summary(path: Path) -> None:
    """Regenerate the summary section in *path* based on its current entries.

    Reads the file, counts entries, and rewrites the summary block. If the entry
    count is at or below ``SUMMARY_THRESHOLD``, any existing summary is removed.
    Idempotent: running twice with no new entries produces the same file.

    Args:
        path: Path to the context file.

    Raises:
        OSError: If the file cannot be read or written.
    """
    if not path.exists():
        return

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot read context file %s for summary generation: %s", path, exc)
        raise

    entry_count = len(_ENTRY_HEADING_RE.findall(content))
    updated = _regenerate_summary(content, entry_count)

    try:
        path.write_text(updated, encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot write updated context file %s: %s", path, exc)
        raise


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _insert_entry_after_header(content: str, new_entry: str) -> str:
    """Insert *new_entry* immediately after the file header block.

    The header block is everything up to (but not including) the first entry
    heading (``## YYYY-MM-DD — agent``). The new entry becomes the first entry,
    pushing existing entries further down — reverse-chronological order.

    If no entry headings exist yet, the new entry is appended to the end.

    Args:
        content:    Current file content.
        new_entry:  Formatted entry string (heading + body).

    Returns:
        Updated file content with the new entry inserted.
    """
    match = _ENTRY_HEADING_RE.search(content)
    if match is None:
        # No existing entries — append after stripping trailing whitespace
        base = content.rstrip()
        return f"{base}\n\n{new_entry}"

    insert_pos = match.start()
    # Separate header from the entries block
    header_block = content[:insert_pos].rstrip()
    entries_block = content[insert_pos:]
    return f"{header_block}\n\n{new_entry}\n{entries_block}"


def _regenerate_summary(content: str, entry_count: int) -> str:
    """Rebuild (or remove) the ``## Summary`` block in *content*.

    When entry_count > SUMMARY_THRESHOLD, a summary block listing the count
    and the most recent entry date is inserted immediately after the first
    heading line (the ``# Component — domain conventions`` or similar title).

    When entry_count <= SUMMARY_THRESHOLD, any existing summary block is stripped.

    Args:
        content:     Current file text.
        entry_count: Number of entry headings already counted.

    Returns:
        Updated file text.
    """
    # Strip any existing summary block first
    content = _strip_existing_summary(content)

    if entry_count <= SUMMARY_THRESHOLD:
        return content

    # Find most recent entry date (first match in the updated content)
    date_match = _ENTRY_HEADING_RE.search(content)
    most_recent = ""
    if date_match:
        # Extract date portion: "## 2026-06-05 — agent" → "2026-06-05"
        heading_text = date_match.group(0)
        date_part = heading_text.split("##")[1].strip().split(" — ")[0]
        most_recent = date_part

    summary_block = (
        f"{_SUMMARY_HEADING}\n"
        f"This file contains **{entry_count} entries**"
        + (f" (most recent: {most_recent})" if most_recent else "")
        + ".\n"
        "Entries are in reverse-chronological order.\n"
    )

    # Insert summary after the first title heading (first line starting with "# ")
    lines = content.splitlines(keepends=True)
    insert_after = 0
    for i, line in enumerate(lines):
        if line.startswith("# "):
            insert_after = i + 1
            break

    # Skip any blank lines immediately after the title
    while insert_after < len(lines) and lines[insert_after].strip() == "":
        insert_after += 1

    before = "".join(lines[:insert_after])
    after = "".join(lines[insert_after:])
    return f"{before.rstrip()}\n\n{summary_block}\n{after.lstrip()}"


def _strip_existing_summary(content: str) -> str:
    """Remove an existing ``## Summary`` block from *content*.

    The block extends from the ``## Summary`` heading up to (but not including)
    the next ``##``-level heading or the end of file.

    Args:
        content: File text that may or may not contain a summary block.

    Returns:
        File text with the summary block removed (or unchanged if none present).
    """
    if _SUMMARY_HEADING not in content:
        return content

    # Match the Summary section: from heading to next ## heading (exclusive)
    pattern = re.compile(
        r"## Summary\n.*?(?=\n## |\Z)",
        re.DOTALL,
    )
    cleaned = pattern.sub("", content)
    # Normalise multiple blank lines left behind
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned
