#!/usr/bin/env python3
"""
MODULE: validate_ac_schema
GOAL: Validate AC YAML files for required schema fields and structural constraints.
BUSINESS CONTEXT: Ensures AC store entries conform to the expected schema before they
    are consumed by scanners, test-writers, and other downstream agents; prevents
    malformed ACs from entering the store.
ARCHITECTURE: Standalone CLI script and importable module invoked by pre-commit hooks;
    reads AC YAML files and reports validation errors to stderr with a non-zero exit code.

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

import json
import sys
from pathlib import Path
from typing import Any

import yaml

# _ac_components lives alongside this script; sys.path[0] is the script dir when
# invoked as `python scripts/ac_store/validate_ac_schema.py ...`.
from _ac_components import components_field_errors, load_registry_ids  # noqa: E402

# Same schema file the commit-time hook (templates/scripts/commit_guardian/
# check_ac_schema.py, SCHEMA_PATH) validates staged ACs against. Resolving the
# repo root the same way _ac_components.default_registry_path() does
# (three parents up from this file: scripts/ac_store/validate_ac_schema.py ->
# repo_root) keeps both validators pinned to the one source-of-truth schema so
# their verdicts cannot drift apart (ACS-200e).
_SCHEMA_REL = Path("config") / "ac_store_schema.json"


def _default_schema_path() -> Path:
    """Return the repo-root-relative config/ac_store_schema.json path.

    Mirrors _ac_components.default_registry_path()'s resolution so both the
    components registry and the AC schema are located the same way regardless
    of whether this script is invoked with a relative or absolute argument.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent
    return repo_root / _SCHEMA_REL


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


def load_ac_store_schema(schema_path: Path | None = None) -> tuple[dict[str, Any] | None, str | None]:
    """Load config/ac_store_schema.json — the same schema file the commit hook uses.

    Args:
        schema_path: Path to the schema JSON file. Defaults to the repo's
            canonical `config/ac_store_schema.json` location.

    Returns:
        A `(schema, warning)` pair. On success `schema` is the parsed dict and
        `warning` is None. When the schema cannot be loaded, `schema` is None
        and `warning` is a human-readable message explaining exactly why —
        per ACS-200e AC-3, this validator must never fall silently back to
        reporting success; the caller is responsible for surfacing `warning`.
    """
    path = schema_path if schema_path is not None else _default_schema_path()
    if not path.is_file():
        return None, f"AC schema file not found at {path} — schema-level validation was SKIPPED."

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"Cannot read schema file {path}: {exc} — schema-level validation was SKIPPED."

    try:
        schema = json.loads(content)
    except json.JSONDecodeError as exc:
        return None, f"Schema file {path} is not valid JSON: {exc} — schema-level validation was SKIPPED."

    return schema, None


