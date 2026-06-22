"""
Pre-commit hook: components.json integrity guard.

MODULE: check_components_integrity
GOAL: Block commits that add a new top-level component to docs/components.json
      without providing a detail_ref pointing to a real on-disk doc AND a
      flight_level in that doc's frontmatter. Also validates that ALL component
      entries satisfy the minimum required schema fields (ACS-300g-1). Skips
      the new-component existence check entirely when a git merge is in progress
      (MERGE_HEAD present), exiting 0 to allow merge commits without --no-verify
      (ACS-300g-5).
BUSINESS CONTEXT: Prevents the registry from drifting ahead of the documentation
      tree — a component added to the registry must have a doc in the same
      commit (or already have one). This closes the "9 undocumented components"
      class of drift. Additionally ensures every component entry carries the
      minimum fields needed for the AC store to cross-reference components
      bidirectionally. During merges, components from the merged-in parent are
      legitimately absent from HEAD, so the new-component check is skipped to
      avoid false positives.
ARCHITECTURE: Not needed.

Logic:
    0. Check if a git merge is in progress (`git rev-parse -q --verify MERGE_HEAD`).
       If MERGE_HEAD exists, exit 0 immediately — the new-component check does
       not apply to merge commits (ACS-300g-5).
    1. `git show HEAD:docs/components.json` → "before" JSON (None if new file).
    2. `git show :docs/components.json` (staged index) → "after" JSON.
    3. Diff top-level keys: `added = after_keys - before_keys`.
    4. For each added key:
       a. `detail_ref` must be present and non-empty.
       b. The path pointed to by `detail_ref` must exist on disk.
       c. The referenced doc must have `flight_level` in its frontmatter.
    5. For ALL keys (new and existing) in the staged version:
       a. Validate minimum required fields: id, name, type, description,
          status, primary_code.
       b. Validate field values against allowed enums.
       c. Validate that detail_ref is either null or a valid on-disk path.

Exit codes:
    0 - All components are valid (or merge in progress)
    1 - One or more components fail validation

Usage (invoked by pre-commit):
    python scripts/commit_guardian/check_components_integrity.py

Manual smoke test:
    # Stage a fake new-component diff, confirm hook blocks
    # Remove the new key, confirm hook passes

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-12 00:00 [Agent]: Created components.json integrity guard
    (EPIC-ArchitectureDocs ticket 21). Only enforces on newly-added keys to
    avoid blocking legacy work-in-progress.
  - 2026-06-08 00:00 [python-coder]: Extended with minimum schema validation for
    ALL entries per ACS-300g-1. Validates required fields and detail_ref invariant.
    (EPIC-Completecomponentcoverageintheregistry ticket 01).
  - 2026-06-22 00:00 [python-coder]: Added merge-in-progress guard per ACS-300g-5.
    When MERGE_HEAD is present the hook exits 0, skipping the new-component check
    so merge commits do not require --no-verify.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPONENTS_JSON_PATH = "docs/components.json"

# Minimum required fields for every component entry (ACS-300g-1).
REQUIRED_FIELDS = ("id", "name", "type", "description", "status", "primary_code")

# Allowed values for the ``type`` field (ACS-300g-1).
ALLOWED_TYPES = frozenset(
    {"infrastructure", "utility", "orchestration", "coding", "review", "documentation", "analysis"}
)

# Allowed values for the ``status`` field (ACS-300g-1).
ALLOWED_STATUSES = frozenset({"active", "reviewed", "planned"})

# Minimum length for the ``description`` field (ACS-300g-1).
DESCRIPTION_MIN_LEN = 10

# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _git_show(ref: str) -> str | None:
    """Return the content of a file from git at the given ref, or None.

    Args:
        ref: Git reference string, e.g. "HEAD:docs/components.json" or
            ":docs/components.json" for the staged version.

    Returns:
        File content as a string, or None if the ref does not exist.
    """
    try:
        result = subprocess.run(
            ["git", "show", ref],
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
    except OSError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout


def _parse_component_keys(content: str | None) -> set[str]:
    """Parse top-level component IDs from a components.json string.

    Args:
        content: JSON string content of the components.json file, or None.

    Returns:
        Set of top-level component ID strings; empty set on parse error or None.
    """
    if content is None:
        return set()
    try:
        data = json.loads(content)
        components_value = data.get("components", {})
        if isinstance(components_value, dict):
            return set(components_value.keys())
        if isinstance(components_value, list):
            return {c["id"] for c in components_value if isinstance(c, dict) and "id" in c}
    except (json.JSONDecodeError, KeyError, TypeError):
        pass
    return set()


def _parse_components_json(content: str | None) -> dict:
    """Parse the full components registry from a JSON string.

    Args:
        content: JSON string content, or None.

    Returns:
        The parsed ``components`` dict; empty dict on error or None.
    """
    if content is None:
        return {}
    try:
        data = json.loads(content)
        components_value = data.get("components", {})
        if isinstance(components_value, dict):
            return components_value
    except (json.JSONDecodeError, TypeError):
        pass
    return {}


def _is_components_json_staged() -> bool:
    """Return True if docs/components.json is in the staged index.

    Returns:
        True if the file is currently staged (modified, added, etc.).
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
        )
    except OSError:
        return False
    if result.returncode != 0:
        return False
    staged_files = result.stdout.strip().split("\n")
    return COMPONENTS_JSON_PATH in staged_files


