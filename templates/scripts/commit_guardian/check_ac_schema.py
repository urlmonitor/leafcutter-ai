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
    jsonschema is available, performs full draft-07 validation. Also performs
    pattern_bindings completeness validation: consuming ACs whose
    implements_pattern references a pattern AC must bind every slot declared in
    that pattern's pattern_slots. Also validates that implements_pattern does not
    reference a deprecated pattern AC (ACS-500a-3-ii). Also detects when a new
    AC's criteria duplicates the structural form of an existing pattern AC by
    restating the same behavior with concrete values in place of pattern slots —
    such ACs should use implements_pattern + pattern_bindings instead
    (ACS-500c-3). Exits 0 when all files pass; exits 1 with per-file error
    messages. Standalone stdlib script — no leafcutter imports.
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

    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except OSError as exc:
        print(f"Warning: cannot read {path}: {exc}", file=sys.stderr)
        raise


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
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.rstrip()
                if stripped.startswith("#") or not stripped:
                    continue
                if ":" in stripped and not stripped[0].isspace():
                    key, _, value = stripped.partition(":")
                    result[key.strip()] = value.strip()
    except OSError as exc:
        print(f"Warning: cannot read {path}: {exc}", file=sys.stderr)
        raise
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
# Pattern bindings completeness validation
# ---------------------------------------------------------------------------

_SLOT_REGEX = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


