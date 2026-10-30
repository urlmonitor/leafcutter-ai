#!/usr/bin/env python3
"""
MODULE: _ac_schema_test_spec_validators
GOAL: Hand-rolled, entry-naming validation for ``test_spec[].angle`` and
    ``test_spec[].must_catch`` — the two TQ-500f-1 / TQ-500f-2-i fields whose
    rejection messages must name the offending entry, the field, and (for
    ``must_catch``) which rule failed.
    Also (ACD-2500c-3) rejects an entry key the schema does not declare, by name.
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


def _declared_entry_keys(schema: dict[str, Any] | None) -> set[str] | None:
    """Return the property names a ``test_spec`` entry may carry, read from *schema*.

    Uses the same ``oneOf`` navigation as ``_permitted_test_spec_angles`` so the
    closed key set has one source of truth (ACD-2500c-3), never a second typed list.

    Args:
        schema: Parsed ``config/ac_store_schema.json`` content, or ``None``.

    Returns:
        The declared item property names, or ``None`` when *schema* is ``None`` or
        its shape is unexpected (the closed set is then unknowable).
    """
    if schema is None:
        return None
    try:
        test_spec = schema["properties"]["test_spec"]
        array_branches = [b for b in test_spec["oneOf"] if b.get("type") == "array"]
        properties = array_branches[0]["items"]["properties"]
    except (KeyError, IndexError, TypeError):
        return None
    return set(properties) if isinstance(properties, dict) and properties else None


def _unknown_key_errors(
    path: Path, entry_name: str, item: dict[str, Any], declared: set[str] | None
) -> list[str]:
    """Report each ``test_spec`` entry key the schema does not declare, by name.

    Args:
        path: The AC YAML file being validated (for error prefixing).
        entry_name: The ``test_spec`` entry's ``name`` (or a placeholder).
        item: The ``test_spec`` entry dict.
        declared: The schema-declared key set, or ``None`` (check skipped).

    Returns:
        One error per undeclared key, in sorted key order.
    """
    if declared is None:
        return []
    return [
        f"{path}: test_spec entry {entry_name!r} has undeclared key {key!r}. "
        f"Declared keys: {sorted(declared)}."
        for key in sorted(map(str, set(item) - declared))
    ]


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


def _replacement_error(item: Any) -> str | None:
    """Return why one declared replacement is malformed, or ``None`` when it is well formed."""
    if not isinstance(item, dict):
        return f"a replacement must be an object, got {type(item).__name__}"
    extra = sorted(map(str, set(item) - {"path", "old", "new"}))
    if extra:
        return f"a replacement has unknown key(s) {extra}"
    for key in ("path", "old", "new"):
        if not isinstance(item.get(key), str):
            return f"a replacement needs a string {key!r}"
    if not item["path"].strip() or not item["old"].strip():
        return "a replacement's 'path' and 'old' need at least one non-whitespace character"
    return None


def _declared_replacements_errors(path: Path, entry_name: str, item: dict[str, Any]) -> list[str]:
    """Report ``test_spec[].declared_replacements`` violations, naming entry/field/name/rule (TQ-500g-1-xvii).

    The value is an object whose keys are names this entry's ``must_catch`` lists (spelled exactly)
    and whose values are non-empty lists of ``{path, old, new}``. The generic schema check cannot
    name the entry or the name, so the gate that actually runs (this module) does.

    Args:
        path: The AC YAML file being validated (for error prefixing).
        entry_name: The ``test_spec`` entry's ``name`` (or a placeholder).
        item: The ``test_spec`` entry dict.

    Returns:
        Error message strings; empty when the field is absent or valid.
    """
    if "declared_replacements" not in item:
        return []
    declared = item["declared_replacements"]
    head = f"{path}: test_spec entry {entry_name!r} field 'declared_replacements'"
    if not isinstance(declared, dict) or not declared:
        return [f"{head} must be a non-empty object keyed by must_catch names, got {declared!r}."]
    listed = item.get("must_catch")
    listed = listed if isinstance(listed, list) else []
    errors: list[str] = []
    for name, repls in declared.items():
        if name not in listed:
            errors.append(f"{head} names {name!r}, which this entry's must_catch does not list.")
        elif not isinstance(repls, list) or not repls:
            errors.append(f"{head} for name {name!r} must be a non-empty list of replacements.")
        else:
            errors.extend(f"{head} for name {name!r}: {why}." for why in map(_replacement_error, repls) if why)
    return errors


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
    declared_keys = _declared_entry_keys(schema)
    errors: list[str] = []
    for item in test_spec:
        if not isinstance(item, dict):
            continue
        entry_name = item.get("name", "<unnamed test_spec entry>")
        errors.extend(_angle_field_errors(path, entry_name, item, permitted_angles))
        errors.extend(_must_catch_field_errors(path, entry_name, item))
        errors.extend(_declared_replacements_errors(path, entry_name, item))
        errors.extend(_unknown_key_errors(path, entry_name, item, declared_keys))
    return errors


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-25 [python-coder/TQ-500f-1, TQ-500f-2-i]: Created. Extracted from
  validate_ac_schema.py (which was already over its 400-line ratchet limit
  at HEAD) so the entry-naming test_spec[].angle / .must_catch checks could
  be added without growing that file past its GE-127b-1 previous length.
- 2026-10-30 [python-coder/TQ-500g-1-xvii]: Added the entry-naming check of the
  optional test_spec[].declared_replacements field (keys must be listed by the
  entry's must_catch; shape of each replacement). (#EPIC-OnceANamedWrongVersionIsPreparedAnd/08) (ADR-080)
====================================================================
"""
