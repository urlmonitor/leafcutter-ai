"""
Pre-commit hook: components.json integrity guard.

MODULE: check_components_integrity
GOAL: Block commits that add a new top-level component to docs/components.json
      without providing a detail_ref pointing to a real on-disk doc AND a
      flight_level in that doc's frontmatter. Also exposes full schema validators
      for programmatic validation (ACS-300g-1, ACS-300h-1, ACS-300i-1,
      ACS-300i-2, ACS-300j-1).
BUSINESS CONTEXT: Prevents the registry from drifting ahead of the documentation
      tree. Standalone validator functions expose full schema enforcement for
      backfill tooling and other hooks.
ARCHITECTURE: Not needed.

Logic:
    1. `git show HEAD:docs/components.json` -> "before" JSON (None if new file).
    2. `git show :docs/components.json` (staged index) -> "after" JSON.
    3. Diff top-level keys: `added = after_keys - before_keys`.
    4. For each added key:
       a. `detail_ref` must be present and non-empty.
       b. The path pointed to by `detail_ref` must exist on disk.
       c. The referenced doc must have `flight_level` in its frontmatter.
    5. Existing components (no diff) are NOT checked -- legacy drift is accepted;
       backfilling is handled by Phase 4 tickets.

    Full schema validators (called from main() for each newly-added component):
      validate_component_minimum_schema  -- id (snake_case), name, type, description,
                                           status, primary_code, detail_ref (ACS-300g-1)
      validate_agent_affinity            -- agent_affinity array (ACS-300h-1)
      validate_exposed_interfaces        -- exposed_interfaces array + element
                                           schema (ACS-300i-1, ACS-300i-2)
      validate_depends_on                -- referential integrity (ACS-300j-1)

Exit codes:
    0 - All new components are valid
    1 - One or more new components fail validation

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
  - 2026-06-22 [Agent]: Added merge-in-progress skip (ACS-300g-5). When
    MERGE_HEAD is present the hook exits 0 immediately so merge commits are
    committable without --no-verify. Normal (non-merge) commits are unchanged.
  - 2026-06-22 [Agent]: Applied I/O-boundary wraps to _git_show() and
    _is_components_json_staged() (ACS-300g-5). Both subprocess.run() calls now
    catch (subprocess.SubprocessError, OSError), print a WARNING diagnostic to
    stderr, and return the function's pre-existing safe default (None / False)
    on error. This satisfies the check-exception-handling (IO-001) pre-commit
    guard. Pattern matches _is_merge_in_progress() which was already compliant.
  - 2026-06-22 [Agent]: Replaced module-level REPO_ROOT constant with
    _repo_root() helper (ACS-300g-6). The helper resolves the project root via
    `git rev-parse --show-toplevel` (CWD-based), so detail_ref existence checks
    resolve against the COMMITTING repository's docs/ rather than against the
    hook file's install location. Falls back to Path(__file__).resolve().parents[2]
    when git is unavailable or returns a non-zero exit code. main() calls
    _repo_root() once and threads the resolved root into validate_new_component().
  - 2026-07-07 [python-coder/ACS-300g-1,h-1,i-1,i-2,j-1]: Added full schema
    validator functions: validate_component_minimum_schema, validate_agent_affinity,
    validate_exposed_interfaces, validate_depends_on. Added module-level constants
    ALLOWED_TYPES, ALLOWED_STATUSES, VALID_INTERFACE_TYPES, DESCRIPTION_MIN_LEN,
    and REPO_ROOT (patchable for tests). Validators exposed for programmatic use;
    main() continues to enforce only the detail_ref+flight_level rule on new
    components (backfill compatibility -- existing entries lack the new fields).
  - 2026-07-08 [python-coder/H-1-fix,M-2]: Wired all four schema validators into
    main() for each added_keys entry: validate_component_minimum_schema,
    validate_agent_affinity, validate_exposed_interfaces, validate_depends_on.
    Added snake_case check for the id field per ACS-300g-1 (M-2). Computed
    all_component_ids once before the loop for validate_depends_on. Existing
    components (no diff) remain unchecked for backfill compatibility.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


COMPONENTS_JSON_PATH = "docs/components.json"

# Allowed enumeration values for component entry fields (ACS-300g-1).
ALLOWED_TYPES: frozenset[str] = frozenset({
    "infrastructure",
    "utility",
    "orchestration",
    "coding",
    "review",
    "documentation",
    "analysis",
})
ALLOWED_STATUSES: frozenset[str] = frozenset({"active", "reviewed", "planned"})

# Allowed type values for elements in exposed_interfaces (ACS-300i-1).
VALID_INTERFACE_TYPES: frozenset[str] = frozenset({
    "file_contract",
    "json_schema",
    "function_signature",
    "cli_command",
    "hook_protocol",
    "event",
    "data_shape",
})

# Minimum character count for the description field (ACS-300g-1).
DESCRIPTION_MIN_LEN: int = 10

# Repository root: initialized to the __file__-relative fallback at import time.
# main() updates this via _repo_root() for CWD-based commit-time resolution.
# Tests may patch this module-level variable to redirect detail_ref existence checks.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# Root resolution
# ---------------------------------------------------------------------------


def _repo_root() -> Path:
    """Return the root of the committing git repository.

    Resolves the root by running ``git rev-parse --show-toplevel`` in the
    current working directory, which is the repository being committed to when
    the hook is invoked by pre-commit.  This is correct regardless of where the
    hook *file* lives (e.g. via a .leafcutter symlink into another repo), fixing
    the false "detail_ref file does not exist" failure described in ACS-300g-6.

    Falls back to ``Path(__file__).resolve().parents[2]`` when:
    - The subprocess call raises (subprocess.SubprocessError or OSError).
    - ``git`` returns a non-zero exit code.
    - ``git`` returns an empty stdout.

    The fallback preserves the hook's pre-ACS-300g-6 behaviour so it never
    hard-crashes in environments where git is unavailable.

    Returns:
        Absolute Path to the repository root; the fallback path when git fails.
    """
    _fallback = Path(__file__).resolve().parents[2]
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"[components-integrity] WARNING: could not run git rev-parse "
            f"--show-toplevel: {exc}; falling back to __file__-relative root",
            file=sys.stderr,
        )
        return _fallback
    if result.returncode != 0 or not result.stdout.strip():
        print(
            "[components-integrity] WARNING: git rev-parse --show-toplevel "
            "returned non-zero or empty output; falling back to __file__-relative root",
            file=sys.stderr,
        )
        return _fallback
    return Path(result.stdout.strip())

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
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"[components-integrity] WARNING: could not run git show {ref!r}: {exc}",
            file=sys.stderr,
        )
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


def _is_merge_in_progress() -> bool:
    """Return True when a git merge is currently in progress.

    Detects the merge state by verifying that MERGE_HEAD resolves to a valid
    commit object via ``git rev-parse -q --verify MERGE_HEAD``.  Exit code 0
    means MERGE_HEAD exists (merge in progress); non-zero means it does not.

    Returns:
        True if a merge is in progress (MERGE_HEAD is present and valid),
        False if no merge is in progress or if the git command cannot be run.
        Fails open toward running the normal check so a broken git environment
        never silently suppresses the integrity guard.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"[components-integrity] WARNING: could not check MERGE_HEAD: {exc}",
            file=sys.stderr,
        )
        return False
    return result.returncode == 0


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
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"[components-integrity] WARNING: could not run git diff --cached: {exc}",
            file=sys.stderr,
        )
        return False
    if result.returncode != 0:
        return False
    staged_files = result.stdout.strip().split("\n")
    return COMPONENTS_JSON_PATH in staged_files


