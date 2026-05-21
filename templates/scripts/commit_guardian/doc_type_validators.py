"""
MODULE: doc_type_validators
GOAL: Load doc_types.json and validate the type frontmatter enum for docs/**/*.md
      files, and validate requires_documentation ticket frontmatter entries against
      the same enum.
BUSINESS CONTEXT: Extracted to keep frontmatter_validators.py under the 400-line
      limit while making doc_types.json the single source of truth for the doc type
      enum (EPIC-ArchitectureDocsEnforcement ticket 08).
ARCHITECTURE: Not needed.
"""

import json
from pathlib import Path
from typing import Any

from scripts.commit_guardian.config import DOC_FM_ALLOWED_TYPES

_DOC_TYPES_JSON = (
    Path(__file__).resolve().parents[2]
    / "leafcutter" / "config" / "doc_types.json"
)
_DOC_TYPES_CACHE: dict | None = None


def _load_doc_types() -> dict:
    """Load and cache doc type definitions from doc_types.json.

    Falls back to DOC_FM_ALLOWED_TYPES (config constant) when the JSON file is
    absent — preserves backward compatibility for projects that have not yet added
    the JSON file.

    Returns:
        dict: Mapping of doc_type key to its definition dict. Each value has
            ``description``, ``writer_agent`` (str or None), and ``default_path``
            fields.
    """
    global _DOC_TYPES_CACHE
    if _DOC_TYPES_CACHE is not None:
        return _DOC_TYPES_CACHE
    if _DOC_TYPES_JSON.exists():
        try:
            with open(_DOC_TYPES_JSON, encoding="utf-8") as f:
                data = json.load(f)
            _DOC_TYPES_CACHE = data.get("doc_types", {})
            return _DOC_TYPES_CACHE
        except (json.JSONDecodeError, OSError):
            pass
    _DOC_TYPES_CACHE = {v: {} for v in DOC_FM_ALLOWED_TYPES}
    return _DOC_TYPES_CACHE


def validate_doc_type(fm: dict[str, Any]) -> list[str]:
    """Validate the ``type`` field against the allowed doc type enum.

    Reads valid values from ``leafcutter/config/doc_types.json``
    (falls back to the hardcoded list in config.py when the file is absent).
    The ``type`` field is required on docs/ files; this function only validates
    the *value* when the field is present.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if type is invalid, empty list when the field
            is absent or contains a valid value.
    """
    doc_type = fm.get("type")
    if doc_type is None:
        return []  # Absence already caught by validate_required_fields
    known = _load_doc_types()
    if doc_type not in known:
        return [
            f"unknown doc type: {doc_type}; "
            f"valid values: {', '.join(sorted(known.keys()))}"
        ]
    return []


def validate_requires_documentation(fm: dict[str, Any]) -> list[str]:
    """Validate the optional ``requires_documentation`` ticket frontmatter field.

    When present, must be a YAML list where each entry is a key in
    ``doc_types.json``. Tickets missing this field pass without error
    (field is optional, backward-compatible).

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error messages for invalid entries; empty list when the
            field is absent or all entries are valid.
    """
    value = fm.get("requires_documentation")
    if value is None:
        return []  # Optional field; absence is fine
    if not isinstance(value, list):
        return ["'requires_documentation' must be a list (e.g. [how_to, reference])"]
    known = _load_doc_types()
    if not known:
        return []  # doc_types.json absent or empty — permissive fallback
    errors: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            errors.append(
                f"'requires_documentation' entries must be strings; got {entry!r}"
            )
        elif entry not in known:
            errors.append(
                f"unknown doc_type in requires_documentation: {entry}; "
                f"valid values: {', '.join(sorted(known.keys()))}"
            )
    return errors


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-14 00:00 [EPIC-ArchitectureDocsEnforcement/ticket 08]:
  Created. Extracted doc-type validation into this module to keep
  frontmatter_validators.py under 400 lines and make doc_types.json
  the SSOT for the type: enum on docs/ files. Added
  validate_requires_documentation() for the new optional ticket
  frontmatter field introduced by ticket 08. Mirrors the
  diagram_type_validators.py pattern introduced in ticket 05.
====================================================================
"""
