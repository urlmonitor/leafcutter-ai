"""
MODULE: check_agent_registry
GOAL: Pre-commit hook that validates agent_registry.json for bidirectional consistency.
BUSINESS CONTEXT: The agent registry is the single source of truth for which
    agents exist and their spawn relationships. This hook runs when any agent
    template, registry file, or build script is staged, validating that the
    registry is consistent before the commit lands. Catches orphan templates,
    orphan registry entries, and spawn_allowlist / spawned_by mismatches early
    rather than at runtime.
ARCHITECTURE: Thin wrapper around registry_validator.validate_agent_registry().
    Resolves the leafcutter package root from the config loader
    pattern (_get fallback). Only fires when agent-registry-related files are
    staged; no-ops on unrelated commits.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _get_staged_files() -> list[str]:
    """Return list of staged file paths from git.

    Returns:
        List of staged file path strings relative to the repo root.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACRM"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.stdout.strip().splitlines()


def _is_registry_related(staged: list[str]) -> bool:
    """Return True if any staged file touches agent registry or templates.

    Args:
        staged: List of staged file paths.

    Returns:
        True if at least one staged file is in leafcutter/config/,
        leafcutter/templates/agents/, or leafcutter/scripts/.
    """
    triggers = (
        "leafcutter/config/",
        "leafcutter/templates/agents/",
        "leafcutter/scripts/",
    )
    return any(
        any(f.replace("\\", "/").startswith(t) for t in triggers)
        for f in staged
    )


def main() -> int:
    """Run agent registry validation as a pre-commit hook.

    Returns:
        Exit code: 0 when registry is consistent or not touched; 1 on errors.
    """
    staged = _get_staged_files()
    if not _is_registry_related(staged):
        return 0  # No agent registry files staged — nothing to check

    # Locate the package root. Try git rev-parse to find the repo root,
    # then look for leafcutter/ relative to it.
    repo_root_result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if repo_root_result.returncode != 0:
        print("[check_agent_registry] Could not determine repo root; skipping.", file=sys.stderr)
        return 0

    repo_root = Path(repo_root_result.stdout.strip())
    package_root = repo_root / "leafcutter"

    if not package_root.exists():
        # Package not present in this repo — nothing to validate
        return 0

    # Import registry_validator from the package's scripts directory
    scripts_dir = package_root / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))

    try:
        from registry_validator import validate_agent_registry  # type: ignore
    except ImportError as exc:
        print(
            f"[check_agent_registry] Cannot import registry_validator: {exc}. Skipping.",
            file=sys.stderr,
        )
        return 0

    errors = validate_agent_registry(package_root)
    if errors:
        print(
            "[check_agent_registry] agent_registry.json validation failed:",
            file=sys.stderr,
        )
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        print(
            "\nFix the registry errors above before committing. "
            "See leafcutter/config/agent_registry.json.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 11:00 [epic-supervisor/ticket-20]: Initial implementation.
#   Thin wrapper around registry_validator.validate_agent_registry().
#   Only fires when agent-registry-related files are staged (prevents
#   spurious failures on unrelated commits). Falls back gracefully when
#   the package or module cannot be found (returns 0) — opt-in safety.
# ====================================================================