# ---------------------------------------------------------------------------
# Full schema validation helpers (ACS-300g-1, ACS-300h-1, ACS-300i-1,
# ACS-300i-2, ACS-300j-1)
# ---------------------------------------------------------------------------


def validate_component_minimum_schema(
    component_id: str,
    component_data: object,
) -> list[str]:
    """Validate required minimum-schema fields for a component entry (ACS-300g-1).

    Checks the six required scalar/list fields (id, name, type, description,
    status, primary_code) plus the optional detail_ref field.  The module-level
    ``REPO_ROOT`` variable controls how detail_ref paths are resolved on disk;
    tests may patch it without patching the filesystem.

    Args:
        component_id: Top-level key name for this component in components.json.
        component_data: The component dict value.  Must be a dict; a non-dict
            value produces a single error and returns immediately.

    Returns:
        List of human-readable error strings.  Empty list means the entry is
        valid against the minimum schema.
    """
    errors: list[str] = []

    if not isinstance(component_data, dict):
        errors.append(
            f"Component '{component_id}': entry is not a JSON object."
        )
        return errors

    # id: present, non-empty string, matches the top-level key, and snake_case
    cid = component_data.get("id")
    if "id" not in component_data or not isinstance(cid, str) or not cid:
        errors.append(
            f"Component '{component_id}': 'id' must be a non-empty string."
        )
    elif cid != component_id:
        errors.append(
            f"Component '{component_id}': 'id' field value {cid!r} does not match "
            f"the top-level key '{component_id}'."
        )
    elif not re.match(r'^[a-z][a-z0-9_]*$', cid):
        errors.append(
            f"Component '{component_id}': 'id' must be snake_case "
            f"(lowercase letters, digits, and underscores only, starting with a "
            f"lowercase letter), got {cid!r}."
        )

    # name: present, non-empty string
    name = component_data.get("name")
    if "name" not in component_data or not isinstance(name, str) or not name:
        errors.append(
            f"Component '{component_id}': 'name' must be a non-empty string."
        )

    # type: present, must be in ALLOWED_TYPES
    comp_type = component_data.get("type")
    if "type" not in component_data:
        errors.append(
            f"Component '{component_id}': 'type' is required and must be "
            f"one of the allowed types: {sorted(ALLOWED_TYPES)}."
        )
    elif comp_type not in ALLOWED_TYPES:
        errors.append(
            f"Component '{component_id}': 'type' value {comp_type!r} is "
            f"not one of the allowed types: {sorted(ALLOWED_TYPES)}."
        )

    # description: present, string, >= DESCRIPTION_MIN_LEN chars
    description = component_data.get("description")
    if "description" not in component_data:
        errors.append(
            f"Component '{component_id}': 'description' is required (>= "
            f"{DESCRIPTION_MIN_LEN} characters)."
        )
    elif not isinstance(description, str) or len(description) < DESCRIPTION_MIN_LEN:
        desc_len = len(description) if isinstance(description, str) else "non-string"
        errors.append(
            f"Component '{component_id}': 'description' must be a string of at least "
            f"{DESCRIPTION_MIN_LEN} characters (got {desc_len})."
        )

    # status: present, must be in ALLOWED_STATUSES
    status = component_data.get("status")
    if "status" not in component_data:
        errors.append(
            f"Component '{component_id}': 'status' is required and must be "
            f"one of the allowed statuses: {sorted(ALLOWED_STATUSES)}."
        )
    elif status not in ALLOWED_STATUSES:
        errors.append(
            f"Component '{component_id}': 'status' value {status!r} is "
            f"not one of the allowed statuses: {sorted(ALLOWED_STATUSES)}."
        )

    # primary_code: present, non-empty list of non-empty strings
    primary_code = component_data.get("primary_code")
    if "primary_code" not in component_data:
        errors.append(
            f"Component '{component_id}': 'primary_code' is required."
        )
    elif not isinstance(primary_code, list):
        errors.append(
            f"Component '{component_id}': 'primary_code' must be an array of path strings."
        )
    elif not primary_code:
        errors.append(
            f"Component '{component_id}': 'primary_code' must contain at least one path string."
        )
    elif not all(isinstance(p, str) and p for p in primary_code):
        errors.append(
            f"Component '{component_id}': 'primary_code' must contain only non-empty strings."
        )

    # detail_ref: optional key; when present and not null must be a valid path
    if "detail_ref" in component_data:
        detail_ref = component_data["detail_ref"]
        if detail_ref is not None:
            if not isinstance(detail_ref, str) or not detail_ref:
                errors.append(
                    f"Component '{component_id}': 'detail_ref' must be a string path or null."
                )
            else:
                doc_path = REPO_ROOT / detail_ref
                if not doc_path.exists():
                    errors.append(
                        f"Component '{component_id}': 'detail_ref' file does not exist: "
                        f"{detail_ref}"
                    )

    return errors


