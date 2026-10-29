"""
MODULE: worktree_remove_checks
GOAL: The safety checks the workspace maker's ``remove`` runs around a deletion:
    the check for programs working inside a workspace (failing closed when the
    check itself cannot run), and the recognition, listing and token binding of
    a half-cleared folder (AC BO-4300e-2-iv, e-2-v, e-2-vi).
BUSINESS CONTEXT: A clearing that stopped part-way leaves a folder whose
    repository is gone; it must still be finishable, but never by silently
    deleting files nobody could verify reached the shared project. A program
    whose current folder is inside a workspace blocks its deletion on Windows
    and is a sign someone is still working there, so clearing refuses before
    anything (fetch, push, deletion) happens - and also refuses when it cannot
    tell, because "could not check" must never read as "nobody there".
ARCHITECTURE: Stdlib-only. Imports ``worktree_answer`` and ``worktree_git``
    only; ``worktree_remove`` imports this module and not the reverse, so the
    path helper ``long_path`` and the content digest live here.
    ``program_check`` returns ``(holders, unavailable_reason)``: the second is
    set when ``worktree/sweep_processes.py`` (loaded from beside the maker) is
    missing, fails to load, raises, or reports an error. ``remaining_files``
    lists a half-cleared folder's files (workspace-relative, forward slashes,
    sorted, the workspace record excluded) and ``half_token`` is the same kind
    of stateless sha256 binding as ``worktree_remove.discard_token``.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg

_log = logging.getLogger(__name__)

_EXTENDED_PREFIX = "\\\\?\\"


def long_path(path: Path) -> str:
    """Return *path* spelled so a path over 260 characters is reachable (Windows extended-length prefix)."""
    text = str(path)
    if os.name != "nt" or text.startswith(_EXTENDED_PREFIX):
        return text
    return _EXTENDED_PREFIX + "UNC\\" + text[2:] if text.startswith("\\\\") else _EXTENDED_PREFIX + text


def content_digest(workspace: Path, rel: str) -> str:
    """sha256 of the file's bytes, or a marker string when it is absent or unreadable."""
    try:
        return hashlib.sha256(Path(long_path(workspace / rel)).read_bytes()).hexdigest()
    except OSError:
        return "<absent>"


def _ancestor_pids() -> frozenset[int]:
    """This process and its ancestors (their command line names the workspace being cleared)."""
    pids = {os.getpid(), os.getppid()}
    try:
        import psutil  # noqa: PLC0415 - optional dependency
        pids.update(p.pid for p in psutil.Process().parents())
    except (ImportError, OSError, ValueError) as exc:
        _log.warning("_ancestor_pids: could not walk ancestors: %s", exc)
    return frozenset(pids)


def _load_sweep() -> tuple[Any | None, str | None]:
    """Load the deployed ``worktree/sweep_processes.py`` beside this maker: ``(module, None)`` or ``(None, why)``."""
    path = Path(__file__).resolve().parent / "worktree" / "sweep_processes.py"
    if not path.is_file():
        _log.warning("_load_sweep: %s is not deployed", path)
        return None, f"{path.name} is not deployed beside the maker"
    try:
        spec = importlib.util.spec_from_file_location("leafcutter_sweep_processes", path)
        if spec is None or spec.loader is None:
            return None, f"{path.name} cannot be loaded"
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 - any failure to load the check means it is unavailable
        _log.warning("_load_sweep: could not load %s: %s", path, exc)
        return None, f"{path.name} failed to load: {type(exc).__name__}"
    return module, None


def holder_entry(entry: dict[str, Any]) -> dict[str, Any]:
    """Reduce a sweep entry to ``{"pid": int, "name": str}`` (the program's name, never its command line).

    Never raises: any failure to ask the system for the name falls back to the command line's first word.
    """
    pid = 0
    try:
        pid = int(entry.get("pid", 0))
        import psutil  # noqa: PLC0415 - optional dependency
        name = psutil.Process(pid).name()
    except Exception as exc:  # noqa: BLE001 - psutil.Error is not an OSError; the answer must still be built
        _log.warning("holder_entry: no process name for pid %s: %s", pid, exc)
        words = str(entry.get("cmdline", "")).split()
        name = Path(words[0]).name if words else "unknown"
    return {"pid": pid, "name": str(name)}


