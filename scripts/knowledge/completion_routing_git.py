"""
MODULE: completion_routing_git
GOAL: Read-only git questions the INF-700a-5 durability step asks about one
    isolated working directory: is this text already on the base branch,
    would changing this file conflict with it, what did the last commit
    actually carry, and where is this working directory's private git dir.
BUSINESS CONTEXT: BrainCandy's 2026-10-08 decision fixes the confirmation
    rule: a record is never marked routed at commit time; a later run claims
    it only once its text is already on the base branch (origin/main), and a
    publication is judged by asking the repository what the commit contains,
    never by the commit agent's own reported status (INF-700a-5-i
    it_requirements). Every one of those answers is a git read, collected
    here so the routing module stays about records and the CLI stays about
    arguments.
ARCHITECTURE: Helper module for the Knowledge System component
    (docs/architecture/components/knowledge-system.md), loaded by path by
    ``completion_routing.py`` (same sibling-loading convention as
    ``harvest_learnings.py``). Every call names its working directory
    explicitly via ``git -C`` -- nothing here resolves against the process's
    current directory. Every call is fail-open: a git failure is logged and
    answered with ``None``, and each caller decides which way ``None`` fails
    (always toward re-routing, never toward a mark).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger("completion_routing")

GIT_TIMEOUT_SECONDS = 30


def run_git(working_dir: Path, *args: str) -> str | None:
    """Run ``git -C <working_dir> <args>`` and return stdout, or ``None``.

    External I/O: a non-zero exit, a timeout or a missing git binary is
    logged at WARNING and answered with ``None`` rather than raised -- the
    routing step must never fail the unit of work.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(working_dir), *args],
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("git %s in %s could not run: %s", " ".join(args), working_dir, exc)
        return None
    if proc.returncode != 0:
        logger.warning(
            "git %s in %s exited %d: %s",
            " ".join(args),
            working_dir,
            proc.returncode,
            proc.stderr.strip(),
        )
        return None
    return proc.stdout


def refresh_base(working_dir: Path, base_ref: str) -> None:
    """Best-effort fetch of *base_ref*'s remote branch, so "already on the
    base branch" is answered against the current merged tree rather than the
    one the working directory was created from. A failed fetch leaves the
    stale ref in place; a stale ref can only cause a re-route (a duplicate),
    never a mark."""
    remote, _, branch = base_ref.partition("/")
    if branch:
        run_git(working_dir, "fetch", "--quiet", remote, branch)


def show_file(working_dir: Path, ref: str, rel_path: str) -> str | None:
    """Return *rel_path*'s content at *ref*, or ``None`` if absent/unreadable."""
    return run_git(working_dir, "show", f"{ref}:{rel_path}")


def blob_id(working_dir: Path, ref: str, rel_path: str) -> str | None:
    """Return the blob id of *rel_path* at *ref*, or ``None`` when absent."""
    out = run_git(working_dir, "rev-parse", "--verify", "--quiet", f"{ref}:{rel_path}")
    return out.strip() if out else None


def merge_base(working_dir: Path, base_ref: str) -> str | None:
    """Return the merge-base of HEAD and *base_ref*, or ``None``."""
    out = run_git(working_dir, "merge-base", "HEAD", base_ref)
    return out.strip() if out else None


def ref_exists(working_dir: Path, ref: str) -> bool:
    """True when *ref* resolves to a commit in *working_dir*'s repository."""
    return run_git(working_dir, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}") is not None


def private_git_dir(working_dir: Path) -> Path | None:
    """Return this working directory's OWN git dir (per-worktree), or ``None``.

    The run record lives here: it is untracked by construction, so no commit
    phase -- including one that stages with ``git add -A`` -- can carry it,
    and it is removed with the working directory it describes.
    """
    out = run_git(working_dir, "rev-parse", "--absolute-git-dir")
    return Path(out.strip()) if out else None


def would_conflict(working_dir: Path, base_ref: str, rel_path: str) -> bool:
    """True when the base branch changed *rel_path* since this branch left it.

    Appending to a file the base branch has also changed since the merge-base
    is what makes carrying the change conflict with the merged tree
    (INF-700a-5-i: "carrying the change conflicts with the merged tree"). With
    no base ref or merge-base there is nothing to conflict with.
    """
    if not ref_exists(working_dir, base_ref):
        return False
    base = merge_base(working_dir, base_ref)
    if base is None:
        return False
    return blob_id(working_dir, base_ref, rel_path) != blob_id(working_dir, base, rel_path)


def text_on_ref(working_dir: Path, ref: str, rel_path: str, text: str) -> bool:
    """True when *text* is present in *rel_path* at *ref*."""
    content = show_file(working_dir, ref, rel_path)
    return content is not None and text in content


# DECISION HISTORY
# ================================================================================
# - 2026-10-08 [python-coder/INF-700a-5 wiring]: Created to give the durability
#   step the read-only git answers BrainCandy's check-the-base-branch
#   confirmation rule and INF-700a-5-i's observe-the-commit rule need. Kept
#   separate from completion_routing.py so that module stays under the
#   check-file-size limit. (#INF-700a-5)
