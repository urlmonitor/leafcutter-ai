"""
MODULE: _ac_schema_validators
GOAL: Pure-function AC YAML validation helpers extracted from check_ac_schema.py
    to keep the main module within the 400-line file-size limit.
BUSINESS CONTEXT: Pattern reuse (ACS-500) requires consuming ACs to declare
    every slot their pattern needs. Criteria duplication (ACS-500c-3) signals
    an AC that should instead inherit from a shared pattern. Schema validation
    ensures required fields, status enum, and ID format are correct. These checks
    enforce the single-source-of-truth invariant for shared behaviors at commit time.
ARCHITECTURE: Pure-function helpers with no external I/O and no subprocess calls.
    YAML loading, JSON Schema validation, and cross-file pattern checks all live
    here. Standalone stdlib module — no leafcutter imports. Imported by
    check_ac_schema.py. The module also exports _load_yaml_from_string so the
    main module can reuse the fallback parser for HEAD-version comparisons.

DOC_LINKS:
  - docs/reference/ac-schema.md
  - docs/acceptance-criteria/ac-store/ACS-500-pattern-reuse/

DECISION HISTORY:
  - 2026-06-17 [python-coder/ACS-500f-1]: Created by extracting validators from
    check_ac_schema.py to stay within the 400-line file size limit. Contains
    YAML loading helpers, schema validation, and three cross-file pattern checks:
    pattern_bindings completeness, deprecated-reference guard, and criteria-
    duplicate detection.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Any

_SLOT_REGEX = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")
_HOOK_PREFIX = "[check-ac-schema]"

REQUIRED_FIELDS = ["id", "title", "component", "status", "created_by", "criteria"]
VALID_STATUSES = {"active", "deprecated", "superseded_by"}
_ID_REGEX = re.compile(r"^[A-Z]{2,6}-[0-9]{3}$")


# ---------------------------------------------------------------------------
# YAML loading
# ---------------------------------------------------------------------------

def load_yaml(path: Path) -> Any:  # noqa: ANN401
    """Load a YAML file using PyYAML; raises ImportError when absent.

    Args:
        path: Path to the YAML file to load.

    Returns:
        Parsed YAML content.

    Raises:
        ImportError: When PyYAML is not installed.
        OSError: When the file cannot be read.
    """
    import yaml  # type: ignore[import]

    try:
        with open(path, encoding="utf-8") as fh:
            return yaml.safe_load(fh)
    except OSError as exc:
        print(f"Warning: cannot read {path}: {exc}", file=sys.stderr)
        raise


def load_yaml_manual(path: Path) -> dict[str, Any]:
    """Minimal YAML parser fallback for simple key: value lines only.

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


def load_yaml_from_string(content: str, source_label: str) -> dict | None:
    """Parse a YAML string; returns dict or None on failure (fail-open).

    Args:
        content: Raw YAML string.
        source_label: Human-readable label for error messages.

    Returns:
        Parsed dict on success, None on parse failure.
    """
    try:
        import yaml  # type: ignore[import]

        try:
            data = yaml.safe_load(content)
            return data if isinstance(data, dict) else None
        except yaml.YAMLError as exc:
            print(
                f"{_HOOK_PREFIX} WARNING: YAML parse error in {source_label}: {exc}",
                file=sys.stderr,
            )
            return None
    except ImportError:
        pass

    result: dict = {}
    for raw_line in content.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#") or line[0:1] in (" ", "\t"):
            continue
        if ":" in line:
            key, _, value = line.partition(":")
            result[key.strip()] = value.strip()
    return result or None


# ---------------------------------------------------------------------------
# Schema validation helpers
# ---------------------------------------------------------------------------

def validate_with_jsonschema(data: Any, schema: dict[str, Any]) -> list[str]:  # noqa: ANN401
    """Validate data against a JSON Schema; raises ImportError when absent.

    Args:
        data: Parsed YAML content to validate.
        schema: JSON Schema dict.

    Returns:
        Validation error messages; empty on pass.

    Raises:
        ImportError: When jsonschema is not installed.
    """
    import jsonschema  # type: ignore[import]

    validator = jsonschema.Draft7Validator(schema)
    return [str(err.message) for err in sorted(validator.iter_errors(data), key=str)]


