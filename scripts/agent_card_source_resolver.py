"""
MODULE: agent_card_source_resolver
GOAL: Resolve a knowledge-channel source string from an agent card to a real,
    tracked file in the package tree, ignoring git-ignored local deployments.
BUSINESS CONTEXT: Split out of generate_agent_cards.py (file-size ratchet,
    GE-127b-1) so that generated card links never point at deployed copies such
    as ``.claude/`` or ``.leafcutter/`` and the build leaves tracked files clean.
ARCHITECTURE: Pure lookup helpers. ``_resolve_source_to_path`` tries three
    strategies (direct path, directory-hint match, unique filename match);
    ``_is_git_ignored`` shells out to ``git check-ignore`` and fails open (not
    ignored) when git is unavailable. generate_agent_cards.py re-exports both
    names, so ``generate_agent_cards._resolve_source_to_path`` keeps working.
    Build-time only: not deployed to consumer installs.

DECISION HISTORY:
    2026-10-06 -- Extracted from generate_agent_cards.py together with the
        git-ignored skip in strategies 2 and 3
        (TICKET-20261002-WorktreeBootstrapLeavesTrackedFilesDirty).
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

_log = logging.getLogger(__name__)

# File extensions and path patterns considered "file-like" sources in
# knowledge_channels.  A source string matching any of these is a candidate
# for hyperlink conversion when the file exists on disk.
_FILE_EXTENSIONS = frozenset(
    {".md", ".py", ".yaml", ".yml", ".json", ".sh", ".toml", ".txt"}
)


def _is_git_ignored(path: Path, package_root: Path) -> bool:
    """Return True when git reports *path* as ignored (e.g. a deployed copy).

    Card links must not depend on gitignored local deployments such as
    ``.claude/`` or ``.leafcutter/``. When git is unavailable or
    *package_root* is not a repository, nothing is treated as ignored.

    Args:
        path: Candidate file path.
        package_root: Repository root used as git's working directory.

    Returns:
        True only when ``git check-ignore`` exits 0 for *path*.
    """
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(path)],
            cwd=package_root,
            capture_output=True,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("git check-ignore failed for %s: %s", path, exc)
        return False
    return result.returncode == 0


def _resolve_source_to_path(
    source: str,
    package_root: Path,
) -> Path | None:
    """Attempt to resolve a knowledge-channel source string to a real file.

    Tries the following strategies in order and returns the first match:

    1. Treat *source* as a path relative to *package_root*.
    2. When the source token has a directory-hinting prefix word (e.g.
       ``"signoff SKILL.md"``), look for a file at
       ``<any-dir-containing-prefix-word>/<filename>`` within the package tree.
    3. Walk the package tree looking for any file whose name matches the
       filename component of *source* (shallow search — only 4 levels deep).

    Args:
        source: Raw source string from a knowledge_channels entry, e.g.
            ``"Root CLAUDE.md"`` or ``"signoff SKILL.md"``.
        package_root: Absolute path to the package root (repo root).

    Strategies 2 and 3 skip git-ignored files (deployed copies).

    Returns:
        Resolved :class:`~pathlib.Path` if found on disk, else ``None``.
    """
    # Strategy 1: direct relative path.
    candidate = package_root / source
    if candidate.exists():
        return candidate

    # Extract filename token (last word that carries a known extension).
    tokens = source.split()
    filename: str | None = None
    filename_idx: int = -1
    for i, token in reversed(list(enumerate(tokens))):
        if Path(token).suffix in _FILE_EXTENSIONS:
            filename = token
            filename_idx = i
            break

    if filename is None:
        return None

    # Strategy 2: directory-hint match.  When there is a word before the
    # filename token, treat that word as a hint for the parent directory name.
    if filename_idx > 0:
        hint = tokens[filename_idx - 1].lower()
        for root_dir, _dirs, files in os.walk(package_root):
            root_path = Path(root_dir)
            try:
                rel_depth = len(root_path.relative_to(package_root).parts)
            except ValueError:
                continue
            if rel_depth > 5:
                _dirs.clear()
                continue
            # Parent directory name must contain the hint word.
            if hint in root_path.name.lower() and filename in files:
                if _is_git_ignored(root_path / filename, package_root):
                    continue
                return root_path / filename

    # Strategy 3: filename-only match (up to 4 levels deep).
    # Collect ALL matches; resolve only when exactly one unique path is found.
    # An ambiguous match (multiple locations share the same basename) returns None
    # so that the caller's missing-doc / plain-text fallback applies rather than
    # producing a non-deterministic hyperlink.
    matches: list[Path] = []
    for root_dir, _dirs, files in os.walk(package_root):
        root_path = Path(root_dir)
        try:
            rel_depth = len(root_path.relative_to(package_root).parts)
        except ValueError:
            continue
        if rel_depth > 4:
            _dirs.clear()  # prune deeper subtrees
            continue
        if filename in files and not _is_git_ignored(
            root_path / filename, package_root
        ):
            matches.append(root_path / filename)

    unique_matches = sorted(set(matches))
    if len(unique_matches) == 1:
        return unique_matches[0]
    return None
