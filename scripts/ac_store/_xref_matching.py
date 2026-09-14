"""
MODULE: scripts.ac_store._xref_matching
GOAL: Run the two-pass heuristic that decides whether an AC and a done ticket
    describe the same piece of work.
BUSINESS CONTEXT: cross_reference_audit.py needs to tell, for each todo AC,
    whether some already-done ticket already implemented it. Pass 1 looks for
    near-identical Acceptance Criteria text (confidence: high, AC-1). Pass 2
    falls back to title keyword overlap plus a component match (confidence:
    medium, AC-2). A ticket with neither signal must never appear as a match
    (AC-3, no false positives).
ARCHITECTURE: Sibling module to cross_reference_audit.py inside
    scripts/ac_store/. It is never executed directly; cross_reference_audit.py
    imports it via the bare-import sys.path bootstrap documented in that
    module's header, so this file works whether the entry point is run as a
    script or imported as a package. Defines MatchRecord, the shared match
    dict shape consumed by the report and apply modules.
"""

from __future__ import annotations

import difflib
from typing import Any

_STOP_WORDS: frozenset[str] = frozenset(
    {"the", "a", "an", "is", "are", "when", "then", "given", "and", "or", "not"}
)

_PASS1_SIMILARITY_THRESHOLD: float = 0.90
_PASS2_MIN_KEYWORD_OVERLAP: int = 2

MatchRecord = dict[str, Any]


def _pass1_similarity(ac_criteria: str, ticket_ac_section: str) -> float:
    """Compute similarity ratio between AC criteria text and ticket AC section."""
    if not ac_criteria or not ticket_ac_section:
        return 0.0
    sm = difflib.SequenceMatcher(None, ac_criteria, ticket_ac_section, autojunk=False)
    return sm.ratio()


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase words, filtering stop words."""
    words = []
    for word in text.lower().split():
        # Strip punctuation
        clean = "".join(ch for ch in word if ch.isalnum())
        if clean and clean not in _STOP_WORDS:
            words.append(clean)
    return words


def _pass2_keyword_overlap(
    ac_title: str,
    ticket_title: str,
    ac_component: str | None,
    ticket_components: list[str],
) -> tuple[bool, str]:
    """Check keyword overlap and component match for medium-confidence matching.

    Returns (matched, reason_string).
    """
    ac_tokens = set(_tokenize(ac_title))
    ticket_tokens = set(_tokenize(ticket_title))
    overlap = ac_tokens & ticket_tokens

    has_component_match = False
    if ac_component and ticket_components:
        # Normalize for comparison
        ac_comp_lower = ac_component.lower().replace("-", "").replace("_", "")
        for tc in ticket_components:
            tc_lower = tc.lower().replace("-", "").replace("_", "")
            if ac_comp_lower == tc_lower or ac_comp_lower in tc_lower or tc_lower in ac_comp_lower:
                has_component_match = True
                break

    if len(overlap) >= _PASS2_MIN_KEYWORD_OVERLAP and has_component_match:
        reason = (
            f"title keyword overlap ({len(overlap)}/{len(ac_tokens)}) "
            f"+ component match ({ac_component})"
        )
        return True, reason
    return False, ""


def _find_matches(
    acs: list[dict[str, Any]],
    tickets: list[dict[str, Any]],
) -> list[MatchRecord]:
    """Run two-pass matching and return deduplicated match records."""
    matches: list[MatchRecord] = []

    for ac in acs:
        ac_id = ac.get("id", "UNKNOWN")
        ac_title = str(ac.get("title", ""))
        ac_criteria = str(ac.get("criteria", ""))
        # component may be a string, list, or dict (various AC YAML schemas)
        ac_component_raw = ac.get("component", ac.get("components", None))
        if isinstance(ac_component_raw, list):
            ac_component: str | None = ac_component_raw[0] if ac_component_raw else None
        elif isinstance(ac_component_raw, dict):
            # Some ACs encode component as a dict with an 'id' or 'name' key
            ac_component = str(
                ac_component_raw.get("id", ac_component_raw.get("name", ""))
            ) or None
        elif ac_component_raw is None:
            ac_component = None
        else:
            ac_component = str(ac_component_raw)

        best_match: MatchRecord | None = None

        for ticket in tickets:
            ticket_path = ticket["path"]
            ticket_title = str(ticket["title"])
            ticket_components = ticket["components"]
            ticket_ac_section = ticket["ac_section"]

            # Pass 1 — exact criteria similarity
            similarity = _pass1_similarity(ac_criteria, ticket_ac_section)
            if similarity >= _PASS1_SIMILARITY_THRESHOLD:
                record: MatchRecord = {
                    "ac_id": ac_id,
                    "ticket_path": ticket_path,
                    "confidence": "high",
                    "reason": f"AC criteria text similarity ({similarity:.0%})",
                    "_ac": ac,
                }
                # High confidence wins — track best
                if best_match is None or best_match["confidence"] == "medium":
                    best_match = record
                continue

            # Pass 2 — keyword + component match
            matched, reason = _pass2_keyword_overlap(
                ac_title, ticket_title, ac_component, ticket_components
            )
            if matched:
                record = {
                    "ac_id": ac_id,
                    "ticket_path": ticket_path,
                    "confidence": "medium",
                    "reason": reason,
                    "_ac": ac,
                }
                # Only record medium if no high match exists yet
                if best_match is None:
                    best_match = record

        if best_match is not None:
            matches.append(best_match)

    return matches


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [python-coder]: Extracted from cross_reference_audit.py into this
  module (the two matching passes) as part of the file-size split required by
  check-file-size (GE-127b-1) — the source file had grown to 557 content
  lines against the 400-line limit. Moved verbatim; no behaviour changed.
====================================================================
"""
