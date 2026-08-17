"""
MODULE: ensure_precommit_config
GOAL: Self-healing pre-commit hook that re-materializes .pre-commit-config.yaml in worktrees.
BUSINESS CONTEXT: Worktrees do not inherit .pre-commit-config.yaml from the main working
    tree. When a worktree is created from origin/main, the .leafcutter symlink and
    populated .leafcutter/ directory are absent, causing all pre-commit hooks to be
    silently skipped. This hook runs at index 0 (before all other hooks) and re-
    materializes the config on every commit, ensuring quality gates fire even in
    fresh worktrees. Atomic (write-temp-then-rename) and idempotent (no-op when config
    already present). Fail-closed: exits 1 when config cannot be established.
ARCHITECTURE: Standalone script — no imports from sibling modules — so it can run in
    isolated worktrees where sys.path may not include the repo root. Two-phase re-
    materialization: (1) create .leafcutter symlink to main tree .leafcutter (preferred,
    POSIX), or (2) copy .pre-commit-config.yaml directly (NTFS/Windows fallback). Main
    tree root resolved via git commondir, with a script-location fallback for test
    environments and edge cases. Registered at hooks_manifest.hooks[0] in
    commit_guardian.json. See ADR-031.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [EPIC-WorktreeQualityGateGuard/05]: Initial implementation.
  Self-healing hook that re-materializes .pre-commit-config.yaml via .leafcutter
  symlink or direct file copy. Registered at manifest index 0. Uses two-phase
  main-tree resolution: git commondir first, script-location fallback. Atomic
  copy uses write-temp-then-rename (os.replace). Idempotent: exits 0 immediately
  when config already present. Fail-closed: exits 1 when config cannot be
  established. See ADR-031.
====================================================================
"""

from __future__ import annotations

import logging
import os
import shutil
import sys
from pathlib import Path

_log = logging.getLogger(__name__)

# Two levels up from scripts/commit_guardian/ → output root (deployed repo root)
_SCRIPT_DIR = Path(__file__).resolve().parent
_PACKAGE_ROOT = _SCRIPT_DIR.parents[1]


def _resolve_git_commondir(cwd: Path) -> Path:
    """Resolve the shared .git directory (commondir) for a worktree or main tree.

    For git worktrees .git is a file whose content is ``gitdir: <path>``; the
    referenced gitdir contains a ``commondir`` file pointing (relative) to the
    main .git directory that holds the shared hooks. For the main working tree
    .git is a directory that is itself the commondir.

    Args:
        cwd: The working directory to resolve from.

    Returns:
        Absolute path to the shared .git directory (the commondir).

    Raises:
        FileNotFoundError: When .git does not exist under cwd.
        OSError: When the .git file or commondir file cannot be read.
    """
    git_path = cwd / ".git"
    if not git_path.exists():
        raise FileNotFoundError(f".git not found at {cwd}")  # noqa: TRY003

    if git_path.is_file():
        try:
            content = git_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            _log.warning("_resolve_git_commondir: cannot read .git file: %s", exc)
            raise

        prefix = "gitdir: "
        if content.startswith(prefix):
            gitdir_str = content[len(prefix):].strip()
            gitdir = Path(gitdir_str)
            if not gitdir.is_absolute():
                gitdir = (cwd / gitdir).resolve()
        else:
            gitdir = Path(content).resolve()
    else:
        gitdir = git_path.resolve()

    commondir_file = gitdir / "commondir"
    if commondir_file.exists():
        try:
            rel = commondir_file.read_text(encoding="utf-8").strip()
        except OSError as exc:
            _log.warning("_resolve_git_commondir: cannot read commondir file: %s", exc)
            raise
        return (gitdir / rel).resolve()

    return gitdir


def _resolve_config_path(worktree_root: Path) -> Path | None:
    """Check if .pre-commit-config.yaml already resolves in the worktree root.

    Resolution order: .leafcutter/pre-commit-config.yaml first (canonical
    location inside the .leafcutter directory or symlink target), then
    .pre-commit-config.yaml directly in worktree_root.

    Args:
        worktree_root: The worktree root directory to check.

    Returns:
        Path to the config file if found, or None if neither location exists.
    """
    leafcutter_config = worktree_root / ".leafcutter" / "pre-commit-config.yaml"
    if leafcutter_config.exists():
        return leafcutter_config
    direct_config = worktree_root / ".pre-commit-config.yaml"
    if direct_config.exists():
        return direct_config
    return None


