"""
MODULE: commit_guardian.check_paths_integrity
GOAL: Pre-commit hook that validates leafcutter/config/paths.json
    whenever it is staged. Ensures all declared paths exist on disk (unless
    marked optional) and that no two keys map to the same resolved path.
BUSINESS CONTEXT: paths.json is the single source of truth for every
    architectural folder location. A typo in paths.json can silently
    mis-route agents or block future commits. This hook catches errors at
    commit time before they reach CI. The [NO-ARCH-UPDATE] bypass token
    allows the hook to be skipped for vendored changes, renames, or
    refactors that deliberately introduce a not-yet-created folder.
ARCHITECTURE: No model calls. Pure filesystem + JSON parsing. Entry point:
    main() called by run_hook.py. Reads paths.json, flattens to leaf string
    entries, reads optional sentinels, checks existence, detects duplicates.
    Respects COMMIT_MSG_FILE env var for bypass-token detection (pre-commit
    framework passes this automatically). Exit 0 = pass, exit 1 = fail.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BYPASS_TOKEN = "[NO-ARCH-UPDATE]"
_PATHS_JSON_REL = "leafcutter/config/paths.json"


def _git_root() -> Path:
    """Return the git working-tree root.

    Returns:
        Absolute path to the git project root. Falls back to cwd on error.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def _staged_files() -> list[str]:
    """Return a list of staged file paths.

    Returns:
        List of relative file path strings that are staged.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, check=True,
        )
        return [f for f in result.stdout.strip().split("\n") if f]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def _get_commit_message() -> str:
    """Return the commit message being authored, or empty string.

    Returns:
        Commit message text, or empty string when not available.
    """
    msg_file = os.environ.get("COMMIT_MSG_FILE") or (
        sys.argv[1] if len(sys.argv) > 1 else ""
    )
    if msg_file and Path(msg_file).exists():
        return Path(msg_file).read_text(encoding="utf-8", errors="replace")
    return ""


def _flat_entries(nested: dict, prefix: str = "") -> dict[str, str]:
    """Flatten a nested dict of path declarations to dotted string entries.

    Skips boolean values (optional sentinels) and other non-string types.
    Returns only leaf string entries.

    Args:
        nested: Nested dict from paths.json.
        prefix: Accumulated dotted-key prefix during recursion.

    Returns:
        Flat dict mapping dotted keys to path strings.
    """
    result: dict[str, str] = {}
    for k, v in nested.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_flat_entries(v, full_key))
        elif isinstance(v, str):
            result[full_key] = v
    return result


def _optional_keys(nested: dict, prefix: str = "") -> set[str]:
    """Collect the base keys that have an ``_optional: true`` sibling sentinel.

    The sentinel pattern is: ``"foo": "path/", "foo_optional": true``.
    This function returns the set of base key names (e.g. ``"foo"``) that
    should be skipped during existence checks.

    Args:
        nested: Nested dict from paths.json.
        prefix: Accumulated dotted-key prefix during recursion.

    Returns:
        Set of full dotted keys that are marked optional.
    """
    result: set[str] = set()
    for k, v in nested.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            result.update(_optional_keys(v, full_key))
        elif isinstance(v, bool) and v is True and k.endswith("_optional"):
            base_key_local = k[: -len("_optional")]
            base_full = f"{prefix}.{base_key_local}" if prefix else base_key_local
            result.add(base_full)
    return result


def main() -> None:
    """Run the paths.json integrity check.

    Exits 0 on pass, exits 1 on failure, printing a summary to stdout.
    """
    staged = _staged_files()
    if _PATHS_JSON_REL not in staged:
        print(f"check-paths-integrity: {_PATHS_JSON_REL} not staged; skipping.")
        sys.exit(0)

    commit_msg = _get_commit_message()
    if BYPASS_TOKEN in commit_msg:
        print(f"check-paths-integrity: bypass token '{BYPASS_TOKEN}' found; skipping.")
        sys.exit(0)

    project_root = _git_root()
    paths_json = project_root / _PATHS_JSON_REL

    if not paths_json.exists():
        print(f"check-paths-integrity: {_PATHS_JSON_REL} not found on disk.")
        sys.exit(1)

    try:
        data = json.loads(paths_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"check-paths-integrity: Failed to parse paths.json: {exc}")
        sys.exit(1)

    nested = data.get("paths", {})
    if not nested:
        print("check-paths-integrity: paths.json has no 'paths' key; nothing to check.")
        sys.exit(0)

    flat = _flat_entries(nested)
    optional = _optional_keys(nested)

    errors: list[str] = []

    # Check 1: existence (skip optional keys)
    for key, rel_path in flat.items():
        if key in optional:
            continue
        resolved = project_root / rel_path
        if rel_path.endswith("/"):
            if not resolved.is_dir():
                errors.append(
                    f"  Missing directory: '{rel_path}' (key: {key}). "
                    f"Add '{key}_optional: true' in paths.json if it may not exist in all clones."
                )
        else:
            if not resolved.is_file():
                errors.append(
                    f"  Missing file: '{rel_path}' (key: {key}). "
                    f"Add '{key}_optional: true' if the file may not exist in all clones."
                )

    # Check 2: no duplicate paths (case-insensitive on Windows)
    resolved_map: dict[str, list[str]] = {}
    for key, rel_path in flat.items():
        norm = rel_path.lower() if os.name == "nt" else rel_path
        resolved_map.setdefault(norm, []).append(key)

    for norm_path, keys in resolved_map.items():
        if len(keys) > 1:
            errors.append(
                f"  Duplicate path: '{norm_path}' declared under keys: {', '.join(keys)}"
            )

    if errors:
        print("check-paths-integrity: FAILED")
        print("\n".join(errors))
        print(f"\nFIX: Correct paths.json or use '{BYPASS_TOKEN}' in commit message to skip.")
        sys.exit(1)

    print(
        f"check-paths-integrity: OK — {len(flat)} paths checked "
        f"({len(optional)} optional skipped)."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-14 11:00 [EPIC-ArchitectureDocsEnforcement/ticket 10 — D10.5]: (#EPIC-LeafcutterMVP/01)
#   Created as the paths.json integrity commit-guardian hook. Checks:
#   (1) all non-optional paths exist, (2) no two keys map to the same path.
#   Bypass token [NO-ARCH-UPDATE] skips the hook. Optional sentinel pattern:
#   foo_optional: true skips existence check for the `foo` key.
# ====================================================================