def validate_agent_affinity(
    component_id: str,
    component_data: object,
) -> list[str]:
    """Validate that agent_affinity is present as a JSON array (ACS-300h-1).

    The field must be present on every component entry; null and absent are
    both invalid.  An empty list ``[]`` is valid (no agent affinity declared).

    Args:
        component_id: Top-level key name for this component.
        component_data: The component dict value.  Non-dict input returns [].

    Returns:
        List of human-readable error strings.  Empty list means the field is valid.
    """
    if not isinstance(component_data, dict):
        return []
    errors: list[str] = []
    if "agent_affinity" not in component_data:
        errors.append(
            f"Component '{component_id}': 'agent_affinity' field is required "
            f"(use [] if no agent affinity)."
        )
    elif not isinstance(component_data["agent_affinity"], list):
        errors.append(
            f"Component '{component_id}': 'agent_affinity' must be a JSON array, "
            f"never null."
        )
    return errors


def validate_exposed_interfaces(
    component_id: str,
    component_data: object,
) -> list[str]:
    """Validate exposed_interfaces field and its element schema (ACS-300i-1, ACS-300i-2).

    The field must be present and must be an array (null and absent are both
    invalid).  Each element must have all four required fields: name, type,
    path, shape.  All missing fields per element are reported in a single error
    (not fail-on-first).  The element ``type`` value is also validated against
    ``VALID_INTERFACE_TYPES``.

    Args:
        component_id: Top-level key name for this component.
        component_data: The component dict value.  Non-dict input returns [].

    Returns:
        List of human-readable error strings.  Empty list means the field is valid.
    """
    if not isinstance(component_data, dict):
        return []
    errors: list[str] = []

    if "exposed_interfaces" not in component_data:
        errors.append(
            f"Component '{component_id}': 'exposed_interfaces' field is required "
            f"(use [] if the component has no external interfaces)."
        )
        return errors

    ifaces = component_data["exposed_interfaces"]
    if not isinstance(ifaces, list):
        errors.append(
            f"Component '{component_id}': 'exposed_interfaces' must be an array, "
            f"never null."
        )
        return errors

    _REQUIRED_IFACE_FIELDS = ("name", "type", "path", "shape")
    for i, iface in enumerate(ifaces):
        if not isinstance(iface, dict):
            errors.append(
                f"Component '{component_id}': exposed_interfaces[{i}] "
                f"must be a JSON object."
            )
            continue
        # Report ALL missing fields in one pass (not fail-on-first).
        missing = [
            f for f in _REQUIRED_IFACE_FIELDS
            if f not in iface or not iface.get(f)
        ]
        if missing:
            errors.append(
                f"Component '{component_id}': exposed_interfaces[{i}] "
                f"is missing required fields: {', '.join(missing)}."
            )
        iface_type = iface.get("type")
        if iface_type and iface_type not in VALID_INTERFACE_TYPES:
            errors.append(
                f"Component '{component_id}': exposed_interfaces[{i}] "
                f"'type' value {iface_type!r} is not one of the valid interface "
                f"types: {sorted(VALID_INTERFACE_TYPES)}."
            )

    return errors


