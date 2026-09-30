"""
MODULE: kernel.capabilities.retrieval.versioning
GOAL: Resolve the repository revision (commit plus dirty flag) stamped on every evidence item.
BUSINESS CONTEXT: Evidence is only as trustworthy as its provenance: a reader must see which
    revision of the source an excerpt came from and whether the working tree had local edits
    (Rev 3 section 10.3).
ARCHITECTURE: Prefers the revision the run already pinned in Scope. Otherwise runs two git
    commands inside try (IO-001), caches the answer per run and root, and reports None when git
    is unavailable so the caller records a limitation instead of inventing a revision.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

from kernel.contracts.evidence import SourceVersion
from kernel.contracts.task import Scope

logger = logging.getLogger(__name__)

GIT_TIMEOUT_SECONDS = 10.0
MAX_CACHED_RUNS = 64
_CACHE: dict[tuple[str, str], SourceVersion | None] = {}


def _git(root: Path, *args: str) -> str | None:
    """Run git in root and return stdout, or None on any failure (logged at WARNING)."""
    try:
        done = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True,
                              timeout=GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("git %s failed: %s", args[0], exc)
        return None
    return done.stdout if done.returncode == 0 else None


def resolve_source_version(run_id: str, scope: Scope) -> SourceVersion | None:
    """Return the revision of the repository the scope points at, or None if unknown.

    Args:
        run_id: Run id (cache key, so git is asked once per run).
        scope: The run scope; `scope.revision` wins when present.

    Returns:
        SourceVersion | None: Commit and dirty flag, or None when unavailable.
    """
    if scope.revision is not None and scope.revision.commit:
        return SourceVersion(commit=scope.revision.commit, dirty=scope.revision.dirty)
    key = (run_id, scope.repository_root)
    if key not in _CACHE:
        if len(_CACHE) >= MAX_CACHED_RUNS:
            _CACHE.clear()
        root = Path(scope.repository_root)
        head = _git(root, "rev-parse", "HEAD")
        status = _git(root, "status", "--porcelain") if head else None
        _CACHE[key] = (SourceVersion(commit=head.strip(), dirty=bool(status and status.strip()))
                       if head else None)
    return _CACHE[key]


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-30 23:00 [python-coder]: The cache is module-level keyed by run id because executors
#   are built per invocation; it is cleared when it grows past MAX_CACHED_RUNS.
#   (#KernelBootstrapV0/P5)
# ====================================================================
