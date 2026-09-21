#!/usr/bin/env python3
"""
MODULE: _gtfa_contracts
GOAL: Build the generated ticket's ``## Agent Contracts`` section — the
    ``### documentation-expert`` checklist, and the ``### Delivers To`` /
    ``### Expects From`` blocks derived from the AC's contract fields.
BUSINESS CONTEXT: The documentation-expert checklist lines are PARSED, not just
    read: ``documentation-verifier.md`` Step 2 splits each ``- [ ] AC-N:`` line
    on pipes into ``<genre> | <target_path> | <content_constraint>``. The
    format is therefore a producer/consumer contract, and it has been broken
    once — the earlier bracket-and-em-dash rendering carried zero pipe
    separators, so every real doc-required ticket failed the verifier's own
    documented parse rule while looking perfectly readable to a human.
ARCHITECTURE: Both ``delivers_to`` and ``expects_from`` may be authored as a
    bare mapping (the legacy form) or as a list of mappings (what BA/IT-PO v3
    emits). Both are schema-valid, so they are normalised to a list before
    iteration — a collapse to "first entry wins" would silently drop every
    contract after the first. The single ``## Agent Contracts`` heading is
    emitted at most once no matter how many subsections fire.
"""

from __future__ import annotations

import importlib
import logging
from pathlib import Path
from typing import Any

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)
_gtfa_doc_genre = importlib.import_module(
    f"{_PKG}._gtfa_doc_genre" if _PKG else "_gtfa_doc_genre"
)

logger = logging.getLogger(_gtfa_seams.logger_name())

AcRecord = _gtfa_constants.AcRecord
_derive_content_constraint = _gtfa_doc_genre._derive_content_constraint
_extract_doc_path = _gtfa_doc_genre._extract_doc_path
_resolve_genres_from_parent = _gtfa_doc_genre._resolve_genres_from_parent


def _as_contract_entries(value: object) -> list[dict]:
    """Normalize a delivers_to / expects_from field to a list of dict entries.

    The field may be a single mapping (legacy dict form, e.g. GE-116a-1) or a
    list of mappings (the BA/IT-PO v3 form, e.g. FIN-100a-4 / FIN-100c-4). Both
    are valid per the AC schema, so the ticket generator must accept either.
    Non-mapping list elements are skipped defensively.

    Args:
        value: The raw ``delivers_to`` or ``expects_from`` value from an AC.

    Returns:
        A list of mapping entries (possibly empty).
    """
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [entry for entry in value if isinstance(entry, dict)]
    return []


def _build_doc_links_cross_link_lines(doc_links: list[Any]) -> list[str]:
    """Render all qualifying doc_links entries as 'existing docs to update / cross-link' bullets.

    Each entry is rendered with its path, relationship, status, and relevance
    fields visible so the documentation-expert knows how each linked doc relates
    (BO-2200c-4).  Entries with HTTP URLs and entries missing a path are skipped.

    The metadata fields are rendered inline in the format:
      ``- <path> (relationship: <val> | status: <val> | relevance: <val>)``
    Any metadata field that is absent or empty is omitted from the inline list.
    When no metadata is present for an entry, the path is rendered as a bare bullet.

    Args:
        doc_links: List of doc_link dicts from an AC record.  Each dict should
            carry at least a ``path`` key; ``relationship``, ``status``, and
            ``relevance`` are optional metadata fields.

    Returns:
        List of formatted bullet strings, one per qualifying doc_links entry.
        Returns an empty list when *doc_links* is empty or no entry qualifies.
    """
    if not doc_links:
        return []
    result: list[str] = []
    for link in doc_links:
        # BO-2200c-4-i: bare-string entries are surfaced with just their path.
        # Previously these hit 'not isinstance(link, dict)' and were silently skipped.
        if isinstance(link, str):
            if link and not link.startswith("http"):
                result.append(f"- {link}")
            continue
        if not isinstance(link, dict):
            continue
        path_val = link.get("path", "")
        if not isinstance(path_val, str) or not path_val or path_val.startswith("http"):
            continue
        relationship = link.get("relationship", "")
        status = link.get("status", "")
        relevance = link.get("relevance", "")
        meta: list[str] = []
        if relationship:
            meta.append(f"relationship: {relationship}")
        if status:
            meta.append(f"status: {status}")
        if relevance:
            meta.append(f"relevance: {relevance}")
        if meta:
            result.append(f"- {path_val} ({' | '.join(meta)})")
        else:
            result.append(f"- {path_val}")
    return result


