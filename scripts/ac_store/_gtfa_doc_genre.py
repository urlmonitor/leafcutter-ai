#!/usr/bin/env python3
"""
MODULE: _gtfa_doc_genre
GOAL: Work out the three things a ``### documentation-expert`` contract line
    needs — the Diataxis genre, the target doc path, and a content constraint
    derived from the criteria.
BUSINESS CONTEXT: The genre comes from the PARENT L1's
    ``documentation_triggers``, not the leaf's, because documentation is
    decided at the feature level. That makes one distinction load-bearing: a
    parent with NO ``documentation_triggers`` key has omitted something, while
    a parent with an explicit ``documentation_triggers: []`` has DECLARED that
    no documentation is required (see e.g. BP-900g.yaml's
    ``documentation_rationale``). Collapsing the two — which is what the code
    did until BO-2200c-5 — emits a phantom ``(unspecified genre)`` contract
    line on every AC whose parent deliberately opted out.
ARCHITECTURE: Fail-soft, but visibly: an unresolvable parent yields the
    explicit ``(unspecified genre)`` marker rather than a blank slot, so the
    omission is readable in the generated ticket instead of looking like a
    field nobody filled in. The deliberate-empty case is the one and only
    branch that returns ``[]``, and the caller reads that as "emit no contract
    line at all".
"""

from __future__ import annotations

import importlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

# See the "Sibling wiring" note in generate_ticket_from_ac.py for why the
# sibling package prefix is derived from __name__ rather than hard-coded.
_PKG = __name__.rpartition(".")[0]
_gtfa_seams = importlib.import_module(f"{_PKG}._gtfa_seams" if _PKG else "_gtfa_seams")
_gtfa_constants = importlib.import_module(
    f"{_PKG}._gtfa_constants" if _PKG else "_gtfa_constants"
)
_gtfa_store = importlib.import_module(f"{_PKG}._gtfa_store" if _PKG else "_gtfa_store")

logger = logging.getLogger(_gtfa_seams.logger_name())

# ``AcRecord`` is bound at RUNTIME by the ``else`` branch, off the sibling
# module object resolved above through importlib under a prefix COMPUTED from
# ``__name__`` -- see the "Sibling wiring" note in generate_ticket_from_ac.py
# for why a literal relative import there would break one of the two supported
# layouts. A computed name is opaque to a type checker, so that rebind reads as
# a VARIABLE and mypy rejects every annotation using it ("Variable ... is not
# valid as a type"). The TYPE_CHECKING branch declares the alias statically and
# is never executed, so the runtime binding is unchanged.
if TYPE_CHECKING:  # pragma: no cover - a static declaration, never executed
    from ._gtfa_constants import AcRecord
else:
    AcRecord = _gtfa_constants.AcRecord

_load_parent_ac = _gtfa_store._load_parent_ac


def _extract_doc_genre(ac: AcRecord) -> str:
    """Extract the Diataxis genre from an AC record's documentation_triggers field.

    Returns the first value from ``documentation_triggers`` when the field is
    present and non-empty.  Falls back to ``"explanation"`` when the field is
    absent, empty, or contains a non-string first element (BO-2200c-2).

    Args:
        ac: Parsed AC record dict.

    Returns:
        A genre string — one of the valid Diataxis genre labels or ``"explanation"``.
    """
    triggers = ac.get("documentation_triggers") or []
    if triggers and isinstance(triggers[0], str) and triggers[0].strip():
        return triggers[0].strip()
    return "explanation"


def _genres_from_parent_triggers(ac_id: str, parent_ac: AcRecord) -> list[str]:
    """Read the genre list out of a RESOLVED parent AC's documentation_triggers.

    Split out of :func:`_resolve_genres_from_parent` so the four distinct
    outcomes of reading the parent's field — absent key, deliberate empty list,
    present-but-unusable value, and real triggers — sit next to each other and
    can be told apart at a glance. The distinction between the first two is the
    whole of BO-2200c-5.

    Args:
        ac_id: Leaf AC identifier, named in the log lines.
        parent_ac: The resolved parent AC record.

    Returns:
        The parent's genre strings; ``[]`` ONLY for a deliberate, explicitly
        empty ``documentation_triggers``; otherwise the
        ``["(unspecified genre)"]`` fail-soft marker.
    """
    if "documentation_triggers" not in parent_ac:
        # BO-2200c-3-i: parent found but the field is absent entirely — an
        # omission, not a deliberate declaration. Fail-soft to the marker.
        logger.warning(
            "Parent AC of %r has no documentation_triggers key; "
            "emitting (unspecified genre) marker (BO-2200c-3-i)",
            ac_id,
        )
        return ["(unspecified genre)"]

    triggers = parent_ac.get("documentation_triggers")
    if triggers == []:
        # BO-2200c-5 / KI-ACD-002: parent EXPLICITLY declares no documentation
        # triggers — a deliberate "no documentation required" (see
        # documentation_rationale on the parent record), not an omission.
        # Return empty so the caller emits no contract line at all.
        logger.info(
            "Parent AC of %r declares documentation_triggers: [] "
            "(deliberate — no documentation required); suppressing the "
            "documentation-expert contract line (BO-2200c-5)",
            ac_id,
        )
        return []

    if not triggers:
        # Present but not a usable list (e.g. null or a falsy non-list value)
        # — treat as an omission, same as the absent-key case above.
        logger.warning(
            "Parent AC of %r has an empty/invalid documentation_triggers "
            "value (%r); emitting (unspecified genre) marker (BO-2200c-3-i)",
            ac_id,
            triggers,
        )
        return ["(unspecified genre)"]

    genres = [
        str(t).strip()
        for t in triggers
        if isinstance(t, str) and str(t).strip()
    ]
    return genres if genres else ["(unspecified genre)"]


