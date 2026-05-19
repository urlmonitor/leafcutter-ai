"""
MODULE: doc_length_helpers
GOAL: Helper functions for AUTOFIX_AGENT dispatch in check_doc_length.py.
BUSINESS CONTEXT: Extracted from check_doc_length.py to stay under the 400-line
    budget. Provides frontmatter type extraction and doc_types.json writer-agent
    lookup used by the AUTOFIX_AGENT hint mechanism.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - docs/architecture/adrs/ADR-006-agent-model-tiers.md
"""

import json
import re
from pathlib import Path

# YAML frontmatter regex — must stay in sync with check_doc_length._FRONTMATTER_RE
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)


def read_frontmatter_type(content: str) -> str | None:
    """Extract the ``type:`` field from YAML frontmatter before it is stripped.

    Parses the raw frontmatter block matched by ``_FRONTMATTER_RE`` and returns
    the value of the ``type:`` key, or ``None`` if the key is absent or if the
    file has no frontmatter.

    Args:
        content: Full file content as a string (before any stripping).

    Returns:
        str | None: The doc type string (e.g. ``'reference'``, ``'how_to'``),
            or ``None`` when the key is missing or frontmatter is absent.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None
    frontmatter_block = match.group(0)
    # Use [^\S\n]* (horizontal whitespace only) so \s* does not consume the
    # newline and incorrectly match the closing '---' as part of the value.
    type_match = re.search(r"^type:[^\S\n]*(.+)$", frontmatter_block, re.MULTILINE)
    if not type_match:
        return None
    value = type_match.group(1).strip()
    value = value.strip("'\"")
    return value if value else None


def lookup_writer_agent(doc_type: str | None, doc_types_path: Path) -> str:
    """Return the writer agent name for a doc type, with safe fallbacks.

    Reads ``doc_types_path`` (a JSON file) and looks up ``doc_type`` in the
    ``doc_types`` map.  Falls back to ``documentation-expert`` whenever:

    * ``doc_type`` is ``None``.
    * ``doc_type`` is not a key in ``doc_types``.
    * The ``writer_agent`` value for the entry is ``None``.
    * ``doc_types_path`` is absent or cannot be parsed.

    Args:
        doc_type: The frontmatter ``type:`` value, or ``None`` when absent.
        doc_types_path: Absolute (or CWD-relative) path to ``doc_types.json``.

    Returns:
        str: The agent name to dispatch to (never ``None``).
    """
    fallback = "documentation-expert"
    if doc_type is None:
        return fallback
    try:
        data = json.loads(doc_types_path.read_text(encoding="utf-8"))
        entry = data.get("doc_types", {}).get(doc_type)
        if entry is None:
            return fallback
        agent = entry.get("writer_agent")
        return agent if agent else fallback
    except (OSError, json.JSONDecodeError, AttributeError):
        return fallback


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-14 09:45 [ticket-11]: Created as helper module extracted (#EPIC-LeafcutterMVP/01)
  from check_doc_length.py to stay under the 400-line code budget.
  Contains read_frontmatter_type() and lookup_writer_agent() for
  the AUTOFIX_AGENT hint dispatch mechanism.
====================================================================
"""
