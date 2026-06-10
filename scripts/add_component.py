"""
Tooling script: add a component entry to docs/components.json.

MODULE: add_component
GOAL: Provide a standalone, idempotent-safe CLI for appending a new component
      entry to the docs/components.json registry.  Validates the entry against
      the minimum required schema before writing, preserves all existing entries
      unchanged, and exits non-zero if the component ID already exists (preventing
      silent overwrites).
BUSINESS CONTEXT: docs/components.json is the canonical component registry for
      the leafcutter-ai package.  Hand-editing the registry is error-prone and
      does not run the minimum-schema validator.  This script closes that gap by
      applying the same enum / field checks used by the pre-commit hook before
      any write reaches disk (ACS-300g-4a).
ARCHITECTURE: Standalone; no project-local imports.  All validation logic is
      self-contained so the script can be called from CI or a one-off shell
      session without installing the full package.

Usage:
    python scripts/add_component.py \\
        --id my_component \\
        --name "My Component" \\
        --type utility \\
        --description "Does something useful." \\
        --primary-code "scripts/my_component.py" \\
        --status active \\
        [--detail-ref "docs/architecture/components/my_component.md"]

    The --primary-code flag may be repeated for multiple paths:
        --primary-code "scripts/a.py" --primary-code "scripts/b.py"

    --components-json may be used to override the default path
    (docs/components.json relative to the repo root inferred from this file).

Exit codes:
    0  — component written successfully.
    1  — validation error or ID already exists.
    2  — I/O error (file unreadable / unwritable).

DOC_LINKS: docs/build-pipeline.md
DECISION HISTORY:
  - 2026-06-08 00:00 [python-coder]: Initial implementation per ACS-300g-4a.
    Standalone validator; no project-local imports. (#EPIC-Completecomponentcoverageintheregistry/04)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants (mirrors check_components_integrity.py to avoid drift)
# ---------------------------------------------------------------------------

ALLOWED_TYPES: frozenset[str] = frozenset(
    {
        "infrastructure",
        "utility",
        "orchestration",
        "coding",
        "review",
        "documentation",
        "analysis",
    }
)

ALLOWED_STATUSES: frozenset[str] = frozenset({"active", "reviewed", "planned"})

DESCRIPTION_MIN_LEN: int = 10

# Default path: repo_root/docs/components.json
# Repo root is two directories above this script (scripts/ → repo_root).
_DEFAULT_COMPONENTS_JSON: Path = (
    Path(__file__).resolve().parent.parent / "docs" / "components.json"
)

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_entry(component_id: str, entry: dict) -> list[str]:
    """Validate a proposed component entry against the minimum schema.

    Args:
        component_id: The top-level key / ``id`` value for the new component.
        entry: The proposed component dictionary.

    Returns:
        A list of human-readable error strings.  Empty list means valid.
    """
    errors: list[str] = []

    # id must match the top-level key
    if entry.get("id") != component_id:
        errors.append(
            f"'id' field ('{entry.get('id')}') does not match the "
            f"component_id argument ('{component_id}')."
        )

    # Required fields: name, type, description, status, primary_code
    for field in ("name", "type", "description", "status", "primary_code"):
        value = entry.get(field)
        if value is None or value == "" or value == []:
            errors.append(f"Required field '{field}' is missing or empty.")

    # type enum
    type_value = entry.get("type")
    if isinstance(type_value, str) and type_value not in ALLOWED_TYPES:
        errors.append(
            f"'type' value '{type_value}' is not one of the allowed types: "
            f"{', '.join(sorted(ALLOWED_TYPES))}."
        )

    # description length
    desc_value = entry.get("description")
    if isinstance(desc_value, str) and len(desc_value) < DESCRIPTION_MIN_LEN:
        errors.append(
            f"'description' must be at least {DESCRIPTION_MIN_LEN} characters "
            f"(got {len(desc_value)})."
        )

    # status enum
    status_value = entry.get("status")
    if isinstance(status_value, str) and status_value not in ALLOWED_STATUSES:
        errors.append(
            f"'status' value '{status_value}' is not one of the allowed statuses: "
            f"{', '.join(sorted(ALLOWED_STATUSES))}."
        )

    # primary_code: non-empty list of strings
    primary_code = entry.get("primary_code")
    if primary_code is not None:
        if not isinstance(primary_code, list):
            errors.append("'primary_code' must be a list of path strings.")
        elif len(primary_code) == 0:
            errors.append("'primary_code' must contain at least one path string.")
        else:
            non_strings = [v for v in primary_code if not isinstance(v, str)]
            if non_strings:
                errors.append(
                    f"'primary_code' must contain only strings "
                    f"(found non-string values: {non_strings})."
                )

    # detail_ref: must be null or a string (we do NOT validate on-disk existence here
    # because the script is meant to be used before the doc is committed)
    detail_ref = entry.get("detail_ref")
    if detail_ref is not None and not isinstance(detail_ref, str):
        errors.append("'detail_ref' must be a string path or null.")

    return errors


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def load_registry(components_json: Path) -> dict:
    """Load and parse the components.json file.

    Args:
        components_json: Absolute path to docs/components.json.

    Returns:
        The parsed top-level dict (``{"components": {...}}``).

    Raises:
        SystemExit(2): If the file cannot be read or parsed.
    """
    try:
        text = components_json.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"ERROR: cannot read '{components_json}': {exc}", file=sys.stderr)
        sys.exit(2)

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: '{components_json}' is not valid JSON: {exc}",
            file=sys.stderr,
        )
        sys.exit(2)

    if not isinstance(data, dict) or "components" not in data:
        print(
            f"ERROR: '{components_json}' does not have a top-level 'components' key.",
            file=sys.stderr,
        )
        sys.exit(2)

    if not isinstance(data["components"], dict):
        print(
            "ERROR: 'components' value must be a JSON object (dict), not a list or scalar.",
            file=sys.stderr,
        )
        sys.exit(2)

    return data


def write_registry(data: dict, components_json: Path) -> None:
    """Write the registry back to disk with consistent formatting.

    Uses 2-space indentation and sorted top-level keys inside the
    ``components`` dict so diffs are deterministic.

    Args:
        data: The full top-level dict to serialise.
        components_json: Destination path.

    Raises:
        SystemExit(2): If the file cannot be written.
    """
    # Sort the inner components dict by key for deterministic output.
    data["components"] = dict(sorted(data["components"].items()))

    try:
        text = json.dumps(data, indent=2, ensure_ascii=False)
        # Ensure the file ends with a newline (POSIX convention).
        if not text.endswith("\n"):
            text += "\n"
        components_json.write_text(text, encoding="utf-8")
    except OSError as exc:
        print(
            f"ERROR: cannot write '{components_json}': {exc}",
            file=sys.stderr,
        )
        sys.exit(2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for this script.

    Returns:
        Configured ``argparse.ArgumentParser`` instance.
    """
    parser = argparse.ArgumentParser(
        prog="add_component",
        description=(
            "Append a new component entry to docs/components.json, validating "
            "against the minimum schema before writing.  Exits non-zero if the "
            "component ID already exists."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--id",
        dest="component_id",
        required=True,
        help="Unique snake_case component identifier (top-level key in the registry).",
    )
    parser.add_argument(
        "--name",
        required=True,
        help="Human-readable display name for the component.",
    )
    parser.add_argument(
        "--type",
        dest="component_type",
        required=True,
        choices=sorted(ALLOWED_TYPES),
        help="Component type (one of the allowed enum values).",
    )
    parser.add_argument(
        "--description",
        required=True,
        help=(
            f"Plain-English description (minimum {DESCRIPTION_MIN_LEN} characters)."
        ),
    )
    parser.add_argument(
        "--primary-code",
        dest="primary_code",
        required=True,
        action="append",
        metavar="PATH",
        help=(
            "Repo-relative path to a primary source file or directory.  "
            "May be repeated for multiple paths."
        ),
    )
    parser.add_argument(
        "--status",
        required=True,
        choices=sorted(ALLOWED_STATUSES),
        help="Component lifecycle status.",
    )
    parser.add_argument(
        "--detail-ref",
        dest="detail_ref",
        default=None,
        help=(
            "Repo-relative path to the architecture doc for this component.  "
            "Use null (omit this flag) when no doc exists yet."
        ),
    )
    parser.add_argument(
        "--components-json",
        dest="components_json",
        default=None,
        help=(
            "Override the path to components.json.  Defaults to "
            "docs/components.json relative to the repo root."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the add_component script.

    Args:
        argv: Argument vector (defaults to sys.argv[1:] when None).

    Returns:
        Exit code: 0 on success, 1 on validation / duplicate error, 2 on I/O error.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    # Resolve the components.json path.
    if args.components_json is not None:
        components_json = Path(args.components_json).resolve()
    else:
        components_json = _DEFAULT_COMPONENTS_JSON

    # Load the existing registry.
    data = load_registry(components_json)
    existing = data["components"]

    # Guard against silent overwrites (AC: exits non-zero if ID already exists).
    if args.component_id in existing:
        print(
            f"ERROR: component ID '{args.component_id}' already exists in "
            f"'{components_json}'.  Use a different --id or remove the existing "
            f"entry manually before re-adding.",
            file=sys.stderr,
        )
        return 1

    # Build the new entry dict.
    new_entry: dict = {
        "id": args.component_id,
        "name": args.name,
        "type": args.component_type,
        "description": args.description,
        "detail_ref": args.detail_ref,
        "status": args.status,
        "primary_code": args.primary_code,
    }

    # Validate before writing.
    errors = validate_entry(args.component_id, new_entry)
    if errors:
        print("ERROR: new component entry failed validation:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    # Append and write back.
    existing[args.component_id] = new_entry
    write_registry(data, components_json)

    print(
        f"[add_component] Added component '{args.component_id}' to '{components_json}'."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
