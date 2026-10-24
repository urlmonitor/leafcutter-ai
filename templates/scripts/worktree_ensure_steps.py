"""
MODULE: worktree_ensure_steps
GOAL: The git steps of ``worktree.py ensure`` that decide where a workspace's
    objects come from and what its remote-tracking refs say -- clone the main
    checkout, strip what the main checkout owns, point origin at the hub, fetch
    from the hub with pruning -- plus the contract fields of an ok answer
    (AC BO-4300a-1 IT3, BO-4300d-4 IT0, BO-4300c-2).
BUSINESS CONTEXT: Cloning the hub works over the network only, and a ``--local``
    clone of an ssh or ``file://`` URL is a full copy with no hardlinks that can
    prompt for credentials. Cloning the main checkout's own path is always a
    hardlinked local clone. The clone then carries the main checkout's local
    branches as ``refs/remotes/origin/*`` (read by
    ``worktree_identity.hub_lines`` as hub lines) and as ``refs/heads/*``, plus
    its tags, so HEAD is detached and all of those are deleted: the line of
    work comes only from the hub's refs, even when the main checkout stands on
    the very branch being resumed. A failed step answers with a short ``step``
    name and a message holding no git text; git's own text goes to stderr only
    (BO-4300c-2).
ARCHITECTURE: Stdlib-only helper imported by ``worktree.py`` (a sibling under
    ``templates/scripts/`` and, after deploy, under ``<install-root>/scripts/``).
    All git calls go through ``worktree_git.run_git``; answers are built by
    ``worktree_answer.error_answer``. The hub may be a ``file://`` URL, an ssh
    URL or a path -- this module never parses it, it only hands the exact
    string to ``git remote set-url``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg
import worktree_paths as wp

_log = logging.getLogger(__name__)

BASE_REF = "origin/main"
FETCH_OK, FETCH_FAILED, FETCH_SKIPPED = "ok", "failed", "skipped"
_CHUNK = 100  # ref names per git call: a repository can hold thousands of tags


def now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a trailing 'Z'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_marker(kind: str, slug: str, branch: str, hub: str, repo_root: Path, base_commit: str | None,
                   state: str, checks: dict[str, bool] | None = None, *, workspace: Path) -> dict[str, Any]:
    """Assemble the marker dict this maker always writes (schema_version 1).

    ``hub`` and ``project_root`` are stored relative to *workspace* (BO-4300b-5:
    no absolute path in one platform's spelling), so either shell recognises it.
    """
    marker: dict[str, Any] = {
        "schema_version": 1,
        "kind": kind,
        "slug": slug,
        "branch": branch,
        "hub": wp.portable(hub, workspace),
        "project_root": wp.portable(str(repo_root), workspace),
        "base_commit": base_commit,
        "maker_version": wg.MAKER_VERSION,
        "state": state,
        "created_at": now_iso(),
    }
    if checks is not None:
        marker["checks"] = checks
    return marker


def step_error(code: str, step: str, message: str) -> dict[str, Any]:
    """Build a non-ok answer naming the failed *step*; *message* must hold no git text."""
    return wa.error_answer(code, message, step=step)


def _failed(step: str, what: str) -> dict[str, Any]:
    """A GIT_FAILED answer for *step*; *what* says what could not be done (no git text)."""
    return step_error("GIT_FAILED", step, f"Could not {what}.")


def _delete_refs(workspace: Path, delete_cmd: list[str], names: list[str]) -> bool:
    """Run ``git <delete_cmd> <names...>`` in chunks; True when every chunk succeeded."""
    for i in range(0, len(names), _CHUNK):
        if wg.run_git([*delete_cmd, *names[i:i + _CHUNK]], workspace).returncode != 0:
            return False
    return True


def _ref_names(workspace: Path, prefix: str) -> list[str]:
    """Short ref names under *prefix* (``refs/heads/`` -> ``main``)."""
    out = wg.run_git(["for-each-ref", "--format=%(refname)", prefix], workspace).stdout.split()
    return [ref[len(prefix):] for ref in out]


def _strip_local_refs(workspace: Path) -> dict[str, Any] | None:
    """Detach HEAD, then delete every local branch and tag copied from the main checkout."""
    head = wg.run_git(["rev-parse", "--verify", "-q", "HEAD"], workspace).stdout.strip()
    if head and wg.run_git(["update-ref", "--no-deref", "HEAD", head], workspace).returncode != 0:
        return _failed("detach-head", "detach the workspace's HEAD")
    if not _delete_refs(workspace, ["branch", "-D"], _ref_names(workspace, "refs/heads/")):
        return _failed("strip-local-refs", "remove the main checkout's local branches from the workspace")
    if not _delete_refs(workspace, ["tag", "-d"], _ref_names(workspace, "refs/tags/")):
        return _failed("strip-local-refs", "remove the main checkout's tags from the workspace")
    return None


def _drop_alternates(workspace: Path) -> dict[str, Any] | None:
    """Make the clone self-contained: pack in any alternate objects, then remove the alternates file."""
    alternates = workspace / ".git" / "objects" / "info" / "alternates"
    if not alternates.exists():
        return None
    if wg.run_git(["repack", "-a", "-d"], workspace).returncode != 0:
        return _failed("alternates", "make the workspace independent of the main checkout's object store")
    try:
        alternates.unlink()
    except OSError as exc:
        _log.warning("_drop_alternates: could not remove %s: %s", alternates, exc)
        return _failed("alternates", "remove the workspace's link to another object store")
    return None


def clone_main_checkout(repo_root: Path, workspace_path: Path) -> dict[str, Any] | None:
    """Hardlink-clone the main checkout (never the hub URL) without a checkout; a refusal on failure.

    The clone holds none of the main checkout's local branches or tags and
    no alternates link, so the line of work comes only from the hub's refs.
    """
    proc = wg.run_git(["clone", "--no-checkout", "--local", str(repo_root), str(workspace_path)], repo_root)
    if proc.returncode != 0:
        return _failed("clone", "clone the main checkout into the workspace")
    return _strip_local_refs(workspace_path) or _drop_alternates(workspace_path)


def _drop_foreign_remote_refs(workspace: Path) -> bool:
    """Delete every ``origin/*`` but main: they are the main checkout's, not the hub's. True on success."""
    names = [n for n in _ref_names(workspace, "refs/remotes/")
             if n.startswith("origin/") and n not in (BASE_REF, "origin/HEAD")]
    return _delete_refs(workspace, ["branch", "-D", "-r"], names)


def _fetch(fetch_args: list[str], workspace: Path, allow_stale_base: bool) -> tuple[str, dict[str, Any] | None]:
    """Run one fetch; ``(status, refusal)`` where a failure refuses unless *allow_stale_base*."""
    if wg.run_git(fetch_args, workspace).returncode == 0:
        return FETCH_OK, None
    if not allow_stale_base:
        return FETCH_FAILED, step_error("FETCH_FAILED", "fetch-hub",
                                        "Could not fetch from the hub; check that it is reachable.")
    return FETCH_FAILED, None


def sync_with_hub(hub: str, workspace: Path, allow_stale_base: bool) -> tuple[str, dict[str, Any] | None]:
    """Point origin at the hub and fetch from it with pruning, so origin/* names only the hub's branches.

    Returns ``(fetch_status, refusal)``. Under *allow_stale_base* a failed
    fetch is tolerated, but the main checkout's branches are still dropped;
    origin/main is then the main checkout's own main (a stale base).
    """
    if wg.run_git(["remote", "set-url", "origin", hub], workspace).returncode != 0:
        return FETCH_FAILED, _failed("set-origin", "point the workspace's origin at the hub")
    status, refusal = _fetch(["fetch", "--prune", "origin"], workspace, allow_stale_base)
    if refusal is not None:
        return status, refusal
    if status == FETCH_FAILED and not _drop_foreign_remote_refs(workspace):
        return status, _failed("strip-remote-refs", "remove the main checkout's branches from the workspace")
    has_main = wg.run_git(["rev-parse", "--verify", "-q", BASE_REF], workspace).returncode == 0
    if has_main and wg.run_git(["remote", "set-head", "origin", "main"], workspace).returncode != 0:
        return status, _failed("set-head", "set the workspace's origin/HEAD")
    return status, None


def refresh_main(workspace: Path, allow_stale_base: bool) -> tuple[str, dict[str, Any] | None]:
    """Ready-path fetch, scoped to the hub's main; returns ``(fetch_status, refusal)``."""
    return _fetch(["fetch", "origin", "main"], workspace, allow_stale_base)


def ok_fields(workspace: Path, base_commit: str, fetch: str, created: bool) -> dict[str, Any]:
    """The BO-4300c-2 base fields of an ensure ok answer.

    After a failed hub fetch origin/main is not the hub's, so
    ``origin_main_commit`` is null and the base never "matches" it; the
    staleness is logged to stderr, never added to the answer.
    """
    stale = fetch == FETCH_FAILED
    tip = None if stale else (wg.run_git(["rev-parse", BASE_REF], workspace).stdout.strip() or None)
    fields: dict[str, Any] = {
        "base_ref": BASE_REF,
        "base_commit": base_commit,
        "origin_main_commit": tip,
        "base_matches_origin_main": tip is not None and tip == base_commit,
        "fetch": fetch,
        "created": created,
    }
    if stale:  # BO-4300c-2 lists no message on an ok answer: the fields carry it, the log says why
        _log.warning("ok_fields: the hub could not be fetched (--allow-stale-base): the base is stale, taken "
                     "from the workspace's own origin/main, not confirmed against the hub.")
    return fields


def bootstrap_fields(bootstrap: dict[str, Any], config_path: Path | str, env_copied: list[str]) -> dict[str, Any]:
    """Merge ``config_path`` and ``env_copied`` into the readiness proof's bootstrap dict.

    ``failure_excerpt`` is always present (``None`` when the build succeeded).
    """
    return {"failure_excerpt": None, **bootstrap, "config_path": str(config_path), "env_copied": list(env_copied)}


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-22 [python-coder/EPIC-WorkspaceMakerHardening/05]:
#   (#EPIC-WorkspaceMakerHardening/05)
#   Created. The clone source moves from the hub to the resolved main
#   checkout (A1) with a pruning fetch from the hub; failed steps answer with
#   ``step`` and no git text (M4); the ok-answer base fields and bootstrap
#   additions (M9c/N1). Kept out of worktree.py for the file-size ratchet. (ADR-018)
# - 2026-10-22 [python-coder/EPIC-WorkspaceMakerHardening/05 rework]:
#   (#EPIC-WorkspaceMakerHardening/05) pr-reviewer H-1/M-1/M-2/M-4: the clone
#   is stripped of the main checkout's branches and tags (HEAD detached) and
#   of any alternates link; every set-url/set-head/ref-delete result is
#   checked; a stale base never reports origin_main_commit; failure_excerpt
#   is always in bootstrap. (ADR-018)
# ===========================================================================