def _extract_slots_from_criteria(criteria: str) -> list[str]:
    """Extract slot names from a pattern AC's criteria text.

    Scans the criteria string for curly-brace placeholders matching the slot
    name pattern (e.g. ``{columns}``, ``{default_sort}``). Returns unique slot
    names preserving first-occurrence order.

    Args:
        criteria: Multi-line Gherkin criteria string from a pattern AC.

    Returns:
        List of unique slot name strings (without curly braces).
    """
    seen: set[str] = set()
    result: list[str] = []
    for match in _SLOT_REGEX.finditer(criteria):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def _validate_pattern_bindings_completeness(
    consuming_path: Path,
    consuming_data: dict[str, Any],
    all_ac_data: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate that a consuming AC's pattern_bindings covers all pattern slots.

    A consuming AC is one where ``implements_pattern`` is set to a non-null
    AC ID. The referenced pattern AC must declare ``pattern_slots`` (or have
    slots extractable from its ``criteria``). Every slot must appear as a key
    in the consuming AC's ``pattern_bindings``.

    The error message follows the canonical format from AC ACS-500a-3-i:
    ``"pattern_bindings missing required key '<slot>' for pattern <id>"``.

    Args:
        consuming_path: Filesystem path to the consuming AC file (for error messages).
        consuming_data: Parsed YAML content of the consuming AC.
        all_ac_data: Mapping of AC id → parsed YAML content for every AC
            file discovered in the store. Used to look up the pattern AC.

    Returns:
        List of error message strings; empty when all bindings are complete.
    """
    pattern_id = consuming_data.get("implements_pattern")
    if not pattern_id:
        return []

    pattern_data = all_ac_data.get(str(pattern_id))
    if pattern_data is None:
        # Pattern AC not found in this scan — cannot validate completeness.
        # Missing-reference errors are out of scope for this hook.
        return []

    # Derive required slot names from pattern_slots field; fall back to
    # scanning the criteria text for curly-brace placeholders.
    raw_slots = pattern_data.get("pattern_slots")
    if raw_slots and isinstance(raw_slots, list):
        required_slots = [
            s.strip("{}") for s in raw_slots if isinstance(s, str)
        ]
    else:
        criteria_text = pattern_data.get("criteria") or ""
        required_slots = _extract_slots_from_criteria(str(criteria_text))

    if not required_slots:
        return []

    bindings = consuming_data.get("pattern_bindings") or {}
    if not isinstance(bindings, dict):
        bindings = {}

    errors: list[str] = []
    for slot in required_slots:
        if slot not in bindings:
            errors.append(
                f"{consuming_path}: pattern_bindings missing required key "
                f"'{slot}' for pattern {pattern_id}"
            )
    return errors


# ---------------------------------------------------------------------------
# Duplicate criteria detection (ACS-500c-3)
# ---------------------------------------------------------------------------


def _normalize_criteria_whitespace(text: str) -> str:
    """Collapse all whitespace runs to a single space and strip leading/trailing.

    Normalizes multi-line Gherkin criteria to a single comparable string so
    that minor formatting differences (extra spaces, different indentation)
    do not prevent structural equivalence detection.

    Args:
        text: Raw criteria string from an AC YAML file.

    Returns:
        Whitespace-normalized string.
    """
    return re.sub(r"\s+", " ", text.strip())


def _build_pattern_duplicate_regex(pattern_criteria: str) -> str | None:
    """Build a regex that matches criteria text structurally equivalent to the pattern.

    Takes a pattern AC's criteria text (which contains ``{slot_name}``
    placeholders) and constructs a regex where each slot is replaced with a
    ``.*`` wildcard that matches any concrete value. The fixed text between
    slots is regex-escaped so it must match literally.

    After whitespace normalization, a candidate AC's criteria is structurally
    equivalent to the pattern if and only if its normalized text matches the
    resulting regex.

    Args:
        pattern_criteria: Multi-line Gherkin criteria string from a pattern AC.
            Must contain at least one ``{slot_name}`` placeholder.

    Returns:
        A compiled-ready regex string, or None if the pattern criteria
        contains no slot placeholders (in which case there is nothing to detect).
    """
    norm = _normalize_criteria_whitespace(pattern_criteria)
    if not _SLOT_REGEX.search(norm):
        return None

    parts = _SLOT_REGEX.split(norm)
    regex_parts: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            # Fixed text between slots — escape for literal matching.
            regex_parts.append(re.escape(part))
        else:
            # Slot name (odd indices after split on a group pattern) —
            # match one or more characters (greedy).
            regex_parts.append(".+")
    return "".join(regex_parts)


def _validate_criteria_not_pattern_duplicate(
    candidate_path: Path,
    candidate_data: dict[str, Any],
    all_ac_data: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate that a standalone AC's criteria does not duplicate a pattern.

    A standalone AC is one that does NOT have ``implements_pattern`` set.
    For each active pattern AC in the store, this function checks whether
    the candidate AC's ``criteria`` text is structurally equivalent to the
    pattern (i.e., the same Gherkin steps with concrete values in place of
    ``{slot_name}`` placeholders). If so, the candidate is a likely duplicate
    that should instead use ``implements_pattern`` + ``pattern_bindings``.

    This check enforces the single-source-of-truth invariant for shared
    behaviors (AC ACS-500c-3).

    The error message follows the canonical format:
    ``"criteria is a likely duplicate of pattern <id>; use implements_pattern:
    <id> with pattern_bindings instead of restating the behavior inline"``

    Args:
        candidate_path: Filesystem path to the candidate AC file
            (for error messages).
        candidate_data: Parsed YAML content of the candidate AC.
        all_ac_data: Mapping of AC id → parsed YAML content for every AC
            file discovered in the store. Used to look up pattern ACs.

    Returns:
        List of error message strings; empty when no duplicate is detected.
    """
    # Only check ACs that do not already reference a pattern.
    if candidate_data.get("implements_pattern"):
        return []

    candidate_criteria_raw = candidate_data.get("criteria")
    if not candidate_criteria_raw or not isinstance(candidate_criteria_raw, str):
        return []

    candidate_norm = _normalize_criteria_whitespace(candidate_criteria_raw)

    candidate_id = candidate_data.get("id")

    errors: list[str] = []
    for pattern_id, pattern_data in all_ac_data.items():
        # Skip the candidate itself (compare by id string, not object identity,
        # because the index and the validated file are loaded as separate dicts).
        if candidate_id and str(candidate_id) == str(pattern_id):
            continue

        # Only match against ACs that explicitly declare pattern_slots — ACs that
        # happen to contain curly-brace notation in their criteria text for other
        # reasons (e.g. describing filename patterns like {PREFIX}-{NNN}) are not
        # patterns. This avoids false positives from ACs without pattern_slots.
        raw_slots = pattern_data.get("pattern_slots")
        if not isinstance(raw_slots, list) or len(raw_slots) == 0:
            continue

        pattern_criteria_raw = pattern_data.get("criteria")
        if not pattern_criteria_raw or not isinstance(pattern_criteria_raw, str):
            continue

        # Skip deprecated patterns — a duplicate of a deprecated pattern is not
        # actionable (there is no live pattern to reference).
        if pattern_data.get("status") == "deprecated":
            continue

        duplicate_regex = _build_pattern_duplicate_regex(str(pattern_criteria_raw))
        if duplicate_regex is None:
            continue

        try:
            if re.fullmatch(duplicate_regex, candidate_norm, re.DOTALL):
                errors.append(
                    f"{candidate_path}: criteria is a likely duplicate of pattern "
                    f"{pattern_id}; use implements_pattern: {pattern_id} with "
                    f"pattern_bindings instead of restating the behavior inline"
                )
        except re.error:
            # Regex construction failed — skip this pattern (fail-open).
            continue

    return errors


# ---------------------------------------------------------------------------
# Deprecated pattern reference validation
# ---------------------------------------------------------------------------