def validate_depends_on(
    component_id: str,
    component_data: object,
    all_component_ids: set[str],
) -> list[str]:
    """Validate depends_on references only valid component IDs (ACS-300j-1, ACS-300j-1-i).

    Each element of the depends_on list is checked individually:
      1. Fast-path self-reference rejection (ACS-300j-1-i): if the element
         equals component_id, an error is emitted immediately for that entry
         before the unknown-ID check runs, so a self-reference is always caught
         even when the component ID is in all_component_ids.
      2. Unknown-ID rejection (ACS-300j-1): any element not present in
         all_component_ids is also flagged.

    Args:
        component_id: Top-level key name for this component.
        component_data: The component dict value.  Non-dict input returns [].
        all_component_ids: Set of all valid component IDs in the same file.

    Returns:
        List of human-readable error strings.  Empty list means all references
        are valid (or depends_on is absent / empty).
    """
    if not isinstance(component_data, dict):
        return []
    errors: list[str] = []
    depends_on = component_data.get("depends_on")
    if not depends_on:
        return []
    if not isinstance(depends_on, list):
        return []
    valid_ids_sorted = sorted(all_component_ids)
    for dep_id in depends_on:
        # Fast-path: self-reference check runs before unknown-ID check (ACS-300j-1-i).
        if dep_id == component_id:
            errors.append(
                f"Component '{component_id}' cannot depend on itself."
            )
            continue
        if dep_id not in all_component_ids:
            errors.append(
                f"Component '{component_id}': depends_on references unknown ID "
                f"'{dep_id}'. Valid component IDs: {valid_ids_sorted}."
            )
    return errors


