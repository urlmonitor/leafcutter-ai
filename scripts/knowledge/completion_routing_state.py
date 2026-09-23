"""
MODULE: completion_routing_state
GOAL: Sink-reading, bookkeeping-state, and unarbitrated-claim primitives for
    the INF-700a-5 completion-routing durability contract.
BUSINESS CONTEXT: Split out of `completion_routing.py` (GE-127b-1-style file
    -size ratchet: a single-file implementation of the whole INF-700a-5
    family exceeded the 400-line commit-guardian limit for new Python
    files) so that module can stay focused on the public staging /
    confirmation / reporting API while this one owns "what is in the
    sink" and "what does the bookkeeping file currently say".
ARCHITECTURE: Required sibling module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md), loaded by
    `completion_routing.py` via `importlib.util.spec_from_file_location`
    -- mirroring `harvest_learnings.py`'s own `_load_required_sibling_module`
    convention, since `completion_routing.py` is itself loaded by path (not
    via a package import) by its test fixture
    (`unit_tests/workflows/_inf700a5_fixtures.py`).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger("completion_routing")

# The idempotency key: the same required-field set harvest_learnings.py's
# own `_event_hash` uses (INF-400b-2-ii's reconciled record shape). `text`
# is deliberately excluded -- it is content, not identity.
REQUIRED_DIGEST_FIELDS: tuple[str, ...] = (
    "timestamp",
    "agent",
    "component",
    "destination",
    "entry_kind",
)

# How long _claim_without_arbitration sleeps between its read and its write
# when deliberately un-arbitrated. Long enough that two callers released from
# a shared barrier at the same instant reliably both finish reading before
# either writes (a read+dict-comprehension is microseconds; this is two to
# three orders of magnitude longer), short enough not to meaningfully slow a
# test suite or a real disabled-arbitration call. Chosen synchronisation,
# recorded here per INF-700a-5-iii's it_requirements ("Record the chosen
# synchronisation so a later reader can tell a real overlap from an
# accidental sequence") -- this is that record.
UNARBITRATED_RACE_WINDOW_SECONDS = 0.05


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def record_hash(event: dict[str, Any]) -> str:
    """Return a stable SHA-256 hex digest for a knowledge_captured event.

    Pure function: no I/O, no shared-state mutation. Raises ``KeyError``
    (named field) if *event* is missing a required digest field -- the
    caller is responsible for skipping such a record rather than hashing
    it on a substituted value.
    """
    key = json.dumps(
        {field: event[field] for field in REQUIRED_DIGEST_FIELDS},
        sort_keys=True,
    )
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def has_real_text(event: dict[str, Any]) -> bool:
    """Return True if *event* carries non-empty learning text.

    Pure function: no I/O, no shared-state mutation.
    """
    text = event.get("text")
    return isinstance(text, str) and bool(text.strip())


# ---------------------------------------------------------------------------
# Sink reading (I/O boundary)
# ---------------------------------------------------------------------------


def read_eligible_sink_records(sink_path: Path) -> list[tuple[str, str, str]]:
    """Read every eligible (text-bearing) knowledge_captured record.

    Returns a list of ``(record_hash, text, destination)`` tuples in file
    order. External I/O: a read failure is logged and degrades to an
    empty result rather than raising, per the fail-open error-handling
    policy this AC family requires of the routing step -- a routing
    failure must never fail the unit of work.
    """
    if not sink_path.exists():
        return []
    try:
        raw_lines = sink_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        logger.warning("Cannot read knowledge sink %s: %s", sink_path, exc)
        return []

    records: list[tuple[str, str, str]] = []
    for raw_line in raw_lines:
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict) or event.get("event") != "knowledge_captured":
            continue
        if not has_real_text(event):
            continue
        try:
            digest = record_hash(event)
        except KeyError:
            continue
        records.append((digest, event["text"], str(event.get("destination", ""))))
    return records


# ---------------------------------------------------------------------------
# Bookkeeping state (I/O boundary)
# ---------------------------------------------------------------------------


def load_state_set(state_path: Path) -> set[str]:
    """Load the set of confirmed-routed record hashes from *state_path*.

    Fails open: a missing, corrupted, or malformed-shape state file is
    treated as an empty set (with a WARNING logged for the latter two)
    rather than raising -- per this family's requirement that bookkeeping
    failures never block the unit of work.
    """
    if not state_path.exists():
        return set()
    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Could not read routing state %s (treated as empty): %s", state_path, exc
        )
        return set()
    if not isinstance(raw, list):
        logger.warning("Routing state %s is not a JSON list (treated as empty)", state_path)
        return set()
    return {str(item) for item in raw}


def persist_state_set(state_path: Path, hashes: set[str]) -> None:
    """Persist *hashes* to *state_path* (write-then-rename for atomicity).

    The temp file name is unique per call (pid + a random token), not a
    fixed ``.tmp`` suffix: two concurrent, unsynchronised persist calls
    over the same *state_path* -- exactly what
    ``claim_and_confirm_routed(arbitration_enabled=False)`` deliberately
    allows -- would otherwise both write through the SAME temp path, and
    whichever call's ``replace()`` runs second finds its own temp file
    already consumed by the other call's rename, raising ``ENOENT`` and
    silently dropping that call's claim. A unique name per call lets both
    renames land (POSIX rename-onto-existing-target is atomic), so the
    race two overlapping claims are meant to exercise is decided by which
    read happened first, never by a temp-file collision.

    Raises ``OSError`` to the caller on failure (logged here first) so
    each caller can decide whether the affected records must be treated
    as still-unconfirmed.
    """
    tmp_path = state_path.parent / f"{state_path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(json.dumps(sorted(hashes), indent=2), encoding="utf-8")
        tmp_path.replace(state_path)
    except OSError as exc:
        logger.warning("Could not persist routing state %s: %s", state_path, exc)
        raise


def claim_without_arbitration(
    state_path: Path, ids: list[str], *, widen_race_window: bool = False
) -> list[str]:
    """Read-compute-write the claim with no synchronisation of its own.

    Used both as the deliberate ``arbitration_enabled=False`` path (with
    *widen_race_window* set, so a genuine overlap is reliably observable --
    see ``UNARBITRATED_RACE_WINDOW_SECONDS``) and as the already-arbitrated
    body run under the caller's held lock (*widen_race_window* left False,
    since the lock is what makes this section atomic across callers there,
    and a real completion path must not pay an artificial delay on every
    claim).
    """
    current = load_state_set(state_path)
    if widen_race_window:
        time.sleep(UNARBITRATED_RACE_WINDOW_SECONDS)
    newly = [record_id for record_id in ids if record_id not in current]
    try:
        persist_state_set(state_path, current | set(ids))
    except OSError:
        # Persist failure already logged. Per the fail-open policy, the
        # claim is not honoured this call but nothing raises into the
        # driver -- the ids remain unconfirmed and retryable.
        return []
    return newly


def read_text_or_empty(path: Path) -> str:
    """Return *path*'s text content, or ``""`` if it does not exist.

    External I/O; a read failure other than absence is logged and treated
    as empty content, since this function backs a read-only reporting
    path that must never raise into a teardown sequence.
    """
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except OSError as exc:
        logger.warning("Could not read %s (treated as empty): %s", path, exc)
        return ""


# DECISION HISTORY
# ================================================================================
# - 2026-09-21 [python-coder]: Extracted from completion_routing.py to relieve
#   the check-file-size ratchet (400-line limit for new .py files), which
#   refused the original single-file implementation of the whole INF-700a-5
#   family at 554 lines. No behaviour change -- every function here is the
#   verbatim body of its former `_`-prefixed counterpart in
#   completion_routing.py, renamed to a public (no leading underscore) name
#   since it is now a cross-module API rather than a same-file private
#   helper. (#TICKETLESS reason=ac-scoped-fastlane-build-INF-700a-5)
