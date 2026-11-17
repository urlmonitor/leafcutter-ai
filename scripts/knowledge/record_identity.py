"""
MODULE: record_identity
GOAL: Define what makes one knowledge_captured record "the same record" as
    another, and how state written under the previous definition is read.
BUSINESS CONTEXT: The harvester and the completion-routing path both decide
    "already routed?" from a hash kept in a shared state file. That hash used
    to ignore the learning text, so distinct learnings emitted in the same
    second by one agent to one destination shared a hash, and routing one
    marked the rest routed without writing them -- a lost learning
    (INF-400b-2-iii, BrainCandy 2026-10-12, option A). The only acceptable
    failure is a duplicate (INF-700a-5-iii).
ARCHITECTURE: Helper module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md), loaded by path by
    ``harvest_learnings.py`` and ``completion_routing_state.py`` so the two
    paths cannot drift apart. Pure functions only: no I/O.

Identity
--------
``event_hash`` (new)    sha256 of the five required fields PLUS ``text``.
``legacy_hash`` (old)   sha256 of the five required fields alone.

Legacy-state rule: a record is processed iff its new hash is in state, or its
legacy hash is in state AND no other record currently in the sink shares that
legacy hash. A record whose legacy hash was shared is routed once more.
Only new hashes are ever written.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

REQUIRED_DIGEST_FIELDS: tuple[str, ...] = (
    "timestamp",
    "agent",
    "component",
    "destination",
    "entry_kind",
)


def _digest(fields: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(fields, sort_keys=True).encode("utf-8")).hexdigest()


def legacy_hash(event: dict[str, Any]) -> str:
    """Return the pre-INF-400b-2-iii digest (required fields only).

    Raises ``KeyError`` naming a missing required field. Pure function.
    """
    return _digest({field: event[field] for field in REQUIRED_DIGEST_FIELDS})


def event_hash(event: dict[str, Any]) -> str:
    """Return the identity digest: the required fields plus the learning text.

    ``text`` is read with ``.get`` -- a textless record is ineligible to be
    routed whatever its identity, so its absence must not read as a missing
    digest field. Raises ``KeyError`` naming a missing required field.
    Pure function.
    """
    return _digest({**{f: event[f] for f in REQUIRED_DIGEST_FIELDS}, "text": event.get("text")})


def shared_legacy_hashes(raw_lines: Iterable[str]) -> set[str]:
    """Return every legacy hash carried by more than one record in *raw_lines*.

    Counts every ``knowledge_captured`` object that has the required fields,
    text-bearing or not: ambiguity errs toward "shared", i.e. toward a
    duplicate. Lines that are not such records are ignored. Pure function.
    """
    seen: set[str] = set()
    shared: set[str] = set()
    for line in raw_lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("event") != "knowledge_captured":
            continue
        try:
            digest = legacy_hash(event)
        except KeyError:
            continue
        (shared if digest in seen else seen).add(digest)
    return shared


def is_processed(
    event: dict[str, Any], state: set[str], shared_legacy: set[str]
) -> bool:
    """Return True if *event* is already routed per *state*.

    The new hash settles it; a legacy hash counts only when unambiguous
    (not in *shared_legacy*). Pure function.
    """
    if event_hash(event) in state:
        return True
    legacy = legacy_hash(event)
    return legacy in state and legacy not in shared_legacy
