"""
Frontmatter validation helpers for check_doc_frontmatter.py.

MODULE: frontmatter_validators.py
GOAL: Provide reusable validation functions for YAML documentation compliance,
    plus the per-file ``validate_doc_file`` / ``validate_ticket_file`` wrappers
    that orchestrate them.
BUSINESS CONTEXT: Extracted from check_doc_frontmatter.py to keep it under the 400-line limit.
ARCHITECTURE: Not needed.
"""

import fnmatch
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from scripts.commit_guardian.config import (
    DOC_FM_ALLOWED_STATUSES,
    DOC_FM_FLIGHT_LEVEL_VALUES,
    DOC_FM_REQUIRED_FIELDS,
    DOC_FM_REQUIRED_FIELDS_BY_GLOB,
    TICKET_FM_ALLOWED_STATUSES,
    TICKET_FM_ALLOWED_TYPES,
    TICKET_FM_REQUIRED_FIELDS,
)
from scripts.commit_guardian.diagram_type_validators import (
    validate_diagram_type,
)
from scripts.commit_guardian.doc_type_validators import (
    validate_doc_type,
    validate_requires_documentation,
)


def extract_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Extract YAML frontmatter and body from markdown content.

    Frontmatter is delimited by ``---`` at the very start of the file.

    Args:
        content: Full file content as a string.

    Returns:
        tuple[dict[str, Any] | None, str]: Parsed frontmatter dict (or None
            if absent/malformed) and the remaining body text.
    """
    if not content.startswith("---"):
        return None, content

    # Find the closing ---
    end_idx = content.find("---", 3)
    if end_idx == -1:
        return None, content

    raw_yaml = content[3:end_idx].strip()
    body = content[end_idx + 3:].strip()

    try:
        parsed = yaml.safe_load(raw_yaml)
    except yaml.YAMLError:
        return None, content

    if not isinstance(parsed, dict):
        return None, content

    return parsed, body


def _required_fields_for_path(filepath: str | None) -> list[str]:
    """Resolve the required-field list for a given file path.

    Iterates the per-glob dict in definition order and returns the field list
    for the first glob that matches *filepath*.  The most-specific glob must
    therefore appear first in ``commit_guardian.json``.

    Args:
        filepath: Repo-relative file path (forward slashes), or None.

    Returns:
        list[str]: Required field names for the matched glob, falling back to
            the broadest ``docs/**`` list when no glob matches or filepath is None.
    """
    if filepath:
        for pattern, fields in DOC_FM_REQUIRED_FIELDS_BY_GLOB.items():
            if fnmatch.fnmatch(filepath, pattern):
                return fields
    return DOC_FM_REQUIRED_FIELDS


def validate_required_fields(fm: dict[str, Any], filepath: str | None = None) -> list[str]:
    """Check that all required frontmatter fields are present.

    The required-field set is resolved per-path using the glob dict in
    ``commit_guardian.json``.  Callers that do not supply *filepath* fall back
    to the broadest ``docs/**`` required-field list (backward-compatible).

    Args:
        fm: Parsed frontmatter dictionary.
        filepath: Repo-relative file path used to select the per-glob required
            field list.  Pass ``None`` to use the broadest fallback list.

    Returns:
        list[str]: Error messages for each missing field.
    """
    required = _required_fields_for_path(filepath)
    errors = []
    for field in required:
        if field not in fm or fm[field] is None:
            errors.append(f"Missing required field: '{field}'")
    return errors


def validate_type_enum(fm: dict[str, Any]) -> list[str]:
    """Validate the ``type`` field against the allowed enum from doc_types.json.

    Delegates to ``validate_doc_type`` from ``doc_type_validators``, which reads
    ``leafcutter/config/doc_types.json`` as the SSOT. Falls back to the
    config constant when the JSON file is absent.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if type is invalid, empty list otherwise.
    """
    return validate_doc_type(fm)


def validate_status_enum(fm: dict[str, Any]) -> list[str]:
    """Validate the ``status`` field against the allowed enum.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if status is invalid, empty list otherwise.
    """
    status = fm.get("status")
    if status is None:
        return []  # Already caught by required-field check
    if status not in DOC_FM_ALLOWED_STATUSES:
        return [
            f"Invalid status '{status}'. Must be one of: {', '.join(DOC_FM_ALLOWED_STATUSES)}"
        ]
    return []


def validate_flight_level(fm: dict[str, Any]) -> list[str]:
    """Validate the optional ``flight_level`` field against the allowed enum.

    The field is optional globally (required-field enforcement is handled by
    ``validate_required_fields``).  This function only checks the *value* when
    the field is present — callers must call ``validate_required_fields`` first
    to catch the missing-field case on architecture docs.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if flight_level value is invalid, empty list
            when the field is absent or contains a valid value.
    """
    value = fm.get("flight_level")
    if value is None:
        return []
    if value not in DOC_FM_FLIGHT_LEVEL_VALUES:
        return [
            f"Invalid flight_level '{value}'. "
            f"Must be one of: {', '.join(DOC_FM_FLIGHT_LEVEL_VALUES)}"
        ]
    return []


# validate_diagram_type is imported from diagram_type_validators above.
# That module reads from leafcutter/config/diagram_types.json,
# which is the canonical source of truth for the diagram_type enum.
# The stale DOC_FM_DIAGRAM_TYPE_VALUES constant in config.py is DEPRECATED
# and no longer used here — see diagram_type_validators._load_diagram_types().
#
# Callers that previously imported validate_diagram_type from this module
# will now transparently use the JSON-backed implementation. No API change.


def validate_components(fm: dict[str, Any], valid_components: set[str]) -> list[str]:
    """Validate that ``components`` entries exist in the registry.

    Args:
        fm: Parsed frontmatter dictionary.
        valid_components: Set of valid component IDs from components.json.

    Returns:
        list[str]: Error messages for unknown components.
    """
    components = fm.get("components")
    if components is None:
        return []  # Already caught by required-field check
    if not isinstance(components, list):
        return ["'components' must be a list"]

    if not valid_components:
        return []  # Registry not available, skip validation

    errors = []
    for comp in components:
        if comp not in valid_components:
            errors.append(
                f"Unknown component '{comp}'. "
                f"Valid components: {', '.join(sorted(valid_components)[:10])}..."
            )
    return errors


def validate_paths(fm: dict[str, Any], project_root_path: Path) -> list[str]:
    """Check that paths in optional path fields actually exist on disk.

    Broken paths block the commit — if you reference a file, it must exist.

    Args:
        fm: Parsed frontmatter dictionary.
        project_root_path: Absolute path to the project root.

    Returns:
        list[str]: Error messages for paths that do not exist.
    """
    errors = []
    path_fields = ["related_docs", "related_code", "architecture_diagrams"]

    for field in path_fields:
        paths = fm.get(field)
        if not paths or not isinstance(paths, list):
            continue
        for p in paths:
            full_path = project_root_path / p
            if not full_path.exists():
                errors.append(f"Broken path in '{field}': '{p}' does not exist")

    return errors


def validate_last_updated(filepath: str) -> list[str]:
    """Warn if body content changed but last_updated was not updated.

    Detects this by comparing the staged content with HEAD via git diff.
    If the body changed but last_updated is the same as HEAD, warns.

    Args:
        filepath: Relative file path within the repo.

    Returns:
        list[str]: Warning messages about stale last_updated.
    """
    try:
        # Get the HEAD version of the file
        result = subprocess.run(
            ["git", "show", f"HEAD:{filepath}"],
            capture_output=True, text=True, encoding="utf-8", check=True,
        )
        old_content = result.stdout
    except subprocess.CalledProcessError:
        return []  # New file — no HEAD version to compare

    if not old_content:
        return []  # Empty or missing HEAD content

    old_fm, old_body = extract_frontmatter(old_content)
    try:
        new_content = Path(filepath).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    new_fm, new_body = extract_frontmatter(new_content)

    if old_fm is None or new_fm is None:
        return []

    # Compare bodies — strip to ignore whitespace-only changes
    if old_body.strip() != new_body.strip():
        old_updated = str(old_fm.get("last_updated", ""))
        new_updated = str(new_fm.get("last_updated", ""))
        if old_updated == new_updated:
            return [
                f"⚠️  Body content changed but 'last_updated' is still '{new_updated}'. "
                f"Consider updating to '{date.today().isoformat()}'."
            ]

    return []


# ---------------------------------------------------------------------------
# Ticket-side validators (tickets/**/*.md)
# ---------------------------------------------------------------------------


