"""
MODULE: _rc_protected_fields
GOAL: Rule family "protected fields": a field the running stage does not own, changed on a
    record that already existed at stage start, is reported `needs a decision` and fails
    the stage; the family never repairs anything.
BUSINESS CONTEXT: ACD-2500a-2-vi / -vii (ADR-072). The test designer and the technical
    planner's hand-back pass each own a few fields of a record and must leave the rest
    byte-identical. templates/agents/test-designer.md says so in prose; this family is the
    deterministic backstop that compares every protected field against its committed value.
ARCHITECTURE: Pure `evaluate_record`. Two tables decide everything, so a rule change is one
    edit here and nothing else: PROTECTED_FIELDS (the fixed list, held once; a parity test
    holds it equal to test-designer.md) and OWNER_MAP ({stage: fields that stage may change}).
    The compared universe is PROTECTED_FIELDS plus the test designer's own outputs
    (DESIGN_OUTPUT_FIELDS); a stage may change whatever OWNER_MAP lists for it, and every
    other compared field is reported. A stage OWNER_MAP does not list (po, ba, itpo,
    approval: they own these fields) is `not evaluated`, never failed. The before value is
    the committed record (`ctx.before.committed_record`); a run with no before-state, a
    readiness-only snapshot, or a record created during the stage is `not evaluated` with
    the reason in the message. it_requirements: list or string form is one value, mapping
    form is compared key by key (never reference_file_path, which the test-design stage
    fills), a change of form is a change. A file finding is compared sub-field by
    sub-field (named `file_findings[<file>].<key>`) when the findings line up, else as
    `file_findings`. A covered_by entry the rule check's own back-link repair appended in
    this run (`ctx.applied_repairs`) is not the stage's change. One finding per
    (record, field); detail is {field, stage, before, after}. Deployed flat.

DECISION HISTORY:
  - 2026-10-21 [python-coder/ACD-2500a-2-vi]: Created. The fixed list and the report-only
    disposition follow the AC; the family reads the committed record from BeforeState.
  - 2026-10-21 [python-coder/ACD-2500a-2-vi, review L-1]: absent, None and empty compare equal; two
    file findings on one file get `file#index` sub-field names so they stay distinct.
  - 2026-10-21 [python-coder/ACD-2500a-2-viii, review H-1]: the no-before-state test is
    `ctx.has_before_state` (an unreadable before-state counts as none).
  - 2026-10-21 [python-coder/ACD-2500a-2-vii]: OWNER_MAP added (user decision): test-design
    owns the designer's outputs, itpo-handback owns assigned_agent, a finding's decision,
    it_requirements, declared_files, delivers_to and expects_from.
"""

from __future__ import annotations

import json
import re
from typing import Any

from _rc_report import DISPOSITION_DECISION, DISPOSITION_NOT_EVALUATED, FAMILY_PROTECTED, Finding

NAME = FAMILY_PROTECTED

PROTECTED_FIELDS: tuple[str, ...] = (
    "criteria", "test_intent", "assigned_agent", "implements_pattern", "pattern_bindings",
    "declared_files", "covered_by", "delivers_to", "expects_from", "test_required", "it_requirements",
)
DESIGN_OUTPUT_FIELDS: tuple[str, ...] = (
    "test_spec", "test_design_authorship", "test_design_opened_files", "file_findings",
    "file_findings_opened_files",
)
OWNER_MAP: dict[str, tuple[str, ...]] = {
    "test-design": DESIGN_OUTPUT_FIELDS,
    "itpo-handback": (
        "assigned_agent", "file_findings[].decision", "it_requirements", "declared_files",
        "delivers_to", "expects_from",
    ),
}

_FREE_KEY = "reference_file_path"
_SHOWN = 80


def _base(name: str) -> str:
    """The field a compared name belongs to: `it_requirements.k` and `file_findings[f].k` -> the field."""
    return re.split(r"[.\[]", name, maxsplit=1)[0]


def _generic(name: str) -> str:
    """`file_findings[<file>].key` -> `file_findings[].key`, the form OWNER_MAP lists; others unchanged."""
    return re.sub(r"\[[^\]]*\]", "[]", name)


def _owned(name: str, allowed: tuple[str, ...]) -> bool:
    """True when the stage may change `name`: listed itself, generically, or by its whole field."""
    return name in allowed or _generic(name) in allowed or _base(name) in allowed


def _same(before: Any, after: Any) -> bool:
    """Equal values; absent, None and an empty list, mapping or string are one value (L-1)."""
    return (before or None) == (after or None)


