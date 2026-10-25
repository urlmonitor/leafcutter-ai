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
import worktree_identity as wi
import worktree_paths as wp

_log = logging.getLogger(__name__)

BASE_REF = "origin/main"
SOURCE_REMOTE = "leafcutter-src"  # the clone's remote name while it points at the main checkout
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


def _swap_source_for_hub(workspace: Path, hub: str) -> dict[str, Any] | None:
    """Add ``origin`` at the hub, seed ``origin/main`` from the source, then remove the temporary remote.

    ``origin`` is never the main checkout, so an outside bare ``git fetch``
    cannot rewrite ``origin/*`` to the main checkout's branches. The seed is
    only a stale base for ``--allow-stale-base``; a hub fetch overwrites it.
    """
    seed = wg.run_git(["rev-parse", "--verify", "-q", f"refs/remotes/{SOURCE_REMOTE}/main"], workspace).stdout.strip()
    if wg.run_git(["remote", "add", "origin", hub], workspace).returncode != 0:
        return _failed("set-origin", "point the workspace's origin at the hub")
    if seed and wg.run_git(["update-ref", f"refs/remotes/{BASE_REF}", seed], workspace).returncode != 0:
        return _failed("set-origin", "seed the workspace's origin/main")
    if wg.run_git(["remote", "remove", SOURCE_REMOTE], workspace).returncode != 0:
        return _failed("strip-remote-refs", "remove the main checkout's branches from the workspace")
    return None


def clone_main_checkout(repo_root: Path, workspace_path: Path, hub: str) -> dict[str, Any] | None:
    """Hardlink-clone the main checkout (never the hub URL) without a checkout; a refusal on failure.

    The clone's remote is named ``leafcutter-src`` while it exists and is swapped for
    ``origin`` at the hub. It holds none of the main checkout's local branches or tags and
    no alternates link, so the line of work comes only from the hub's refs.
    """
    cmd = ["clone", "-o", SOURCE_REMOTE, "--no-checkout", "--local", str(repo_root), str(workspace_path)]
    if wg.run_git(cmd, repo_root).returncode != 0:
        return _failed("clone", "clone the main checkout into the workspace")
    return _strip_local_refs(workspace_path) or _drop_alternates(workspace_path) or _swap_source_for_hub(workspace_path, hub)


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
    has_origin = wg.run_git(["remote", "get-url", "origin"], workspace).returncode == 0
    if wg.run_git(["remote", "set-url" if has_origin else "add", "origin", hub], workspace).returncode != 0:
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


def _verify_built(workspace: Path, sha: str) -> dict[str, Any] | None:
    """Refuse (VERIFY_FAILED, step ``verify-checkout``) unless HEAD is *sha* and the tracked tree is clean."""
    head = wg.run_git(["rev-parse", "HEAD"], workspace).stdout.strip()
    status = wg.run_git(["status", "--porcelain", "-z", "--untracked-files=no"], workspace)
    if head == sha and status.returncode == 0 and not any(status.stdout.split("\0")):
        return None
    return step_error("VERIFY_FAILED", "verify-checkout", "The new line of work does not start exactly where its files are.")


def _unsent_local_refusal(workspace: Path, branch: str, sha: str) -> dict[str, Any] | None:
    """WORK_AT_RISK when local *branch* exists and holds commits not under *sha* (``-B`` would drop them)."""
    ref = f"refs/heads/{branch}"
    if wg.run_git(["rev-parse", "--verify", "-q", ref], workspace).returncode != 0:
        return None
    if wg.run_git(["merge-base", "--is-ancestor", ref, sha], workspace).returncode == 0:
        return None
    return wa.error_answer("WORK_AT_RISK", f"The local branch {branch!r} holds commits the hub's line lacks; "
                           "it was not reset. Push or move them, then ask again.", step="checkout", branch=branch)


def build_line(workspace: Path, ident: Any, ticket: Any,
               base_commit: str) -> tuple[str, str, str, dict[str, Any] | None]:
    """Build the line of work from ONE resolved commit: ``(branch, line_of_work, start_sha, refusal)``.

    The start is the hub line's tip (``resumed``) or *base_commit* (``new``), read as a SHA once and
    handed to ``checkout --no-track -B`` so a ref moved meanwhile cannot split HEAD from the files.
    A local branch of a resumed line holding commits the hub lacks is never reset (WORK_AT_RISK).
    HEAD must then equal that SHA with a clean tree. The caller discards a clone on a refusal.
    """
    lines = wi.hub_lines(workspace, ident)
    refusal = wi.line_refusal(lines, ident)
    branch, line = (lines[0], "resumed") if lines else (ident.branch, "new")
    sha = base_commit
    if lines and refusal is None:
        sha = wg.run_git(["rev-parse", f"origin/{branch}"], workspace).stdout.strip()
        refusal = _unsent_local_refusal(workspace, branch, sha)
    if refusal is None and ticket is not None:
        refusal = wi.base_ticket_refusal(workspace, sha, ticket)
    if refusal is None and (not sha or wg.run_git(["checkout", "--no-track", "-B", branch, sha], workspace).returncode != 0):
        refusal = _failed("checkout", "check out the line of work")
    if refusal is None and lines and wg.run_git(["branch", f"--set-upstream-to=origin/{branch}"], workspace).returncode != 0:
        refusal = _failed("set-upstream", "set the line's upstream")
    return branch, line, sha, refusal or _verify_built(workspace, sha)


def ok_fields(workspace: Path, base_commit: str, fetch: str, created: bool,
              built_from: str | None = None) -> dict[str, Any]:
    """The BO-4300c-2 base fields of an ensure ok answer.

    After a failed hub fetch origin/main is not the hub's, so
    ``origin_main_commit`` is null and the base never "matches" it; the
    staleness is logged to stderr, never added to the answer. *built_from* is
    the SHA the line was built from (resolved right after the fetch); it is
    the tip reported, so a ref moved since never changes the answer.
    """
    stale = fetch == FETCH_FAILED
    tip = None if stale else (built_from or wg.run_git(["rev-parse", BASE_REF], workspace).stdout.strip() or None)
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
# - 2026-10-25 [python-coder/EPIC-WorkspaceMakerHardening/11]:
#   (#EPIC-WorkspaceMakerHardening/11) The clone's remote is ``leafcutter-src``
#   until ``origin`` is added at the hub (no ``origin`` ever names the main
#   checkout); ``build_line`` builds the line from one resolved SHA with
#   ``checkout --no-track -B`` and refuses (GIT_FAILED / VERIFY_FAILED, with a
#   step) unless HEAD is that SHA on a clean tree. No new contract code. (ADR-018)
# - 2026-10-25 [python-coder/EPIC-WorkspaceMakerHardening/11 rework]:
#   (#EPIC-WorkspaceMakerHardening/11) M-3: build_line refuses WORK_AT_RISK (step
#   ``checkout``, naming the branch) instead of ``-B``-resetting a local branch with commits the hub lacks. (ADR-018)
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
