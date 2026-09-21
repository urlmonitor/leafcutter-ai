"""
MODULE: scripts.ac_store._xref_tickets
GOAL: Load and parse "done" tickets so cross_reference_audit.py has something
    to match AC records against.
BUSINESS CONTEXT: The audit's matching passes need each done ticket's title,
    components, and Acceptance Criteria section text. This module owns
    deciding which tickets count as "done" (by lifecycle folder or
    frontmatter status) and extracting the frontmatter and AC-section text
    those matching passes read.
ARCHITECTURE: Sibling module to cross_reference_audit.py inside
    scripts/ac_store/. It is never executed directly; cross_reference_audit.py
    imports it via the bare-import sys.path bootstrap documented in that
    module's header, so this file works whether the entry point is run as a
    script or imported as a package.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

_log = logging.getLogger(__name__)

# Lifecycle folders whose tickets are considered "done" even without status: done
_DONE_FOLDER_MARKERS: frozenset[str] = frozenset({"99_done"})


def _is_done_ticket(ticket_path: Path, ticket_text: str) -> bool:
    """Return True if the ticket is 'done' by folder name or frontmatter status."""
    # Check if any parent folder name is a done-marker
    for part in ticket_path.parts:
        if part in _DONE_FOLDER_MARKERS:
            return True
    # Parse frontmatter for status: done
    if ticket_text.startswith("---"):
        end = ticket_text.find("\n---", 3)
        if end != -1:
            fm_text = ticket_text[3:end]
            try:
                fm = yaml.safe_load(fm_text)
                if isinstance(fm, dict) and fm.get("status") == "done":
                    return True
            except yaml.YAMLError:
                pass
    return False


def _extract_ticket_frontmatter(ticket_text: str) -> dict[str, Any]:
    """Extract YAML frontmatter from a ticket file."""
    if ticket_text.startswith("---"):
        end = ticket_text.find("\n---", 3)
        if end != -1:
            try:
                fm = yaml.safe_load(ticket_text[3:end])
                return fm if isinstance(fm, dict) else {}
            except yaml.YAMLError:
                pass
    return {}


def _extract_acceptance_criteria_section(ticket_text: str) -> str:
    """Extract text of the ## Acceptance Criteria section from a ticket body."""
    # Find the section header
    marker = "## Acceptance Criteria"
    idx = ticket_text.find(marker)
    if idx == -1:
        return ""
    # Extract until the next ## section or end of file
    start = idx + len(marker)
    next_section = ticket_text.find("\n## ", start)
    if next_section != -1:
        return ticket_text[start:next_section].strip()
    return ticket_text[start:].strip()


def _load_done_tickets(tickets_root: Path) -> list[dict[str, Any]]:
    """Load all done tickets from the tickets root directory.

    Returns a list of dicts with: path, title, components, ac_section.
    Skips files that cannot be read.
    """
    tickets: list[dict[str, Any]] = []
    if not tickets_root.exists():
        _log.warning("Tickets root does not exist: %s", tickets_root)
        return tickets

    for md_path in sorted(tickets_root.rglob("*.md")):
        try:
            ticket_text = md_path.read_text(encoding="utf-8")
        except OSError as exc:
            _log.warning("Cannot read ticket %s: %s", md_path, exc)
            continue

        if not _is_done_ticket(md_path, ticket_text):
            continue

        fm = _extract_ticket_frontmatter(ticket_text)
        title = fm.get("title", md_path.stem)
        components = fm.get("components", [])
        if isinstance(components, str):
            components = [components]
        ac_section = _extract_acceptance_criteria_section(ticket_text)

        tickets.append(
            {
                "path": str(md_path),
                "title": title,
                "components": components,
                "ac_section": ac_section,
            }
        )
    return tickets


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: Extracted from cross_reference_audit.py into this
  module (ticket loading/parsing) as part of the file-size split required by
  check-file-size (GE-127b-1) — the source file had grown to 557 content
  lines against the 400-line limit. Moved verbatim; no behaviour changed.
====================================================================
"""
