"""
MODULE: worktree_remove_half
GOAL: Recognise a clearing that stopped part-way and say what the maker's verbs
    do with it: ``remove`` finishes it, ``ensure`` and ``locate`` refuse it as
    HALF_CLEARED, ``list`` shows it as half-cleared (AC BO-4300e-2-ix..xii).
BUSINESS CONTEXT: A clearing that stops (a program holds a file, the machine
    stops) must never leave something that reads as a ready workspace, and
    asking to clear again must finish it: without a token, a fetch or a second
    unsent-work check when the first clearing already checked the work, and with
    the one-time token for exactly the remaining files when the work cannot be
    checked any more (repository unreadable or gone).
ARCHITECTURE: Stdlib-only. Imports ``worktree_answer``, ``worktree_git``,
    ``worktree_layout``, ``worktree_paths`` and ``worktree_remove_checks``;
    ``worktree_remove`` and ``worktree_admin`` import this module, never the
    reverse. ``head_state`` reads only the workspace's own repository folder
    (``--git-dir``, never a parent's) and tells readable, unreadable and unknown
    (git itself failed to run, which is not damage) apart. ``half_state`` returns
    ``(record, kind)`` with kind ``resume`` | ``unreadable`` | ``gone`` |
    ``identified`` | ``foreign``; a record-less leftover is ``identified`` only
    when every shared-project address its repository leftovers (``FETCH_HEAD``,
    ``config``) name is this project's ``origin``.
"""

from __future__ import annotations

import argparse
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg
import worktree_layout as wl
import worktree_paths as wp
import worktree_remove_checks as wrc

_log = logging.getLogger(__name__)

