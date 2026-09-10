"""
MODULE: product_truth_index_checks
GOAL: The checks that compare the store's INDEX against a fresh derivation.
BUSINESS CONTEXT: Split out of product_truth_checks so both stay inside the
    GE-127a-1 limit, on the seam that was already there: everything here is
    about the DERIVED index (does index.json still agree with what the flows,
    mocks and mockups say?), whereas its sibling validates the artifacts
    themselves. The asof-stripping and separator-normalizing helpers live here
    because they exist only to make that index comparison date- and
    platform-agnostic; they have no meaning outside it.
ARCHITECTURE: Leaf module, same shape as product_truth_checks: every function
    is pure, taking its inputs as arguments and appending to the shared
    `errors` list. Imported by product_truth_checks, which re-exports it so
    validate_product_truth's existing imports are unchanged.
"""
from __future__ import annotations

from generate_product_truth import (
    _without_asof,
    build_by_ac,
    build_by_component,
    build_by_entity,
    build_by_flow,
)


def _strip_by_ac_asof(by_ac: dict) -> dict:
    """Return by_ac with 'asof' stripped from every entry, for date-agnostic comparison.

    The stored by_ac index carries an ``asof`` timestamp per entry that records
    when the edge was last written.  The validator's fresh rebuild always uses
    today's date, so comparing with asof intact produces false mismatches on any
    day after the last regen. Stripping both sides before the equality check lets
    us verify that the *logical* content (flow / node / entities / source / …)
    is current without being confused by the calendar.
    """
    return {
        ac_id: [_without_asof(entry) for entry in entries]
        for ac_id, entries in by_ac.items()
    }


def _strip_by_flow_asof(by_flow: dict) -> dict:
    """Return by_flow with 'asof' stripped and 'path' separator-normalized.

    The stored by_flow index carries an ``asof`` timestamp inside each flow's
    ``impl_summary``.  Same rationale as ``_strip_by_ac_asof``: stripping both
    sides isolates logical content (done / in_progress / not_started counts) from
    the calendar date. The ``path`` field is additionally separator-normalized
    (see ``_normalize_path_separators``) so a spelling-only difference between
    a POSIX- and a Windows-written path is never reported as drift
    (UXP-700c-3-i AC-2).
    """
    result = {}
    for flow_id, entry in by_flow.items():
        entry_copy = dict(entry)
        if "impl_summary" in entry_copy and isinstance(entry_copy["impl_summary"], dict):
            entry_copy["impl_summary"] = _without_asof(entry_copy["impl_summary"])
        if "path" in entry_copy:
            entry_copy["path"] = _normalize_path_separators(entry_copy["path"])
        result[flow_id] = entry_copy
    return result


def _check_derived_indexes(
    index: dict, flows: dict, flow_paths: dict, mocks: dict, ac_map: dict, errors: list[str]
) -> None:
    """D3 — the derived index maps must equal a fresh rebuild.

    For ``by_ac`` and ``by_flow``, asof timestamps are stripped from both the
    stored index and the fresh rebuild before comparison.  This avoids false
    "does not match" errors when the calendar date has advanced past the last
    regeneration but no logical content has changed.  ``by_component`` and
    ``by_entity`` contain no asof fields and are compared as-is.
    """
    rebuilds = {
        "by_component": build_by_component(index.get("artifacts", [])),
        "by_entity": build_by_entity(flows, mocks),
        "by_flow": build_by_flow(flows, flow_paths, ac_map),
        "by_ac": build_by_ac(flows),
    }
    for key, expected in rebuilds.items():
        stored = index.get(key)
        if key == "by_ac":
            stored_cmp = _strip_by_ac_asof(stored or {})
            expected_cmp = _strip_by_ac_asof(expected)
        elif key == "by_flow":
            stored_cmp = _strip_by_flow_asof(stored or {})
            expected_cmp = _strip_by_flow_asof(expected)
        else:
            stored_cmp = stored
            expected_cmp = expected
        if stored_cmp != expected_cmp:
            errors.append(f"[index] {key} does not match a fresh rebuild — run generate_product_truth.py")


def _check_index(index: dict, flows: dict, mocks: dict, mockups: dict, errors: list[str]) -> None:
    by_id = {**flows, **mocks, **mockups}
    registry = set(index.get("entity_registry", []))
    for artifact in index.get("artifacts", []):
        src = by_id.get(artifact["id"])
        if src is None:
            errors.append(f"[index] artifact '{artifact['id']}' has no file")
            continue
        for field in ("status", "readiness", "version"):
            if artifact.get(field) != src.get(field):
                errors.append(f"[index] {artifact['id']}.{field}={artifact.get(field)} != artifact {src.get(field)}")
    for artifact in list(flows.values()) + list(mocks.values()) + list(mockups.values()):
        entities = artifact.get("entities")
        iterable = entities if isinstance(entities, list) else (entities or {})
        for ent in iterable:
            if ent not in registry:
                errors.append(f"[index] entity '{ent}' (in {artifact.get('id')}) missing from entity_registry")


def _normalize_path_separators(path_value: object) -> object:
    """Return ``path_value`` with backslashes rendered as forward slashes.

    Store-relative paths are identifiers, not filesystem paths (UXP-700c-3-i):
    the record's own D3 drift check must not report a foreign-platform spelling
    of the SAME path as the record having fallen behind. ``generate_product_truth``
    always writes ``.as_posix()`` output, but a ``by_flow['path']`` entry that
    reaches this comparison by any other route (e.g. a legacy write, or a
    manual edit) may still hold a backslash-spelled value; normalizing both
    sides of the comparison here means a separator-only difference can never
    surface as drift. Non-string values pass through unchanged.
    """
    if isinstance(path_value, str):
        return path_value.replace(chr(92), "/")
    return path_value

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-10 [python-coder]: Split from product_truth_checks, which landed 3
  lines over the 400-line limit after validate_product_truth.py was broken up.
  The seam is the one already implied by the names: index-vs-derivation checks
  here, artifact checks there. Pure move, no behaviour change; the helpers came
  along because they serve only this comparison. (#EPIC-TruthfulProjectRecord)
====================================================================
"""
