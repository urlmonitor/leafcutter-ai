"""
MODULE: agent_ability_accounts
GOAL: Recognise, in a markdown prompt or template body, every "account" of an
    agent's abilities -- a structured section that NAMES installed skills --
    while ignoring fenced examples and prose that merely discusses skills.
BUSINESS CONTEXT: AR-300a-1 / AR-300a-4 / AR-300a-4-i. Two checks need the same
    notion of "this text states which abilities the agent holds": the delivery
    verifier (compiled prompts) and the in-place detector (source templates).
    AR-200b-1 recorded the cost of a looser rule -- a detector matching the bare
    word "skills" flagged most of the tree and was switched off -- so the rule is
    anchored on STRUCTURE, never on a word count.
ARCHITECTURE: ``find_accounts(text, known_ids)`` walks the lines outside code
    fences. A ``##``/``###`` heading whose text mentions skill(s)/abilit* opens a
    candidate account that runs to the next heading of the same or higher level;
    table rows, list items and ``###``+ sub-headings inside it whose first token
    is an installed skill id are the ids it NAMES. A candidate is an account when
    it names at least one id, or when its heading is the bare delivered one
    ("Your Available Skills", "Abilities", ...). Pure text computation (no I/O).
    Build-engine module under ``scripts/``; no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300a]: Created so the verifier and the detector
  share one account definition instead of two drifting copies. (#AR-300a-4)
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^(#{1,6})\s+\S")
_SKILLISH_RE = re.compile(r"^#{2,3}\s+.*\b(abilit\w*|skills?)\b", re.IGNORECASE)
_BARE_RE = re.compile(r"^#{2,3}\s+(?:your\s+)?(?:available\s+)?(?:skills?|abilit(?:y|ies))\s*$", re.IGNORECASE)
_ROW_RE = re.compile(r"^\s*(?:\||[-*])\s*[`*]*([a-z][a-z0-9_-]*)")
# A sub-heading names an ability only when the id IS the heading (``### write-c4-diagram``,
# optionally followed by a separator and a note) -- ``### webapp-testing skill`` is prose
# about the skill, not a row of the grant.
_SUBHEAD_RE = re.compile(r"^#{3,6}\s+[`*]*([a-z][a-z0-9_-]*)[`*]*\s*(?:[:—–-].*)?$")


def prose_lines(text: str) -> Iterator[str]:
    """Yield the lines of ``text`` that sit outside code fences."""
    open_char = None
    for line in text.splitlines():
        fence = _FENCE_RE.match(line)
        if fence:
            char = fence.group(1)[0]
            if open_char is None:
                open_char = char
                continue
            if char == open_char:
                open_char = None
                continue
        if open_char is None:
            yield line


def find_accounts(text: str, known_ids: set[str]) -> list[dict[str, Any]]:
    """Return every account of abilities in ``text`` as ``{heading, level, ids, bare}``.

    Args:
        text: A compiled prompt or a source template body.
        known_ids: Installed skill ids; only these count as NAMED abilities.

    Returns:
        One dict per account, in document order; ``ids`` lists the installed
        skill ids the account names (with repeats), ``bare`` is True for the
        bare delivered heading.
    """
    found: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in prose_lines(text):
        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            if current is not None and level <= current["level"]:
                found.append(current)
                current = None
            if current is None:
                if 2 <= level <= 3 and _SKILLISH_RE.match(line):
                    current = {"heading": line.strip(), "level": level, "ids": [],
                               "bare": bool(_BARE_RE.match(line))}
                continue
        if current is not None:
            named = _ROW_RE.match(line) or _SUBHEAD_RE.match(line)
            if named and named.group(1) in known_ids:
                current["ids"].append(named.group(1))
    if current is not None:
        found.append(current)
    return [a for a in found if a["ids"] or a["bare"]]
