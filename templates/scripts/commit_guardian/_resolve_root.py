"""Resolve the project root regardless of deployment depth.

Handles both source layout (repo/scripts/commit_guardian/) and deployed
layout (project/.leafcutter/scripts/commit_guardian/).

The preferred resolution strategy is ``git rev-parse --show-toplevel``,
which always reports the root of the git repository containing the current
working directory, regardless of symlinks.  This correctly resolves consumer
project roots even when the script is deployed via a symlinked ``.leafcutter``
directory.  The ``__file__``-based ancestor walk is used only as a fallback
when git is unavailable or exits non-zero.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

_PROJECT_ROOT: Path | None = None


def find_project_root() -> Path:
    """Return the project root, preferring ``git rev-parse --show-toplevel``.

    Tries ``git rev-parse --show-toplevel`` first (correct in symlinked
    deployed layouts).  Falls back to walking ancestors of ``__file__``
    when git exits non-zero or raises ``OSError`` (e.g. git not installed).

    Returns:
        Absolute Path to the project root directory.
    """
    global _PROJECT_ROOT
    if _PROJECT_ROOT is not None:
        return _PROJECT_ROOT

    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if proc.returncode == 0:
            git_root = proc.stdout.strip()
            if git_root:
                _PROJECT_ROOT = Path(git_root)
                return _PROJECT_ROOT
    except OSError:
        pass  # git unavailable — fall through to __file__ walk

    here = Path(__file__).resolve().parent
    for ancestor in [here, *here.parents]:
        if (ancestor / ".git").exists() or (ancestor / "CLAUDE.md").exists():
            _PROJECT_ROOT = ancestor
            return _PROJECT_ROOT

    # Fallback: assume 2 levels up (original behavior)
    _PROJECT_ROOT = here.parent.parent
    return _PROJECT_ROOT
