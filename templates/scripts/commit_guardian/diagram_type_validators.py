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
ARCHITECTURE: Resolves diagram_types.json via an ancestor-directory walk
      (checks both ``leafcutter/config/diagram_types.json`` and
      ``config/diagram_types.json`` at each ancestor level, starting from this
      script's directory). The ancestor walk is portable across both the source-
      tree layout (templates/scripts/commit_guardian/) and deployed layout
      (.leafcutter/scripts/commit_guardian/) without a hardcoded parents[N]
      index. Falls back to DOC_FM_DIAGRAM_TYPE_VALUES (config constant) when no
      JSON file is found. I/O and parse errors are logged at WARNING level before
      falling through to the fallback.
"""

import json
import logging
from pathlib import Path
from typing import Any

from config import DOC_FM_DIAGRAM_TYPE_VALUES

logger = logging.getLogger(__name__)

_DIAGRAM_TYPES_CACHE: dict | None = None


def _find_diagram_types_json(_start_dir: Path | None = None) -> Path | None:
    """Search ancestor directories for diagram_types.json.

    Checks both ``leafcutter/config/diagram_types.json`` (deployed consumer-
    project layout) and ``config/diagram_types.json`` (development layout)
    at each ancestor level, stopping at the filesystem root.

    Args:
        _start_dir: Override the starting directory (used in tests). Defaults
                    to the directory containing this script file.

    Returns:
        Path to diagram_types.json if found, else None.
    """
    script_dir = _start_dir if _start_dir is not None else Path(__file__).resolve().parent
    for ancestor in [script_dir, *script_dir.parents]:
        for rel in ("leafcutter/config/diagram_types.json", "config/diagram_types.json"):
            candidate = ancestor / rel
            if candidate.exists():
                return candidate
    return None


def _load_diagram_types() -> dict:
    """Load and cache diagram type definitions from diagram_types.json.

    Resolves the JSON file via an ancestor-directory walk (see
    ``_find_diagram_types_json``). Falls back to DOC_FM_DIAGRAM_TYPE_VALUES
    (config constant) when the JSON file is absent, malformed, or unreadable.
    I/O and parse errors are logged at WARNING level before falling through
    to the fallback.

    Returns:
        dict: Mapping of diagram_type key to its definition dict. Each value
            carries ``description`` and ``requires_frontmatter`` fields when
            loaded from JSON; an empty dict when synthesised from the fallback
            constant.
    """
    global _DIAGRAM_TYPES_CACHE
    if _DIAGRAM_TYPES_CACHE is not None:
        return _DIAGRAM_TYPES_CACHE

    json_path = _find_diagram_types_json()
    if json_path is not None:
        try:
            with open(json_path, encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            logger.warning(
                "diagram_type_validators: diagram_types.json is malformed at %s"
                " — using config fallback: %s",
                json_path,
                exc,
            )
        except OSError as exc:
            logger.warning(
                "diagram_type_validators: cannot read diagram_types.json at %s"
                " — using config fallback: %s",
                json_path,
                exc,
            )
        else:
            _DIAGRAM_TYPES_CACHE = data.get("diagram_types", {})
            return _DIAGRAM_TYPES_CACHE

    _DIAGRAM_TYPES_CACHE = {v: {} for v in DOC_FM_DIAGRAM_TYPE_VALUES}
    return _DIAGRAM_TYPES_CACHE


def validate_diagram_type(fm: dict[str, Any]) -> list[str]:
    """Validate the ``diagram_type`` field against the allowed enum.

    Reads valid values from ``diagram_types.json`` via an ancestor-directory
    walk (falls back to the config constant when the file is absent). The
    ``diagram_type`` field is optional; this function only validates the
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
- 2026-07-14 [python-coder/TICKET-20260709-CommitGuardianHardeningFollowups]:
  AC-2: Replaced broken parents[2] fixed path (resolved to
  templates/leafcutter/config/ — never exists in any layout) with the
  _find_diagram_types_json() ancestor walk ported from the superior legacy
  implementation in templates/commit-guardian/diagram_type_validators.py.
  Added WARNING logging to the now-reachable except (json.JSONDecodeError, OSError)
  blocks (previously unreachable because parents[2] never existed, so the code
  always fell through to the config fallback silently). Added optional _start_dir
  parameter to _find_diagram_types_json() for testability without __file__
  patching. Accept/reject behavior for all canonical enum values (data_flow,
  user_flow, agent_flow, dataflow) is unchanged. (AC-2)
====================================================================
"""