def _is_merge_in_progress() -> bool:
    """Return True if a git merge is currently in progress.

    Detects a merge by verifying MERGE_HEAD via ``git rev-parse -q --verify
    MERGE_HEAD``.  A returncode of 0 means MERGE_HEAD exists (merge in
    progress).  Any non-zero returncode — including the OSError fallback
    path — means no merge is in progress.

    Returns:
        True if MERGE_HEAD is present (merge in progress), False otherwise.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        import warnings

        warnings.warn(
            f"check_components_integrity: could not verify MERGE_HEAD: {exc}",
            RuntimeWarning,
            stacklevel=2,
        )
        return False
    else:
        return result.returncode == 0


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _extract_flight_level(doc_path: Path) -> str | None:
    """Extract the flight_level field from a doc's YAML frontmatter.

    Args:
        doc_path: Absolute path to the markdown doc file.

    Returns:
        The flight_level string if present in frontmatter, None otherwise.
    """
    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError:
        return None

    if not text.startswith("---"):
        return None

    end = text.find("---", 3)
    if end == -1:
        return None

    fm_text = text[3:end]
    try:
        fm = yaml.safe_load(fm_text)
        if isinstance(fm, dict):
            return fm.get("flight_level")
    except yaml.YAMLError:
        pass
    return None


def validate_new_component(
    component_id: str,
    component_data: dict,
) -> list[str]:
    """Validate that a newly-added component entry meets integrity requirements.

    Args:
        component_id: The top-level key name of the new component.
        component_data: The component's dict value from components.json.

    Returns:
        List of error message strings; empty list if the component is valid.
    """
    errors: list[str] = []

    # 1. detail_ref must be present and non-empty
    detail_ref = component_data.get("detail_ref") if isinstance(component_data, dict) else None
    if not detail_ref:
        errors.append(
            f"  New component '{component_id}' has no detail_ref.\n"
            f"  FIX: Add a 'detail_ref' pointing to the component's architecture doc.\n"
            f"  Example: \"detail_ref\": \"docs/architecture/components/{component_id}.md\""
        )
        return errors  # Can't check further without a path

    # 2. detail_ref path must exist on disk
    doc_path = REPO_ROOT / detail_ref
    if not doc_path.exists():
        errors.append(
            f"  New component '{component_id}': detail_ref file does not exist: {detail_ref}\n"
            f"  FIX: Create the doc at '{detail_ref}' or correct the path."
        )
        return errors  # Can't check frontmatter of non-existent file

    # 3. Referenced doc must have flight_level in its frontmatter
    flight_level = _extract_flight_level(doc_path)
    if not flight_level:
        errors.append(
            f"  New component '{component_id}': detail_ref doc must have flight_level "
            f"frontmatter.\n"
            f"  File: {detail_ref}\n"
            f"  FIX: Add 'flight_level: \"L2-Container\"' (or appropriate tier) to the "
            f"frontmatter of '{detail_ref}'."
        )

    return errors


def validate_component_minimum_schema(
    component_id: str,
    component_data: dict,
) -> list[str]:
    """Validate that a component entry satisfies the minimum required schema.

    Checks all entries in the staged components.json — not just newly-added
    ones — to ensure the registry never drifts below the minimum schema bar
    defined in ACS-300g-1.

    Required fields: id, name, type, description (>= 10 chars), status,
    primary_code (non-empty array of strings).
    Optional: detail_ref must be either null or a valid on-disk Markdown path.

    Args:
        component_id: The top-level key name of the component.
        component_data: The component's dict value from components.json.

    Returns:
        List of error message strings; empty list if the component is valid.
    """
    errors: list[str] = []

    if not isinstance(component_data, dict):
        errors.append(
            f"  Component '{component_id}' entry is not a JSON object."
        )
        return errors

    # 1. Check all required fields are present and non-empty
    for field in REQUIRED_FIELDS:
        value = component_data.get(field)
        if value is None or value == "" or value == []:
            errors.append(
                f"  Component '{component_id}' is missing required field '{field}' "
                f"or it is empty."
            )

    # 2. Validate id is a snake_case string matching the top-level key
    id_value = component_data.get("id")
    if isinstance(id_value, str):
        if id_value != component_id:
            errors.append(
                f"  Component '{component_id}': 'id' field ('{id_value}') does not "
                f"match the top-level key '{component_id}'."
            )

    # 3. Validate type enum
    type_value = component_data.get("type")
    if isinstance(type_value, str) and type_value not in ALLOWED_TYPES:
        errors.append(
            f"  Component '{component_id}': 'type' value '{type_value}' is not one "
            f"of the allowed types: {', '.join(sorted(ALLOWED_TYPES))}."
        )

    # 4. Validate description length
    desc_value = component_data.get("description")
    if isinstance(desc_value, str) and len(desc_value) < DESCRIPTION_MIN_LEN:
        errors.append(
            f"  Component '{component_id}': 'description' must be at least "
            f"{DESCRIPTION_MIN_LEN} characters (got {len(desc_value)})."
        )

    # 5. Validate status enum
    status_value = component_data.get("status")
    if isinstance(status_value, str) and status_value not in ALLOWED_STATUSES:
        errors.append(
            f"  Component '{component_id}': 'status' value '{status_value}' is not "
            f"one of the allowed statuses: {', '.join(sorted(ALLOWED_STATUSES))}."
        )

    # 6. Validate primary_code is a non-empty array of strings
    primary_code = component_data.get("primary_code")
    if primary_code is not None:
        if not isinstance(primary_code, list):
            errors.append(
                f"  Component '{component_id}': 'primary_code' must be an array "
                f"of path strings."
            )
        elif len(primary_code) == 0:
            errors.append(
                f"  Component '{component_id}': 'primary_code' array must contain "
                f"at least one path string."
            )
        else:
            non_strings = [v for v in primary_code if not isinstance(v, str)]
            if non_strings:
                errors.append(
                    f"  Component '{component_id}': 'primary_code' must contain only "
                    f"strings (found non-string values: {non_strings})."
                )

    # 7. Validate detail_ref is null or a valid on-disk Markdown path
    detail_ref = component_data.get("detail_ref")
    if "detail_ref" in component_data and detail_ref is not None:
        if not isinstance(detail_ref, str):
            errors.append(
                f"  Component '{component_id}': 'detail_ref' must be a string path "
                f"or null."
            )
        else:
            doc_path = REPO_ROOT / detail_ref
            if not doc_path.exists():
                errors.append(
                    f"  Component '{component_id}': 'detail_ref' path does not exist "
                    f"on disk: {detail_ref}. Use null if no architecture doc exists yet."
                )

    return errors


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the components.json integrity check against the staged index.

    When a git merge is in progress (MERGE_HEAD present) the hook exits 0
    immediately — components arriving from the merged-in parent are legitimately
    absent from HEAD's registry, so the new-component check must not run
    (ACS-300g-5).

    For normal (non-merge) commits two validation passes are performed
    (ACS-300g-1):
    1. New-component pass: newly-added entries must have detail_ref pointing to an
       on-disk doc with flight_level frontmatter.
    2. Minimum-schema pass: ALL entries (new and existing) must satisfy the required
       field set (id, name, type, description, status, primary_code) and the
       detail_ref invariant (null or valid on-disk path).

    Returns:
        Exit code: 0 on success, 1 if any component fails validation.
    """
    # ACS-300g-5: skip the new-component existence check for merge commits.
    if _is_merge_in_progress():
        print(
            "check_components_integrity: merge in progress — "
            "skipping new-component existence check."
        )
        return 0

    if not _is_components_json_staged():
        # File not staged — nothing to check
        return 0

    before_content = _git_show(f"HEAD:{COMPONENTS_JSON_PATH}")
    after_content = _git_show(f":{COMPONENTS_JSON_PATH}")

    if after_content is None:
        # Staged version unreadable — let other hooks deal with it
        return 0

    before_keys = _parse_component_keys(before_content)
    after_keys = _parse_component_keys(after_content)
    after_components = _parse_components_json(after_content)

    all_errors: list[str] = []

    # -----------------------------------------------------------------------
    # Pass 1: New-component validation (detail_ref + flight_level required)
    # -----------------------------------------------------------------------
    added_keys = after_keys - before_keys
    new_component_errors: list[str] = []
    for component_id in sorted(added_keys):
        component_data = after_components.get(component_id, {})
        errors = validate_new_component(component_id, component_data)
        new_component_errors.extend(errors)

    # -----------------------------------------------------------------------
    # Pass 2: Minimum-schema validation (ALL entries, ACS-300g-1)
    # -----------------------------------------------------------------------
    schema_errors: list[str] = []
    for component_id in sorted(after_keys):
        component_data = after_components.get(component_id, {})
        errors = validate_component_minimum_schema(component_id, component_data)
        schema_errors.extend(errors)

    all_errors = new_component_errors + schema_errors

    if not all_errors:
        msg_parts: list[str] = []
        if added_keys:
            msg_parts.append(
                f"{len(added_keys)} new component(s) validated OK: "
                f"{', '.join(sorted(added_keys))}"
            )
        msg_parts.append(
            f"{len(after_keys)} total component(s) passed minimum-schema check."
        )
        print(f"[components-integrity] {'; '.join(msg_parts)}")
        return 0

    print("\nComponents Integrity Check Failed\n", file=sys.stderr)

    if new_component_errors:
        print(
            f"   {len(added_keys)} new component(s) detected in docs/components.json:\n"
            f"   {', '.join(sorted(added_keys))}\n",
            file=sys.stderr,
        )
        for error in new_component_errors:
            print(f"[new-component] {error}\n", file=sys.stderr)
        print(
            "   RULE (new components): Every new component added to docs/components.json must have:\n"
            "     1. A 'detail_ref' field pointing to an on-disk architecture doc.\n"
            "     2. That doc must exist at the referenced path.\n"
            "     3. That doc must have 'flight_level' in its YAML frontmatter.\n"
            "   This ensures the registry and the documentation tree stay in sync.",
            file=sys.stderr,
        )

    if schema_errors:
        for error in schema_errors:
            print(f"[minimum-schema] {error}\n", file=sys.stderr)
        print(
            "   RULE (minimum schema, ACS-300g-1): Every component in docs/components.json must have:\n"
            "     Required: id (snake_case), name, type (one of: infrastructure, utility,\n"
            "               orchestration, coding, review, documentation, analysis),\n"
            "               description (>= 10 chars), status (one of: active, reviewed, planned),\n"
            "               primary_code (non-empty array of path strings).\n"
            "     Optional: detail_ref must be null or a valid on-disk Markdown path.",
            file=sys.stderr,
        )

    return 1


if __name__ == "__main__":
    sys.exit(main())