def _doc_expert_subsection_lines(
    ac: AcRecord, ac_id: str, genres: list[str]
) -> list[str]:
    """Render the ``### documentation-expert`` subsection.

    BO-2200c-2: each AC-N line must name three parts —

    1. Diataxis genre — sourced from the PARENT L1's documentation_triggers when
       ac_root is provided (BO-2200c-3), or from the leaf's own field (legacy).
    2. Target doc path from doc_links or a computed default under docs/<genre>/.
    3. Content constraint derived from the AC criteria Then/And clauses.

    BO-2200c-5 / KI-ACD-002: the line MUST be pipe-delimited
    ``<genre> | <target_path> | <content_constraint>`` to match the consumer's
    documented parse rule (documentation-verifier.md Step 2, "Parse Required
    Docs"). The prior bracket + em-dash format (``[genre] path — constraint``)
    has zero pipe separators and is rejected outright by that documented
    algorithm.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id.
        genres: Resolved genre list — one AC-N line is emitted per genre, so
            multiple parent triggers are each reflected. Single-genre (legacy
            or single trigger) produces one line, identical to the
            pre-BO-2200c-3 output.

    Returns:
        The subsection's lines, ready to extend the section body.
    """
    # Use the first genre for doc_path derivation (consistent with single-genre legacy).
    path_genre = genres[0]
    doc_path = _extract_doc_path(ac, path_genre, ac_id)
    constraint = _derive_content_constraint(ac, ac_id)
    lines: list[str] = ["### documentation-expert", ""]
    # BO-2200c-4: Surface ALL doc_links entries as 'existing docs to update /
    # cross-link' with relationship, status, and relevance metadata intact so
    # the documentation-expert knows how each linked doc relates.  The previous
    # behaviour (_extract_doc_path) reduced doc_links to a single bare path,
    # discarding all metadata and every entry after the first.
    cross_link_lines = _build_doc_links_cross_link_lines(ac.get("doc_links") or [])
    if cross_link_lines:
        lines.append("Existing docs to update / cross-link:")
        lines.append("")
        lines.extend(cross_link_lines)
        lines.append("")
    for i, genre in enumerate(genres, 1):
        lines.append(f"- [ ] AC-{i}: {genre} | {doc_path} | {constraint}")
    lines.append("")
    return lines


def _contract_block_lines(
    heading: str, value: object, id_label: str, id_key: str
) -> list[str]:
    """Render a ``### Delivers To`` / ``### Expects From`` block.

    TKT-500f-10: both fields may be authored as a bare dict OR as a list of
    dicts (BA/IT-PO v3 emits list form); :func:`_as_contract_entries`
    normalises to a list so iteration always works and no entry after the
    first is silently dropped.

    Args:
        heading: Subsection heading, e.g. ``"### Delivers To"``.
        value: The raw field value from the AC record.
        id_label: Bold label for the entry's identifying field, e.g. ``"Agent"``.
        id_key: Key holding that identifying value, e.g. ``"agent"``.

    Returns:
        The block's lines, ready to extend the section body.
    """
    lines: list[str] = [heading, ""]
    for entry in _as_contract_entries(value):
        id_value = entry.get(id_key, "")
        contract_text = entry.get("contract", "")
        if id_value:
            lines.append(f"- **{id_label}:** {id_value}")
        if contract_text:
            lines.append(f"- **Contract:** {contract_text}")
    lines.append("")
    return lines


