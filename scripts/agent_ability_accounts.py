"""
MODULE: agent_ability_accounts
GOAL: Recognise, in a markdown prompt or template body, every "account" of what
    an agent holds -- a structured section that NAMES installed skills, or the
    sub-agents it may dispatch -- while ignoring fenced examples elsewhere and
    prose that merely discusses the subject.
BUSINESS CONTEXT: AR-300a-1 / AR-300a-4 / AR-300a-4-i / AR-300a-5-i. Two checks
    need the same notion of "this text states what the agent holds": the
    delivery verifier (compiled prompts) and the in-place detector (source
    templates). AR-200b-1 recorded the cost of a looser rule -- a detector
    matching the bare word "skills" flagged most of the tree and was switched
    off -- so the rule is anchored on STRUCTURE, never on a word count. The
    sub-agent kind exists because a hand-written permission list is a second
    source of truth beside the delivered one, whether it is written as a table,
    a bulleted or numbered list, or a fenced list of ids.
ARCHITECTURE: ``find_accounts(text, known_ids, kind)`` walks the lines. A
    ``##``/``###`` heading whose text is about the kind (``abilities``: skill(s)/
    abilit*; ``sub-agents``: sub-agent(s) or a spawn allowlist) opens a candidate
    account that runs to the next heading of the same or higher level; table
    rows, list items and ``###``+ sub-headings inside it whose first token is a
    known id are the ids it NAMES. A candidate is an account when it names at
    least one id, or when its heading is the bare delivered one ("Your Available
    Skills", "Your Available Sub-Agents", ...). Code fences are ignored for the
    abilities kind; for the sub-agents kind a fenced run of ids INSIDE an open
    account counts as a list (ticket-supervisor wrote its permission that way),
    while fences outside an account stay ignored. Pure text computation (no I/O).
    Build-engine module under ``scripts/``; no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-09 [python-coder/AR-300a]: Created so the verifier and the detector
  share one account definition instead of two drifting copies. (#AR-300a-4)
- 2026-10-09 [python-coder/AR-300a-5-i]: ``find_accounts`` takes a ``kind`` so the
  one recogniser covers hand-written sub-agent tables AND lists instead of a
  parallel spawn detector; ``abilities`` behaviour is unchanged. (#AR-300a-5-i)
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
_SUB_HEADING_RE = re.compile(r"^#{2,3}\s+.*\b(?:sub-?agents?|spawn[\s_-]*allow\w*)\b", re.IGNORECASE)
_SUB_BARE_RE = re.compile(r"^#{2,3}\s+(?:your\s+)?(?:available\s+|permitted\s+)?sub-?agents?\s*$", re.IGNORECASE)
_SUB_ROW_RE = re.compile(r"^\s*(?:\||[-*]|\d+[.)])\s*[`*]*([a-z][a-z0-9_-]*)")
_FENCED_ITEM_RE = re.compile(r"^\s*(?:[-*]|\d+[.)])?\s*[`*]*([a-z][a-z0-9_-]*)")
# kind -> (heading, bare heading, item) patterns; only the sub-agent kind reads fenced lines.
_KINDS = {
    "abilities": (_SKILLISH_RE, _BARE_RE, _ROW_RE),
    "sub-agents": (_SUB_HEADING_RE, _SUB_BARE_RE, _SUB_ROW_RE),
}


def _walk(text: str) -> Iterator[tuple[str, bool]]:
    """Yield ``(line, fenced)`` for every line of ``text`` except the fence delimiters."""
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
        yield line, open_char is not None


def prose_lines(text: str) -> Iterator[str]:
    """Yield the lines of ``text`` that sit outside code fences."""
    for line, fenced in _walk(text):
        if not fenced:
            yield line


def _close_ended(found: list[dict[str, Any]], current: dict[str, Any] | None, level: int) -> dict[str, Any] | None:
    """Move ``current`` to ``found`` when a heading of the same or higher level ends it; return what stays open."""
    if current is not None and level <= current["level"]:
        found.append(current)
        return None
    return current


def _opened(line: str, level: int, heading_re: re.Pattern[str], bare_re: re.Pattern[str]) -> dict[str, Any] | None:
    """Return a new candidate account when ``line`` is a ``##``/``###`` heading about the kind, else None."""
    if 2 <= level <= 3 and heading_re.match(line):
        return {"heading": line.strip(), "level": level, "ids": [], "bare": bool(bare_re.match(line))}
    return None


def _named_id(line: str, fenced: bool, item_re: re.Pattern[str]) -> str | None:
    """Return the first-token id of a table row / list item / sub-heading (or fenced list line), else None."""
    named = _FENCED_ITEM_RE.match(line) if fenced else (item_re.match(line) or _SUBHEAD_RE.match(line))
    return named.group(1) if named else None


def find_accounts(text: str, known_ids: set[str], kind: str = "abilities") -> list[dict[str, Any]]:
    """Return every account of ``kind`` in ``text`` as ``{heading, level, ids, bare}``.

    Args:
        text: A compiled prompt or a source template body.
        known_ids: Installed skill ids (``abilities``) or agent ids
            (``sub-agents``); only these count as NAMED.
        kind: ``"abilities"`` (default) or ``"sub-agents"``.

    Returns:
        One dict per account, in document order; ``ids`` lists the known ids the
        account names (with repeats), ``bare`` is True for the bare delivered
        heading.
    """
    heading_re, bare_re, item_re = _KINDS[kind]
    fenced_items = kind == "sub-agents"
    found: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line, fenced in _walk(text):
        heading = None if fenced else _HEADING_RE.match(line)
        if heading:
            current = _close_ended(found, current, len(heading.group(1)))
            if current is None:
                current = _opened(line, len(heading.group(1)), heading_re, bare_re)
                continue
        if current is None or (fenced and not fenced_items):
            continue
        sid = _named_id(line, fenced, item_re)
        if sid in known_ids:
            current["ids"].append(sid)
    if current is not None:
        found.append(current)
    return [a for a in found if a["ids"] or a["bare"]]