def _schema_field_errors(path: Path, data: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate `data` against `schema` using jsonschema, returning error strings.

    Uses the identical mechanism the commit-time hook's `validate_with_jsonschema`
    helper uses (`jsonschema.Draft7Validator`) against the SAME schema file, so
    a file that fails here is guaranteed to also fail at commit time and vice
    versa (ACS-200e parity requirement).

    Args:
        path: The AC YAML file being validated (used only for error prefixing).
        data: Parsed YAML content.
        schema: Parsed JSON Schema dict.

    Returns:
        Error message strings; empty list when `data` satisfies `schema`. If
        jsonschema is not importable, returns a single explicit error string
        rather than silently treating the file as valid.
    """
    try:
        import jsonschema
    except ImportError as exc:
        return [
            f"{path}: jsonschema is not importable ({exc}) — schema-level "
            "validation was SKIPPED. Install jsonschema to enable it."
        ]

    validator = jsonschema.Draft7Validator(schema)
    return [
        f"{path}: schema violation at "
        f"{'.'.join(str(part) for part in err.absolute_path) or '<root>'} — {err.message}"
        for err in sorted(validator.iter_errors(data), key=str)
    ]


def _validate_file(
    path: Path,
    registry_ids: set[str] | None = None,
    schema: dict[str, Any] | None = None,
) -> list[str]:
    """Validate a single YAML file for required readiness/priority/components fields.

    Args:
        path: YAML file to validate.
        registry_ids: Valid component ids from index.yaml. When None, the
            registry is loaded lazily (per-call) — callers validating many files
            should load it once and pass it in.
        schema: Parsed `config/ac_store_schema.json` content. When provided,
            the file is ALSO validated against it via jsonschema (ACS-200e) so
            the standalone validator's verdict agrees with the commit-time
            hook's. When None, schema-level validation is skipped for this
            call — callers must surface that explicitly (see
            `load_ac_store_schema`'s warning return value) rather than let the
            skip look like a passing schema check.

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
            # L1-only constraint: documentation_triggers is permitted only on L1 ACs.
            # BO-2200a-5: reject the field on L0, L2, L3 with a message that names
            # the offending AC id and its level.
            ac_level = data.get("level")
            if ac_level != "L1":
                errors.append(
                    f"{path}: Field 'documentation_triggers' is permitted only on L1 "
                    f"ACs. AC {data['id']} has level {ac_level!r}."
                )

    # --- Validate against config/ac_store_schema.json (ACS-200e) ---
    # This is the SAME schema file the commit-time hook
    # (templates/scripts/commit_guardian/check_ac_schema.py) validates staged
    # ACs against, so a file that passes here is guaranteed to also pass the
    # hook and vice versa. Only runs when a schema was actually loaded — the
    # caller (main()) is responsible for printing an explicit warning when it
    # was not, per ACS-200e AC-3 (never silently report success without the
    # schema check having run).
    if schema is not None:
        errors.extend(_schema_field_errors(path, data, schema))

    return errors


def _resolve_ac_yaml_paths(args: list[str]) -> tuple[list[Path], list[str]]:
    """Expand CLI arguments into the concrete AC YAML files to validate.

    A **directory** argument is walked recursively, because that is plainly what
    every caller means by it and because AC YAML sits at more than one depth —
    some records live directly under a component directory, others inside a
    feature folder. A fixed-depth glob such as ``*/*.yaml`` silently skips whole
    directories, which is the same no-op defect in a smaller costume (KI-ACS-001).

    ``index.yaml`` is excluded from directory walks: it is the component
    registry, not an acceptance criterion, and validating it as one would fail
    every directory run on a file that was never an AC. Naming it explicitly on
    the command line still validates it, so this narrows discovery only.

    Args:
        args: Raw command-line arguments — file paths, directory paths, or both.

    Returns:
        ``(paths, errors)``: the AC YAML files to validate, de-duplicated and
        sorted, plus one error string per argument that could not be resolved.
    """
    resolved: list[Path] = []
    errors: list[str] = []

    for arg in args:
        path = Path(arg)
        if not path.exists():
            errors.append(f"{path}: File not found.")
            continue
        if path.is_dir():
            found = sorted(
                p
                for p in (*path.rglob("*.yaml"), *path.rglob("*.yml"))
                if p.is_file() and p.name != "index.yaml"
            )
            if not found:
                errors.append(f"{path}: directory contains no AC YAML files.")
            resolved.extend(found)
            continue
        if path.suffix not in {".yaml", ".yml"}:
            continue  # Skip non-YAML files silently
        resolved.append(path)

    # De-duplicate while preserving order: overlapping arguments (a directory
    # plus a file inside it) must not validate the same record twice, which
    # would double-count files_checked and any error it produces.
    seen: set[Path] = set()
    unique = [p for p in resolved if not (p in seen or seen.add(p))]
    return unique, errors


def main(argv: list[str] | None = None) -> int:
    """Validate AC YAML files and return exit code (0 = ok, 1 = errors, 2 = usage error)."""
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print(
            "Usage: validate_ac_schema.py <path> [<path> ...]\n"
            "\n"
            "Each <path> is an AC YAML file or a DIRECTORY, which is walked\n"
            "recursively (index.yaml is skipped — it is the component registry,\n"
            "not an acceptance criterion).\n"
            "\n"
            "Validates each record for required fields:\n"
            "  readiness: [draft | reviewed | approved]\n"
            "  priority:  [critical | high | medium | low]\n"
            "\n"
            "Exits non-zero if any validation error is found, AND if the\n"
            "arguments resolve to zero files — a run that checked nothing is\n"
            "not a pass.",
            file=sys.stderr,
        )
        return 2

    all_errors: list[str] = []
    files_checked = 0

    # Load the component registry once for the whole run.
    registry_ids = load_registry_ids()

    # Load the AC store schema once for the whole run (ACS-200e). Both the
    # schema file's presence and jsonschema's importability are checked up
    # front so a run-wide skip is reported explicitly ONCE via a WARNING,
    # rather than looking like a passing schema check for every file (AC-3:
    # never silently report success without the schema check having run).
    try:
        import jsonschema  # noqa: F401
    except ImportError as exc:
        print(
            f"WARNING: jsonschema is not importable ({exc}) — schema-level "
            "validation against config/ac_store_schema.json was SKIPPED for "
            "this entire run. Install jsonschema to enable parity with the "
            "commit-time hook.",
            file=sys.stderr,
        )
        schema: dict[str, Any] | None = None
    else:
        schema, schema_warning = load_ac_store_schema()
        if schema_warning is not None:
            print(f"WARNING: {schema_warning}", file=sys.stderr)

    paths, resolve_errors = _resolve_ac_yaml_paths(args)
    all_errors.extend(resolve_errors)

    for path in paths:
        errors = _validate_file(path, registry_ids, schema)
        all_errors.extend(errors)
        files_checked += 1

    if all_errors:
        print("AC schema validation FAILED:", file=sys.stderr)
        for err in all_errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    if files_checked == 0:
        # KI-ACS-001: exiting 0 here reported a success-shaped result from a run
        # that checked nothing. A validator consulted for reassurance must be
        # able to distinguish "clean" from "I was given nothing".
        print(
            "ERROR: no AC YAML files were validated. The arguments resolved to "
            "zero files, so nothing was checked — this is NOT a pass.\n"
            f"  arguments: {' '.join(args)}",
            file=sys.stderr,
        )
        return 1

    if files_checked == 1:
        print(f"OK: {args[0]} is valid.")
    else:
        print(f"OK: all {files_checked} AC YAML files are valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


# DECISION HISTORY
# ================================================================================
# - 2026-07-17 15:00 [python-coder]: Verified that the enum-value check and the
#   L1-only level check for documentation_triggers are independent (both run as
#   separate if-branches with no short-circuit); added MODULE/GOAL/BUSINESS CONTEXT/
#   ARCHITECTURE docstring fields and this DECISION HISTORY block per doc-enforcer.
#   (#EPIC-DocumentationCoverageGuarantee/07)
# - 2026-08-13 15:00 [python-coder]: Closed the false-green gap where this
#   validator's docstring claimed schema validation it never performed. Added
#   load_ac_store_schema() + _schema_field_errors(), which load and apply the
#   SAME config/ac_store_schema.json the commit-time hook
#   (templates/scripts/commit_guardian/check_ac_schema.py) validates against,
#   via the identical jsonschema.Draft7Validator mechanism — so the two
#   verdicts cannot drift. Schema path is resolved the same way
#   _ac_components.default_registry_path() resolves docs/components.json
#   (three parents up from this file), so it works for both relative and
#   absolute invocation. When jsonschema is not importable or the schema file
#   is absent/unreadable/invalid JSON, main() prints an explicit WARNING to
#   stderr naming the reason and falls back to the existing hand-rolled checks
#   only — it never silently reports success as if the schema check had run.
#   (#TICKETLESS reason=quick-fix-ACS-200e-schema-validator-parity)
