"""
MODULE: check_ac_schema
GOAL: Pre-commit hook validating staged AC YAML files against the JSON Schema,
    enforcing pattern_bindings completeness and implements_pattern field-preservation.
BUSINESS CONTEXT: Malformed AC files are rejected at commit time. The
    pattern_bindings completeness and field-preservation checks enforce ACS-500f.
ARCHITECTURE: Phase 1 validates all AC YAML files against config/ac_store_schema.json;
    cross-file checks delegated to _ac_schema_validators.py (file-size limit).
    Phase 2 compares HEAD vs staged for each modified AC and blocks if
    implements_pattern was present in HEAD but absent in staged. Fail-open.

Exit codes:
    0 - All staged AC YAML files pass validation
    1 - One or more validation errors detected

DOC_LINKS:
  - docs/reference/ac-schema.md

DECISION HISTORY:
  - 2026-06-17 [python-coder/ACS-500f-1]: Created. Phase 1: schema +
    pattern_bindings completeness (cross-file checks in _ac_schema_validators.py).
    Phase 2: implements_pattern field-preservation via HEAD vs staged diff.
  - 2026-06-18 [python-coder/ACS-500f-1-i]: Verified fail-open behavior: the
    __main__ exception handler (added in ACS-500f-1) catches unexpected errors
    and exits 0 with a stderr diagnostic. Unit tests added for all fail-open
    and no-staged-relevant-files paths.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

from _ac_schema_validators import (  # noqa: E402
    load_yaml, load_yaml_from_string, load_yaml_manual,
    validate_criteria_not_pattern_duplicate, validate_deprecated_pattern_reference,
    validate_manually, validate_pattern_bindings_completeness, validate_with_jsonschema,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AC_GLOB_PATTERN = "docs/acceptance-criteria"
SCHEMA_PATH = "config/ac_store_schema.json"
_HOOK_PREFIX = "[check-ac-schema]"
_AC_STORE_DIR = "docs/acceptance-criteria"

# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------

def _find_project_root() -> Path | None:
    """Find the project root by .git or CLAUDE.md presence.

    Returns:
        Absolute Path of the project root, or None if not found.
    """
    env_root = os.environ.get("HOOK_ROOT")
    if env_root:
        return Path(env_root)

    for ancestor in [Path.cwd(), *Path.cwd().parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            return ancestor

    return None


# ---------------------------------------------------------------------------
# implements_pattern field-preservation check (ACS-500f-1)
# ---------------------------------------------------------------------------

def _load_head_yaml(rel_path: str, project_root: Path | None) -> dict | None:
    """Load HEAD version of an AC YAML file from git; None on any error.

    Args:
        rel_path: Repo-relative path.
        project_root: Absolute repo root path, or None.

    Returns:
        Parsed dict or None.
    """
    if os.environ.get("HOOK_NO_GIT"):
        return None

    git_cmd = ["git"]
    if project_root:
        git_cmd = ["git", "-C", str(project_root)]

    try:
        result = subprocess.run(
            [*git_cmd, "show", f"HEAD:{rel_path}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: git show failed for {rel_path}: {exc}",
            file=sys.stderr,
        )
        return None

    if result.returncode != 0:
        return None

    return load_yaml_from_string(result.stdout, source_label=f"HEAD:{rel_path}")


def _get_modified_ac_paths() -> list[str]:
    """Return staged modified (not added) .yaml paths under docs/acceptance-criteria/.

    Returns:
        List of repo-relative path strings.
    """
    if os.environ.get("HOOK_NO_GIT"):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=M"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: could not run git diff: {exc}",
            file=sys.stderr,
        )
        return []

    if result.returncode != 0:
        return []

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
        and _AC_STORE_DIR in line
        and line.strip().endswith(".yaml")
    ]


def _check_implements_pattern_preserved(
    staged_abs_path: str,
    rel_path: str,
    project_root: Path | None,
) -> list[str]:
    """Block if implements_pattern was present in HEAD but absent in staged.

    Args:
        staged_abs_path: Absolute path to the staged file on disk.
        rel_path: Repo-relative path for git show.
        project_root: Absolute repo root path, or None.

    Returns:
        Violation strings; empty when the field was not dropped.
    """
    if os.environ.get("HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED"):
        return [
            f"{rel_path}: implements_pattern was dropped — this field must not be "
            f"removed from an AC that previously declared it"
        ]

    try:
        staged_content = Path(staged_abs_path).read_text(encoding="utf-8")
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read staged file {staged_abs_path}: {exc}",
            file=sys.stderr,
        )
        return []

    staged_data = load_yaml_from_string(staged_content, source_label=staged_abs_path)
    if staged_data is None:
        return []

    head_data = _load_head_yaml(rel_path, project_root)
    if head_data is None:
        return []

    head_val = head_data.get("implements_pattern")
    staged_val = staged_data.get("implements_pattern")
    head_has_it = bool(head_val and str(head_val).strip())
    staged_has_it = bool(staged_val and str(staged_val).strip())

    if head_has_it and not staged_has_it:
        return [
            f"{rel_path}: implements_pattern was dropped — this field must not be "
            f"removed from an AC that previously declared it "
            f"(was: '{head_val}')"
        ]

    return []


# ---------------------------------------------------------------------------
# File discovery and schema loading
# ---------------------------------------------------------------------------

def _find_ac_files(root: Path) -> list[Path]:
    """Discover all .yaml files under docs/acceptance-criteria/.

    Args:
        root: Repository root directory.

    Returns:
        Sorted list of Paths.
    """
    ac_dir = root / AC_GLOB_PATTERN
    if not ac_dir.is_dir():
        return []
    return sorted(ac_dir.rglob("*.yaml"))


def _load_schema(root: Path) -> dict[str, Any] | None:
    """Load config/ac_store_schema.json; None if absent.

    Args:
        root: Repository root directory.

    Returns:
        Parsed schema dict, or None.
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
# Per-file validation
# ---------------------------------------------------------------------------

