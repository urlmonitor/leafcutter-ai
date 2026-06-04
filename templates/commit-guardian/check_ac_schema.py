"""
MODULE: check_ac_schema
GOAL: Pre-commit hook that validates every YAML file under
    docs/acceptance-criteria/ against the AC store JSON Schema
    (config/ac_store_schema.json).
BUSINESS CONTEXT: Ensures that all acceptance criterion files conform to the
    canonical schema defined in ADR-007. Malformed AC files are rejected at
    commit time before they enter the repository, preventing downstream tooling
    from processing invalid data.
ARCHITECTURE: Discovers all AC YAML files under docs/acceptance-criteria/,
    loads each with PyYAML (fallback: manual field checks when PyYAML is absent),
    and validates required fields, status enum, and ID format regex. When
    jsonschema is available, performs full draft-07 validation. Exits 0 when
    all files pass; exits 1 with per-file error messages.
    Standalone stdlib script — no leafcutter imports.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AC_GLOB_PATTERN = "docs/acceptance-criteria"
ID_REGEX = re.compile(r"^[A-Z]{2,6}-[0-9]{3}$")
REQUIRED_FIELDS = ["id", "title", "component", "status", "created_by", "criteria"]
VALID_STATUSES = {"active", "deprecated", "superseded_by"}
SCHEMA_PATH = "config/ac_store_schema.json"


# ---------------------------------------------------------------------------
# YAML loading (soft dependency on PyYAML)
# ---------------------------------------------------------------------------


def _load_yaml(path: Path) -> Any:  # noqa: ANN401
    """Load a YAML file using PyYAML.

    Callers must catch ``ImportError`` to detect that PyYAML is absent and
    fall back to ``_load_yaml_manual``.

    Args:
        path: Path to the YAML file to load.

    Returns:
        Parsed YAML content.

    Raises:
        ImportError: When PyYAML is not installed.
        Exception: When the file cannot be parsed.
    """
    import yaml  # type: ignore[import]  # ImportError propagates to caller

    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _load_yaml_manual(path: Path) -> dict[str, Any]:
    """Minimal YAML parser fallback for simple key: value lines.

    Only handles top-level scalar fields needed for validation. Does not
    handle multi-line blocks, lists, or nested mappings. Used only when PyYAML
    is unavailable.

    Args:
        path: Path to the YAML file to parse.

    Returns:
        Dict of parsed top-level key-value pairs (values as strings).
    """
    result: dict[str, Any] = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.rstrip()
            if stripped.startswith("#") or not stripped:
                continue
            if ":" in stripped and not stripped[0].isspace():
                key, _, value = stripped.partition(":")
                result[key.strip()] = value.strip()
    return result


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_with_jsonschema(data: Any, schema: dict[str, Any]) -> list[str]:  # noqa: ANN401
    """Validate data against a JSON Schema using the jsonschema library.

    Callers must catch ``ImportError`` and fall back to ``_validate_manually``
    when jsonschema is not installed.

    Args:
        data: Parsed YAML content to validate.
        schema: JSON Schema dict to validate against.

    Returns:
        List of validation error messages; empty when all checks pass.

    Raises:
        ImportError: When jsonschema is not installed.
    """
    import jsonschema  # type: ignore[import]  # ImportError propagates to caller

    validator = jsonschema.Draft7Validator(schema)
    return [str(err.message) for err in sorted(validator.iter_errors(data), key=str)]


def _validate_manually(data: dict[str, Any]) -> list[str]:
    """Validate AC data manually when PyYAML/jsonschema are unavailable.

    Checks required fields, status enum, and ID format regex. Does not verify
    optional fields or data types beyond string scalars.

    Args:
        data: Parsed (or partially parsed) dict of AC YAML content.

    Returns:
        List of validation error messages; empty when all checks pass.
    """
    errors: list[str] = []

    for field_name in REQUIRED_FIELDS:
        if field_name not in data or data[field_name] in (None, "", "null"):
            errors.append(f"missing required field: '{field_name}'")

    if "status" in data and data["status"] not in VALID_STATUSES:
        errors.append(
            f"invalid status '{data['status']}': must be one of "
            f"{sorted(VALID_STATUSES)}"
        )

    if "id" in data and data["id"] and not ID_REGEX.match(str(data["id"])):
        errors.append(
            f"invalid id format '{data['id']}': must match ^[A-Z]{{2,6}}-[0-9]{{3}}$"
        )

    return errors


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _find_ac_files(root: Path) -> list[Path]:
    """Discover all .yaml files under docs/acceptance-criteria/ from root.

    Args:
        root: Repository root directory.

    Returns:
        Sorted list of Path objects for each .yaml file found.
    """
    ac_dir = root / AC_GLOB_PATTERN
    if not ac_dir.is_dir():
        return []
    return sorted(ac_dir.rglob("*.yaml"))


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def _load_schema(root: Path) -> dict[str, Any] | None:
    """Load the AC store JSON Schema from config/ac_store_schema.json.

    Args:
        root: Repository root directory.

    Returns:
        Parsed schema dict, or None if the schema file does not exist.
    """
    schema_path = root / SCHEMA_PATH
    if not schema_path.is_file():
        return None
    with open(schema_path, encoding="utf-8") as fh:
        return json.load(fh)  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Main validation loop
# ---------------------------------------------------------------------------


def _validate_file(
    path: Path,
    schema: dict[str, Any] | None,
) -> list[str]:
    """Validate a single AC YAML file and return a list of error messages.

    Uses jsonschema for full draft-07 validation when both PyYAML and
    jsonschema are available. Falls back to manual field checks otherwise.

    Args:
        path: Path to the YAML file to validate.
        schema: Pre-loaded JSON Schema dict, or None when the schema file
            is unavailable.

    Returns:
        List of error message strings; empty when the file is valid.
    """
    errors: list[str] = []

    yaml_available = True
    data: Any = None
    try:
        data = _load_yaml(path)
    except ImportError:
        yaml_available = False
    except Exception as exc:  # noqa: BLE001
        errors.append(f"YAML parse error: {exc}")
        return errors

    if not yaml_available:
        try:
            data = _load_yaml_manual(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"manual YAML parse error: {exc}")
            return errors

    if data is None:
        errors.append("file is empty or parsed to null")
        return errors

    if not isinstance(data, dict):
        errors.append(
            f"expected a YAML mapping at top level, got {type(data).__name__}"
        )
        return errors

    # Attempt full JSON Schema validation when both libraries are present.
    if schema is not None and yaml_available:
        try:
            schema_errors = _validate_with_jsonschema(data, schema)
        except ImportError:
            pass  # jsonschema unavailable; fall through to manual validation
        else:
            errors.extend(schema_errors)
            return errors

    # Manual validation fallback (jsonschema absent or schema file missing).
    errors.extend(_validate_manually(data))
    return errors


def main() -> int:
    """Validate all AC YAML files; return 0 on success, 1 on any failure.

    Returns:
        Exit code: 0 when all files pass, 1 when any validation error is found.
    """
    root = Path(os.environ.get("HOOK_ROOT", str(Path.cwd())))
    schema = _load_schema(root)

    if schema is None:
        print(
            f"WARNING: {SCHEMA_PATH} not found at {root}; "
            "falling back to manual field validation.",
            file=sys.stderr,
        )

    files = _find_ac_files(root)
    if not files:
        # No AC files present — nothing to validate.
        return 0

    failed: list[tuple[Path, list[str]]] = []
    for path in files:
        file_errors = _validate_file(path, schema)
        if file_errors:
            failed.append((path, file_errors))

    if not failed:
        return 0

    print(
        f"check-ac-schema: {len(failed)} file(s) failed validation:",
        file=sys.stderr,
    )
    for path, file_errors in failed:
        rel = path.relative_to(root) if path.is_absolute() else path
        for err in file_errors:
            print(f"  {rel}: {err}", file=sys.stderr)

    return 1


if __name__ == "__main__":
    sys.exit(main())
