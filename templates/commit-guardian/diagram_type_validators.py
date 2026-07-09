"""
MODULE: diagram_type_validators
GOAL: Load diagram_types.json and validate the diagram_type frontmatter enum
      for docs/**/*.md files, making diagram_types.json the single source of
      truth for the diagram_type enum.
BUSINESS CONTEXT: Standalone copy for templates/commit-guardian/ (legacy
      template directory). Searches ancestor directories for diagram_types.json;
      falls back to a hardcoded list when the JSON file is absent. Recreated
      under GE-103 after the module was lost in the empty-tree corruption merge
      2c2aa22. The legacy template location is maintained for hook parity
      checking only (see check_hook_parity.py).
ARCHITECTURE: Not needed.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-08 [GE-103]: Created standalone copy for templates/commit-guardian/.
  Mirrors scripts/commit_guardian/diagram_type_validators.py — self-contained,
  no import from config.py (absent in this directory). Hardcoded fallback
  includes ALL canonical enum values (GE-105). See the canonical copy at
  templates/scripts/commit_guardian/diagram_type_validators.py for the
  authoritative implementation (imports config.py from its own directory).
====================================================================
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Hardcoded fallback list — used when diagram_types.json is absent or unreadable.
# Includes ALL canonical values (GE-105) and the deprecated alias 'dataflow'.
_FALLBACK_DIAGRAM_TYPE_VALUES: list[str] = [
    "context",
    "container",
    "component",
    "sequence",
    "erd",
    "state",
    "data_flow",
    "dataflow",
    "user_flow",
    "agent_flow",
    "none",
]

_DIAGRAM_TYPES_CACHE: dict | None = None


def _find_diagram_types_json() -> Path | None:
    """Search ancestor directories for diagram_types.json.

    Checks both ``leafcutter/config/diagram_types.json`` (deployed consumer-
    project layout) and ``config/diagram_types.json`` (development layout).
    Stops at the filesystem root.

    Returns:
        Path to diagram_types.json if found, else None.
    """
    script_dir = Path(__file__).resolve().parent
    for ancestor in [script_dir, *script_dir.parents]:
        for rel in ("leafcutter/config/diagram_types.json", "config/diagram_types.json"):
            candidate = ancestor / rel
            if candidate.exists():
                return candidate
    return None


def _load_diagram_types() -> dict:
    """Load and cache diagram type definitions from diagram_types.json.

    Falls back to the hardcoded ``_FALLBACK_DIAGRAM_TYPE_VALUES`` list when
    the JSON file is absent, malformed, or unreadable. I/O and parse errors
    are logged at WARNING level before falling through to the fallback.

    Returns:
        dict: Mapping of diagram_type key to its definition dict.
    """
    global _DIAGRAM_TYPES_CACHE
    if _DIAGRAM_TYPES_CACHE is not None:
        return _DIAGRAM_TYPES_CACHE

    json_path = _find_diagram_types_json()
    if json_path is not None:
        try:
            with open(json_path, encoding="utf-8") as fh:
                data = json.load(fh)
        except json.JSONDecodeError as exc:
            logger.warning(
                "diagram_type_validators: diagram_types.json is malformed at %s"
                " — using hardcoded fallback: %s",
                json_path,
                exc,
            )
        except OSError as exc:
            logger.warning(
                "diagram_type_validators: cannot read diagram_types.json at %s"
                " — using hardcoded fallback: %s",
                json_path,
                exc,
            )
        else:
            _DIAGRAM_TYPES_CACHE = data.get("diagram_types", {})
            return _DIAGRAM_TYPES_CACHE

    _DIAGRAM_TYPES_CACHE = {v: {} for v in _FALLBACK_DIAGRAM_TYPE_VALUES}
    return _DIAGRAM_TYPES_CACHE


def validate_diagram_type(fm: dict[str, Any]) -> list[str]:
    """Validate the ``diagram_type`` field against the allowed enum.

    Reads valid values from ``diagram_types.json`` (falls back to the
    hardcoded list when the file is absent). The ``diagram_type`` field is
    optional; this function only validates the *value* when present.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if diagram_type is invalid; empty list when
            the field is absent or contains a valid value.
    """
    diagram_type = fm.get("diagram_type")
    if diagram_type is None:
        return []
    known = _load_diagram_types()
    if diagram_type not in known:
        return [
            f"unknown diagram_type: {diagram_type}; "
            f"valid values: {', '.join(sorted(known.keys()))}"
        ]
    return []