def validate_ticket_required_fields(fm: dict[str, Any]) -> list[str]:
    """Check that all required ticket frontmatter fields are present.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error messages for each missing required field.
    """
    errors = []
    for field in TICKET_FM_REQUIRED_FIELDS:
        if field not in fm or fm[field] is None:
            errors.append(f"Missing required field: '{field}'")
    return errors


def validate_ticket_status_enum(fm: dict[str, Any]) -> list[str]:
    """Validate the ticket ``status`` field against the allowed enum.

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if status is invalid, empty list otherwise.
    """
    status = fm.get("status")
    if status is None:
        return []  # Already caught by required-field check
    if status not in TICKET_FM_ALLOWED_STATUSES:
        return [
            f"Invalid status '{status}'. Must be one of: "
            f"{', '.join(TICKET_FM_ALLOWED_STATUSES)}"
        ]
    return []


def validate_ticket_type_enum(fm: dict[str, Any]) -> list[str]:
    """Validate the optional ticket ``type`` field against the allowed enum.

    The ``type`` field is optional on tickets. When absent, returns an empty
    list. When present, it must match one of the configured allowed values
    (e.g. ``epic``).

    Args:
        fm: Parsed frontmatter dictionary.

    Returns:
        list[str]: Error message if type is provided but invalid, otherwise [].
    """
    if "type" not in fm or fm.get("type") is None:
        return []
    ticket_type = fm["type"]
    if ticket_type not in TICKET_FM_ALLOWED_TYPES:
        return [
            f"Invalid type '{ticket_type}'. Must be one of: "
            f"{', '.join(TICKET_FM_ALLOWED_TYPES)}"
        ]
    return []


