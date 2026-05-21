"""
MODULE: commit_guardian.check_architecture_scaffolds
GOAL: Pre-commit hook that validates scaffold files staged under
    leafcutter/templates/docs/architecture/. Ensures every scaffold
    has well-formed YAML frontmatter, that cross-links reference files that
    exist within the scaffold tree, and that {paths.X.Y} placeholders reference
    keys that exist in paths.json.
BUSINESS CONTEXT: Architecture scaffold files are the convention contract that
    every new project adopting leafcutter receives. A malformed scaffold
    (missing frontmatter, broken cross-link, unknown paths.json key) would be
    silently copied into new projects and cause downstream failures. This hook
    catches such errors at commit time. The [NO-ARCH-UPDATE] bypass token allows
    the hook to be skipped during work-in-progress scaffold authoring.
ARCHITECTURE: No model calls. Pure filesystem + YAML parsing + JSON key lookup.
    Entry point: main() called by run_hook.py. Three sequential checks:
    (1) frontmatter well-formedness, (2) cross-link existence, (3) paths.json
    key validity. Bypass via COMMIT_MSG_FILE env var or sys.argv[1] message file.
    Exit 0 = pass, exit 1 = fail.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml  # type: ignore[import]
    _YAML_AVAILABLE = True
except ImportError:
    _YAML_AVAILABLE = False

BYPASS_TOKEN = "[NO-ARCH-UPDATE]"
_SCAFFOLD_DIR_REL = "leafcutter/templates/docs/architecture"
_PATHS_JSON_REL = "leafcutter/config/paths.json"
_PATHS_PLACEHOLDER_RE = re.compile(r"\{paths\.([a-zA-Z0-9_.]+)\}")


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
    """Return a list of staged file paths relative to the git root.

    Returns:
        List of relative file path strings that are currently staged.
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


