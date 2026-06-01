"""Resolve the project root regardless of deployment depth.

Handles both source layout (repo/scripts/commit_guardian/) and deployed
layout (project/.leafcutter/scripts/commit_guardian/).
"""

from pathlib import Path

_PROJECT_ROOT: Path | None = None


def find_project_root() -> Path:
    """Walk up from this directory to find the project root."""
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    here = Path(__file__).resolve().parent
    for ancestor in [here, *here.parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            _PROJECT_ROOT = ancestor
            return _PROJECT_ROOT

    # Fallback: assume 2 levels up (original behavior)
    _PROJECT_ROOT = here.parent.parent
    return _PROJECT_ROOT
