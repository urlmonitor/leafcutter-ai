#!/usr/bin/env python3
"""
_ac_components.py — Shared helpers for the AC `components` membership field.

The knowledge graph's `component_membership` edge is built from the LIST field
`components` on each AC (see config/paths.json `acs` surface `edge_fields` and
scripts/knowledge_query.py). The authoritative registry of valid component ids
is docs/components.json (the top-level `components` object's keys, underscore-case).
This is the SAME registry the docs surface validates against (check_doc_frontmatter),
so ACs, docs, tickets, and registries all share one component vocabulary.

This module centralises two concerns so the schema validator
(validate_ac_schema.py) and the backfill (backfill_components.py) agree exactly
on what "a valid components field" means:

  - load_registry_ids(): parse the docs/components.json registry keys.
  - components_field_errors(): validate an AC's `components` field against it.

KM-KGS-100e-1 / -1-i / -1-ii: a criterion must declare a non-empty `components`
list, every entry must be a non-empty string, and every entry must name a
component present in the registry.
"""

from __future__ import annotations

import json
from pathlib import Path

# Default location of the canonical component registry, relative to the repo root.
_REGISTRY_REL = Path("docs") / "components.json"


def default_registry_path() -> Path:
    """Return the repo-root-relative components.json path from this script's location.

    scripts/ac_store/_ac_components.py -> repo_root/docs/components.json
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / _REGISTRY_REL


# Backward-compatible alias for callers that still import default_index_path.
default_index_path = default_registry_path


def load_registry_ids(registry_path: Path | None = None) -> set[str]:
    """Load the set of valid component ids from docs/components.json.

    Args:
        registry_path: Path to components.json. Defaults to the repo's canonical
            location.

    Returns:
        Set of component id strings (the keys of the top-level `components`
        object). Empty set if the registry cannot be read or parsed (callers
        decide how to treat an empty registry).
    """
    path = registry_path if registry_path is not None else default_registry_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return set()

    if not isinstance(data, dict):
        return set()
    components = data.get("components")
    if not isinstance(components, dict):
        return set()

    return {str(k).strip() for k in components if isinstance(k, str) and k.strip()}


def components_field_errors(
    data: dict,
    registry_ids: set[str],
) -> list[str]:
    """Validate an AC's `components` field. Returns error strings (empty = valid).

    Rules (KM-KGS-100e-1, -1-i, -1-ii):
      - `components` must be present and a non-empty list — a missing key, an
        empty list, and a list containing only empty strings all fail (-1-i).
      - every entry must be a non-empty string.
      - every entry must name a component present in the registry (-1-ii). This
        check is skipped only when the registry is empty (unreadable components.json),
        so a broken registry never blocks all commits.
    """
    errors: list[str] = []

    raw = data.get("components")
    if raw is None or not isinstance(raw, list):
        errors.append(
            "Missing required field 'components': declare a non-empty list naming "
            "the component(s) this criterion belongs to, e.g. "
            "components: [knowledge_system]. This is the field the knowledge "
            "graph reads to build component_membership edges."
        )
        return errors

    non_empty = [v for v in raw if isinstance(v, str) and v.strip()]
    if not non_empty:
        errors.append(
            "Field 'components' must be a non-empty list of component ids "
            "(got an empty list or only blank entries)."
        )
        return errors

    if registry_ids:
        unknown = sorted(
            {v for v in non_empty if v not in registry_ids}
        )
        if unknown:
            errors.append(
                f"Field 'components' names unknown component(s) {unknown}. "
                f"Valid components (docs/components.json): "
                f"{sorted(registry_ids)}."
            )

    return errors
