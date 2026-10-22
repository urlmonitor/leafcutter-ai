"""
MODULE: worktree_admin
GOAL: The three read-only/removal verbs of the one workspace maker --
    ``locate``, ``list``, and ``remove`` -- split out of worktree.py's CLI
    dispatch file.
BUSINESS CONTEXT: AC BO-4300a-1 requires ``locate`` and ``list`` to scan the
    landing place's own marker registry rather than any ``git worktree``
    command (no git command lists clones), and ``remove`` to refuse a dirty
    or unpushed workspace unless explicitly forced. Kept in its own module,
    a sibling of worktree.py and worktree_git.py under ``templates/scripts/``,
    so worktree.py itself stays under the package's 400-line file-size
    ratchet -- the same "further helper module the maker imports needs a
    named deploy-manifest entry too" pattern this ticket's own Implementation
    Notes call out for the resolver module.
ARCHITECTURE: ``remove`` now lives in ``worktree_remove`` (BO-4300e). Stdlib-only (argparse typing only; no CLI parsing of its own --
    worktree.py owns argument parsing and calls these three functions
    directly with the parsed ``argparse.Namespace``). Depends only on
    ``worktree_git`` for the marker registry, landing-place resolution, and
    git primitives -- never imports ``worktree`` itself, so there is no
    import cycle between this module and its caller.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_ensure_state as wes
import worktree_git as wg
import worktree_identity as wi
import worktree_layout as wl
import worktree_paths as wp
import worktree_readiness as wr

_log = logging.getLogger(__name__)


_err = wa.error_answer  # shared status/code rule; worktree_answer owns the table


def _project_and_place(args: argparse.Namespace) -> tuple[Path | None, Path | None, dict[str, Any] | None]:
    """Resolve the project and its landing root, or return the refusal/usage answer that says why not."""
    repo_root, refusal = wl.resolve_repo_root(args.repo_root)
    if refusal is not None:
        return None, None, refusal
    place, usage = wl.landing_for(args.landing_root, repo_root)
    return repo_root, place, usage


def incomplete_answer(workspace: Path, marker: dict[str, Any]) -> dict[str, Any]:
    """INCOMPLETE answer for a half-made workspace: names ``remnant_path``, never a ``workspace_path``."""
    return {**wes.incomplete_refusal(workspace, marker), "remnant_path": str(workspace)}


def _last_fetched_main(workspace: Path) -> str | None:
    """The workspace's own last-fetched ``origin/main`` commit (read only), or ``None``."""
    proc = wg.run_git(["rev-parse", "--verify", "--quiet", "refs/remotes/origin/main"], workspace)
    return (proc.stdout.strip() or None) if proc.returncode == 0 else None


