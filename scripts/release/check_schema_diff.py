"""
MODULE: check_schema_diff
GOAL: CI gate that detects backwards-incompatible changes to
    skills_config.schema.json and fails when no corresponding breaking=true
    changelog entry exists.
BUSINESS CONTEXT: Closes the "silent omission" gap — a developer who introduces
    a breaking schema change but forgets to set breaking=true will be caught at
    CI time, before the change can produce an incorrect SemVer bump.
ARCHITECTURE: Single-module CLI (stdlib-only). Compares the current schema
    against the version at the previous v* tag via git show. Checks three
    categories: removed keys, newly-required keys, and type narrowings. If any
    are found and no breaking=true changelog entry exists, exits non-zero.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Self-location
# ---------------------------------------------------------------------------


def _resolve_repo_root() -> Path:
    """Compute the repository root from this script's own location."""
    resolved_self = Path(__file__).resolve()
    p2 = resolved_self.parents[2]
    if (p2 / ".git").is_dir():
        return p2
    return resolved_self.parents[3]


# ---------------------------------------------------------------------------
# Schema loading
# ---------------------------------------------------------------------------


def _load_current_schema(schema_path: Path) -> dict:
    """Load the current schema from disk."""
    with schema_path.open(encoding="utf-8") as fh:
        return json.load(fh)


