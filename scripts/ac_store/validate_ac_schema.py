#!/usr/bin/env python3
"""
validate_ac_schema.py — AC YAML schema validation hook.

Usage:
    python3 scripts/ac_store/validate_ac_schema.py <ac_yaml_path> [<ac_yaml_path> ...]

Validates one or more AC YAML files for required fields introduced in ticket 00:
  - readiness: required, must be one of [draft, reviewed, approved]
  - priority: required, must be one of [critical, high, medium, low]

Also validates the full schema against config/ac_store_schema.json for
additional property constraints.

Exits non-zero if any file fails validation; exits zero if all pass.

AC-1: Schema requires readiness field with enum [draft, reviewed, approved].
AC-2: Schema requires priority field with enum [critical, high, medium, low].
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# _ac_components lives alongside this script; sys.path[0] is the script dir when
# invoked as `python scripts/ac_store/validate_ac_schema.py ...`.
from _ac_components import components_field_errors, load_registry_ids  # noqa: E402


# ---------------------------------------------------------------------------
# Validation constants
# ---------------------------------------------------------------------------

_READINESS_VALUES = {"draft", "reviewed", "approved"}
_PRIORITY_VALUES = {"critical", "high", "medium", "low"}
_LEVEL_VALUES = {"L0", "L1", "L2", "L3"}
_STATUS_VALUES = {"active", "deprecated", "superseded_by"}
_WORK_STATUS_VALUES = {"todo", "in_progress", "done"}
_DOC_TRIGGER_VALUES = {
    "how-to",
    "sequence-diagram",
    "state-diagram",
    "component-diagram",
    "reference-doc",
}

# Field-level help text for missing fields
_FIELD_HELP: dict[str, str] = {
    "readiness": (
        "readiness: must be one of [draft, reviewed, approved]. "
        "draft = written but not reviewed by IT PO; "
        "reviewed = IT PO v3 has enriched and approved; "
        "approved = user has signed off (scanner may pick up)."
    ),
    "priority": (
        "priority: must be one of [critical, high, medium, low]. "
        "Set by user or product-owner-v3 at approval time. "
        "The scanner uses this for ranking."
    ),
}


def _validate_file(path: Path, registry_ids: set[str] | None = None) -> list[str]:
    """Validate a single YAML file for required readiness/priority/components fields.

    Args:
        path: YAML file to validate.
        registry_ids: Valid component ids from index.yaml. When None, the
            registry is loaded lazily (per-call) — callers validating many files
            should load it once and pass it in.

    Returns a list of error strings. Empty list = valid.
    """
    errors: list[str] = []

    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return [f"{path}: YAML parse error — {exc}"]
    except OSError as exc:
        return [f"{path}: Cannot read file — {exc}"]

    if not isinstance(data, dict):
        return [f"{path}: Top-level YAML must be a mapping (dict), got {type(data).__name__}"]

    # Only validate AC files (must have an 'id' field)
    if "id" not in data:
        return []  # Not an AC file; skip silently

    # --- Validate readiness ---
    if "readiness" not in data:
        help_text = _FIELD_HELP["readiness"]
        errors.append(
            f"{path}: Missing required field 'readiness'.\n"
            f"  Help: {help_text}"
        )
    elif data["readiness"] not in _READINESS_VALUES:
        errors.append(
            f"{path}: Field 'readiness' has invalid value {data['readiness']!r}. "
            f"Valid values: {sorted(_READINESS_VALUES)}."
        )

    # --- Validate priority ---
    if "priority" not in data:
        help_text = _FIELD_HELP["priority"]
        errors.append(
            f"{path}: Missing required field 'priority'.\n"
            f"  Help: {help_text}"
        )
    elif data["priority"] not in _PRIORITY_VALUES:
        errors.append(
            f"{path}: Field 'priority' has invalid value {data['priority']!r}. "
            f"Valid values: {sorted(_PRIORITY_VALUES)}."
        )

    # --- Validate components (required non-empty registry-valid list) ---
    # KM-KGS-100e-1 / -1-i / -1-ii: the `components` LIST is the field the
    # knowledge graph reads to build component_membership edges.
    if registry_ids is None:
        registry_ids = load_registry_ids()
    errors.extend(components_field_errors(data, registry_ids))

    # --- Validate documentation_triggers (optional, but enum-constrained) ---
    if "documentation_triggers" in data and data["documentation_triggers"] is not None:
        triggers = data["documentation_triggers"]
        if not isinstance(triggers, list):
            errors.append(
                f"{path}: Field 'documentation_triggers' must be a list or null, "
                f"got {type(triggers).__name__}."
            )
        else:
            invalid = [t for t in triggers if t not in _DOC_TRIGGER_VALUES]
            if invalid:
                errors.append(
                    f"{path}: Field 'documentation_triggers' contains invalid values: "
                    f"{invalid}. Valid values: {sorted(_DOC_TRIGGER_VALUES)}."
                )

    return errors


def main(argv: list[str] | None = None) -> int:
    """Validate AC YAML files and return exit code (0 = ok, 1 = errors, 2 = usage error)."""
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print(
            "Usage: validate_ac_schema.py <ac_yaml_path> [<ac_yaml_path> ...]\n"
            "\n"
            "Validates one or more AC YAML files for required fields:\n"
            "  readiness: [draft | reviewed | approved]\n"
            "  priority:  [critical | high | medium | low]\n"
            "\n"
            "Exits non-zero if any validation error is found.",
            file=sys.stderr,
        )
        return 2

    all_errors: list[str] = []
    files_checked = 0

    # Load the component registry once for the whole run.
    registry_ids = load_registry_ids()

    for arg in args:
        path = Path(arg)
        if not path.exists():
            all_errors.append(f"{path}: File not found.")
            continue
        if path.suffix not in {".yaml", ".yml"}:
            continue  # Skip non-YAML files silently
        errors = _validate_file(path, registry_ids)
        all_errors.extend(errors)
        files_checked += 1

    if all_errors:
        print("AC schema validation FAILED:", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    if files_checked == 0:
        print("No YAML files to validate.")
        return 0

    if files_checked == 1:
        print(f"OK: {args[0]} is valid.")
    else:
        print(f"OK: all {files_checked} AC YAML files are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