def _it_requirements_changes(before: Any, after: Any) -> list[tuple[str, Any, Any]]:
    """Per-key changes when both are mappings (reference_file_path ignored); one value otherwise."""
    if not (isinstance(before, dict) and isinstance(after, dict)):
        return [("it_requirements", before, after)] if not _same(before, after) else []
    keys = sorted((set(before) | set(after)) - {_FREE_KEY}, key=str)
    return [(f"it_requirements.{k}", before.get(k), after.get(k)) for k in keys if not _same(before.get(k), after.get(k))]


def _lined_up(before: Any, after: Any) -> bool:
    """True when both are lists of mappings with the same length and the same `file` at each index."""
    if not (isinstance(before, list) and isinstance(after, list) and len(before) == len(after)):
        return False
    pairs = list(zip(before, after))
    return all(isinstance(b, dict) and isinstance(a, dict) and b.get("file") == a.get("file") for b, a in pairs)


def _file_findings_changes(before: Any, after: Any, allowed: tuple[str, ...]) -> list[tuple[str, Any, Any]]:
    """Sub-field changes of the file findings a stage may not change; the whole list when they do not line up."""
    if _same(before, after):
        return []
    if not _lined_up(before, after):
        return [("file_findings", before, after)]
    found: list[tuple[str, Any, Any]] = []
    files = [old.get("file") for old in before]
    for index, (old, new) in enumerate(zip(before, after)):
        label = f"{old.get('file')}#{index}" if files.count(old.get("file")) > 1 else str(old.get("file"))
        for key in sorted((set(old) | set(new)) - {"file"}, key=str):
            name = f"file_findings[{label}].{key}"
            if not _same(old.get(key), new.get(key)) and not _owned(name, allowed):
                found.append((name, old.get(key), new.get(key)))
    return found


def _stage_additions(ctx: Any, record: Any, field: str, after: Any) -> Any:
    """`after` without the covered_by entries this run's own back-link repair appended."""
    if field != "covered_by" or not isinstance(after, list):
        return after
    added = {how[1] for name, how in ctx.applied_repairs.get(record.file, []) if name == "covered_by"}
    return [item for item in after if item not in added]


def changes(ctx: Any, record: Any, committed: dict[str, Any], allowed: tuple[str, ...]) -> list[tuple[str, Any, Any]]:
    """Every (field, before, after) the stage changed that it does not own, in a fixed order."""
    found: list[tuple[str, Any, Any]] = []
    for field in (*PROTECTED_FIELDS, *DESIGN_OUTPUT_FIELDS):
        if field in allowed:
            continue
        before, after = committed.get(field), _stage_additions(ctx, record, field, record.get(field))
        if field == "it_requirements":
            found.extend(c for c in _it_requirements_changes(before, after) if not _owned(c[0], allowed))
        elif field == "file_findings":
            found.extend(_file_findings_changes(before, after, allowed))
        elif not _same(before, after):
            found.append((field, before, after))
    return found


def _skip_reason(ctx: Any, record: Any) -> str | None:
    """Why this record cannot be judged (a `not evaluated` message), or None when it can."""
    if not ctx.has_before_state:
        return "not evaluated: no before-state"
    if not ctx.before.has_fields:
        return "not evaluated: the before-state holds readiness only, no field values"
    if ctx.stage not in OWNER_MAP:
        return f"not evaluated: stage {ctx.stage!r} is not in the owner map"
    committed = ctx.before.committed_record(record)
    if committed is None:
        return "not evaluated: new record"
    if not committed:
        return "not evaluated: the committed record could not be read"
    return None


def _shown(value: Any) -> str:
    """A short repr of a value for the message (the full value is in the detail)."""
    text = repr(value)
    return text if len(text) <= _SHOWN else text[:_SHOWN] + "..."


def _plain(value: Any) -> Any:
    """`value` as plain JSON data (a YAML date or other non-JSON scalar becomes its string)."""
    return json.loads(json.dumps(value, default=str))


def evaluate_record(ctx: Any, record: Any) -> list[Finding]:
    """One `needs a decision` per protected field the stage changed without owning it; never repairs."""
    reason = _skip_reason(ctx, record)
    if reason is not None:
        return [Finding.for_record(record, NAME, DISPOSITION_NOT_EVALUATED, reason, subject="not-evaluated")]
    committed = ctx.before.committed_record(record)
    found: list[Finding] = []
    for field, before, after in changes(ctx, record, committed, OWNER_MAP[ctx.stage]):
        message = (
            f"{record['id']} ({record.file}): field {field} was changed during stage {ctx.stage}, "
            f"which does not own it: before {_shown(before)}, after {_shown(after)}"
        )
        detail = {"field": field, "stage": ctx.stage, "before": _plain(before), "after": _plain(after)}
        found.append(Finding.for_record(record, NAME, DISPOSITION_DECISION, message, subject=field, detail=detail))
    return found