def _load_previous_schema(tag: str, schema_rel_path: str, repo_root: Path) -> Optional[dict]:
    """Load the schema at a previous tag via git show."""
    try:
        result = subprocess.run(
            ["git", "show", f"{tag}:{schema_rel_path}"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
        return json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return None


# ---------------------------------------------------------------------------
# Schema comparison
# ---------------------------------------------------------------------------


def _extract_properties(schema: dict) -> dict[str, dict]:
    """Extract the properties dict from a JSON Schema, handling nested structure."""
    props = {}
    if "properties" in schema:
        for key, value in schema["properties"].items():
            props[key] = value
            if value.get("type") == "object" and "properties" in value:
                for sub_key, sub_value in value["properties"].items():
                    props[f"{key}.{sub_key}"] = sub_value
    return props


def _get_required_keys(schema: dict) -> set[str]:
    """Get all required keys from a schema (including nested)."""
    required = set(schema.get("required", []))
    for key, value in schema.get("properties", {}).items():
        if isinstance(value, dict) and value.get("type") == "object":
            for sub_key in value.get("required", []):
                required.add(f"{key}.{sub_key}")
    return required


def _normalize_type(type_spec) -> set[str]:
    """Normalize a type spec to a set of type strings."""
    if isinstance(type_spec, str):
        return {type_spec}
    if isinstance(type_spec, list):
        return set(type_spec)
    return set()


def find_breaking_changes(prev_schema: dict, curr_schema: dict) -> list[str]:
    """Compare two schemas and return a list of breaking change descriptions.

    Checks for:
    1. Removed keys (present in prev, absent in curr)
    2. Newly-required keys (optional in prev, required in curr)
    3. Type narrowings (type set shrunk)
    """
    changes: list[str] = []

    prev_props = _extract_properties(prev_schema)
    curr_props = _extract_properties(curr_schema)

    prev_required = _get_required_keys(prev_schema)
    curr_required = _get_required_keys(curr_schema)

    # 1. Removed keys
    for key in prev_props:
        if key not in curr_props:
            changes.append(f"Removed key: '{key}'")

    # 2. Newly-required keys
    for key in curr_required:
        if key not in prev_required and key in prev_props:
            changes.append(f"Newly required key: '{key}'")

    # 3. Type narrowings
    for key in prev_props:
        if key not in curr_props:
            continue
        prev_type = _normalize_type(prev_props[key].get("type"))
        curr_type = _normalize_type(curr_props[key].get("type"))
        if prev_type and curr_type and curr_type < prev_type:
            removed_types = prev_type - curr_type
            changes.append(f"Type narrowing on '{key}': removed {sorted(removed_types)}")

    return changes


# ---------------------------------------------------------------------------
# Changelog scanning
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _has_breaking_entry_since(tag: str, changelogs_dir: Path, repo_root: Path) -> bool:
    """Check if any changelog entry committed after tag has breaking=true."""
    if not changelogs_dir.is_dir():
        return False

    try:
        result = subprocess.run(
            ["git", "log", f"{tag}..HEAD", "--name-only", "--pretty=format:", "--", str(changelogs_dir)],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
        files = {line.strip() for line in result.stdout.strip().split("\n") if line.strip()}
    except subprocess.CalledProcessError:
        return False

    for f in files:
        p = repo_root / f
        if not p.exists() or p.suffix != ".md":
            continue
        content = p.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(content)
        if not match:
            continue
        for line in match.group(1).split("\n"):
            line = line.strip()
            if line.startswith("breaking:") and "true" in line.lower():
                return True

    return False


# ---------------------------------------------------------------------------
# Tag resolution
# ---------------------------------------------------------------------------


def _find_previous_tag(repo_root: Path) -> Optional[str]:
    """Find the most recent v* tag."""
    try:
        result = subprocess.run(
            ["git", "tag", "--sort=-version:refname", "--list", "v*"],
            capture_output=True,
            text=True,
            cwd=repo_root,
            check=True,
        )
        tags = [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]
        return tags[0] if tags else None
    except subprocess.CalledProcessError:
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for check_schema_diff."""
    parser = argparse.ArgumentParser(
        prog="check_schema_diff",
        description="CI gate: fail on backwards-incompatible schema changes without a breaking entry.",
    )
    parser.add_argument(
        "--previous-tag",
        default=None,
        help="Tag to compare against (default: auto-detect most recent v* tag).",
    )
    parser.add_argument(
        "--schema-path",
        default=None,
        help="Path to skills_config.schema.json (default: config/skills_config.schema.json).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Override repo root detection (for testing).",
    )
    parser.add_argument(
        "--changelogs-dir",
        type=Path,
        default=None,
        help="Override changelogs directory (for testing).",
    )
    args = parser.parse_args(argv)

    repo_root = args.repo_root or _resolve_repo_root()
    schema_path = Path(args.schema_path) if args.schema_path else repo_root / "config" / "skills_config.schema.json"
    changelogs_dir = args.changelogs_dir or repo_root / "changelogs"

    tag = args.previous_tag or _find_previous_tag(repo_root)
    if not tag:
        print("No previous v* tag found — nothing to compare against. Passing.")
        return 0

    if not schema_path.exists():
        print(f"Schema file not found: {schema_path}. Passing.")
        return 0

    # Compute relative path for git show
    try:
        schema_rel = str(schema_path.resolve().relative_to(repo_root.resolve()))
    except ValueError:
        schema_rel = str(schema_path)

    prev_schema = _load_previous_schema(tag, schema_rel, repo_root)
    if prev_schema is None:
        print(f"Schema not found at tag {tag} — first introduction. Passing.")
        return 0

    curr_schema = _load_current_schema(schema_path)
    breaking_changes = find_breaking_changes(prev_schema, curr_schema)

    if not breaking_changes:
        print("No backwards-incompatible schema changes detected. Passing.")
        return 0

    # Breaking changes found — check for a corresponding breaking entry
    if _has_breaking_entry_since(tag, changelogs_dir, repo_root):
        print("Backwards-incompatible schema changes detected, but a breaking=true")
        print("changelog entry exists. Passing.")
        return 0

    # FAIL: breaking changes without a breaking entry
    print("ERROR: Backwards-incompatible schema changes detected without a", file=sys.stderr)
    print("breaking=true changelog entry.", file=sys.stderr)
    print("", file=sys.stderr)
    print("Changes found:", file=sys.stderr)
    for change in breaking_changes:
        print(f"  - {change}", file=sys.stderr)
    print("", file=sys.stderr)
    print("To fix: add a changelog entry with breaking=true and migration_steps", file=sys.stderr)
    print("describing what consumers need to do to handle this change.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-26 [python-coder/EPIC-LeafcutterVersioning/05]: (#EPIC-LeafcutterVersioning/05)
#   Created module. Implements the schema-diff CI gate that compares
#   skills_config.schema.json against the previous v* tag. Checks three
#   breaking-change categories: removed keys, newly-required keys, type
#   narrowings. If breaking changes are found and no breaking=true entry
#   exists, exits 1. Stdlib-only. Nested property support via dot-notation.
# ====================================================================
