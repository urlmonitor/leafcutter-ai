"""
MODULE: _rc_record_schema
GOAL: Make the requirement rule check a CALLER of the store's existing record check
    (validate_ac_schema._validate_file) and turn its bare-string output into at most one
    finding per rule violated per record.
BUSINESS CONTEXT: ACD-2500a-1 ("a record that violates a rule the commit-time record
    check already enforces produces exactly one finding, not one per check that knows the
    rule"). The store check reports one rule twice inside a single call: an empty
    `components` list yields both the components rule and the schema's minItems/enum
    violation. A caller that forwards strings would double-report.
ARCHITECTURE: `collapsed_messages` runs `_validate_file` with the rule sources the
    context carries (schema and registry passed EXPLICITLY, never its script-relative
    defaults: the deployed layout has no docs/components.json), classifies each message
    to a SUBJECT (the schema form `schema violation at <path> -` -> first path segment;
    `Field '<x>'` / `Missing required field '<x>'` -> x; anything else -> the message
    itself) and keeps exactly one message per subject, preferring the non-schema
    producer because it names the registry and the fix. The absolute path prefix is
    stripped (reports carry no absolute paths). `declared_files_reports` are
    informational and dropped. A family can OWN a subject by listing it in
    `CLAIMS_SUBJECTS`: the adapter then stays silent about it and the owner reads it via
    `messages_for(ctx, record, subject)` (the non-empty-components family does this for
    `components`). This module is itself registered first in FAMILIES under the name
    "record schema" and is report-only. Deployed flat into <root>/scripts/ac_store/.

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-1]: Created per architect-review section 2.
    Known gap kept on purpose: `_validate_file` lacks the commit-hook-only checks
    (test contract, side effect, pattern bindings); the commit hook still enforces them.
"""

from __future__ import annotations

import re
from typing import Any

import validate_ac_schema
from _rc_report import DISPOSITION_DECISION, FAMILY_RECORD_SCHEMA, Finding

NAME = FAMILY_RECORD_SCHEMA

_SCHEMA_FORM = re.compile(r"schema violation at (\S+) ")
_FIELD_FORM = re.compile(r"(?:Missing required field|Field) '([^']+)'")


def subject_of(message: str) -> str:
    """The subject a store-check message is about (see module docstring)."""
    schema_hit = _SCHEMA_FORM.search(message)
    if schema_hit:
        first = schema_hit.group(1).split(".")[0]
        return first if first != "<root>" else message
    field_hit = _FIELD_FORM.search(message)
    return field_hit.group(1) if field_hit else message


def _is_schema_form(message: str) -> bool:
    """True for the jsonschema-form message (the lower-priority producer)."""
    return _SCHEMA_FORM.search(message) is not None


def collapsed_messages(ctx: Any, record: Any) -> dict[str, str]:
    """{subject: message} for `record`: one message per subject, path prefix removed.

    Cached on the record object (a repaired record is re-loaded, so its cache is fresh).
    """
    cache = getattr(record, "_rc_schema_cache", None)
    if cache is not None:
        return cache
    raw = validate_ac_schema._validate_file(  # noqa: SLF001 - the store's per-file record check
        record.path, ctx.registry_ids, ctx.schema, []
    )
    prefix = f"{record.path}: "
    chosen: dict[str, str] = {}
    for message in raw:
        text = message[len(prefix):] if message.startswith(prefix) else message
        subject = subject_of(text)
        held = chosen.get(subject)
        if held is None or (_is_schema_form(held) and not _is_schema_form(text)):
            chosen[subject] = text
    record._rc_schema_cache = chosen  # noqa: SLF001
    return chosen


def messages_for(ctx: Any, record: Any, subject: str) -> list[str]:
    """The (zero or one) collapsed store-check message for `subject` -- for the family that owns it."""
    message = collapsed_messages(ctx, record).get(subject)
    return [message] if message else []


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """One `needs a decision` finding per unclaimed subject the store check objects to."""
    claimed = ctx.claimed_subjects()
    return [
        Finding.for_record(
            record, NAME, DISPOSITION_DECISION, message, subject=subject
        )
        for subject, message in collapsed_messages(ctx, record).items()
        if subject not in claimed
    ]
