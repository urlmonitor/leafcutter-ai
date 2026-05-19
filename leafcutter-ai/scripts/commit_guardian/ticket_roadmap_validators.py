"""
MODULE: ticket_roadmap_validators.py
GOAL: Warn-only validators for the optional roadmap ticket frontmatter fields
    ``roadmap_phase`` and ``advances_current_outcome``.
BUSINESS CONTEXT: Extracted from frontmatter_validators.py (EPIC-ProjectRoadmap
    ticket 04) to keep that file under the 400-non-docstring-line limit.
    Both validators are warn-only — they return warning strings and never block
    commits during the backfill period.
ARCHITECTURE: Imported by frontmatter_validators.validate_ticket_file. Reads
    docs/roadmap.json at validation time to verify phase IDs. Fail-open:
    absent file or parse error returns an empty list.

Warn-only contract:
- Returns a list of warning strings (never raises, never calls sys.exit).
- Callers surface warnings without blocking.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _load_roadmap_phase_ids(project_root_path: Path) -> list[str]:
    """Load valid phase IDs from docs/roadmap.json.

    Args:
        project_root_path: Absolute path to the project root where
            ``docs/roadmap.json`` resides.

    Returns:
        list[str]: Phase ID strings from ``phases[*].id``, or an empty list
            when the file is absent, unreadable, or malformed (fail-open).
    """
    roadmap_path = project_root_path / "docs" / "roadmap.json"
    try:
        with open(roadmap_path, encoding="utf-8") as f:
            data = json.load(f)
        phases = data.get("phases", [])
        if isinstance(phases, list):
            return [p["id"] for p in phases if isinstance(p, dict) and "id" in p]
    except (OSError, ValueError, KeyError):
        pass
    return []


def validate_roadmap_phase(fm: dict[str, Any], project_root_path: Path) -> list[str]:
    """Warn when roadmap_phase is present but not a known phase ID.

    Validation is warn-only (never blocks) during the backfill period.
    When ``docs/roadmap.json`` is absent the function returns no warnings
    (fail-open contract).

    Args:
        fm: Parsed frontmatter dictionary.
        project_root_path: Absolute path to the project root.

    Returns:
        list[str]: Warning messages; empty when the field is absent, valid,
            or docs/roadmap.json cannot be read.
    """
    phase = fm.get("roadmap_phase")
    if phase is None:
        return []
    known = _load_roadmap_phase_ids(project_root_path)
    if not known:
        return []
    if phase in known:
        return []
    return [
        f"roadmap_phase '{phase}' is not a known phase ID. "
        f"Valid IDs: {', '.join(known)}. (warn-only)"
    ]


def validate_advances_current_outcome(fm: dict[str, Any]) -> list[str]:
    """Warn when advances_current_outcome is present but not a boolean or null.

    The field is optional; absence or null produces no warning. Only
    non-boolean, non-null values (strings, integers, etc.) trigger a warning.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Warning messages; empty when the field is absent, null,
            or contains a boolean value.
    """
    if "advances_current_outcome" not in fm:
        return []
    value = fm["advances_current_outcome"]
    if value is None or isinstance(value, bool):
        return []
    return [
        f"advances_current_outcome must be a boolean (true/false); "
        f"got {type(value).__name__} {value!r}. (warn-only)"
    ]


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-18 00:00 [EPIC-ProjectRoadmap/ticket 04]: Extracted from (#EPIC-ProjectRoadmap/04)
  frontmatter_validators.py to keep that file under the 400-line limit.
  Contains _load_roadmap_phase_ids(), validate_roadmap_phase(), and
  validate_advances_current_outcome(). All functions are warn-only;
  they return warning strings and never call sys.exit().
  Imported by frontmatter_validators.validate_ticket_file() warnings path.
====================================================================
"""
