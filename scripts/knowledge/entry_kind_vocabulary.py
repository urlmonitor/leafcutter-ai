"""
MODULE: entry_kind_vocabulary
GOAL: Load the single declared ``entry_kind`` vocabulary and normalise a
    caller-supplied ``entry_kind`` string against it, so both the emission
    helper (``emit_knowledge.py``) and the harvester
    (``harvest_learnings.py``) compare values the same way.
BUSINESS CONTEXT: AC INF-400c-5 closes a vocabulary drift where the
    route-knowledge classifier's 16 ``target_surface`` labels and the
    harvester's 11 routable ``entry_kind`` values overlapped on only four
    values, making a classifier-produced label more often unroutable than
    routable. AC INF-400c-5-i additionally requires separator/case variants
    of one entry_kind (``component_convention`` vs ``component-convention``
    vs ``COMPONENT_CONVENTION``) to normalise to a single canonical,
    hyphenated lower-case member before comparison.
ARCHITECTURE: Plain-data/helper module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md) — not itself a CLI.
    Read by ``emit_knowledge.py`` (validates and writes an event) so
    normalisation happens in exactly one place, per this AC's
    it_requirements ("Normalisation must be applied at both the emission
    helper and the harvester read path, from one shared function").

The declared vocabulary lives at ``config/entry_kind_vocabulary.json``
(shape: ``{"members": {"<canonical-entry-kind>": {...routing metadata...}}}``),
mirroring the existing ``config/knowledge_sink.json`` declaration pattern
already used by ``harvest_learnings.py`` (INF-400c-4).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("entry_kind_vocabulary")


def default_vocabulary_path() -> Path:
    """Return the vocabulary config path beside this deployed script.

    Mirrors ``sink_resolution.deployed_output_root()``: this file deploys
    to ``<output_root>/scripts/knowledge/entry_kind_vocabulary.py``, so the
    output root is always two directories above this file's own location,
    and the vocabulary lives at ``<output_root>/config/entry_kind_vocabulary
    .json`` beside the other build-time declarations.

    Pure function: no I/O, no shared-state mutation.
    """
    return Path(__file__).resolve().parents[2] / "config" / "entry_kind_vocabulary.json"


def load_vocabulary(vocab_path: Path) -> dict[str, dict[str, Any]]:
    """Read the declared vocabulary and return its ``members`` mapping.

    Returns an empty mapping (never raises) when the file is absent,
    unreadable, or not valid JSON — the caller (``emit_knowledge.py``) must
    treat "no vocabulary" the same as "every entry_kind is out of
    vocabulary" and reject accordingly, per the best-effort /
    non-fatal-to-the-caller contract this AC's sibling INF-400c-5-iii
    requires. External I/O (file read), so wrapped and logged per the
    project error-handling policy rather than left to propagate.
    """
    try:
        data = json.loads(vocab_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Could not read entry_kind vocabulary %s: %s", vocab_path, exc)
        return {}
    members = data.get("members")
    if not isinstance(members, dict):
        logger.warning(
            "Entry_kind vocabulary %s has no valid 'members' mapping", vocab_path
        )
        return {}
    return members


def normalize_entry_kind(value: str) -> str:
    """Return the normalised form of *value* for vocabulary comparison.

    Lower-cases the value and treats ``_`` and ``-`` as the same separator
    (AC INF-400c-5-i). Does not touch any other character — e.g. a literal
    ``.`` is preserved verbatim, since normalisation must not "strip or
    collapse other characters" per this AC's it_requirements.

    Pure function: no I/O, no shared-state mutation.
    """
    return value.strip().lower().replace("_", "-")


def resolve_canonical(value: str, members: dict[str, Any]) -> str | None:
    """Return the canonical vocabulary member matching *value*, or ``None``.

    *value* is normalised (see ``normalize_entry_kind``) and compared against
    the normalised form of every member key in *members*. The return value is
    the ORIGINAL member spelling as declared in the vocabulary (its canonical
    spelling for this codebase), not the caller's variant spelling — this is
    the form written into the sink and used in every report (AC
    INF-400c-5-i). A normalised value that matches no member's normalised
    form returns ``None``: normalisation never invents a member.

    Pure function: no I/O, no shared-state mutation.
    """
    normalized = normalize_entry_kind(value)
    for member in members:
        if normalize_entry_kind(member) == normalized:
            return member
    return None
