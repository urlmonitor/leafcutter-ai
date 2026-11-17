"""
MODULE: _rc_changed
GOAL: Find the requirement record files a stage left changed against a git revision, so the
    rule check can find the stage's records itself and report what the stage commit must stage.
BUSINESS CONTEXT: ACD-2500a-1. The check used to trust the author agent's list of written
    ids; a typo'd list read as all clear and a parent repaired by the check was never
    committed. `--changed-since REV` asks git instead: every record file under the store
    that is modified, added or untracked relative to REV in the worktree.
ARCHITECTURE: Pure subprocess wrapper over `git diff --name-only` plus
    `git ls-files --others --exclude-standard`, both restricted to the store path and run with
    the repo root as the working directory (so paths are repo-root-relative). Deleted files and
    the index registry are skipped. Any git failure raises `ChangedError`; the orchestrator
    turns it into a `failed` finding. Deployed flat into <root>/scripts/ac_store/
    (AC_STORE_DEPLOY_MAP).

DECISION HISTORY:
  - 2026-10-14 [python-coder/ACD-2500a-1]: Created for review fixes H-1 / M-1 (G2).
"""

from __future__ import annotations

import subprocess
from pathlib import Path, PurePosixPath

from _rc_records import to_rel_posix

_REGISTRY_FILE = "index.yaml"
_SUFFIXES = (".yaml", ".yml")


class ChangedError(RuntimeError):
    """Raised when git cannot say which record files changed."""


def _git_names(repo_root: Path, argv: list[str]) -> list[str]:
    """NUL-separated path list printed by `git <argv>` run in `repo_root`."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "-c", "core.quotepath=false", *argv],
            capture_output=True, timeout=60, check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        reason = f"git could not run: {exc}"
        raise ChangedError(reason) from exc
    if proc.returncode != 0:
        reason = f"git {argv[0]} failed: {proc.stderr.decode('utf-8', 'replace').strip()[:300]}"
        raise ChangedError(reason)
    return [name for name in proc.stdout.decode("utf-8").split("\0") if name]


def changed_record_files(repo_root: Path, store_root: Path, rev: str) -> list[str]:
    """Sorted repo-relative POSIX paths of record files under `store_root` changed against `rev`."""
    store_rel = to_rel_posix(store_root, repo_root)
    if PurePosixPath(store_rel).is_absolute() or ":" in store_rel[:3]:
        reason = f"store root {store_root} is outside the repository {repo_root}"
        raise ChangedError(reason)
    diff = _git_names(repo_root, ["diff", "--name-only", "-z", "--relative", "--diff-filter=d", rev, "--", store_rel])
    untracked = _git_names(repo_root, ["ls-files", "-z", "--others", "--exclude-standard", "--", store_rel])
    names = {
        n for n in (*diff, *untracked)
        if PurePosixPath(n).suffix.lower() in _SUFFIXES
        and PurePosixPath(n).name != _REGISTRY_FILE
        and (Path(repo_root) / n).is_file()
    }
    return sorted(names)