def _validate_deprecated_pattern_reference(
    consuming_path: Path,
    consuming_data: dict[str, Any],
    all_ac_data: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate that implements_pattern does not reference a deprecated pattern AC.

    A consuming AC is one where ``implements_pattern`` is set to a non-null
    AC ID. If the referenced pattern AC has ``status: deprecated``, the
    consuming AC must be updated to either reference the successor (identified
    by the pattern's ``superseded_by`` field) or remove the reference entirely.

    The error message follows the canonical format from AC ACS-500a-3-ii:
    ``"implements_pattern references deprecated pattern <id>; use its successor
    (see <id> superseded_by field) or remove the reference"``.

    Args:
        consuming_path: Filesystem path to the consuming AC file (for error messages).
        consuming_data: Parsed YAML content of the consuming AC.
        all_ac_data: Mapping of AC id → parsed YAML content for every AC
            file discovered in the store. Used to look up the pattern AC status.

    Returns:
        List of error message strings; empty when the reference is valid.
    """
    pattern_id = consuming_data.get("implements_pattern")
    if not pattern_id:
        return []

    pattern_data = all_ac_data.get(str(pattern_id))
    if pattern_data is None:
        # Pattern AC not found in this scan — status cannot be checked.
        # Missing-reference errors are out of scope for this hook.
        return []

    if pattern_data.get("status") != "deprecated":
        return []

    return [
        f"{consuming_path}: implements_pattern references deprecated pattern "
        f"{pattern_id}; use its successor (see {pattern_id} superseded_by field) "
        f"or remove the reference"
    ]


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
    try:
        with open(schema_path, encoding="utf-8") as fh:
            return json.load(fh)  # type: ignore[return-value]
    except OSError as exc:
        print(f"Warning: cannot read schema {schema_path}: {exc}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Main validation loop
# ---------------------------------------------------------------------------


def _validate_file(
    path: Path,
    schema: dict[str, Any] | None,
    all_ac_data: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Validate a single AC YAML file and return a list of error messages.

    Uses jsonschema for full draft-07 validation when both PyYAML and
    jsonschema are available. Falls back to manual field checks otherwise.
    When ``all_ac_data`` is provided, also validates pattern_bindings
    completeness for consuming ACs.

    Args:
        path: Path to the YAML file to validate.
        schema: Pre-loaded JSON Schema dict, or None when the schema file
            is unavailable.
        all_ac_data: Optional mapping of AC id → parsed YAML content for every
            AC file in the store. When provided, enables cross-file
            pattern_bindings completeness validation.

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
    except (OSError, ValueError) as exc:
        print(f"Warning: YAML parse error in {path}: {exc}", file=sys.stderr)
        errors.append(f"YAML parse error: {exc}")
        return errors

    if not yaml_available:
        try:
            data = _load_yaml_manual(path)
        except (OSError, ValueError) as exc:
            print(f"Warning: manual YAML parse error in {path}: {exc}", file=sys.stderr)
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
            # Continue to pattern bindings check even when schema passes.

    # Manual validation fallback (jsonschema absent or schema file missing).
    if not errors:
        errors.extend(_validate_manually(data))

    # Cross-file pattern_bindings completeness check (ACS-500a-3-i).
    if all_ac_data is not None:
        errors.extend(
            _validate_pattern_bindings_completeness(path, data, all_ac_data)
        )

    # Deprecated pattern reference check (ACS-500a-3-ii).
    if all_ac_data is not None:
        errors.extend(
            _validate_deprecated_pattern_reference(path, data, all_ac_data)
        )

    # Duplicate criteria detection (ACS-500c-3).
    if all_ac_data is not None:
        errors.extend(
            _validate_criteria_not_pattern_duplicate(path, data, all_ac_data)
        )

    return errors


def _build_ac_index(files: list[Path]) -> dict[str, dict[str, Any]]:
    """Load all AC YAML files and index them by their ``id`` field.

    Files that cannot be parsed, or that lack an ``id`` field, are silently
    skipped (their schema errors will be reported by the main validation loop).

    Args:
        files: List of AC YAML file paths to load.

    Returns:
        Mapping of AC id string → parsed YAML content dict.
    """
    index: dict[str, dict[str, Any]] = {}
    for path in files:
        try:
            data = _load_yaml(path)
        except (ImportError, OSError, ValueError):  # noqa: BLE001
            try:
                data = _load_yaml_manual(path)
            except (OSError, ValueError):  # noqa: BLE001
                continue
        if isinstance(data, dict) and data.get("id"):
            index[str(data["id"])] = data
    return index


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

    # Build a cross-file index for pattern_bindings completeness checks.
    all_ac_data = _build_ac_index(files)

    failed: list[tuple[Path, list[str]]] = []
    for path in files:
        file_errors = _validate_file(path, schema, all_ac_data)
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
