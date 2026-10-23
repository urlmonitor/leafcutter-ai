"""
MODULE: worktree_paths
GOAL: Path spelling for the workspace maker (BO-4300b-5): native + POSIX
    alias for every emitted path, acceptance of Git Bash / PowerShell / WSL
    spellings on input, and portable (relative) storage of paths in the
    marker.
BUSINESS CONTEXT: A Windows machine with a Linux shell reaching the same
    project must get one workspace, whichever shell asks, and a location it
    can use from both. Nothing here splits a path on whitespace or builds a
    shell string, so a project under "My Projects" works.
ARCHITECTURE: Stdlib-only, no sibling imports. ``to_native`` maps any
    accepted spelling to a native ``Path``; ``to_posix`` gives the alias
    (``/mnt/<drive>/...`` on Windows, ``as_posix()`` elsewhere);
    ``portable``/``from_portable`` store a filesystem path relative to the
    marker's own workspace so no platform's absolute spelling is persisted.
    ``path_fields``, ``repo_fields`` and ``add_ticket_fields`` build the
    answer's path fields for ``worktree.py``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_IS_WINDOWS = os.name == "nt"
_WSL_RE = re.compile(r"^/mnt/([A-Za-z])(?:/(.*))?$")
_GITBASH_RE = re.compile(r"^/([A-Za-z])(?:/(.*))?$")
_URL_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*://|[\w.-]+@[\w.-]+:)")


def to_native(spelling: str) -> Path:
    """Map a Git Bash, PowerShell or WSL spelling of a folder to a native ``Path``.

    On Windows ``/mnt/c/x`` and ``/c/x`` become ``C:/x`` (only when that
    drive exists, so a genuine root-relative path is left alone); every
    other spelling (and every non-Windows host) passes through unchanged.
    The result is not resolved.
    """
    if _IS_WINDOWS:
        for pattern in (_WSL_RE, _GITBASH_RE):
            match = pattern.match(spelling)
            if match and Path(f"{match.group(1).upper()}:/").exists():
                return Path(f"{match.group(1).upper()}:/{match.group(2) or ''}")
    return Path(spelling)


def to_posix(path: Path) -> str:
    """Return the POSIX alias of *path*: ``/mnt/<drive>/...`` on Windows, else ``as_posix()``."""
    text = path.as_posix()
    if _IS_WINDOWS and len(text) >= 2 and text[1] == ":":
        return f"/mnt/{text[0].lower()}/{text[3:]}".rstrip("/")
    return text


def resolve_arg(spelling: str) -> Path:
    """Return the resolved native ``Path`` for a caller-supplied ``--path``/``--repo-root``."""
    return to_native(spelling).resolve()


def portable(value: str, base: Path) -> str:
    """Return *value* in a form holding no absolute path in one platform's spelling.

    A URL is returned as is. A filesystem path is stored relative to *base*,
    with forward slashes and a leading ``./`` or ``../``. When no relative
    form exists (different Windows drive) the value is returned unchanged.
    """
    if not value or _URL_RE.match(value) or not Path(value).is_absolute():
        return value
    try:
        rel = os.path.relpath(value, str(base)).replace("\\", "/")
    except ValueError:
        return value
    return rel if rel.startswith(".") else f"./{rel}"


def from_portable(stored: str, base: Path) -> str:
    """Invert :func:`portable`: turn a stored relative path back into an absolute one."""
    if stored.startswith(("./", "../")):
        return str((base / stored).resolve())
    return stored


def path_fields(workspace_path: Path) -> dict[str, str]:
    """Return ``workspace_path`` / ``workspace_path_posix`` / ``worktree_path`` (alias)."""
    return {
        "workspace_path": str(workspace_path),
        "workspace_path_posix": to_posix(workspace_path),
        "worktree_path": str(workspace_path),
    }


def repo_fields(repo_root: Path) -> dict[str, str]:
    """Return ``repo_root`` and ``repo_root_posix``."""
    return {"repo_root": str(repo_root), "repo_root_posix": to_posix(repo_root)}


def _ticket_in_workspace(repo_root: Path, workspace_path: Path, ticket_arg: str) -> Path | None:
    """Map a ticket path given relative to the main checkout onto its workspace copy."""
    ticket_path = to_native(ticket_arg)
    if not ticket_path.is_absolute():
        ticket_path = repo_root / ticket_path
    try:
        rel = ticket_path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None
    return workspace_path / rel


def add_ticket_fields(answer: dict[str, Any], ticket_arg: str | None, repo_root: Path, workspace_path: Path) -> None:
    """Add ``ticket_path_in_worktree(_posix)`` to *answer* only when a ticket was named."""
    if not ticket_arg:
        return
    found = _ticket_in_workspace(repo_root, workspace_path, ticket_arg)
    if found is not None:
        answer["ticket_path_in_worktree"] = str(found)
        answer["ticket_path_in_worktree_posix"] = to_posix(found)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-30 22:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
#   Created for BO-4300b-5 / b-5-i: native + POSIX alias for every emitted
#   path, three-spelling input, relative marker storage. The ticket-path
#   helpers moved here from worktree.py (file-size ratchet). (ADR-018)
# ===========================================================================
