#!/usr/bin/env python3
"""
validate_ac.py — Package-surface AC implementation-spec validator.

Usage:
    python3 scripts/ac_store/validate_ac.py <ac_yaml_path> [<ac_yaml_path> ...]

Validates package-surface ACs for machine-checkable implementation specs.

An AC is package-surface when EITHER of the following holds:

  1. DECLARED (ACS-100i-6, the canonical trigger). The record carries
     ``package_surface: true``. Nothing else is consulted — not the assigned
     agent, not the ``component`` scalar, not the ``components`` list. A package
     surface can be registered from any namespace, so the obligation follows the
     declaration wherever it goes.

  2. LEGACY PROXY (deprecated, retained for the pre-declaration corpus).
     ``assigned_agent == "python-coder"`` AND the ``component`` scalar or any
     ``components`` entry is in PACKAGE_SURFACE_COMPONENTS
     (``build_pipeline``, ``build-pipeline``, ``build-orchestration``).

``package_surface: false`` is an explicit denial and switches the obligation OFF
outright, including for records the legacy proxy would otherwise have matched.

The legacy proxy is the trigger KI-ACS-005 measured as both over- and
under-matching, and the *schema* (config/ac_store_schema.json) no longer uses it
at all — only the declaration fires there, which is what the commit-time
``check-ac-schema`` hook and the required ``AC store valid`` CI job read. It
survives here, in this standalone authoring-time CLI, purely so the pre-existing
BO-2000d regression suite keeps its meaning while the corpus is backfilled with
explicit declarations. Do not reintroduce it into the schema.

For such ACs, it_requirements MUST be a structured object with:
  - config_schema_fragment  (any value — the JSON Schema fragment for the key)
  - reference_file_path     (string — must resolve to an existing file in the repo)
  - n_location_rule         (string — how many locations must be updated)
  - required_skills         (non-empty list of strings)
  - post_write_commands     (list of strings, may be empty)

Exits non-zero if any file fails validation; exits zero if all pass.

AC-3: validator rejects a thin/fictional package-surface spec (BO-2000d-2).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

#: Component names that qualify an AC as "package-surface".
#: Includes both kebab (``build-pipeline``) and underscore (``build_pipeline``)
#: spellings so scalar ``component:`` fields and ``components:`` graph-id lists
#: are both matched regardless of normalisation form.
PACKAGE_SURFACE_COMPONENTS: frozenset[str] = frozenset(
    {"build_pipeline", "build-pipeline", "build-orchestration"}
)

#: The record-level field that DECLARES a package surface (ACS-100i-6). Its
#: presence with the value ``True`` is the canonical trigger; ``False`` is an
#: explicit denial that switches the obligation off.
DECLARATION_FIELD: str = "package_surface"

#: Required sub-keys in it_requirements for package-surface ACs.
REQUIRED_IMPL_FIELDS: tuple[str, ...] = (
    "config_schema_fragment",
    "reference_file_path",
    "n_location_rule",
    "required_skills",
    "post_write_commands",
)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    """Result of validate_package_surface_spec.

    Attributes:
        ok: True when the AC passed all checks; False otherwise.
        errors: Human-readable error strings (empty when ok=True).
    """

    ok: bool
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def declares_package_surface(ac_data: dict[str, Any]) -> bool | None:
    """Return the record's explicit package-surface declaration, if it made one.

    Args:
        ac_data: The parsed AC YAML as a Python dict.

    Returns:
        ``True`` when the record carries ``package_surface: true``, ``False``
        when it carries ``package_surface: false``, and ``None`` when it made no
        declaration at all. The three cases are deliberately distinct: an
        omission is an oversight, a ``false`` is a statement (ACS-100i-8-i).
    """
    value = ac_data.get(DECLARATION_FIELD)
    if value is None:
        return None
    return bool(value)


def is_package_surface_ac(ac_data: dict[str, Any]) -> bool:
    """Return True if this AC is classified as a package-surface AC.

    An AC qualifies when EITHER:
      - it DECLARES the surface with ``package_surface: true`` (ACS-100i-6 — the
        canonical trigger, which consults nothing else); or
      - the deprecated legacy proxy matches: ``assigned_agent == "python-coder"``
        AND the scalar ``component`` is in PACKAGE_SURFACE_COMPONENTS, OR at
        least one entry in the ``components`` list (graph ids) is.

    An explicit ``package_surface: false`` denies the surface and short-circuits
    to False even when the legacy proxy would have matched.

    Both the kebab form (``build-pipeline``) and the underscore form
    (``build_pipeline``) are accepted by the legacy proxy for robustness against
    normalisation divergence between the scalar and list representations.

    Args:
        ac_data: The parsed AC YAML as a Python dict.

    Returns:
        True when the AC is subject to the structured implementation-spec
        obligation; False otherwise.
    """
    declaration = declares_package_surface(ac_data)
    if declaration is not None:
        return declaration
    if ac_data.get("assigned_agent") != "python-coder":
        return False
    # Fast path: scalar component field (accepts both kebab and underscore forms)
    if ac_data.get("component", "") in PACKAGE_SURFACE_COMPONENTS:
        return True
    # Fallback: components list (graph ids, e.g. ["build_pipeline"])
    components_list = ac_data.get("components", [])
    if isinstance(components_list, list):
        return any(c in PACKAGE_SURFACE_COMPONENTS for c in components_list)
    return False


def validate_package_surface_spec(
    ac_data: dict[str, Any],
    *,
    repo_root: Path | None = None,
) -> ValidationResult:
    """Validate that a package-surface AC has a machine-checkable implementation spec.

    Classification is delegated to :func:`is_package_surface_ac`, so the record's
    own ``package_surface`` declaration is the primary trigger (ACS-100i-6).
    For non-package-surface ACs, returns ValidationResult(ok=True) immediately —
    the stricter impl-field rules do not apply.

    For package-surface ACs, checks:
      1. it_requirements is a dict (not a string/array/null).
      2. All five required keys are present in it_requirements.
      3. reference_file_path resolves to an existing file under repo_root.
      4. required_skills is a non-empty list.

    Args:
        ac_data: The parsed AC YAML as a Python dict.
        repo_root: The repository root directory. When None, defaults to the
            directory three levels above this module file (i.e. the worktree root).

    Returns:
        A ValidationResult with ok=True if all checks pass, or ok=False
        with a populated errors list describing each failure.
    """
    errors: list[str] = []

    # Fast path: not a package-surface AC — no impl-spec validation needed.
    if not is_package_surface_ac(ac_data):
        return ValidationResult(ok=True)

    ac_id = ac_data.get("id", "<unknown>")

    it_req = ac_data.get("it_requirements")

    # --- Check 1: it_requirements must be a dict ---
    if it_req is None:
        errors.append(
            f"[{ac_id}] it_requirements is absent. A record that registers a package "
            f"surface must carry a structured it_requirements object with keys: "
            f"{', '.join(REQUIRED_IMPL_FIELDS)}."
        )
        return ValidationResult(ok=False, errors=errors)

    if not isinstance(it_req, dict):
        errors.append(
            f"[{ac_id}] it_requirements must be an object (dict) for package-surface ACs, "
            f"got {type(it_req).__name__!r}. Provide a structured spec with: "
            f"{', '.join(REQUIRED_IMPL_FIELDS)}."
        )
        return ValidationResult(ok=False, errors=errors)

    # --- Check 2: all required keys must be present ---
    missing_keys = [k for k in REQUIRED_IMPL_FIELDS if k not in it_req]
    if missing_keys:
        for key in missing_keys:
            errors.append(
                f"[{ac_id}] it_requirements is missing required key '{key}'. "
                f"Package-surface ACs must supply all of: {', '.join(REQUIRED_IMPL_FIELDS)}."
            )

    # --- Check 3: reference_file_path must resolve to an existing file ---
    ref_path_raw = it_req.get("reference_file_path")
    if ref_path_raw is not None:
        if not isinstance(ref_path_raw, str) or not ref_path_raw.strip():
            errors.append(
                f"[{ac_id}] reference_file_path must be a non-empty string, "
                f"got {type(ref_path_raw).__name__!r}."
            )
        else:
            root = repo_root if repo_root is not None else _default_repo_root()
            resolved = root / ref_path_raw
            if not resolved.exists():
                errors.append(
                    f"[{ac_id}] reference_file_path '{ref_path_raw}' does not exist "
                    f"at resolved path '{resolved}'. Verify the path is correct relative "
                    f"to the repository root '{root}'."
                )

    # --- Check 4: required_skills must be a non-empty list ---
    skills = it_req.get("required_skills")
    if skills is not None and "required_skills" not in missing_keys:
        if not isinstance(skills, list) or len(skills) == 0:
            errors.append(
                f"[{ac_id}] required_skills must be a non-empty list, "
                f"got {type(skills).__name__!r} with value {skills!r}."
            )

    return ValidationResult(ok=len(errors) == 0, errors=errors)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _default_repo_root() -> Path:
    """Return the default repo root (three levels above this module file)."""
    return Path(__file__).resolve().parent.parent.parent


def _validate_file(
    path: Path,
    repo_root: Path | None = None,
) -> list[str]:
    """Parse and validate a single AC YAML file.

    Returns:
        List of error strings. Empty list means the file is valid.
    """
    try:
        content = path.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        return [f"{path}: YAML parse error — {exc}"]
    except OSError as exc:
        return [f"{path}: Cannot read file — {exc}"]

    if not isinstance(data, dict):
        return [
            f"{path}: Top-level YAML must be a mapping (dict), "
            f"got {type(data).__name__!r}"
        ]

    # Only process AC files (must have an 'id' field).
    if "id" not in data:
        return []

    result = validate_package_surface_spec(data, repo_root=repo_root)
    if not result.ok:
        return [f"{path}: {e}" for e in result.errors]
    return []


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Validate AC YAML files for package-surface spec completeness.

    Returns:
        0 on success, 1 on validation errors, 2 on usage error.
    """
    args = argv if argv is not None else sys.argv[1:]

    if not args:
        print(
            "Usage: validate_ac.py <ac_yaml_path> [<ac_yaml_path> ...]\n"
            "\n"
            "Validates package-surface AC YAML files for machine-checkable "
            "implementation specs.\n"
            "\n"
            "Package-surface ACs — those declaring `package_surface: true`, plus "
            "the deprecated legacy proxy (assigned_agent=python-coder with "
            "component in build_pipeline/build-pipeline/build-orchestration) — "
            "must have it_requirements as a structured object with:\n"
            f"  {', '.join(REQUIRED_IMPL_FIELDS)}\n"
            "\n"
            "Non-package-surface ACs are skipped (no impl-spec requirement).\n"
            "Exits non-zero if any validation error is found.",
            file=sys.stderr,
        )
        return 2

    all_errors: list[str] = []
    files_checked = 0

    for arg in args:
        path = Path(arg)
        if not path.exists():
            all_errors.append(f"{path}: File not found.")
            continue
        if path.suffix not in {".yaml", ".yml"}:
            continue  # Skip non-YAML files silently
        errors = _validate_file(path)
        all_errors.extend(errors)
        files_checked += 1

    if all_errors:
        print("Package-surface AC spec validation FAILED:", file=sys.stderr)
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
