"""
MODULE: check_surface_components_e3
GOAL: Pre-commit hook that blocks a commit when a staged registry file
    (config/agent_registry.json, config/skill_registry.json, docs/roadmap.json)
    contains an entry missing a non-empty `components` field (KM-KGS-100e-3).
BUSINESS CONTEXT: The knowledge graph builds component_membership edges from the
    `components` field on registry entries (config/paths.json edge_fields). An
    agent, skill, or roadmap phase without `components` is a disconnected node.
ARCHITECTURE: Reads config/paths.json to find non-directory surfaces whose
    edge_fields contain "components". The glossary surface is automatically
    exempt (edge_fields: []). For each staged matching file, JSON is parsed and
    top-level entries extracted via the knowledge_query.py strategy (try surface
    name as key, then "agents", "skills", "phases", "items"). Enforcement is
    presence + non-empty only — registry-membership validation deferred because
    no current registry entry has a `components` field. Fail-open: internal
    errors exit 0 with a WARNING on stderr.

Exit codes: 0 = clean or no registry files staged; 1 = missing components found.

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_surface_components_e3.py

DECISION HISTORY:
  - 2026-07-08 [python-coder/KM-KGS-100e-3]: Initial implementation.
    Surfaces derived from paths.json edge_fields; glossary exempt. Hook
    registered with enabled:false — enabling blocks all registry changes until
    a backfill adds `components` to every entry.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


_HOOK_PREFIX = "[check-surface-components-e3]"
_PATHS_JSON_REL = "config/paths.json"

# Ordered list of fallback keys to try when the surface name key is absent.
# Mirrors the logic in knowledge_query.py's extract_nodes().
_ENTRY_FALLBACK_KEYS = ("agents", "skills", "phases", "items")


# ---------------------------------------------------------------------------
# Project root detection
# ---------------------------------------------------------------------------


def _find_project_root() -> Path | None:
    """Find the project root by walking up from cwd.

    Uses HOOK_ROOT env var when set (testing / CI override).

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
# paths.json: membership-declaring registry surface discovery
# ---------------------------------------------------------------------------


def _load_registry_surfaces(project_root: Path) -> dict[str, str]:
    """Load membership-declaring registry surfaces from paths.json.

    A membership-declaring registry surface is a non-directory path (no
    trailing slash) whose edge_fields list contains "components". Surfaces
    with empty edge_fields (the glossary) are automatically excluded.

    Args:
        project_root: Absolute path to the repository root.

    Returns:
        Dict mapping surface name to its relative file path (e.g.
        {"agents": "config/agent_registry.json", "roadmap": "docs/roadmap.json"}).
        Returns a safe fallback dict on any load error.
    """
    fallback = {
        "agents": "config/agent_registry.json",
        "skills": "config/skill_registry.json",
        "roadmap": "docs/roadmap.json",
    }

    paths_json = project_root / _PATHS_JSON_REL
    try:
        raw = paths_json.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {paths_json}: "
            f"{type(exc).__name__}: {exc}; using fallback surfaces",
            file=sys.stderr,
        )
        return fallback

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot parse {paths_json}: "
            f"{exc}; using fallback surfaces",
            file=sys.stderr,
        )
        return fallback

    surfaces = data.get("surfaces", {})
    if not isinstance(surfaces, dict):
        return fallback

    result: dict[str, str] = {}
    for name, surface in surfaces.items():
        if not isinstance(surface, dict):
            continue
        path = surface.get("path", "")
        edge_fields = surface.get("edge_fields", [])
        # Registry surfaces are file paths (no trailing slash) with "components"
        # in edge_fields.
        if (
            isinstance(path, str)
            and not path.endswith("/")
            and isinstance(edge_fields, list)
            and "components" in edge_fields
        ):
            result[name] = path

    # Return whatever was found (may be empty if no membership-declaring surfaces exist).
    # Only the error-path branches above return the fallback dict.
    return result


# ---------------------------------------------------------------------------
# Staged file detection
# ---------------------------------------------------------------------------


def _get_staged_registry_paths(registry_surfaces: dict[str, str]) -> list[tuple[str, str]]:
    """Return staged files that match a membership-declaring registry surface.

    Uses HOOK_TEST_FILES env var when set (OS pathsep- or newline-separated).
    In HOOK_NO_GIT mode, returns an empty list (no git interaction).

    Args:
        registry_surfaces: Dict from surface name to relative file path.

    Returns:
        List of (file_path, surface_name) tuples for matching staged files.
    """
    valid_paths = set(registry_surfaces.values())

    test_files = os.environ.get("HOOK_TEST_FILES")
    if test_files:
        raw_paths = test_files.replace(os.pathsep, "\n").splitlines()
        results: list[tuple[str, str]] = []
        for p in raw_paths:
            p = p.strip()
            if not p:
                continue
            for surface_name, rel_path in registry_surfaces.items():
                if p == rel_path or p.endswith(rel_path):
                    results.append((p, surface_name))
                    break
        return results

    if os.environ.get("HOOK_NO_GIT"):
        return []

    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=AM"],
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

    results = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line in valid_paths:
            for surface_name, rel_path in registry_surfaces.items():
                if line == rel_path:
                    results.append((line, surface_name))
                    break
    return results