def _find_main_tree_root(worktree_root: Path) -> Path | None:
    """Resolve the main git working tree root for config source lookup.

    Tries git commondir resolution first. Falls back to the script's own
    package root (_PACKAGE_ROOT) when git resolution is unavailable — for
    example in test environments or fresh directories without a .git entry.

    Args:
        worktree_root: The worktree root to resolve from.

    Returns:
        Path to the main tree root directory, or None when resolution fails.
    """
    # Primary path: derive from git commondir (commondir parent = main tree root)
    try:
        commondir = _resolve_git_commondir(worktree_root)
        return commondir.parent
    except (FileNotFoundError, OSError) as exc:
        _log.warning(
            "_find_main_tree_root: git resolution failed for %s (%s); trying script fallback",
            worktree_root,
            exc,
        )

    # Fallback: use the package root derived from this script's installed location
    if _PACKAGE_ROOT.exists():
        _log.warning(
            "_find_main_tree_root: using script-based fallback root: %s",
            _PACKAGE_ROOT,
        )
        return _PACKAGE_ROOT

    _log.warning("_find_main_tree_root: all resolution strategies exhausted")
    return None


def _atomic_copy(src: Path, dest: Path) -> None:
    """Copy src to dest atomically using write-temp-then-rename.

    Writes to a temporary path first (.tmp suffix appended to dest name),
    then renames atomically. If rename fails, the temporary file is cleaned
    up before re-raising the original exception.

    Args:
        src: Source file to copy from.
        dest: Destination path to install.

    Raises:
        OSError: When the copy or rename step fails (temp file is cleaned up
            before the exception propagates).
    """
    tmp_path = Path(str(dest) + ".tmp")
    try:
        shutil.copy2(src, tmp_path)
        os.replace(tmp_path, dest)
    except OSError:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError as cleanup_exc:
            _log.warning("_atomic_copy: temp file cleanup failed: %s", cleanup_exc)
        raise


def ensure_config(worktree_root: Path) -> bool:
    """Re-materialize .pre-commit-config.yaml in the worktree if absent.

    Checks whether .pre-commit-config.yaml resolves to a readable file in the
    worktree root. If already present, returns True immediately (idempotent
    no-op). If absent, attempts two re-materialization strategies in order:

    1. Create a .leafcutter symlink pointing to the main tree's .leafcutter
       directory, then verify .leafcutter/pre-commit-config.yaml is readable.
    2. If the symlink fails (OSError, e.g. NTFS/Windows), copy the main tree's
       .pre-commit-config.yaml directly using an atomic write-temp-then-rename
       pattern so partial failures leave no residue.

    Fail-closed: returns False (never raises) when config cannot be established
    after both strategies are exhausted.

    Args:
        worktree_root: The worktree root directory to check and potentially
            re-materialize.

    Returns:
        True when .pre-commit-config.yaml resolves in worktree_root after this
        call. False when re-materialization fails (fail-closed).
    """
    # Step 1: idempotent fast-exit — config already present
    if _resolve_config_path(worktree_root) is not None:
        return True

    # Step 2: locate the main tree root (git resolution or script fallback)
    main_tree_root = _find_main_tree_root(worktree_root)
    if main_tree_root is None:
        _log.warning(
            "ensure_config: cannot resolve main tree root for worktree %s; giving up",
            worktree_root,
        )
        return False

    leafcutter_src = main_tree_root / ".leafcutter"
    leafcutter_dest = worktree_root / ".leafcutter"

    # Step 3: attempt .leafcutter symlink (preferred — preserves all hook configs)
    symlink_ok = False
    try:
        os.symlink(leafcutter_src, leafcutter_dest)
        if (leafcutter_dest / "pre-commit-config.yaml").exists():
            symlink_ok = True
        else:
            _log.warning(
                "ensure_config: symlink created but .leafcutter/pre-commit-config.yaml "
                "not readable — symlink target may be empty: %s",
                leafcutter_src,
            )
    except OSError as exc:
        _log.warning(
            "ensure_config: symlink creation failed (%s); falling back to direct copy",
            exc,
        )

    if symlink_ok:
        return True

    # Step 4: copy fallback — locate source config file
    config_src = leafcutter_src / "pre-commit-config.yaml"
    if not config_src.exists():
        # Secondary lookup: bare config at main tree root (non-.leafcutter layout)
        config_src = main_tree_root / ".pre-commit-config.yaml"

    if not config_src.exists():
        _log.warning(
            "ensure_config: source .pre-commit-config.yaml not found under %s; "
            "cannot complete copy fallback",
            main_tree_root,
        )
        return False

    dest = worktree_root / ".pre-commit-config.yaml"
    try:
        _atomic_copy(config_src, dest)
    except OSError as exc:
        _log.warning("ensure_config: atomic copy to %s failed: %s", dest, exc)
        return False

    return True


def main() -> None:
    """CLI entry point: re-materialize .pre-commit-config.yaml in the current directory.

    Reads Path.cwd() as the worktree root, calls ensure_config(), and exits 0 on
    success or 1 on failure (fail-closed). Called by the pre-commit framework at
    every commit (registered at hooks_manifest.hooks[0] in commit_guardian.json).
    """
    worktree_root = Path.cwd()
    success = ensure_config(worktree_root)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
