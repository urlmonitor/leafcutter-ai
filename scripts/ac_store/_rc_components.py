"""
MODULE: _rc_components
GOAL: Rule family "non-empty graph component list": an empty `components` list is filled
    only when the record's namespace maps to exactly one graph id; everything else the
    store's record check objects to about `components` is reported, never rewritten.
BUSINESS CONTEXT: ACD-2500a-2-ii. `component` is the kebab namespace ("ac-driven-dev");
    `components` holds graph ids ("ac_driven_dev"). Filling the second from the first is
    only safe with one candidate. A non-empty list (even a wrong one) is never rewritten.
ARCHITECTURE: Claims the store-check subject `components` (CLAIMS_SUBJECTS) so the
    "record schema" adapter stays silent and this family is the single reporter. An empty
    or missing list: candidates come from `ctx.migration_map[record["component"]]` (a
    string or a list of strings); exactly one candidate present in the registry gives a
    `fixed` finding with `repair=("components", ("set", [id]))`, zero or several give
    `needs a decision` naming them. A non-empty list is judged by the store check's own
    message (`_rc_record_schema.messages_for`), so the registry stays the one rule source.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-2-ii]: Created (ticket 11).
"""

from __future__ import annotations

from typing import Any

import _rc_record_schema
from _rc_report import DISPOSITION_DECISION, DISPOSITION_FIXED, FAMILY_COMPONENTS, Finding

NAME = FAMILY_COMPONENTS
CLAIMS_SUBJECTS = ("components",)


def _candidates(ctx: Any, namespace: Any) -> list[str]:
    """The graph ids the migration map offers for `namespace` (deduplicated, in order)."""
    mapped = ctx.migration_map.get(namespace) if isinstance(namespace, str) else None
    if mapped is None:
        return []
    items = [mapped] if isinstance(mapped, str) else list(mapped)
    return list(dict.fromkeys(str(i) for i in items if i))


def _fill(ctx: Any, record: Any) -> list[Finding]:
    """Findings for an empty or missing `components` list."""
    namespace = record.get("component")
    found = _candidates(ctx, namespace)
    if len(found) != 1:
        detail = f"candidates: {', '.join(found)}" if found else "no candidate graph component id"
        message = (
            f"components is empty and namespace {namespace!r} does not map to exactly one graph "
            f"component id ({detail}); choose the components by hand"
        )
        return [Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject="components")]
    if ctx.registry_ids and found[0] not in ctx.registry_ids:
        message = f"components is empty and its only candidate {found[0]!r} is not in the components registry"
        return [Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject="components")]
    message = f"components was empty; set to [{found[0]}] from namespace {namespace!r}"
    return [
        Finding.for_record(
            record, NAME, DISPOSITION_FIXED, message,
            subject="components", repair=("components", ("set", [found[0]])),
        )
    ]


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """Fill an empty list from a single mapping; report any other `components` violation."""
    value = record.get("components")
    if value is None or value == []:
        return _fill(ctx, record)
    return [
        Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject="components")
        for message in _rc_record_schema.messages_for(ctx, record, "components")
    ]