def _validate_file(
    path: Path,
    schema: dict[str, Any] | None,
    all_ac_data: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Validate a single AC YAML file and return error messages.

    Args:
        path: YAML file to validate.
        schema: Pre-loaded JSON Schema dict, or None.
        all_ac_data: Optional AC id to parsed content mapping; enables
            cross-file checks when provided.

    Returns:
        Error message strings; empty when valid.
    """
    errors: list[str] = []

    yaml_available = True
    data: Any = None
    try:
        data = load_yaml(path)
    except ImportError:
        yaml_available = False
    except (OSError, ValueError) as exc:
        errors.append(f"YAML parse error: {exc}")
        return errors

    if not yaml_available:
        try:
            data = load_yaml_manual(path)
        except (OSError, ValueError) as exc:
            errors.append(f"manual YAML parse error: {exc}")
            return errors

    if data is None:
        errors.append("file is empty or parsed to null")
        return errors

    if not isinstance(data, dict):
        errors.append(f"expected YAML mapping at top level, got {type(data).__name__}")
        return errors

    if schema is not None and yaml_available:
        try:
            errors.extend(validate_with_jsonschema(data, schema))
        except ImportError:
            pass

    if not errors:
        errors.extend(validate_manually(data))

    if all_ac_data is not None:
        errors.extend(validate_pattern_bindings_completeness(path, data, all_ac_data))
        errors.extend(validate_deprecated_pattern_reference(path, data, all_ac_data))
        errors.extend(validate_criteria_not_pattern_duplicate(path, data, all_ac_data))

    return errors


def _build_ac_index(files: list[Path]) -> dict[str, dict[str, Any]]:
    """Build an AC id to parsed content mapping from a file list.

    Args:
        files: AC YAML file paths to load.

    Returns:
        Mapping of AC id string to parsed YAML content dict.
    """
    index: dict[str, dict[str, Any]] = {}
    for path in files:
        try:
            data = load_yaml(path)
        except (ImportError, OSError, ValueError):  # noqa: BLE001
            try:
                data = load_yaml_manual(path)
            except (OSError, ValueError):  # noqa: BLE001
                continue
        if isinstance(data, dict) and data.get("id"):
            index[str(data["id"])] = data
    return index


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    """Run AC schema validation and field-preservation checks.

    Returns:
        0 on pass, 1 on any error.
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
        return 0
    all_ac_data = _build_ac_index(files)
    failed: list[tuple[Path, list[str]]] = []
    for path in files:
        errs = _validate_file(path, schema, all_ac_data)
        if errs:
            failed.append((path, errs))
    # Phase 2: implements_pattern field-preservation
    project_root = _find_project_root()
    modified_paths = _get_modified_ac_paths()
    test_files_env = os.environ.get("HOOK_TEST_FILES_MODIFIED")
    if test_files_env:
        extra = test_files_env.replace(os.pathsep, "\n").splitlines()
        modified_paths = [p.strip() for p in extra if p.strip() and p.strip().endswith(".yaml")]
    for rel_path in modified_paths:
        abs_path = rel_path
        if not Path(rel_path).is_absolute() and project_root:
            abs_path = str(project_root / rel_path)
        p_errs = _check_implements_pattern_preserved(abs_path, rel_path, project_root)
        if p_errs:
            failed.append((Path(abs_path), p_errs))
    if not failed:
        return 0
    print(f"{_HOOK_PREFIX}: {len(failed)} file(s) failed validation:", file=sys.stderr)
    for path, file_errors in failed:
        try:
            rel = path.relative_to(root) if path.is_absolute() else path
        except ValueError:
            rel = path
        for err in file_errors:
            print(f"  {rel}: {err}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"{_HOOK_PREFIX} unexpected error (fail-open): {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