# ---------------------------------------------------------------------------
# Validation helpers (pre-existing)
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
    root: Path,
    component_id: str,
    component_data: dict,
) -> list[str]:
    """Validate that a newly-added component entry meets integrity requirements.

    Args:
        root: Absolute path to the committing repository root, used to resolve
            the detail_ref path on disk.  Must be obtained from _repo_root() so
            that the resolution is CWD-based (the committing repo), not relative
            to the hook file's install location.
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

    # 2. detail_ref path must exist on disk (resolved against the committing repo root)
    doc_path = root / detail_ref
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


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the components.json integrity check against the staged index.

    Returns:
        Exit code: 0 on success, 1 if any new component fails validation.
    """
    if not _is_components_json_staged():
        # File not staged -- nothing to check
        return 0

    if _is_merge_in_progress():
        # Components arriving from the merged-in parent appear "newly added"
        # relative to HEAD but are not genuine additions by this commit.
        # Skipping the new-component check lets merge commits proceed without
        # --no-verify. (ACS-300g-5)
        print(
            "[components-integrity] merge in progress (MERGE_HEAD present)"
            " -- skipping new-component check",
            file=sys.stderr,
        )
        return 0

    before_content = _git_show(f"HEAD:{COMPONENTS_JSON_PATH}")
    after_content = _git_show(f":{COMPONENTS_JSON_PATH}")

    if after_content is None:
        # Staged version unreadable -- let other hooks deal with it
        return 0

    before_keys = _parse_component_keys(before_content)
    after_keys = _parse_component_keys(after_content)

    added_keys = after_keys - before_keys

    if not added_keys:
        return 0  # No new components -- nothing to enforce

    after_components = _parse_components_json(after_content)

    repo_root = _repo_root()
    # Update module-level REPO_ROOT so validate_component_minimum_schema uses
    # the CWD-based path at runtime (not the __file__-relative fallback).
    global REPO_ROOT  # noqa: PLW0603
    REPO_ROOT = repo_root

    all_component_ids = set(after_components.keys())
    all_errors: list[str] = []
    for component_id in sorted(added_keys):
        component_data = after_components.get(component_id, {})
        errors = validate_new_component(repo_root, component_id, component_data)
        all_errors.extend(errors)
        all_errors.extend(validate_component_minimum_schema(component_id, component_data))
        all_errors.extend(validate_agent_affinity(component_id, component_data))
        all_errors.extend(validate_exposed_interfaces(component_id, component_data))
        all_errors.extend(validate_depends_on(component_id, component_data, all_component_ids))

    if not all_errors:
        print(
            f"[components-integrity] {len(added_keys)} new component(s) validated OK: "
            f"{', '.join(sorted(added_keys))}"
        )
        return 0

    print("\n[components-integrity] Components Integrity Check Failed\n", file=sys.stderr)
    print(
        f"   {len(added_keys)} new component(s) detected in docs/components.json:\n"
        f"   {', '.join(sorted(added_keys))}\n",
        file=sys.stderr,
    )
    for error in all_errors:
        print(f"[x] {error}\n", file=sys.stderr)

    print(
        "   RULE: Every new component added to docs/components.json must have:\n"
        "     1. A 'detail_ref' field pointing to an on-disk architecture doc.\n"
        "     2. That doc must exist at the referenced path.\n"
        "     3. That doc must have 'flight_level' in its YAML frontmatter.\n"
        "     4. All minimum-schema fields: id (snake_case), name, type, description\n"
        "        (>= 10 chars), status (active|reviewed|planned), primary_code (>= 1 path).\n"
        "     5. An 'agent_affinity' field that is a JSON array (use [] if none).\n"
        "     6. An 'exposed_interfaces' field that is a JSON array (use [] if none).\n"
        "     7. All 'depends_on' entries must reference existing component IDs.\n"
        "   This ensures the registry and the documentation tree stay in sync.\n"
        "   Existing components (no diff) are not checked -- legacy state is accepted.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