def program_check(workspace: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Programs working inside, or holding files of, *workspace*: ``(holders, unavailable_reason)``.

    Programs are reported, never killed. When the check cannot run (module
    missing, load error, ``sweep()`` raising, or an error in its result) the
    second element says why and the caller must refuse: unknown is not "none".
    """
    sweep, why = _load_sweep()
    if sweep is None:
        return [], why
    config = {"kill_residual_processes": False, "protected_paths": []}
    try:
        result = sweep.sweep(str(workspace), config=config, exclude_pids=_ancestor_pids())
        error, found = result.error, list(result.conflict_pids)
    except Exception as exc:  # noqa: BLE001 - a failing check must refuse, never read as "no programs"
        _log.warning("program_check: the program check failed for %s: %s", workspace, exc)
        return [], f"it raised {type(exc).__name__}"
    if error:
        return [], str(error)
    return [holder_entry(h) for h in found], None


def is_half_slot(resolved: Path, root: Path) -> bool:
    """True when *resolved* is a folder at ``<root>/<kind>/<slug>`` (depth 2, known kind) with no repository of its own."""
    try:
        parts = resolved.relative_to(root).parts
    except ValueError:
        return False
    return len(parts) == 2 and parts[0] in wg.VALID_KINDS and resolved.is_dir() and not (resolved / ".git").exists()


def remaining_files(folder: Path) -> list[str]:
    """Files left in a half-cleared *folder*, workspace-relative with forward slashes, sorted.

    The workspace record is not counted, and empty sub-folders hold nothing.
    A symlinked folder counts as one entry (it is deleted as a link).
    """
    record = wg.marker_path(folder)
    found: list[str] = []
    for dirpath, dirs, names in os.walk(folder):
        linked = [d for d in dirs if os.path.islink(os.path.join(dirpath, d))]
        for name in [*names, *linked]:
            path = Path(dirpath) / name
            if path != record:
                found.append(path.relative_to(folder).as_posix())
    return sorted(found)


def half_token(folder: Path, marker: dict[str, Any] | None, files: list[str]) -> str:
    """Stateless one-time token bound to this folder, its record and exactly these files with content."""
    binding = {
        "path": os.path.normcase(str(folder)),
        "half_cleared": True,
        "marker": marker,
        "files": [[rel, content_digest(folder, rel)] for rel in files],
    }
    return hashlib.sha256(json.dumps(binding, sort_keys=True).encode("utf-8")).hexdigest()[:32]


def half_refusal(folder: Path, files: list[str], token: str, presented: str | None) -> dict[str, Any]:
    """UNSENT_WORK refusal for a half-cleared folder that still holds files, carrying the fresh token."""
    why = " The discard token presented does not match what the folder holds now." if presented else ""
    return wa.error_answer(
        "UNSENT_WORK",
        f"{folder} is a half-cleared workspace (a clearing stopped part-way and its repository is gone): its "
        f"{len(files)} remaining file(s) cannot be checked against the shared project, so they count as unsent."
        f"{why} Repeat the request with --discard-token to discard them.",
        unsent={"commits": [], "files": files}, discard_token=token,
    )


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-26 [python-coder/fast-lane bo-4300e-2, BO-4300e-2-iv/-v/-vi]:
#   Created. The program check moved here from worktree_remove and now fails
#   closed (a missing, broken or raising check refuses instead of reading as
#   "no programs", closing pr-reviewer M-1 of ticket 08). Half-cleared folders
#   (repository gone) are finished when they hold no files and need the
#   one-time token for exactly their files otherwise. (#fast-lane/BO-4300e-2) (ADR-018)
# ===========================================================================