def validate_depends_on(fm: dict[str, Any], ticket_path: Path) -> list[str]:
    """Validate that ``depends_on`` entries reference existing sibling tickets.

    Each entry must be a string filename. The referenced file must exist in:
    - ``ticket_path.parent / entry``, OR
    - ``ticket_path.parent / "done" / entry``, OR
    - if the ticket is itself inside a ``done/`` subfolder, also
      ``ticket_path.parent.parent / entry``.

    An empty list ``[]`` is acceptable. A missing field is caught by the
    required-fields validator and not re-reported here.

    Args:
        fm: Parsed frontmatter dictionary.
        ticket_path: Absolute path to the ticket file being validated.

    Returns:
        list[str]: Error messages for malformed entries or unresolved siblings.
    """
    if "depends_on" not in fm:
        return []  # Caught by required-field check

    depends_on = fm.get("depends_on")
    if depends_on is None:
        return []  # Caught by required-field check
    if not isinstance(depends_on, list):
        return ["'depends_on' must be a list"]
    if not depends_on:
        return []  # Empty list is fine

    parent = ticket_path.parent
    in_done = parent.name == "done"
    grandparent = parent.parent if in_done else None

    errors: list[str] = []
    for entry in depends_on:
        if not isinstance(entry, str):
            errors.append(
                f"Invalid 'depends_on' entry: {entry!r} (must be a string filename)"
            )
            continue

        candidates = [parent / entry, parent / "done" / entry]
        if grandparent is not None:
            candidates.append(grandparent / entry)

        if not any(c.exists() for c in candidates):
            tried = ", ".join(str(c) for c in candidates)
            errors.append(
                f"depends_on '{entry}' not found. Looked in: {tried}"
            )
    return errors


from scripts.commit_guardian.ticket_roadmap_validators import (
    validate_roadmap_phase,
    validate_advances_current_outcome,
)

# ---------------------------------------------------------------------------
# Per-file orchestrators (used by check_doc_frontmatter.main)
# ---------------------------------------------------------------------------


def validate_doc_file(filepath: str, valid_components: set[str],
                      project_root_path: Path) -> tuple[list[str], list[str]]:
    """Run all frontmatter validations on a single docs/ markdown file.

    Args:
        filepath: Relative file path within the repo.
        valid_components: Set of valid component IDs.
        project_root_path: Absolute path to the project root.

    Returns:
        tuple[list[str], list[str]]: (blocking_errors, warnings).
    """
    errors: list[str] = []
    warnings: list[str] = []

    try:
        content = (project_root_path / filepath).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"Could not read file: {e}"], []

    fm, _ = extract_frontmatter(content)

    if fm is None:
        errors.append(
            "Missing YAML frontmatter.\n"
            "   FIX: Add a frontmatter block at the very top of the file:\n"
            "   ---\n"
            "   title: \"Your Title\"\n"
            "   type: how-to\n"
            "   status: active\n"
            f"   created: {date.today().isoformat()}\n"
            f"   last_updated: {date.today().isoformat()}\n"
            "   components:\n"
            "     - your_component\n"
            "   ---\n"
            "   📖 Spec: docs/FRONTMATTER.md"
        )
        return errors, warnings

    errors.extend(validate_required_fields(fm, filepath))
    errors.extend(validate_type_enum(fm))
    errors.extend(validate_status_enum(fm))
    errors.extend(validate_flight_level(fm))
    errors.extend(validate_diagram_type(fm))
    errors.extend(validate_components(fm, valid_components))
    errors.extend(validate_paths(fm, project_root_path))

    warnings.extend(validate_last_updated(filepath))

    return errors, warnings