def validate_manually(data: dict[str, Any]) -> list[str]:
    """Check required fields, status enum, and ID format without jsonschema.

    Args:
        data: Parsed AC YAML content dict.

    Returns:
        Validation error messages; empty on pass.
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

    if "id" in data and data["id"] and not _ID_REGEX.match(str(data["id"])):
        errors.append(
            f"invalid id format '{data['id']}': must match ^[A-Z]{{2,6}}-[0-9]{{3}}$"
        )

    return errors


# ---------------------------------------------------------------------------
# Pattern bindings completeness validation (ACS-500f-1)
# ---------------------------------------------------------------------------

def _extract_slots_from_criteria(criteria: str) -> list[str]:
    """Extract unique slot names from pattern criteria text.

    Args:
        criteria: Gherkin criteria string from a pattern AC.

    Returns:
        Unique slot names (without braces), in first-occurrence order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for match in _SLOT_REGEX.finditer(criteria):
        name = match.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def validate_pattern_bindings_completeness(
    consuming_path: Path,
    consuming_data: dict[str, Any],
    all_ac_data: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate that a consuming AC's pattern_bindings covers all pattern slots.

    A consuming AC is one where ``implements_pattern`` is set to a non-null
    AC ID. The referenced pattern AC must declare ``pattern_slots`` (or have
    slots extractable from its ``criteria``). Every slot must appear as a key
    in the consuming AC's ``pattern_bindings``.

    Error format: ``"pattern_bindings missing required key '<slot>' for pattern <id>"``.

    Args:
        consuming_path: Filesystem path to the consuming AC file.
        consuming_data: Parsed YAML content of the consuming AC.
        all_ac_data: Mapping of AC id to parsed YAML content for every AC
            file discovered in the store.

    Returns:
        List of error message strings; empty when all bindings are complete.
    """
    pattern_id = consuming_data.get("implements_pattern")
    if not pattern_id:
        return []

    pattern_data = all_ac_data.get(str(pattern_id))
    if pattern_data is None:
        return []

    raw_slots = pattern_data.get("pattern_slots")
    if raw_slots and isinstance(raw_slots, list):
        required_slots = [s.strip("{}") for s in raw_slots if isinstance(s, str)]
    else:
        criteria_text = pattern_data.get("criteria") or ""
        required_slots = _extract_slots_from_criteria(str(criteria_text))

    if not required_slots:
        return []

    bindings = consuming_data.get("pattern_bindings") or {}
    if not isinstance(bindings, dict):
        bindings = {}

    return [
        f"{consuming_path}: pattern_bindings missing required key "
        f"'{slot}' for pattern {pattern_id}"
        for slot in required_slots
        if slot not in bindings
    ]


# ---------------------------------------------------------------------------
# Deprecated pattern reference validation (ACS-500a-3-ii)
# ---------------------------------------------------------------------------

def validate_deprecated_pattern_reference(
    consuming_path: Path,
    consuming_data: dict[str, Any],
    all_ac_data: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate that implements_pattern does not reference a deprecated pattern AC.

    Args:
        consuming_path: Filesystem path to the consuming AC file.
        consuming_data: Parsed YAML content of the consuming AC.
        all_ac_data: Mapping of AC id to parsed YAML content for every AC
            file discovered in the store.

    Returns:
        List of error message strings; empty when the reference is valid.
    """
    pattern_id = consuming_data.get("implements_pattern")
    if not pattern_id:
        return []

    pattern_data = all_ac_data.get(str(pattern_id))
    if pattern_data is None:
        return []

    if pattern_data.get("status") != "deprecated":
        return []

    return [
        f"{consuming_path}: implements_pattern references deprecated pattern "
        f"{pattern_id}; use its successor (see {pattern_id} superseded_by field) "
        f"or remove the reference"
    ]


# ---------------------------------------------------------------------------
# Duplicate criteria detection (ACS-500c-3)
# ---------------------------------------------------------------------------

def _normalize_criteria_whitespace(text: str) -> str:
    """Collapse whitespace to single space and strip.

    Args:
        text: Raw criteria string.

    Returns:
        Whitespace-normalized string.
    """
    return re.sub(r"\s+", " ", text.strip())


def _build_pattern_duplicate_regex(pattern_criteria: str) -> str | None:
    """Build a regex matching criteria structurally equivalent to the pattern.

    Args:
        pattern_criteria: Criteria string with ``{slot}`` placeholders.

    Returns:
        Regex string, or None if no placeholders present.
    """
    norm = _normalize_criteria_whitespace(pattern_criteria)
    if not _SLOT_REGEX.search(norm):
        return None

    parts = _SLOT_REGEX.split(norm)
    regex_parts: list[str] = []
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            regex_parts.append(re.escape(part))
        else:
            regex_parts.append(".+")
    return "".join(regex_parts)


def validate_criteria_not_pattern_duplicate(
    candidate_path: Path,
    candidate_data: dict[str, Any],
    all_ac_data: dict[str, dict[str, Any]],
) -> list[str]:
    """Validate that a standalone AC's criteria does not duplicate a pattern.

    Standalone ACs (no ``implements_pattern``) whose ``criteria`` text is
    structurally equivalent to an active pattern AC should instead use
    ``implements_pattern`` + ``pattern_bindings`` (AC ACS-500c-3).

    Args:
        candidate_path: Filesystem path to the candidate AC file.
        candidate_data: Parsed YAML content of the candidate AC.
        all_ac_data: Mapping of AC id to parsed YAML content for every AC
            file discovered in the store.

    Returns:
        List of error message strings; empty when no duplicate is detected.
    """
    if candidate_data.get("implements_pattern"):
        return []

    candidate_criteria_raw = candidate_data.get("criteria")
    if not candidate_criteria_raw or not isinstance(candidate_criteria_raw, str):
        return []

    candidate_norm = _normalize_criteria_whitespace(candidate_criteria_raw)
    candidate_id = candidate_data.get("id")

    errors: list[str] = []
    for pattern_id, pattern_data in all_ac_data.items():
        if candidate_id and str(candidate_id) == str(pattern_id):
            continue

        raw_slots = pattern_data.get("pattern_slots")
        if not isinstance(raw_slots, list) or len(raw_slots) == 0:
            continue

        pattern_criteria_raw = pattern_data.get("criteria")
        if not pattern_criteria_raw or not isinstance(pattern_criteria_raw, str):
            continue

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
            print(
                f"{_HOOK_PREFIX} WARNING: regex build failed for pattern "
                f"{pattern_id} — skipping duplicate check",
                file=sys.stderr,
            )

    return errors
