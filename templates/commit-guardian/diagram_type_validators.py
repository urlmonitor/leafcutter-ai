"""
MODULE: diagram_type_validators
GOAL: Load diagram_types.json and validate the diagram_type frontmatter enum
      for docs/**/*.md files, making diagram_types.json the single source of
      truth for the diagram_type enum.
BUSINESS CONTEXT: Extracted from frontmatter_validators.py so diagram_types.json
      is the SSOT for the diagram_type: enum on docs/ files, fixing silent
      rejection of valid types (user_flow, data_flow, agent_flow) that were
      missing from the stale hardcoded DOC_FM_DIAGRAM_TYPE_VALUES list in
      config.py (EPIC-EmbeddedArchDiagramsHardening ticket 07; recreated under
      GE-103 after the module was lost in the empty-tree corruption merge).
ARCHITECTURE: Not needed.
"""

import json
from pathlib import Path
from typing import Any

from config import DOC_FM_DIAGRAM_TYPE_VALUES

_DIAGRAM_TYPES_JSON = (
    Path(__file__).resolve().parents[2]
    / "leafcutter" / "config" / "diagram_types.json"
)
_DIAGRAM_TYPES_CACHE: dict | None = None


def _load_diagram_types() -> dict:
    """Load and cache diagram type definitions from diagram_types.json.

    Falls back to DOC_FM_DIAGRAM_TYPE_VALUES (config constant) when the JSON
    file is absent — preserves backward compatibility for projects that have
    not yet added the JSON file.

    Returns:
        dict: Mapping of diagram_type key to its definition dict. Each value
            carries ``description`` and ``requires_frontmatter`` fields when
            loaded from JSON; an empty dict when synthesised from the fallback
            constant.
    """
    global _DIAGRAM_TYPES_CACHE
    if _DIAGRAM_TYPES_CACHE is not None:
        return _DIAGRAM_TYPES_CACHE
    if _DIAGRAM_TYPES_JSON.exists():
        try:
            with open(_DIAGRAM_TYPES_JSON, encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass  # Malformed/unreadable JSON — fall through to the config constant.
        else:
            _DIAGRAM_TYPES_CACHE = data.get("diagram_types", {})
            return _DIAGRAM_TYPES_CACHE
    _DIAGRAM_TYPES_CACHE = {v: {} for v in DOC_FM_DIAGRAM_TYPE_VALUES}
    return _DIAGRAM_TYPES_CACHE


def validate_diagram_type(fm: dict[str, Any]) -> list[str]:
    """Validate the ``diagram_type`` field against the allowed enum.

    Reads valid values from ``leafcutter/config/diagram_types.json``
    (falls back to the hardcoded list in config.py when the file is absent).
    The ``diagram_type`` field is optional; this function only validates the
    *value* when the field is present.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if diagram_type is invalid, empty list when
            the field is absent or contains a valid value.
    """
    diagram_type = fm.get("diagram_type")
    if diagram_type is None:
        return []  # Optional field; absence is fine.
    known = _load_diagram_types()
    if diagram_type not in known:
        return [
            f"unknown diagram_type: {diagram_type}; "
            f"valid values: {', '.join(sorted(known.keys()))}"
        ]
    return []


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-06-17 00:00 [GE-103]: Recreated this module. It was introduced by
  EPIC-EmbeddedArchDiagramsHardening ticket 07 (delegating
  frontmatter_validators.validate_diagram_type to diagram_types.json as SSOT)
  but was lost in the empty-tree corruption merge (commit 2c2aa22) and never
  redeployed, so check_doc_frontmatter.py crashed on import — silently
  disabling ALL doc-frontmatter enforcement in every consumer repo. Mirrors
  the doc_type_validators.py pattern: load JSON SSOT, fall back to the config
  constant when absent. (#GE-103)
====================================================================
"""