def validate_ticket_file(filepath: str, valid_components: set[str],
                         project_root_path: Path) -> tuple[list[str], list[str]]:
    """Run all frontmatter validations on a single tickets/ markdown file.

    Args:
        filepath: Relative file path within the repo.
        valid_components: Set of valid component IDs from components.json.
        project_root_path: Absolute path to the project root.

    Returns:
        tuple[list[str], list[str]]: (blocking_errors, warnings). Warnings are
        reserved for future use; ticket validation currently produces no
        warning-only diagnostics.
    """
    errors: list[str] = []
    warnings: list[str] = []

    ticket_path = project_root_path / filepath
    try:
        content = ticket_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        return [f"Could not read file: {e}"], []

    fm, _ = extract_frontmatter(content)

    if fm is None:
        errors.append(
            "Missing YAML frontmatter.\n"
            "   FIX: Add a frontmatter block at the very top of the ticket:\n"
            "   ---\n"
            "   title: \"Your Ticket Title\"\n"
            "   status: todo\n"
            f"   created: {date.today().isoformat()}\n"
            "   components:\n"
            "     - your_component\n"
            "   depends_on: []\n"
            "   ---\n"
            "   📖 Spec: docs/FRONTMATTER.md (ticket section)"
        )
        return errors, warnings

    errors.extend(validate_ticket_required_fields(fm))
    errors.extend(validate_ticket_status_enum(fm))
    errors.extend(validate_ticket_type_enum(fm))
    errors.extend(validate_components(fm, valid_components))
    errors.extend(validate_depends_on(fm, ticket_path))
    errors.extend(validate_requires_documentation(fm))

    warnings.extend(validate_roadmap_phase(fm, project_root_path))
    warnings.extend(validate_advances_current_outcome(fm))

    return errors, warnings


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-18 00:00 [EPIC-ProjectRoadmap/ticket 04]: Added validate_roadmap_phase() (#EPIC-ProjectRoadmap/04)
  and validate_advances_current_outcome() warn-only validators (imported from
  ticket_roadmap_validators.py — extracted to keep this file under the 400-line
  limit). Both functions return warnings (never errors) and are wired into
  validate_ticket_file() warnings list. Removed inline json import (no longer
  needed here; moved to ticket_roadmap_validators.py).
- 2026-05-15 00:00 [EPIC-EmbeddedArchDiagramsHardening/ticket 07]: Replaced validate_diagram_type with import delegation to diagram_type_validators. (#EPIC-EmbeddedArchDiagramsHardening/07)
  Removed DOC_FM_DIAGRAM_TYPE_VALUES import. Fixes silent rejection of user_flow, data_flow, agent_flow.
- 2026-05-14 00:00 [EPIC-ArchitectureDocsEnforcement/ticket 08]: Replaced
  validate_type_enum inline logic with a delegation call to
  validate_doc_type from doc_type_validators (doc_types.json SSOT). Added
  validate_requires_documentation call in validate_ticket_file for the new
  optional ticket frontmatter field. Removed DOC_FM_ALLOWED_TYPES import
  (no longer needed; enum comes from doc_types.json at runtime).
- 2026-05-12 00:00 [Merge]: Integrated validate_flight_level and validate_diagram_type
  calls into validate_doc_file. Added DOC_FM_REQUIRED_FIELDS_BY_GLOB import and
  pass filepath to validate_required_fields for per-glob resolution.
- 2026-05-11 00:00 [Agent]: Added validate_flight_level and validate_diagram_type.
  Refactored validate_required_fields to accept an optional filepath and resolve
  the required-field set from DOC_FM_REQUIRED_FIELDS_BY_GLOB (ticket 02).
- 2026-05-05 12:00 [AI]: Added ticket-side validators
  (validate_ticket_required_fields, validate_ticket_status_enum,
  validate_ticket_type_enum, validate_depends_on) and the per-file
  orchestrators validate_doc_file / validate_ticket_file (moved from
  check_doc_frontmatter.py to keep that file under the 400-line cap)
  to support YAML frontmatter checking on tickets/**/*.md
  (EPIC-DocTraceability #15).
- 2026-05-04 19:04 [AI]: Extracted frontmatter validators from doc_validators.py
  to keep it under the 400-line limit.
====================================================================
"""