def _parse_frontmatter(content: str) -> dict | None:
    """Parse YAML frontmatter from a markdown file's content.

    Frontmatter is the YAML block between the first and second ``---``
    delimiters at the start of the file. Returns None when frontmatter is
    absent or unparseable.

    Args:
        content: Full text content of the file.

    Returns:
        Parsed frontmatter dict, or None on failure.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = i
            break
    if end is None:
        return None
    fm_text = "\n".join(lines[1:end])
    if _YAML_AVAILABLE:
        try:
            return yaml.safe_load(fm_text) or {}
        except yaml.YAMLError:
            return None
    # Minimal fallback: parse simple key: value lines only.
    result: dict = {}
    for line in fm_text.splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            result[k.strip()] = v.strip()
    return result


def _flat_paths_keys(paths_json: Path) -> set[str]:
    """Extract all dotted path keys from paths.json.

    Args:
        paths_json: Absolute path to paths.json.

    Returns:
        Set of dotted key strings (e.g. ``{"docs.root", "docs.architecture", …}``).
    """
    try:
        data = json.loads(paths_json.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()
    nested = data.get("paths", {})

    def _flatten(d: dict, prefix: str = "") -> set[str]:
        """Recursively flatten nested dict to dotted keys.

        Args:
            d: Nested dict of path declarations.
            prefix: Accumulated dotted-key prefix during recursion.

        Returns:
            Set of dotted key strings for all non-boolean leaf values.
        """
        keys: set[str] = set()
        for k, v in d.items():
            full = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                keys.update(_flatten(v, full))
            elif not isinstance(v, bool):
                keys.add(full)
        return keys

    return _flatten(nested)


def _collect_cross_links(fm: dict) -> list[str]:
    """Collect all cross-link values from a parsed frontmatter dict.

    Reads ``parent``, ``children``, ``affects_diagrams``, and ``related_adrs``
    fields. Skips null values and empty lists.

    Args:
        fm: Parsed frontmatter dict from _parse_frontmatter.

    Returns:
        List of cross-link path strings to verify.
    """
    links: list[str] = []
    for field in ("parent", "children", "affects_diagrams", "related_adrs"):
        val = fm.get(field)
        if val is None or val == [] or val is False:
            continue
        if isinstance(val, str):
            links.append(val)
        elif isinstance(val, list):
            links.extend(v for v in val if isinstance(v, str))
    return links


def _check_one_scaffold(
    rel_path: str,
    project_root: Path,
    scaffold_dir: Path,
    known_path_keys: set[str],
) -> list[str]:
    """Run the three integrity checks on a single scaffold file.

    Args:
        rel_path: Repository-relative path of the staged scaffold file.
        project_root: Absolute path to the git project root.
        scaffold_dir: Absolute path to the scaffold template directory.
        known_path_keys: Set of dotted path keys from paths.json (empty if unavailable).

    Returns:
        List of error strings found in this file (empty list on pass).
    """
    abs_path = project_root / rel_path
    if not abs_path.exists():
        return []
    content = abs_path.read_text(encoding="utf-8", errors="replace")
    errors: list[str] = []

    # Check 1: well-formed YAML frontmatter.
    fm = _parse_frontmatter(content)
    if fm is None:
        errors.append(f"  Missing or unparseable frontmatter: {rel_path}")
        return errors  # Skip further checks for broken files.

    # Check 2: cross-link existence.
    for link in _collect_cross_links(fm):
        candidate = scaffold_dir / link
        if not candidate.exists() and not (scaffold_dir / Path(link).name).exists():
            errors.append(f"  scaffold cross-link not found: {link} in {rel_path}")

    # Check 3: {paths.X.Y} placeholder key validity.
    for match in _PATHS_PLACEHOLDER_RE.finditer(content):
        key = match.group(1)
        if known_path_keys and key not in known_path_keys:
            errors.append(f"  unknown paths.json key: {{paths.{key}}} in {rel_path}")

    return errors


def main() -> None:
    """Run the architecture scaffold integrity checks.

    Exits 0 on pass, exits 1 on failure, printing a summary to stdout.
    """
    staged = _staged_files()
    scaffold_dir_prefix = _SCAFFOLD_DIR_REL.replace("\\", "/")
    scaffold_files = [
        f for f in staged
        if f.replace("\\", "/").startswith(scaffold_dir_prefix + "/")
        and (f.endswith(".md") or f.endswith(".template"))
    ]

    if not scaffold_files:
        print("check-architecture-scaffolds: no scaffold files staged; skipping.")
        sys.exit(0)

    commit_msg = _get_commit_message()
    if BYPASS_TOKEN in commit_msg:
        print(
            f"check-architecture-scaffolds: bypass token '{BYPASS_TOKEN}' found; skipping."
        )
        sys.exit(0)

    project_root = _git_root()
    paths_json = project_root / _PATHS_JSON_REL
    scaffold_dir = project_root / _SCAFFOLD_DIR_REL
    known_path_keys = _flat_paths_keys(paths_json) if paths_json.exists() else set()

    errors: list[str] = []
    for rel_path in scaffold_files:
        errors.extend(
            _check_one_scaffold(rel_path, project_root, scaffold_dir, known_path_keys)
        )

    if errors:
        print("check-architecture-scaffolds: FAILED")
        print("\n".join(errors))
        print(
            f"\nFIX: Correct the scaffold files or use '{BYPASS_TOKEN}' "
            "in commit message to skip."
        )
        sys.exit(1)

    print(
        f"check-architecture-scaffolds: OK — {len(scaffold_files)} scaffold "
        f"file(s) checked."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-14 13:00 [EPIC-ArchitectureDocsEnforcement/ticket 11 — D11.3]: (#EPIC-LeafcutterMVP/01)
#   Created as the architecture-scaffold integrity commit-guardian hook. Three
#   checks: (1) YAML frontmatter well-formedness, (2) cross-link existence
#   within the scaffold tree, (3) {paths.X.Y} placeholder key validity against
#   paths.json. Bypass token [NO-ARCH-UPDATE] skips the hook. yaml imported
#   with graceful fallback to minimal key:value parser when PyYAML is absent.
# ====================================================================
