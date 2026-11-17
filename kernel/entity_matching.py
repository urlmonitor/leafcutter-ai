"""MODULE: kernel.entity_matching
GOAL: Deterministic Unicode-aware exact matching over permitted index names.
BUSINESS CONTEXT: Ordinary prose is not a retrieval query and frequency adds no relevance.
ARCHITECTURE: One folded trie scan plus explicit-reference syntax, then typed deduplication.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Literal

from kernel.contracts.entity_context import EntityMatch, Family
from kernel.entity_records import IndexEntry

_EXPLICIT = re.compile(r"(?<![\w/])(?:[\w./-]+\.[A-Za-z]+::[\w.]+|[A-Z]{2,6}(?:-[A-Z]{2,6})?-\d[\w-]*|dec-[\w-]+)(?!\w)")
_TYPED = re.compile(r"\b(flow|ticket)\s*:\s*[`'\"]?([^\s`'\"<>(),;!?]+)", re.IGNORECASE)


@dataclass
class Candidate:
    """A distinct permitted lookup candidate with all admitted mention positions."""

    family: Family
    reference: str
    entries: list[IndexEntry] = field(default_factory=list)
    matches: list[EntityMatch] = field(default_factory=list)
    priority: int = 1
    order: int = 0
    state: Literal["unknown_id", "invalid_reference", "unsupported_kind"] | None = None


def _word(char: str) -> bool:
    """Use Unicode identifier continuation boundaries, including combining marks."""
    return bool(char) and (char.isalnum() or char == "_" or ("a" + char).isidentifier())


def _fold(text: str) -> tuple[str, list[int]]:
    """Casefold while preserving original offsets when one code point expands."""
    pieces, positions = [], []
    for offset, char in enumerate(text):
        folded = char.casefold()
        pieces.append(folded)
        positions.extend([offset] * len(folded))
    return "".join(pieces), positions


def _cued(text: str, start: int, end: int, family: str, alias: bool) -> bool:
    """Generic vocabulary words require a declaration cue; aliases are owner-approved."""
    if family == "native_kind":
        surface = text[start:end]
        if end < len(text) and text[end] in "-/":
            return False
        return alias or bool(re.search(r"native_kind\s*:\s*$", text[:start], re.IGNORECASE)) or (
            any(c.isupper() for c in surface[1:]) and any(c.islower() for c in surface))
    if family not in {"doc_type", "entry_kind"} or alias:
        return True
    before, after = text[:start], text[end:]
    cue = r"(?:doc_type|type)\s*:\s*[`'\"]?$" if family == "doc_type" else r"entry_kind\s*:\s*[`'\"]?$"
    return bool(re.search(cue, before, re.IGNORECASE) or
                family == "doc_type" and re.match(r"\s+(?:document|doc)\b", after, re.IGNORECASE))


def _trie(entries: list[IndexEntry], deadline: float) -> dict | None:
    """Build exact-name transitions; no source lookup occurs here."""
    trie: dict = {}
    for entry in entries:
        if time.monotonic() >= deadline:
            return None
        for name in entry.names:
            node = trie
            for char in name.casefold():
                node = node.setdefault(char, {})
            node.setdefault(None, []).append((name, entry))
    return trie


def _hits(text: str, trie: dict, deadline: float) -> tuple[list[tuple], bool]:
    """Scan every admitted code point, keeping exact owner casing and longest phrases."""
    folded, offsets = _fold(text)
    found: list[tuple] = []
    for start in range(len(folded)):
        if time.monotonic() >= deadline:
            return found, False
        original = offsets[start]
        if (start and offsets[start - 1] == original) or (original and _word(text[original - 1])):
            continue
        found.extend(_at_offset(text, folded, offsets, trie, start))
    # Per-family left-to-right longest matching; namespaces never suppress one another.
    accepted: list[tuple] = []
    occupied: dict[str, tuple[int, int]] = {}
    for hit in sorted(found, key=lambda row: (row[0], -(row[1] - row[0]), row[2], row[4].identity)):
        start, end, family, _, _ = hit
        prior = occupied.get(family)
        if prior and start < prior[1] and (start, end) != prior:
            continue
        occupied[family] = (start, end)
        accepted.append(hit)
    return accepted, True


def _at_offset(text: str, folded: str, offsets: list[int], trie: dict, start: int) -> list[tuple]:
    """Resolve the trie at one original identifier boundary."""
    node, end, found = trie, start, []
    original = offsets[start]
    while end < len(folded) and folded[end] in node:
        node = node[folded[end]]
        end += 1
        stop = offsets[end - 1] + 1
        if end < len(offsets) and offsets[end] == offsets[end - 1]:
            continue
        if stop < len(text) and _word(text[stop]):
            continue
        for name, entry in node.get(None, []):
            surface = text[original:stop]
            if entry.family in {"symbol", "artifact_id"} and name != surface:
                continue
            if _identity_boundary(text, original, stop, entry.family) and _cued(
                    text, original, stop, entry.family, name in entry.aliases):
                found.append((original, stop, entry.family, surface, entry))
    return found


def _identity_boundary(text: str, start: int, end: int, family: str) -> bool:
    """An artifact reference must consume its complete native token, never a known prefix."""
    if family != "artifact_id":
        return True
    if start and text[start - 1] in "-/":
        return False
    if end < len(text) and text[end] in "-/":
        return False
    return not (end + 1 < len(text) and text[end] == "." and _word(text[end + 1]))


def _unknown_state(reference: str, patterns: dict[str, str], owner: str | None = None
                   ) -> tuple[Family, Literal["unknown_id", "invalid_reference", "unsupported_kind"]]:
    """Distinguish explicit unsupported symbols and owner-invalid/absent identifiers."""
    if "::" in reference:
        return "symbol", "unknown_id" if ".py::" in reference else "unsupported_kind"
    pattern = patterns.get(owner) if owner else (r"dec-[0-9a-f]{16}" if reference.startswith("dec-") else
               r"ADR-\d+" if reference.startswith("ADR-") else patterns.get("AcceptanceCriterion"))
    valid = pattern is not None and re.fullmatch(pattern, reference) is not None and ".." not in reference.split("/")
    return "artifact_id", "unknown_id" if valid else "invalid_reference"


def _explicit_references(text: str) -> list[tuple[int, int, str, str | None]]:
    """Owner cues admit path identities without treating ordinary slash prose as references."""
    typed = [(m.start(2), m.end(2), m[2], m[1].title()) for m in _TYPED.finditer(text)]
    plain = [(m.start(), m.end(), m[0], None) for m in _EXPLICIT.finditer(text)
             if not any(start <= m.start() < end for start, end, _, _ in typed)]
    return sorted([*typed, *plain])


def _add_unknowns(text: str, known: set, groups: dict, patterns: dict, channel: str,
                  record_index: int | None, order: int) -> int:
    """Record one complete explicit reference and its owner-specific syntax outcome."""
    for start, _, raw, owner in _explicit_references(text):
        reference = raw.rstrip(".")
        end = start + len(reference)
        if (start, end) in known:
            continue
        family, state = _unknown_state(reference, patterns, owner)
        candidate = groups.setdefault((family, reference), Candidate(family, reference, priority=0,
                                                                      order=order, state=state))
        candidate.matches.append(EntityMatch(channel=channel, record_index=record_index,
            start=start, end=end, surface=reference))
        order += 1
    return order


def scan_candidates(channels: list[tuple[str, int | None, str]], entries: list[IndexEntry],
                    patterns: dict[str, str], deadline: float) -> tuple[list[Candidate], bool]:
    """Scan full goal before bounded caller text and deduplicate lookup candidates."""
    trie = _trie(entries, deadline)
    if trie is None:
        return [], False
    groups: dict[tuple, Candidate] = {}
    order = 0
    for channel, record_index, text in channels:
        hits, complete = _hits(text, trie, deadline)
        by_span: dict[tuple, list[IndexEntry]] = {}
        for start, end, family, surface, entry in hits:
            by_span.setdefault((start, end, family, surface), []).append(entry)
        for (start, end, family, surface), matching in by_span.items():
            identities = tuple(sorted({entry.identity for entry in matching}))
            key = (family, identities)
            priority = 0 if family == "artifact_id" or family == "symbol" and ("." in surface or "::" in surface) else 2 if family == "symbol" else 1
            candidate = groups.setdefault(key, Candidate(family, surface, matching, priority=priority, order=order))
            candidate.priority = min(candidate.priority, priority)
            mention = EntityMatch(channel=channel, record_index=record_index, start=start, end=end, surface=surface)
            if mention not in candidate.matches:
                candidate.matches.append(mention)
            order += 1
        known = {(start, end) for start, end, _, _ in by_span}
        if complete:
            order = _add_unknowns(text, known, groups, patterns, channel, record_index, order)
        if not complete:
            return list(groups.values()), False
    return sorted(groups.values(), key=lambda c: (c.priority, c.matches[0].channel != "goal",
                                                   c.matches[0].start, c.order, c.family, c.reference)), True

# DECISION HISTORY
# ================================================================================
# - 2026-10-03 15:05 [python-coder]: Keep pre-intent meanings deterministic, scoped and separate from task evidence. (#TICKETLESS reason=user-approved-ac-first-DK300)
# - 2026-10-03 15:30 [python-coder]: Normalize punctuation before excluding known spans so one symbol consumes one lookup. (#DK-300/entity-context)
# - 2026-10-03 17:00 [python-coder]: Require whole artifact identities and explicit owner cues for unknown Flow or Ticket path references. (#DK-300/entity-context)
