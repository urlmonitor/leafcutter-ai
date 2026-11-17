"""
MODULE: _drift_scan_population
GOAL: Enumerate the files check_output_drift.py must census under its scan
    directories, pruning nested git worktrees/repos, ``__pycache__`` and
    git-ignored paths so they are never reported as coverage GAPs.
BUSINESS CONTEXT: In a consumer layout the manifest records
    ``.claude/settings.json``, so ``.claude/`` becomes a scan dir. An
    ``rglob("*")`` then walked all of it, including gitignored
    ``.claude/worktrees/`` (nested git worktrees) and ``.claude/.cache/``,
    producing ~79k GAP lines that blocked every commit although nothing had
    drifted (BP-100k-3-vii).
ARCHITECTURE: Private helper of check_output_drift.py, split out because that
    file is over the 400-line limit and may not grow. ``collect_output_files``
    walks each scan dir with ``os.walk(followlinks=False)`` and prunes:
    (a) ``__pycache__`` and ``.git`` directories; (b) any subdirectory that
    itself holds a ``.git`` entry (file or dir: a nested worktree or repo),
    which needs no git; (c) git-ignored files/dirs, read from ONE
    ``git ls-files -z --others --ignored --exclude-standard --directory`` call
    at the repo root. An ignored dir that is, or contains, the parent dir of a
    recorded manifest key is never pruned, so deployed-output dirs stay fully
    censused. If git is unavailable the walk falls back to (a)+(b) only and
    logs a WARNING. Per-file ``git check-ignore`` is deliberately not used (it
    exits 128 "beyond a symbolic link" on tracked symlink dirs), nor is a
    ``git ls-files`` allow-list (it drops files reached through tracked
    symlinks). Like the rglob it replaces, the walk does not descend into
    symlinked directories.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_TIMEOUT_SECONDS = 30
_ALWAYS_PRUNED_NAMES = frozenset({"__pycache__", ".git"})


def _git_ignored_entries(repo_root: Path) -> tuple[set[str], set[str]] | None:
    """Return the git-ignored ``(files, dirs)`` under ``repo_root``, or None.

    Paths are repo-root-relative with forward slashes; directory entries are
    returned without their trailing slash. None signals that git could not
    answer (missing binary, timeout, non-zero exit, not a repository) and a
    WARNING has been logged.

    Args:
        repo_root: Directory to run git in.

    Returns:
        ``(ignored_files, ignored_dirs)`` or None when git is unavailable.
    """
    cmd = ["git", "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory"]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("git ignore listing failed (%s); scanning without ignore filter", exc)
        return None
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        logger.warning(
            "git ignore listing exited %d (%s); scanning without ignore filter",
            proc.returncode,
            detail,
        )
        return None
    files: set[str] = set()
    dirs: set[str] = set()
    for raw in proc.stdout.decode("utf-8", "replace").split("\0"):
        if raw.endswith("/"):
            dirs.add(raw.rstrip("/"))
        elif raw:
            files.add(raw)
    return files, dirs


def _protected_dirs(output_mappings: dict) -> set[str]:
    """Return every repo-relative dir that is, or contains, a recorded key's parent.

    Args:
        output_mappings: The manifest's ``output_mappings`` dict.

    Returns:
        Set of forward-slash relative directory paths that must not be pruned.
    """
    protected: set[str] = set()
    for key in output_mappings:
        parent = key.rpartition("/")[0]
        while parent and parent not in protected:
            protected.add(parent)
            parent = parent.rpartition("/")[0]
    return protected


def _rel(path: str, repo_root: Path) -> str:
    """Return ``path`` relative to ``repo_root`` with forward slashes."""
    return os.path.relpath(path, repo_root).replace(os.sep, "/")


def collect_output_files(
    output_dirs: list[Path], repo_root: Path, output_mappings: dict
) -> list[Path]:
    """Return all real files under the scan directories (sorted), minus pruned paths.

    Pruned: ``__pycache__`` (generated, non-reproducible bytecode that
    build_phases never writes), ``.git``, subdirectories holding a ``.git``
    entry, and git-ignored paths -- except ignored dirs that are, or contain,
    the parent dir of a recorded manifest key, and ignored files that are
    themselves recorded keys. Symlinked directories are not descended into
    (matching the pathlib ``rglob`` this replaces); symlinked files count.

    Args:
        output_dirs: Absolute paths of directories to scan; missing ones are skipped.
        repo_root: Absolute repository root every manifest key is relative to.
        output_mappings: The manifest's ``output_mappings`` dict.

    Returns:
        Sorted list of absolute Path objects for every file kept.
    """
    ignored = _git_ignored_entries(repo_root)
    ignored_files, ignored_dirs = ignored if ignored is not None else (set(), set())
    protected = _protected_dirs(output_mappings)
    found: set[Path] = set()
    for scan_dir in output_dirs:
        if not scan_dir.is_dir():
            continue
        for root, dirnames, filenames in os.walk(scan_dir, followlinks=False):
            prefix = _rel(root, repo_root) + "/"
            if prefix == "./":
                prefix = ""
            dirnames[:] = [
                d
                for d in dirnames
                if d not in _ALWAYS_PRUNED_NAMES
                and not os.path.lexists(os.path.join(root, d, ".git"))
                and not _is_pruned_ignored(prefix + d, ignored_dirs, protected)
            ]
            for name in filenames:
                rel = prefix + name
                if rel in ignored_files and rel not in output_mappings:
                    continue
                path = Path(root) / name
                if path.is_file():
                    found.add(path)
    return sorted(found)


def _is_pruned_ignored(rel_dir: str, ignored_dirs: set[str], protected: set[str]) -> bool:
    """Return True when ``rel_dir`` is git-ignored and not a protected output dir.

    Args:
        rel_dir: Repo-relative forward-slash directory path.
        ignored_dirs: Ignored directory entries from git.
        protected: Dirs that are, or contain, a recorded key's parent.

    Returns:
        True when the directory should be pruned from the walk.
    """
    return rel_dir in ignored_dirs and rel_dir not in protected
