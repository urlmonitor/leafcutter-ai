"""
MODULE: _hook_trigger_tracked_paths
GOAL: Tracked-path acquisition (``git ls-files``) for
    check_hook_trigger_reachability.py's per-gate reachability rule
    (BP-100k-4 / BP-100k-4-i). Split out into its own sibling module
    (BP-100n-4) rather than folded into either existing sibling —
    _hook_trigger_census.py owns the disk-side gate-SCRIPT inventory and
    registry loading, _hook_trigger_reachability_helpers.py owns the
    per-gate REACHABILITY RULE that consumes a tracked-path list once it has
    one; acquiring that list via git is a third, distinct concern (this
    process's own working copy, not the gate-script directory and not the
    registry), so it gets its own well-named module rather than being
    forced into either.
BUSINESS CONTEXT: See check_hook_trigger_reachability.py's own DECISION
    HISTORY for the full BP-100k-4 / BP-100k-4-i / BP-100n-4 account. In
    short: a gate's ``files`` regex is matched against exactly this list, so
    an unobtainable or successfully-empty tracked-path set is the same
    epistemic state as the lookup failing outright — no evidence either
    way — and must never be treated as proof that every files-triggered
    gate is unreachable.
ARCHITECTURE: ``get_tracked_paths`` enumerates tracked files and existing,
    unignored files Git could stage next. It returns None on I/O error or a
    non-zero Git exit, never an empty list standing in for failure.
    ``resolve_tracked_paths_or_reason`` layers the BP-100k-4 round-2
    hardening (M) zero-tracked-path floor on top: a git call that succeeds
    but returns nothing (fresh clone/submodule/shallow checkout before the
    first ``git add``) is floor-checked into the same ``(None, reason)``
    shape as an outright failure, so the caller's INDETERMINATE branch
    handles both uniformly.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_GATE_NAME = "check-hook-trigger-reachability"

# Wall-clock bound for the ``git ls-files`` subprocess call.
_SUBPROCESS_TIMEOUT_SECONDS = 20


def get_tracked_paths(cwd: Path) -> list[str] | None:
    """Return existing paths Git tracks or can stage next.

    Args:
        cwd: Working directory to run ``git ls-files`` in.

    Returns:
        Tracked and unignored untracked repo-root-relative paths, or None
        if Git could not enumerate them.
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"{_GATE_NAME}: WARNING - could not enumerate stageable paths: {exc}", file=sys.stderr)
        return None

    if result.returncode != 0:
        print(
            f"{_GATE_NAME}: WARNING - stageable-path enumeration exited "
            f"{result.returncode}: {result.stderr.strip()}",
            file=sys.stderr,
        )
        return None

    return [line for line in result.stdout.splitlines() if line]


def resolve_tracked_paths_or_reason(cwd: Path) -> tuple[list[str] | None, str | None]:
    """Obtain the stageable-path set and floor-check it against emptiness.

    BP-100k-4 round-2 hardening (M / zero-path finding): a
    SUCCESSFUL empty result (Git exited 0 with no paths) is
    the same epistemic state as the lookup failing outright: no evidence
    either way. It must never be treated as proof that every
    files-triggered gate is unreachable.

    Args:
        cwd: Working directory to run ``git ls-files`` in.

    Returns:
        A ``(tracked_paths, reason)`` pair: ``(paths, None)`` on success, or
        ``(None, reason)`` with a diagnostic suitable for the
        ``INDETERMINATE: reason=<...>`` line.
    """
    tracked_paths = get_tracked_paths(cwd)
    if tracked_paths is None:
        return None, "could not obtain the repository's stageable-path set via 'git ls-files'"
    if not tracked_paths:
        return None, (
            "the repository has zero stageable paths ('git ls-files' succeeded "
            "but returned no paths) — reachability cannot be established "
            "from no evidence"
        )
    return tracked_paths, None


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-07 [python-coder/BP-100n-4, file-size split]: created module.
#   check_hook_trigger_reachability.py exceeded the 400-line file-size cap
#   (424 counted lines); moving these two functions into
#   _hook_trigger_reachability_helpers.py instead (the first split target
#   tried) would have pushed THAT file over the cap in turn (406 counted
#   lines), so tracked-path acquisition — a distinct concern from both the
#   disk-side script census and the per-gate reachability rule — got its
#   own sibling module rather than being forced into either. Pure move: no
#   behavior change. See check_hook_trigger_reachability.py's own DECISION
#   HISTORY for the full integration.
#   (#BP-100n-4)
# ====================================================================