def _resolve_genres_from_parent(
    ac_id: str,
    ac_root: "Path | None",
    leaf_ac: AcRecord,
) -> list[str]:
    """Resolve Diataxis genre strings from the parent L1 AC's documentation_triggers.

    When *ac_root* is ``None`` (backward-compat / legacy path), falls back to
    reading the leaf AC's own ``documentation_triggers`` via
    :func:`_extract_doc_genre` — identical to the pre-BO-2200c-3 behaviour.

    When *ac_root* is provided, resolves the parent L1 via
    :func:`_load_parent_ac` and reads the parent's ``documentation_triggers``
    list.  Multiple triggers each contribute a genre to the returned list
    (BO-2200c-3 multi-trigger requirement).

    Returns a list of genre strings — possibly empty — in all cases:

    - When *ac_root* is ``None``: ``[leaf_genre]`` (backward-compat).
    - When the parent resolves and has triggers: all genre strings from the
      parent's ``documentation_triggers``.
    - When the parent cannot be resolved, OR the parent record has no
      ``documentation_triggers`` KEY at all: the explicit marker
      ``["(unspecified genre)"]`` so the omission is visible
      (BO-2200c-3-i fail-soft).
    - When the parent resolves and its ``documentation_triggers`` key is
      present but an EXPLICIT empty list (``[]``): the empty list ``[]`` is
      returned as-is — NOT the ``(unspecified genre)`` marker. Per the AC
      store's convention (see e.g. BP-900g.yaml's ``documentation_rationale``
      field), an explicit ``documentation_triggers: []`` is the parent's
      deliberate declaration that no documentation is required, not an
      omission to paper over with a placeholder (BO-2200c-5 / KI-ACD-002).
      The caller (:func:`_build_agent_contracts_section`) treats an empty
      return as "emit no documentation-expert contract line".

    Args:
        ac_id: Leaf AC identifier.
        ac_root: Root directory of the AC store, or ``None`` for legacy mode.
        leaf_ac: The parsed leaf AC record.

    Returns:
        List of genre strings. Empty only when the parent explicitly
        declares ``documentation_triggers: []``; every other unresolved case
        falls back to the ``["(unspecified genre)"]`` marker.

    DECISION HISTORY:
        BO-2200c-3 / BO-2200c-3-i (2026-08-11): Introduced as the single
        entry-point for genre resolution so that _build_agent_contracts_section
        can be extended cleanly while keeping _extract_doc_genre unchanged for
        backward compatibility with callers that do not supply ac_root.
        BO-2200c-5 (2026-08-26): An explicit ``documentation_triggers: []`` on
        the parent was previously treated identically to "parent could not be
        resolved" (both fell back to the ``(unspecified genre)`` marker), which
        the caller rendered as a phantom documentation contract line for ACs
        whose parent deliberately declares no documentation is needed. Now
        distinguishes an ABSENT ``documentation_triggers`` key (still
        `(unspecified genre)`, fail-soft) from a present, explicitly EMPTY list
        (deliberate — returns ``[]``, no fallback marker).
    """
    if ac_root is None:
        # Backward-compat: no ac_root provided → use leaf's own triggers.
        return [_extract_doc_genre(leaf_ac)]

    parent_ac = _load_parent_ac(ac_id, ac_root)
    if parent_ac is None:
        # BO-2200c-3-i: parent unresolved — emit explicit marker (not blank).
        return ["(unspecified genre)"]

    return _genres_from_parent_triggers(ac_id, parent_ac)


def _extract_doc_path(ac: AcRecord, genre: str, ac_id: str) -> str:
    """Extract a target documentation path from an AC record's doc_links field.

    Scans ``doc_links`` for the first entry whose ``path`` value is a non-empty
    local string (not an http URL) containing at least one ``/`` separator.
    When no qualifying link is found, a default path is computed under
    ``docs/<genre>/<slugified-ac_id>.md`` (BO-2200c-2).

    Args:
        ac: Parsed AC record dict.
        genre: Diataxis genre string (used in the computed default path).
        ac_id: AC identifier string (used in the computed default path).

    Returns:
        A documentation path string that contains at least one ``/`` separator.
    """
    doc_links = ac.get("doc_links") or []
    for link in doc_links:
        if not isinstance(link, dict):
            continue
        path_val = link.get("path", "")
        if (
            isinstance(path_val, str)
            and path_val
            and "/" in path_val
            and not path_val.startswith("http")
        ):
            return path_val
    # Compute a sensible default: docs/<genre>/<ac-id-slug>.md
    slug = re.sub(r"[^a-z0-9]+", "-", (ac_id or "ac").lower()).strip("-")
    return f"docs/{genre}/{slug}.md"


def _derive_content_constraint(ac: AcRecord, ac_id: str) -> str:
    """Derive a content constraint from an AC record's criteria field.

    Extracts the text of the first ``Then`` clause in the Gherkin criteria.
    Falls back to the first non-empty criteria line when no ``Then`` clause is
    found.  Returns a generic placeholder when the criteria field is absent or
    blank (BO-2200c-2).

    Args:
        ac: Parsed AC record dict.
        ac_id: AC identifier string (used in the fallback placeholder).

    Returns:
        A non-empty constraint string derived from the criteria (not the AC title).
    """
    criteria_text = str(ac.get("criteria") or "")
    for line in criteria_text.split("\n"):
        stripped = line.strip()
        m = re.match(r"^Then\s+(.*)", stripped, re.IGNORECASE)
        if m:
            clause = m.group(1).rstrip(",").strip()
            if clause:
                return clause
    # Fallback: first non-empty criteria line
    for line in criteria_text.split("\n"):
        stripped = line.strip()
        if stripped:
            return stripped
    return f"cover the behaviour described in {ac_id}"
