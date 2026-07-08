"""
MODULE: check_surface_components_e2
GOAL: Pre-commit hook that blocks a commit when a staged ticket or documentation
    file carries no `components` frontmatter field (or carries an empty one),
    enforcing KM-KGS-100e-2.
BUSINESS CONTEXT: The knowledge graph builds component_membership edges from the
    `components` field declared in tickets and docs (config/paths.json surface
    edge_fields). A ticket or doc committed without `components` produces a
    disconnected node in the graph, breaking the component-level view of what
    each feature or document belongs to.
ARCHITECTURE: Reads config/paths.json at runtime to derive which surfaces are
    membership-declaring (those whose edge_fields list contains "components").
    Staged .md files are matched against surface paths. For each matching file,
    YAML frontmatter is parsed and `components` is validated via a presence +
    non-empty check. Registry-membership validation is intentionally SKIPPED for
    this surface: real ticket and doc files use both underscore-case IDs
    (docs/components.json vocabulary: build_pipeline, commit_guardian, ...) and
    kebab-case IDs (AC index.yaml vocabulary: build-pipeline, ac-store, ...),
    and a significant tail of values (build_system, agents, workflow_deployment,
    ...) appears in neither registry. Enforcing membership would produce
    widespread false-positive blocks on the existing corpus. The decision is
    recorded here so the registry-membership check can be enabled once the project
    standardises on a single component vocabulary across all surfaces.

    Fail-open: unexpected internal errors exit 0 with a WARNING on stderr so that
    a hook fault never blocks an otherwise-valid commit.

Exit codes:
    0 — all staged files pass, or no membership-declaring staged .md files
    1 — one or more staged files missing a valid `components` frontmatter field

Usage:
    python scripts/commit_guardian/run_hook.py \\
        scripts/commit_guardian/check_surface_components_e2.py

DECISION HISTORY:
  - 2026-07-08 [python-coder/KM-KGS-100e-2]: Initial implementation.
    Surfaces: tickets/ and docs/ (derived from paths.json edge_fields).
    Enforcement: presence + non-empty only; registry-membership deferred
    (vocabulary mismatch — see ARCHITECTURE note).
    Hook is registered in commit_guardian.json with enabled:false to prevent
    blocking commits until a coordinated backfill populates components across
    all tickets and docs.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


_HOOK_PREFIX = "[check-surface-components-e2]"
_PATHS_JSON_REL = "config/paths.json"

# File extensions of the surfaces covered by this hook (.md only)
_MD_SUFFIX = ".md"

# Regex that recognises a YAML frontmatter block at the start of a file.
_FRONTMATTER_RE = re.compile(r"^---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n", re.DOTALL)


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
# paths.json: membership-declaring surface discovery
# ---------------------------------------------------------------------------


def _load_membership_prefixes(project_root: Path) -> list[str]:
    """Load the set of path prefixes for membership-declaring .md surfaces.

    Reads config/paths.json and collects all surface paths that (1) end with
    a slash (directory surface) and (2) have "components" in edge_fields.
    These are the directory prefixes under which staged .md files must carry
    a components frontmatter field.

    The glossary and other surfaces with empty edge_fields are automatically
    excluded because they do not declare component-membership relationships.

    Args:
        project_root: Absolute path to the repository root.

    Returns:
        List of path prefix strings (e.g. ["tickets/", "docs/"]).
        Returns a safe fallback list on any load error.
    """
    paths_json = project_root / _PATHS_JSON_REL
    try:
        raw = paths_json.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {paths_json}: "
            f"{type(exc).__name__}: {exc}; using fallback prefixes",
            file=sys.stderr,
        )
        return ["tickets/", "docs/"]

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot parse {paths_json}: "
            f"{exc}; using fallback prefixes",
            file=sys.stderr,
        )
        return ["tickets/", "docs/"]

    surfaces = data.get("surfaces", {})
    if not isinstance(surfaces, dict):
        return ["tickets/", "docs/"]

    prefixes: list[str] = []
    for _name, surface in surfaces.items():
        if not isinstance(surface, dict):
            continue
        path = surface.get("path", "")
        edge_fields = surface.get("edge_fields", [])
        # Membership-declaring .md surfaces are directory paths (trailing slash)
        # whose edge_fields include "components".
        if (
            isinstance(path, str)
            and path.endswith("/")
            and isinstance(edge_fields, list)
            and "components" in edge_fields
        ):
            prefixes.append(path)

    return prefixes if prefixes else ["tickets/", "docs/"]


# ---------------------------------------------------------------------------
# Staged file detection
# ---------------------------------------------------------------------------


def _get_staged_md_paths(prefixes: list[str]) -> list[str]:
    """Return staged .md file paths that fall under membership-declaring surfaces.

    Uses HOOK_TEST_FILES env var when set (OS pathsep- or newline-separated).
    In HOOK_NO_GIT mode, returns an empty list (no git interaction).

    Args:
        prefixes: List of path prefixes to filter staged files by.

    Returns:
        List of path strings (absolute when from HOOK_TEST_FILES,
        relative to repo root when from git diff --cached).
    """
    test_files = os.environ.get("HOOK_TEST_FILES")
    if test_files:
        raw_paths = test_files.replace(os.pathsep, "\n").splitlines()
        return [
            p.strip()
            for p in raw_paths
            if p.strip() and p.strip().endswith(_MD_SUFFIX)
            and any(p.strip().startswith(px) or px in p.strip() for px in prefixes)
        ]

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

    return [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
        and line.strip().endswith(_MD_SUFFIX)
        and any(line.strip().startswith(px) for px in prefixes)
    ]


# ---------------------------------------------------------------------------
# Frontmatter extraction
# ---------------------------------------------------------------------------


def _extract_frontmatter(content: str) -> dict | None:
    """Parse YAML frontmatter from a markdown file.

    Args:
        content: Raw file content.

    Returns:
        Parsed dict on success, None if no frontmatter or parse failure.
    """
    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None

    try:
        import yaml  # type: ignore[import]

        data = yaml.safe_load(match.group(1))
        return data if isinstance(data, dict) else None
    except (ImportError, Exception):  # noqa: BLE001
        # PyYAML unavailable or parse error — skip the file (fail-open)
        return None


# ---------------------------------------------------------------------------
# Components validation
# ---------------------------------------------------------------------------


def _check_components(data: dict, file_label: str) -> list[str]:
    """Validate the `components` field in frontmatter data.

    Enforces KM-KGS-100e-2 presence + non-empty requirement.
    Registry-membership validation is intentionally skipped (see module
    ARCHITECTURE note for the rationale).

    Args:
        data: Parsed YAML frontmatter dict.
        file_label: Human-readable file identifier for error messages.

    Returns:
        List of human-readable violation strings. Empty = no violations.
    """
    raw = data.get("components")

    if raw is None or not isinstance(raw, list):
        return [
            f"{file_label}: missing required `components` frontmatter field. "
            "Declare a non-empty list naming the component(s) this file belongs to, "
            "e.g. components: [knowledge-management]. This field is required for the "
            "knowledge graph to build component_membership edges."
        ]

    non_empty = [v for v in raw if isinstance(v, str) and v.strip()]
    if not non_empty:
        return [
            f"{file_label}: `components` frontmatter field is present but empty. "
            "Provide at least one component id, e.g. components: [knowledge-management]."
        ]

    return []


# ---------------------------------------------------------------------------
# Per-file check
# ---------------------------------------------------------------------------


def _check_file(file_path: str, project_root: Path | None) -> list[str]:
    """Run the components check for a single staged markdown file.

    Args:
        file_path: Absolute or repo-relative path to a staged .md file.
        project_root: Resolved project root Path, or None.

    Returns:
        List of violation strings. Empty = no violations.
    """
    abs_path = file_path
    if not Path(file_path).is_absolute() and project_root is not None:
        abs_path = str(project_root / file_path)

    path = Path(abs_path)
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read {file_path}: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return []

    data = _extract_frontmatter(content)
    if data is None:
        # No YAML frontmatter — file does not participate in surface; skip silently
        return []

    return _check_components(data, file_path)


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _emit_violations(violations: list[str]) -> None:
    """Print violation messages to stderr for human-readable CI output.

    Args:
        violations: List of violation description strings.
    """
    print(
        f"\n{_HOOK_PREFIX} BLOCKED — `components` frontmatter missing or empty:",
        file=sys.stderr,
    )
    for i, v in enumerate(violations, start=1):
        print(f"  [{i}] {v}", file=sys.stderr)
    print(
        "\nTo fix: add `components: [<component-id>]` to the frontmatter of each "
        "listed file. Valid IDs are found in docs/components.json (underscore-case) "
        "and docs/acceptance-criteria/index.yaml (kebab-case).",
        file=sys.stderr,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the ticket/doc surface components check.

    Returns:
        0 when all staged files pass (or no membership-declaring .md files staged).
        1 when one or more files missing a valid `components` field.
    """
    project_root = _find_project_root()
    prefixes = _load_membership_prefixes(project_root) if project_root else ["tickets/", "docs/"]

    staged_paths = _get_staged_md_paths(prefixes)
    if not staged_paths:
        return 0

    all_violations: list[str] = []
    for staged_path in staged_paths:
        file_violations = _check_file(staged_path, project_root)
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
