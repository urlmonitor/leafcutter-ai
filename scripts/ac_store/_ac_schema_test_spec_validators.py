#!/usr/bin/env python3
"""
MODULE: _ac_schema_test_spec_validators
GOAL: Hand-rolled, entry-naming validation for ``test_spec[].angle`` and
    ``test_spec[].must_catch`` — the two TQ-500f-1 / TQ-500f-2-i fields whose
    rejection messages must name the offending entry, the field, and (for
    ``must_catch``) which rule failed.
BUSINESS CONTEXT: ``test_spec`` is a JSON Schema ``oneOf`` (array branch or
    null branch) in ``config/ac_store_schema.json``. jsonschema's generic
    ``Draft7Validator`` report against a ``oneOf`` collapses any violation
    inside the array branch into one "is not valid under any of the given
    schemas" message, which names neither the offending entry nor the
    field. TQ-500f-1's own it_requirement is explicit that the validator
    which actually gates commits (``validate_ac_schema.py`` / the
    check-ac-schema hook) must name both, plus (for ``angle``) the full
    permitted list and (for ``must_catch``) which rule failed — empty list,
    blank entry, or not a list. This module supplies that hand-rolled pass;
    it runs ALONGSIDE the generic schema check in ``validate_ac_schema.py``,
    never instead of it.
ARCHITECTURE: Split out of ``validate_ac_schema.py`` itself (GE-127b-1's
    file-size ratchet: that module was already over its 400-line limit at
    HEAD, so growing it further would be refused at commit time). Pure
    functions, no I/O beyond the ``schema``/``data`` dicts the caller
    already loaded; imported as a bare sibling module the same way
    ``validate_ac_schema.py`` already imports ``_ac_components``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _permitted_test_spec_angles(schema: dict[str, Any] | None) -> set[str] | None:
    """Return the permitted ``test_spec[].angle`` enum from *schema*, or ``None``.

    Navigates the same ``oneOf`` shape (``test_spec`` is either the array
    branch or the null branch) that ``done_proof._load_permitted_angle_kinds``
    and the BP-1100g-1 lockstep test both use, so this reads the identical
    single source of truth rather than a fourth hand-typed copy of the
    vocabulary.

    Args:
        schema: Parsed ``config/ac_store_schema.json`` content, or ``None``
            when schema-level validation was skipped for this run.

    Returns:
        The permitted angle strings, or ``None`` when *schema* is ``None``
        or its shape is unexpected — distinct from an empty set, which would
        wrongly read as "nothing is permitted".
    """
    if schema is None:
        return None
    try:
        test_spec = schema["properties"]["test_spec"]
        array_branches = [b for b in test_spec["oneOf"] if b.get("type") == "array"]
        item_schema = array_branches[0]["items"]
        enum = item_schema.get("properties", {}).get("angle", {}).get("enum")
    except (KeyError, IndexError, TypeError):
        return None
    return set(enum) if enum else None


def _angle_field_errors(
    path: Path, entry_name: str, item: dict[str, Any], permitted: set[str] | None
) -> list[str]:
    """Report an unrecognised ``test_spec[].angle`` value, naming entry/field/permitted list.

    Args:
        path: The AC YAML file being validated (for error prefixing).
        entry_name: The ``test_spec`` entry's ``name`` (or a placeholder).
        item: The ``test_spec`` entry dict.
        permitted: The schema-backed permitted angle set, or ``None`` when
            unavailable (in which case this check is skipped — the schema
            check itself already ran, or was explicitly reported as
            skipped).

    Returns:
        Zero or one error string.
    """
    if "angle" not in item or permitted is None:
        return []
    angle = item["angle"]
    if angle in permitted:
        return []
    return [
        f"{path}: test_spec entry {entry_name!r} has invalid field 'angle' "
        f"value {angle!r}. Permitted values: {sorted(permitted)}."
    ]


def _must_catch_field_errors(path: Path, entry_name: str, item: dict[str, Any]) -> list[str]:
    """Report ``test_spec[].must_catch`` shape violations, naming entry/field/rule.

    TQ-500f-2-i: each rejection must name the entry, the field 'must_catch',
    and which rule failed — empty list, blank entry (empty or whitespace-only
    string), or not a list. A raw jsonschema dump that only says "does not
    match" satisfies none of those.

    Args:
        path: The AC YAML file being validated (for error prefixing).
        entry_name: The ``test_spec`` entry's ``name`` (or a placeholder).
        item: The ``test_spec`` entry dict.

    Returns:
        Error message strings; empty when ``must_catch`` is absent or valid.
    """
    if "must_catch" not in item:
        return []
    must_catch = item["must_catch"]
    if not isinstance(must_catch, list):
        return [
            f"{path}: test_spec entry {entry_name!r} field 'must_catch' must be "
            f"a list, got {type(must_catch).__name__}."
        ]
    if not must_catch:
        return [
            f"{path}: test_spec entry {entry_name!r} field 'must_catch' must not "
            "be an empty list — absence already means 'none named'."
        ]
    return [
        f"{path}: test_spec entry {entry_name!r} field 'must_catch' has a blank "
        f"entry ({entry!r}) — every item must contain at least one "
        "non-whitespace character."
        for entry in must_catch
        if not isinstance(entry, str) or not entry.strip()
    ]


def test_spec_entry_errors(
    path: Path, data: dict[str, Any], schema: dict[str, Any] | None
) -> list[str]:
    """Hand-rolled, entry-naming validation for ``test_spec[].angle``/``.must_catch``.

    Runs ALONGSIDE the generic ``jsonschema`` check (``_schema_field_errors``
    in ``validate_ac_schema.py``), never instead of it: the generic check is
    still the authoritative gate, but because ``test_spec`` is a ``oneOf`` its
    own failures collapse into one message that names neither the offending
    entry nor the field. TQ-500f-1 / TQ-500f-2-i require the validator that
    actually gates commits (this CLI, the check-ac-schema hook) to name both,
    so this function re-walks ``test_spec`` by hand.

    Args:
        path: The AC YAML file being validated (for error prefixing).
        data: Parsed YAML content.
        schema: Parsed ``config/ac_store_schema.json`` content, or ``None``.

    Returns:
        Error message strings; empty when every entry is well-formed.
    """
    test_spec = data.get("test_spec")
    if not isinstance(test_spec, list):
        return []
    permitted_angles = _permitted_test_spec_angles(schema)
    errors: list[str] = []
    for item in test_spec:
        if not isinstance(item, dict):
            continue
        entry_name = item.get("name", "<unnamed test_spec entry>")
        errors.extend(_angle_field_errors(path, entry_name, item, permitted_angles))
        errors.extend(_must_catch_field_errors(path, entry_name, item))
    return errors


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-25 [python-coder/TQ-500f-1, TQ-500f-2-i]: Created. Extracted from
  validate_ac_schema.py (which was already over its 400-line ratchet limit
  at HEAD) so the entry-naming test_spec[].angle / .must_catch checks could
  be added without growing that file past its GE-127b-1 previous length.
====================================================================
"""