def head_state(workspace: Path) -> tuple[str, str | None]:
    """``(state, commit)``: ``readable`` with the checked-out commit, ``unreadable``, or ``unknown``.

    Only the workspace's own repository folder is consulted (``--git-dir``), so
    git never climbs into a parent repository; nothing is fetched or written.
    ``unknown`` means git itself could not run (missing, timed out): that is not damage.
    ``safe.directory=*`` keeps git's ownership refusal from passing for damage.
    """
    git_dir = workspace / ".git"
    if not (git_dir.is_dir() and (git_dir / "HEAD").is_file()):
        return "unreadable", None
    cmd = ["git", "-c", "safe.directory=*", "--git-dir", str(git_dir),
           "rev-parse", "--verify", "--quiet", "HEAD^{commit}"]
    try:
        proc = subprocess.run(cmd, cwd=str(workspace), stdin=subprocess.DEVNULL, env=wg.git_env(),
                              capture_output=True, text=True, timeout=60, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("head_state: git could not run in %s: %s", workspace, exc)
        return "unknown", None
    sha = proc.stdout.strip()
    return ("readable", sha) if proc.returncode == 0 and sha else ("unreadable", None)


HALF_CLEARED_STATE = "half-cleared"


def is_half_cleared(workspace: Path, marker: dict[str, Any]) -> bool:
    """True for a clearing that started (record state ``clearing``) or a ready record whose repository is unreadable."""
    state = marker.get("state", "ready")
    if state == "clearing":
        return True
    return state == "ready" and (workspace / ".git").is_dir() and head_state(workspace)[0] == "unreadable"


def half_cleared_answer(workspace: Path) -> dict[str, Any]:
    """HALF_CLEARED refusal for ensure and locate: the leftover is never ready, and clearing it again finishes it."""
    return wa.error_answer(
        "HALF_CLEARED",
        f"The workspace at {workspace} is half-cleared: an earlier clearing of it stopped part-way. It is not "
        "ready and was left untouched; asking to clear it again finishes it.",
        remnant_path=str(workspace),
    )


_URL_LINE = re.compile(r"^\s*url\s*=\s*(\S.*?)\s*$", re.MULTILINE)


def _leftover_addresses(git_dir: Path) -> list[str]:
    """Shared-project addresses a repository folder's leftover ``FETCH_HEAD`` and ``config`` name."""
    found: list[str] = []
    for name in ("FETCH_HEAD", "config"):
        try:
            text = (git_dir / name).read_bytes().decode("utf-8", errors="replace") if (git_dir / name).is_file() else ""
        except OSError as exc:
            _log.warning("_leftover_addresses: cannot read %s: %s", git_dir / name, exc)
            continue
        if name == "config":
            found.extend(_URL_LINE.findall(text))
            continue
        for line in text.splitlines():
            fields = line.split("\t")
            if len(fields) >= 3 and " of " in fields[2]:
                found.append(fields[2].split(" of ", 1)[1].strip())
    return found


def names_project(folder: Path, hub: str | None) -> bool:
    """True when every address the leftover repository folder names is *hub* (and at least one is named)."""
    git_dir = folder / ".git"
    if not hub or not git_dir.is_dir():
        return False
    addresses = _leftover_addresses(git_dir)
    return bool(addresses) and all(wg.same_location(address, hub) for address in addresses)


def clearing_marker(marker: dict[str, Any], workspace: Path, project: Path, commit: str | None) -> dict[str, Any]:
    """The record rewritten once the checks passed: state ``clearing``, the workspace, the project, the checked commit."""
    return {**marker, "state": "clearing", "clearing_commit": commit, "clearing_workspace": str(workspace),
            "clearing_project": str(project)}


def project_and_root(args: argparse.Namespace, workspace: Path,
                      marker: dict[str, Any] | None) -> tuple[Path | None, Path | None]:
    """The project (``--repo-root``, else the one *marker* records) and its resolved landing place, or ``(None, None)``."""
    project = None
    if args.repo_root:
        project, refusal = wl.resolve_repo_root(args.repo_root)
        project = None if refusal is not None else project
    elif marker is not None:
        project = wl.project_of(workspace, marker)
    if project is None:
        return None, None
    place, usage = wl.landing_for(getattr(args, "landing_root", None), project)
    return (None, None) if usage is not None or place is None else (project, place.resolve())


def half_state(args: argparse.Namespace, workspace: Path) -> tuple[dict[str, Any], str] | None:
    """``(record, kind)`` when *workspace* is a clearing left part-way in this project's own landing place, else ``None``.

    *record* is ``{}`` when the folder has none. *kind*: ``resume`` (the clearing started and the checked commit is
    still readable and unchanged), ``unreadable`` (the repository can no longer be read), ``gone`` (no repository
    folder), ``identified`` (no record, but the repository's leftovers name this project's shared project) or
    ``foreign`` (a record-less folder not shown to be ours). A repository that git merely failed to read stays ``None``.
    """
    marker = wg.read_marker(workspace)
    project, root = project_and_root(args, workspace, marker)
    resolved = workspace.resolve()
    if project is None or root is None or not wrc.is_leftover_slot(resolved, root):
        return None
    has_repo = (resolved / ".git").exists()
    if marker is None:
        if not has_repo:
            return {}, "gone"
        state, _sha = head_state(resolved)
        named = state == "unreadable" and names_project(resolved, wg.origin_url(project))
        return {}, "identified" if named else "foreign"
    kind, slug = resolved.parts[-2:]  # a record that names another slot is a copy, not a leftover
    if wl.other_project_occupant(workspace, marker, project) or (marker.get("kind"), marker.get("slug")) != (kind, slug):
        return None
    if not has_repo:
        return marker, "gone"
    state, sha = head_state(resolved)
    if state == "unknown" or marker.get("state") not in ("ready", "clearing"):
        return None
    if state == "unreadable":
        return marker, "unreadable"
    return (marker, "resume") if marker.get("state") == "clearing" and sha == marker.get("clearing_commit") else None


def target_path(args: argparse.Namespace) -> tuple[Path | None, dict[str, Any] | None]:
    """The folder to clear: ``--path``, else the one ``--kind``/``--slug`` name in this project's landing place."""
    if args.path:
        return wp.resolve_arg(args.path), None
    if not (args.kind and args.slug) or args.kind not in wg.VALID_KINDS:
        return None, wa.error_answer("USAGE", "remove requires --path, or a valid --kind with --slug.")
    project, refusal = wl.resolve_repo_root(args.repo_root)
    if refusal is not None:
        return None, refusal
    place, usage = wl.landing_for(getattr(args, "landing_root", None), project)
    if usage is not None or place is None:
        return None, usage
    import worktree_identity as wi  # noqa: PLC0415 - function-level: identity imports worktree_remove
    return wl.workspace_path_for(place, args.kind, wi.resolve(args.kind, args.slug).slug), None


def half_cleared_refusal(workspace: Path, marker: dict[str, Any] | None, project: Path) -> dict[str, Any] | None:
    """HALF_CLEARED refusal for ensure when *workspace* (with its *marker*) is a leftover of *project*, else ``None``."""
    if marker is None or wl.other_project_occupant(workspace, marker, project) or not is_half_cleared(workspace, marker):
        return None
    return half_cleared_answer(workspace)


def add_target_args(parser: argparse.ArgumentParser) -> None:
    """Add the ways ``remove`` names its workspace: ``--path``, or ``--kind`` with ``--slug``."""
    for option in ("--path", "--kind", "--slug"):
        parser.add_argument(option)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-11-03 [python-coder/fast-lane bo-4300e-2, BO-4300e-2-ix..xii]:
#   Created. A clearing that passed its checks marks the record ``clearing``;
#   a stopped clearing is finished by asking again, never read as ready or
#   resumed by ensure; an unreadable repository or a record-less leftover that
#   names this project's shared project is half-cleared (token for its files).
#   (#fast-lane/BO-4300e-2) (ADR-018)
# ===========================================================================