def _checks_for(workspace: Path, marker: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Recompute the read-only ingredient checks of a ready workspace and overlay its stored proofs."""
    hub = wp.from_portable(marker.get("hub", ""), workspace)
    project = wl.project_of(workspace, marker) or workspace.parent
    computed = wr.compute_checks(workspace, hub, branch=marker.get("branch") or "", project_root=project)
    return wr.stored_checks(computed, marker), hub


def _located_fields(workspace: Path, marker: dict[str, Any], checks: dict[str, Any]) -> dict[str, Any]:
    """The BO-4300c-2 top-level fields every locate and verify ok answer carries (no bootstrap, no hooks list)."""
    tip = _last_fetched_main(workspace)
    return {
        "kind": marker.get("kind"), "slug": marker.get("slug"), "branch": marker.get("branch"), "checks": checks,
        "workspace_action": "located", "line_of_work": "existing", "created": False, "fetch": "skipped",
        "origin_main_commit": tip, "base_matches_origin_main": bool(tip) and marker.get("base_commit") == tip,
    }


def _located_answer(workspace: Path, marker: dict[str, Any]) -> dict[str, Any]:
    """The ok answer for one found workspace: path fields, marker, and (when ready) checks and located fields."""
    base = {"status": "ok", **wp.path_fields(workspace), "marker": marker}
    if marker.get("state", "ready") != "ready":
        return base  # the caller turns a half-made workspace into INCOMPLETE; nothing to check
    checks, _hub = _checks_for(workspace, marker)
    return {**base, **_located_fields(workspace, marker, checks)}


class AmbiguousBranch(Exception):
    """A declared alias spelling matches more than one distinct workspace."""

    def __init__(self, candidates: list[str]) -> None:
        super().__init__("; ".join(candidates))
        self.candidates = candidates


def _find_by_branch(place: Path, repo_root: Path, branch: str) -> tuple[Path, dict[str, Any]] | None:
    """The workspace whose line is *branch*: an exact (canonical) match first, then a declared alias spelling."""
    found = list(wl.iter_markers(place, repo_root))
    for path, marker in found:
        if marker.get("branch") == branch:
            return path, marker
    hits = [(path, marker) for path, marker in found if marker.get("kind") in wg.VALID_KINDS and marker.get("slug")
            and wi.Identity(marker["kind"], marker["slug"]).matches_branch(branch)]
    if len(hits) > 1:
        raise AmbiguousBranch([str(path) for path, _marker in hits])
    return hits[0] if hits else None


def _locate_by_name(args: argparse.Namespace, repo_root: Path, place: Path, ctx: dict[str, Any]) -> dict[str, Any]:
    """Locate by ``--kind``/``--slug`` through the declared aliases (canonical first)."""
    slug = wi.normalize_slug(args.slug, args.kind)
    problem = wi.slug_problem(slug)
    if problem is not None:
        return _err("USAGE", f"--slug {args.slug!r} cannot name work: {problem}.")
    workspace_path = wl.workspace_path_for(place, args.kind, slug)
    marker = wg.read_marker(workspace_path)
    if marker is not None and wl.other_project_occupant(workspace_path, marker, repo_root):
        marker = None  # another project's workspace is never this project's answer
    if marker is None:
        return {**_err("NOT_FOUND", f"No workspace marker found at {workspace_path}."), **ctx}
    return {**ctx, **_located_answer(workspace_path, marker)}


def cmd_locate(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only lookup of a workspace by ``--path``, ``--kind``/``--slug``, or ``--branch``."""
    if args.path:
        workspace_path = wp.resolve_arg(args.path)
        marker = wg.read_marker(workspace_path)
        if marker is None:
            return _err("NOT_FOUND", f"No workspace marker found at {workspace_path}.")
        return _located_answer(workspace_path, marker)

    if args.kind and args.kind not in wg.VALID_KINDS:
        return _err("USAGE", f"Unknown --kind {args.kind!r}; expected one of {wg.VALID_KINDS}.")
    repo_root, place, refusal = _project_and_place(args)
    if refusal is not None:
        return refusal
    ctx = {**wp.repo_fields(repo_root), "layout": wl.layout_for(repo_root)}

    if args.kind and args.slug:
        return _locate_by_name(args, repo_root, place, ctx)

    if args.branch:
        try:
            hit = _find_by_branch(place, repo_root, args.branch)
        except AmbiguousBranch as exc:
            return {**_err("AMBIGUOUS_LINE", f"More than one workspace answers to {args.branch!r}; name one with "
                           "--path or --kind/--slug.", candidates=exc.candidates), **ctx}
        if hit is None:
            return {**_err("NOT_FOUND", f"No workspace found for branch {args.branch!r}."), **ctx}
        return {**ctx, **_located_answer(*hit)}

    return _err("USAGE", "locate requires --path, or --kind with --slug, or --branch.")


def _identity_mismatch(args: argparse.Namespace, marker: dict[str, Any]) -> bool:
    """True when ``--kind``/``--slug`` name a different canonical identity than the marker holds."""
    if not args.kind:
        return False
    if args.slug:
        want = wi.resolve(args.kind, args.slug)
        return (marker.get("kind"), marker.get("slug")) != (want.kind, want.slug)
    return marker.get("kind") != args.kind


def cmd_verify(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only readiness re-check of the workspace at ``--path``: never fetches, builds or commits.

    Refuses ``VERIFY_FAILED`` naming every false ingredient in
    :data:`worktree_readiness.VERIFY_REFUSALS` (and any false recorded hook
    stage); ``base_is_fresh`` and ``tree_clean`` are reported, never refused on.
    """
    bad_override = wl.override_refusal(args)
    if bad_override is not None:
        return bad_override
    if args.kind and args.kind not in wg.VALID_KINDS:
        return _err("USAGE", f"Unknown --kind {args.kind!r}; expected one of {wg.VALID_KINDS}.")
    if args.slug and not args.kind:
        return _err("USAGE", "--slug needs --kind.")
    workspace_path = wp.resolve_arg(args.path)
    marker = wg.read_marker(workspace_path)
    if marker is None:
        return _err("NOT_FOUND", f"No leafcutter workspace marker found at {workspace_path}.")
    if marker.get("state", "ready") != "ready":
        return incomplete_answer(workspace_path, marker)
    checks, hub = _checks_for(workspace_path, marker)
    failed = (["identity"] if _identity_mismatch(args, marker) else []) + wr.failed_for_verify(checks)
    if failed:
        return _err("VERIFY_FAILED", "Not ready -- untrue of the workspace: " + ", ".join(failed) + ".",
                    checks=checks, failed_ingredients=failed)
    answer = {"status": "ok", "path": str(workspace_path), **wp.path_fields(workspace_path), "marker": marker,
              "hub": hub, **_located_fields(workspace_path, marker, checks)}
    project = wl.project_of(workspace_path, marker)
    if project is not None:
        answer.update(wp.repo_fields(project), layout=wl.layout_for(project))
    return answer


def _list_entry(path: Path, marker: dict[str, Any]) -> dict[str, Any]:
    """One list entry: exactly kind, slug, branch, both path spellings and ready|incomplete."""
    state = "ready" if marker.get("state", "ready") == "ready" else "incomplete"
    paths = wp.path_fields(path)
    return {"kind": marker.get("kind"), "slug": marker.get("slug"), "branch": marker.get("branch"),
            "workspace_path": paths["workspace_path"], "workspace_path_posix": paths["workspace_path_posix"],
            "state": state}


def cmd_list(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only scan of the landing place's markers -- never ``git worktree list``."""
    repo_root, place, refusal = _project_and_place(args)
    if refusal is not None:
        return refusal
    workspaces = [_list_entry(path, marker) for path, marker in wl.iter_markers(place, repo_root)]
    return {
        "status": "ok", "landing_place": str(place), "workspaces": workspaces,
        **wp.repo_fields(repo_root), "layout": wl.layout_for(repo_root),
    }


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-22 [python-coder/EPIC-WorkspaceMakerHardening/07]:
#   (#EPIC-WorkspaceMakerHardening/07) verify moved here from worktree.py and made
#   read-only-refusing (VERIFY_FAILED, own refusal set); locate/verify/list answer
#   in the BO-4300c-2 field shape; locate resolves declared aliases and refuses
#   a bad kind or slug as USAGE. (ADR-018)
# - 2026-10-12 17:30 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/08)
#   cmd_remove and _branch_pushed moved to worktree_remove.py (BO-4300e-2/-3:
#   fetch-before-verdict, discard token, process check); this file keeps the
#   read-only locate/list verbs. (ADR-018)
# - 2026-09-27 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Split out of worktree.py to keep that file under the package's 400-line
#   file-size ratchet. locate/list scan the marker registry only -- no git
#   command lists clones. remove refuses a dirty or unpushed workspace
#   unless --force is given, per this ticket's Delivers To contract.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-28 02:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Fixed pr-reviewer H-2 (2026-09-28 00:43): _err() now derives status
#   ok/refused/error from worktree_git.status_for_code() instead of always
#   "error"; BAD_ARGS collapsed onto the contract's own USAGE code;
#   cmd_remove's rmtree OSError now answers PROCESS_HOLDS_FILES instead of
#   the non-contract REMOVE_FAILED; locate/list attach
#   repo_root/repo_root_posix/layout once repo_root resolves.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-30 22:05 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
#   Answers now carry native + POSIX path fields (worktree_paths) and --path
#   accepts any shell's spelling; _err is the shared worktree_answer rule.
#   (ADR-018)
# - 2026-09-30 23:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
#   locate/list/remove compute the location through worktree_layout (one
#   function for all verbs), accept and validate --landing-root, and filter
#   markers by project_root; a refused resolution is returned as-is. (ADR-018)
# ===========================================================================