def _build_agent_contracts_section(
    ac: AcRecord,
    ac_id: str = "",
    agents_map: dict[str, str] | None = None,
    ac_root: "Path | None" = None,
) -> str:
    """Build the ## Agent Contracts section.

    Emits the section when either of the following conditions is met:

    * ``documentation-expert`` appears in *agents_map* with status ``'needed'``
      AND genre resolution (:func:`_resolve_genres_from_parent`) yields at
      least one genre (BO-2200c-1): a ``### documentation-expert`` subsection
      is appended listing one globally-numbered ``- [ ] AC-1:`` checklist
      item per genre. Per BO-2200c-2/BO-2200c-5, each checklist item is
      pipe-delimited with three fields — ``<genre> | <target_path> |
      <content_constraint>`` — matching documentation-verifier.md Step 2's
      documented parse rule verbatim. When the resolved parent L1 explicitly
      declares ``documentation_triggers: []`` (deliberate "no documentation
      required" — BO-2200c-5 / KI-ACD-002), genre resolution returns an empty
      list and this subsection is suppressed entirely rather than emitting a
      placeholder line.
    * The AC record has a non-null ``delivers_to`` or ``expects_from`` field
      (TKT-500f-10): the contract details are rendered under ``### Delivers To``
      or ``### Expects From`` subsections.

    Both conditions may fire simultaneously; each contributes its own subsection.
    Returns ``""`` when neither condition is met.

    The section is placed after ``## Acceptance Criteria`` (and any Test
    Requirements / Implementation Notes blocks) and before ``## Sign-offs``, as
    required by BO-2200c-1 n_location_rule='1'.

    Args:
        ac: Parsed AC record.
        ac_id: The AC id (used in the computed default doc path and the
            content-constraint fallback for the BO-2200c-1/c-2 subsection).
        agents_map: The computed agents map (agent name → status). When ``None``
            or when ``documentation-expert`` is absent or not ``'needed'``, the
            BO-2200c-1 subsection is suppressed.
        ac_root: Root directory of the AC store.  When provided, the parent L1
            AC is loaded and its ``documentation_triggers`` are used as the genre
            source (BO-2200c-3).  When ``None`` (default / legacy mode), the
            leaf AC's own ``documentation_triggers`` are used for backward compat.

    Returns:
        Formatted ``## Agent Contracts`` markdown block, or ``""`` when neither
        condition fires.
    """
    delivers_to = ac.get("delivers_to") or None
    expects_from = ac.get("expects_from") or None
    doc_expert_needed = (agents_map or {}).get("documentation-expert") == "needed"

    # BO-2200c-5 / KI-ACD-002: resolve genres up front so a parent's DELIBERATE
    # documentation_triggers: [] (empty list returned by
    # _resolve_genres_from_parent) suppresses the whole documentation-expert
    # subsection rather than emitting a phantom contract line. An empty list
    # here is the store's documented way of saying "no documentation
    # required" — distinct from the "(unspecified genre)" fail-soft marker
    # used when the parent can't be resolved at all.
    genres: list[str] = []
    if doc_expert_needed:
        genres = _resolve_genres_from_parent(ac_id, ac_root, ac)
    emit_doc_expert_subsection = doc_expert_needed and bool(genres)

    if not emit_doc_expert_subsection and delivers_to is None and expects_from is None:
        return ""

    lines: list[str] = ["## Agent Contracts", ""]

    if emit_doc_expert_subsection:
        lines.extend(_doc_expert_subsection_lines(ac, ac_id, genres))

    if delivers_to is not None:
        lines.extend(_contract_block_lines(
            "### Delivers To", delivers_to, "Agent", "agent"
        ))
    if expects_from is not None:
        lines.extend(_contract_block_lines(
            "### Expects From", expects_from, "AC", "ac_id"
        ))

    return "\n".join(lines)