# ---------------------------------------------------------------------------
# Entry extraction
# ---------------------------------------------------------------------------


def _extract_entries(data: Any, surface_name: str) -> list[Any]:
    """Extract the entries list from a registry JSON payload.

    Mirrors knowledge_query.py: try surface name key, then "agents",
    "skills", "phases", "items". Non-dicts in the list are skipped by callers.

    Args:
        data: Parsed JSON data.
        surface_name: The surface name from paths.json (e.g. "agents").
    """
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    # Try the surface name first, then fallback keys
    for key in (surface_name, *_ENTRY_FALLBACK_KEYS):
        candidate = data.get(key)
        if isinstance(candidate, list):
            return candidate

    return []


# ---------------------------------------------------------------------------
# Components validation
# ---------------------------------------------------------------------------


def _check_entry_components(entry: dict, entry_label: str) -> list[str]:
    """Validate the `components` field in a registry entry (KM-KGS-100e-3).

    Enforces presence + non-empty; registry-membership check deferred.

    Args:
        entry: A single registry entry dict.
        entry_label: Human-readable entry identifier for error messages.
    """
    raw = entry.get("components")

    if raw is None or not isinstance(raw, list):
        return [
            f"{entry_label}: missing required `components` field. "
            "Declare a non-empty list naming the component(s) this entry belongs to, "
            "e.g. \"components\": [\"knowledge-management\"]. This field is required "
            "for the knowledge graph to build component_membership edges."
        ]

    non_empty = [v for v in raw if isinstance(v, str) and v.strip()]
    if not non_empty:
        return [
            f"{entry_label}: `components` field is present but empty. "
            "Provide at least one component id."
        ]

    return []


# ---------------------------------------------------------------------------
# Per-file check
# ---------------------------------------------------------------------------


def _check_registry_file(
    file_path: str,
    surface_name: str,
    project_root: Path | None,
) -> list[str]:
    """Run the components check for a single staged registry JSON file.

    Args:
        file_path: Absolute or repo-relative path to a staged registry file.
        surface_name: The surface name for this file (e.g. "agents").
        project_root: Resolved project root Path, or None.
    """
    abs_path = file_path
    if not Path(file_path).is_absolute() and project_root is not None:
        abs_path = str(project_root / file_path)

    path = Path(abs_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {file_path}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: JSON parse error in {file_path}: {exc}",
            file=sys.stderr,
        )
        return []

    entries = _extract_entries(data, surface_name)
    violations: list[str] = []

    for idx, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        entry_id = str(entry.get("id", f"<entry {idx}>"))
        label = f"{file_path}:{entry_id}"
        violations.extend(_check_entry_components(entry, label))

    return violations


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _emit_violations(violations: list[str]) -> None:
    """Print violation messages to stderr for human-readable CI output.

    Args:
        violations: List of violation description strings.
    """
    print(
        f"\n{_HOOK_PREFIX} BLOCKED — registry entries missing `components` field:",
        file=sys.stderr,
    )
    for i, v in enumerate(violations, start=1):
        print(f"  [{i}] {v}", file=sys.stderr)
    print(
        "\nTo fix: add a \"components\" list to each listed registry entry. "
        "Valid IDs are found in docs/components.json (underscore-case) "
        "and docs/acceptance-criteria/index.yaml (kebab-case).",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the registry surface components check. Returns 0 = clean, 1 = violations."""
    project_root = _find_project_root()

    if project_root is not None:
        registry_surfaces = _load_registry_surfaces(project_root)
    else:
        registry_surfaces = {
            "agents": "config/agent_registry.json",
            "skills": "config/skill_registry.json",
            "roadmap": "docs/roadmap.json",
        }

    staged_files = _get_staged_registry_paths(registry_surfaces)
    if not staged_files:
        return 0

    all_violations: list[str] = []
    for file_path, surface_name in staged_files:
        file_violations = _check_registry_file(file_path, surface_name, project_root)
        all_violations.extend(file_violations)

    if not all_violations:
        return 0

    _emit_violations(all_violations)
    return 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"{_HOOK_PREFIX} unexpected error (fail-open): "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
