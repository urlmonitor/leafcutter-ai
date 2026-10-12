"""
Merge-parent snapshot helper for check_folder_density.py.

During a merge commit, HEAD is only ONE of the commit's parents. Folders that
grew dense on the merged-in side (MERGE_HEAD) are pre-existing from the point
of view of the merge, so the density hook must also read each MERGE_HEAD
parent's tree when building its BEFORE snapshot.

MODULE: _density_parents.py
GOAL: List the files of every MERGE_HEAD parent tree while a merge is in progress.
BUSINESS CONTEXT: Lets a branch take in main without a hook skip when main
    already pushed unrelated folders over the density limit.
ARCHITECTURE: Not needed.
"""

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def get_merge_head_shas() -> list[str]:
    """
    Read the commit shas recorded in MERGE_HEAD.

    The file holds one sha per line (several for an octopus merge).

    Returns:
        List of shas; empty when no merge is in progress.

    Raises:
        subprocess.CalledProcessError: ``git rev-parse --git-path`` failed.
        OSError: git could not run or MERGE_HEAD could not be read.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-path", "MERGE_HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("git rev-parse --git-path MERGE_HEAD failed: %s", exc)
        raise
    merge_head = Path(result.stdout.strip())
    if not merge_head.is_file():
        return []
    try:
        text = merge_head.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read %s: %s", merge_head, exc)
        raise
    return [line.strip() for line in text.splitlines() if line.strip()]


def get_merge_parent_files() -> list[list[str]]:
    """
    List the files of every MERGE_HEAD parent tree.

    Returns:
        One file list per MERGE_HEAD sha; empty list when no merge is in
        progress (so a normal commit is unaffected).

    Raises:
        subprocess.CalledProcessError: ``git ls-tree`` failed for a parent.
    """
    snapshots: list[list[str]] = []
    for sha in get_merge_head_shas():
        try:
            result = subprocess.run(
                ["git", "ls-tree", "-r", sha, "--name-only"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )
        except (subprocess.CalledProcessError, OSError) as exc:
            logger.warning("git ls-tree -r %s --name-only failed: %s", sha, exc)
            raise
        snapshots.append([f for f in result.stdout.strip().split("\n") if f])
    return snapshots
