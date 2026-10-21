"""
MODULE: scripts/ac_store/ac_retirement.py
GOAL: Hold the ONE definition of "is this AC record retired", so every
    forward-build gate that must skip a retired record asks the same question
    and can never reach a different verdict about the same record.
BUSINESS CONTEXT: ACS-900d-4 (KI-ACS-20261015-superseded-records-held-to-forward-
    rules). A record whose behaviour was deliberately removed and handed to an
    existing successor is no longer owed a covering test, a test contract or
    finished children. Before this module the only shared notion was
    ``is_superseded_ac`` (KI-ACS-016), which counted any non-empty
    ``superseded_by`` -- even one naming a record that does not exist, or the
    record itself -- or ``req_status: superseded`` as withdrawn, so
    ``superseded_by: [anything]`` was a way to dodge done-proof. Retirement is
    therefore strict: it needs a superseded STATUS, real successors, and no
    self-reference. ``deprecated`` is never retired, and ``req_status`` is not
    an input.
ARCHITECTURE: Pure functions, no file, git or environment access. The caller
    supplies the record mapping (a parsed AC YAML mapping or a
    ``_build_ac_status_map`` entry carrying ``id``, ``status`` and
    ``superseded_by``) and ``store_ids``, any container of every AC id in the
    WHOLE store (a ``set`` or the status map itself -- only ``in`` is used).
    Consumed by check_done_proof.py, check_ac_schema.py (through
    ``validate_test_contract``), check_ac_limits.py,
    ``_done_proof_composite.py`` (both composite rollups) and ``done_proof.py``.
    The commit-guardian hooks reach this module through
    ``_ac_store_locator.ensure_ac_store_on_syspath``; it deploys with the
    ``build_ac_store`` deploy map (scripts/build_phases_ac_store.py).

DECISION HISTORY:
  - 2026-10-15 [python-coder/ACS-900d-4]: Created. Replaces the weaker
    ``_done_proof_composite.is_superseded_ac``. An unresolvable or malformed
    successor entry (blank, null) is never in ``store_ids``, so the predicate
    answers "not retired" and the gate fails closed.
"""

from __future__ import annotations

from collections.abc import Container, Mapping

# Both spellings are retired states; ac-schema.md calls "superseded" the older form.
RETIRED_STATUSES: frozenset[str] = frozenset({"superseded_by", "superseded"})


def successor_ids(record: Mapping[str, object]) -> list[str]:
    """Return the successor ids named by *record*'s ``superseded_by`` value.

    Accepts the scalar-string and list forms (ac-schema.md). A null or absent
    value yields an empty list. A blank or null list entry is kept as ``""`` so
    it can never resolve against the store.

    Args:
        record: A parsed AC mapping or a status-map entry.

    Returns:
        The whitespace-trimmed successor ids, in authored order.
    """
    raw = record.get("superseded_by")
    if isinstance(raw, str):
        items: list[object] = [raw]
    elif isinstance(raw, (list, tuple)):
        items = list(raw)
    else:
        return []
    return ["" if i is None else str(i).strip() for i in items]


def is_retired(record: Mapping[str, object] | None, store_ids: Container[str]) -> bool:
    """Return whether *record* is retired by supersession.

    True only when ALL hold: ``status`` is ``superseded_by`` or ``superseded``;
    ``superseded_by`` names at least one successor; every successor is in
    *store_ids*; and no successor equals the record's own ``id``. ``deprecated``
    is never retired and ``req_status`` is never read.

    Args:
        record: A parsed AC mapping or a status-map entry with keys ``id``,
            ``status`` and ``superseded_by``. ``None`` or a non-mapping is
            never retired.
        store_ids: Container of every AC id in the whole store.

    Returns:
        ``True`` for a retired record, ``False`` otherwise.
    """
    if not isinstance(record, Mapping) or record.get("status") not in RETIRED_STATUSES:
        return False
    successors = successor_ids(record)
    if not successors:
        return False
    own_id = str(record.get("id") or "").strip()
    return all(s in store_ids and s != own_id for s in successors)
