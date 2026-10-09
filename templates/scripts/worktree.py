"""
MODULE: worktree
GOAL: The one maker every workspace-creation route calls -- ``ensure``,
    ``verify``, and ``where`` directly, ``locate``/``list``/``remove`` via
    ``worktree_admin`` -- so that a long-running build, a quick fix, a
    requirements-authoring session, an agent following the workspace skill,
    and a person at a terminal all get the same kind of workspace, made the
    same way (AC BO-4300a-1).
BUSINESS CONTEXT: Before this script, worktree creation was duplicated across
    ``setup_ticket_worktree.py``'s several subcommands, each with its own
    slightly different recipe. ADR-018 Amendment 1 decided every workspace is
    now a hardlinked, ``--no-checkout`` local-path clone (never a linked git
    worktree, never ``os.symlink``), with a real install built inside it and
    a durable marker registry recording what was made. After BO-4300f-2, no
    other code path in the package may create, clone, locate or remove a
    workspace.
ARCHITECTURE: Stdlib-only CLI (argparse, json, subprocess, shutil, sys,
    pathlib). Run as ``python <absolute path> <verb> ...`` from any cwd --
    Python puts this script's own directory on ``sys.path``, which is how
    ``import workspace_root``, ``import worktree_git`` and ``import
    worktree_admin`` resolve both in the source tree (as siblings under
    ``templates/scripts/``) and after deploy (as siblings under
    ``<install-root>/scripts/``). All git-subprocess, marker-registry,
    install-build, and identity plumbing lives in ``worktree_git``;
    project-root resolution lives in ``workspace_root`` and the landing
    place, ``--landing-root`` validation and config derivation in
    ``worktree_layout`` (never re-implemented here); the read-only/removal verbs live in
    ``worktree_admin`` so this file stays under the package's file-size
    ratchet. A caller-supplied condition this script cannot classify is
    answered as ``{"status": "error", "code": "INTERNAL_ERROR", ...}`` on
    stdout -- never a raw traceback, never an "ok" answer for a request that
    did not actually succeed.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import worktree_admin
import worktree_answer as wa
import worktree_git as wg
import worktree_layout as wl
import worktree_paths as wp
import worktree_readiness as wr

_log = logging.getLogger(__name__)


_err = wa.error_answer  # the one status/code rule (worktree_answer owns the table)


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with a trailing 'Z'."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _copy_optional_files(repo_root: Path, workspace_path: Path) -> None:
    """Best-effort copy ``.env``/``.mcp.json`` from the main checkout into the workspace."""
    for name in (".env", ".mcp.json"):
        src = repo_root / name
        if not src.is_file():
            continue
        try:
            shutil.copy2(src, workspace_path / name)
        except OSError as exc:
            _log.warning("_copy_optional_files: could not copy %s: %s", src, exc)


def _repo_context(repo_root: Path) -> dict[str, Any]:
    """Build the BO-4300c-2 'Common fields' this maker can supply as soon as repo_root resolves."""
    return {**wp.repo_fields(repo_root), "layout": wl.layout_for(repo_root)}


def _answer_from_existing(workspace_path: Path, marker: dict[str, Any], hub: str,
                         repo_root: Path) -> dict[str, Any]:
    """Build an ``ensure`` answer for an already-ready workspace (idempotent short-circuit)."""
    computed = wr.compute_checks(workspace_path, hub, branch=marker.get("branch") or "", project_root=repo_root)
    return {
        "status": "ok",
        "mechanism": "clone",
        "kind": marker.get("kind"),
        "slug": marker.get("slug"),
        "branch": marker.get("branch"),
        "hub": hub,
        **wp.path_fields(workspace_path),
        "base_commit": marker.get("base_commit"),
        "bootstrap": {"restored_tracked": []},
        "hooks_stages_declared": marker.get("hooks_stages_declared", []),
        "checks": wr.stored_checks(computed, marker),
    }


def _build_marker(kind: str, slug: str, branch: str, hub: str, repo_root: Path, base_commit: str | None,
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
        "created_at": _now_iso(),
    }
    if checks is not None:
        marker["checks"] = checks
    return marker


def _create_workspace(repo_root: Path, hub: str, kind: str, slug: str, branch: str,
                       workspace_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    """Clone, fetch, checkout, install, and mark a brand-new workspace ready."""
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    clone_proc = wg.run_git(["clone", "--no-checkout", "--local", hub, str(workspace_path)], repo_root)
    if clone_proc.returncode != 0:
        return _err("FETCH_FAILED", f"git clone --no-checkout --local failed: {clone_proc.stderr.strip()}")

    wg.write_marker(workspace_path, _build_marker(kind, slug, branch, hub, repo_root, None, "creating", workspace=workspace_path))

    wg.run_git(["remote", "set-url", "origin", hub], workspace_path)
    fetch_proc = wg.run_git(["fetch", "origin", "main"], workspace_path)
    if fetch_proc.returncode != 0 and not args.allow_stale_base:
        return _err("FETCH_FAILED", f"git fetch origin main failed: {fetch_proc.stderr.strip()}")

    base_commit = wg.run_git(["rev-parse", "origin/main"], workspace_path).stdout.strip()
    if not base_commit:
        return _err("FETCH_FAILED", "origin/main did not resolve to a commit after fetch.")

    checkout_proc = wg.run_git(["checkout", "-B", branch, "origin/main"], workspace_path)
    if checkout_proc.returncode != 0:
        return _err("GIT_FAILED", f"git checkout -B {branch} origin/main failed: {checkout_proc.stderr.strip()}")

    wg.run_git(["config", "gc.auto", "0"], workspace_path)
    wg.run_git(["config", "maintenance.auto", "false"], workspace_path)
    _copy_optional_files(repo_root, workspace_path)

    if args.config_path:
        config_path = wp.resolve_arg(args.config_path)
    else:
        config_path, derive_err = wl.derive_config_path(repo_root, workspace_path)
        if derive_err:
            return _err(
                derive_err,
                f"No usable skills_config.json in {repo_root} or {repo_root.parent} "
                "(.claude/, .gemini/, .cursor/, .github/, .cline/); never the build's "
                "default config, never this maker's own location.",
            )
    proof = wr.prove_ready(workspace_path, hub, kind=kind, branch=branch, project_root=repo_root,
                           config_path=config_path, line_of_work=getattr(args, "line_of_work", "new"))
    if proof.get("status") in ("refused", "error"):
        return proof  # a refusal never carries a workspace location
    checks = proof["checks"]
    marker = _build_marker(kind, slug, branch, hub, repo_root, base_commit, "ready", checks, workspace=workspace_path)
    marker["hooks_stages_declared"] = proof["hooks_stages_declared"]
    wg.write_marker(workspace_path, marker)

    answer = {
        "status": "ok",
        "mechanism": "clone",
        "kind": kind,
        "slug": slug,
        "branch": branch,
        "hub": hub,
        **wp.path_fields(workspace_path),
        "base_commit": base_commit,
        "bootstrap": proof["bootstrap"],
        "hooks_stages_declared": proof["hooks_stages_declared"],
        "checks": checks,
    }
    wp.add_ticket_fields(answer, getattr(args, "ticket", None), repo_root, workspace_path)
    return answer


def cmd_ensure(args: argparse.Namespace) -> dict[str, Any]:
    """Create (or idempotently confirm) the workspace for ``--kind``/``--slug``."""
    if args.kind not in wg.VALID_KINDS:
        return _err("USAGE", f"Unknown --kind {args.kind!r}; expected one of {wg.VALID_KINDS}.")

    repo_root, refusal = wl.resolve_repo_root(args.repo_root)
    if refusal is not None:
        return refusal
    place, usage = wl.landing_for(args.landing_root, repo_root)
    if usage is not None:
        return usage
    ctx = _repo_context(repo_root)

    hub = wg.origin_url(repo_root)
    if hub is None:
        return {**_err("NO_HUB", f"{repo_root} has no 'origin' remote; cannot determine the hub."), **ctx}
    ctx["hub"] = hub

    slug = wg.normalize_slug(args.slug)
    branch = f"{wg.KIND_BRANCH_PREFIX[args.kind]}/{slug}"
    workspace_path = wl.workspace_path_for(place, args.kind, slug)

    existing_marker = wg.read_marker(workspace_path) if workspace_path.exists() else None
    occupant = wl.other_project_occupant(workspace_path, existing_marker, repo_root) if existing_marker else None
    if occupant is not None:
        return {**_err("OCCUPIED", f"{workspace_path} holds another project's workspace.", occupant=occupant), **ctx}
    if existing_marker is not None and existing_marker.get("state") == "ready":
        answer = {**ctx, **_answer_from_existing(workspace_path, existing_marker, hub, repo_root)}
        wp.add_ticket_fields(answer, getattr(args, "ticket", None), repo_root, workspace_path)
        return answer
    if workspace_path.exists() and existing_marker is None:
        return {
            **_err("OCCUPIED", f"{workspace_path} already exists and carries no leafcutter workspace marker."),
            **ctx,
        }

    return {**ctx, **_create_workspace(repo_root, hub, args.kind, slug, branch, workspace_path, args)}


def cmd_verify(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only readiness re-check of the workspace marker at ``--path``."""
    bad_override = wl.override_refusal(args)
    if bad_override is not None:
        return bad_override
    workspace_path = wp.resolve_arg(args.path)
    marker = wg.read_marker(workspace_path)
    if marker is None:
        return _err("NOT_FOUND", f"No leafcutter workspace marker found at {workspace_path}.")
    hub = wp.from_portable(marker.get("hub", ""), workspace_path)
    project_root = marker.get("project_root")
    computed = wr.compute_checks(workspace_path, hub, branch=marker.get("branch") or "",
                                 project_root=Path(wp.from_portable(project_root or "", workspace_path)))
    checks = wr.stored_checks(computed, marker)
    answer = {"status": "ok", "path": str(workspace_path), **wp.path_fields(workspace_path),
              "marker": marker, "checks": checks, "hub": hub}
    if project_root:
        answer.update(_repo_context(Path(wp.from_portable(project_root, workspace_path))))
    return answer


def cmd_where(_args: argparse.Namespace) -> dict[str, Any]:
    """Print the maker's own absolute path."""
    here = Path(__file__).resolve()
    return {"status": "ok", "path": str(here), "path_posix": wp.to_posix(here)}


def build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser for all six verbs."""
    parser = wa.MakerParser(prog="worktree.py")
    sub = parser.add_subparsers(dest="verb", required=True)

    ensure_p = sub.add_parser("ensure")
    ensure_p.add_argument("--kind", required=True)
    ensure_p.add_argument("--slug", required=True)
    ensure_p.add_argument("--ticket")
    ensure_p.add_argument("--repo-root")
    ensure_p.add_argument("--allow-stale-base", action="store_true")
    ensure_p.add_argument("--config-path")

    locate_p = sub.add_parser("locate")
    locate_p.add_argument("--kind")
    locate_p.add_argument("--slug")
    locate_p.add_argument("--path")
    locate_p.add_argument("--branch")
    locate_p.add_argument("--repo-root")

    list_p = sub.add_parser("list")
    list_p.add_argument("--repo-root")

    verify_p = sub.add_parser("verify")
    verify_p.add_argument("--path", required=True)
    verify_p.add_argument("--kind")
    verify_p.add_argument("--slug")
    verify_p.add_argument("--repo-root")

    remove_p = sub.add_parser("remove")
    remove_p.add_argument("--path", required=True)
    remove_p.add_argument("--force", action="store_true")
    remove_p.add_argument("--delete-remote-branch", action="store_true")
    remove_p.add_argument("--repo-root")

    sub.add_parser("where")
    for name in ("ensure", "locate", "list", "verify", "remove"):
        sub.choices[name].add_argument("--landing-root")
    return parser


_DISPATCH = {
    "ensure": cmd_ensure,
    "locate": worktree_admin.cmd_locate,
    "list": worktree_admin.cmd_list,
    "verify": cmd_verify,
    "remove": worktree_admin.cmd_remove,
    "where": cmd_where,
}


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: parse argv, dispatch to the verb, print one JSON answer.

    Any exception the dispatched verb does not itself convert into a
    structured answer is caught here and reported as ``INTERNAL_ERROR`` --
    never a bare traceback on stdout, per this maker's error-handling
    contract.

    Args:
        argv: Argument vector, or ``None`` to use ``sys.argv[1:]``.

    Returns:
        The BO-4300c-2 result-contract exit code for the printed answer: 0
        for ``status: "ok"``, 2 for ``"refused"``, 64 for ``code: "USAGE"``,
        1 for every other ``"error"`` -- see
        :func:`worktree_answer.exit_code_for_answer`, the single place that
        maps an answer to an exit code so the two can never disagree.
    """
    verb = "unknown"
    try:
        args = build_parser().parse_args(argv)
        verb = args.verb
        answer = _DISPATCH[verb](args)
    except wa.UsageError as exc:
        answer = _err("USAGE", f"Usage error: {exc}")
    except Exception as exc:  # noqa: BLE001 - last-resort boundary: still exactly one JSON object
        _log.warning("main: unhandled %s: %s", type(exc).__name__, exc)
        answer = _err("INTERNAL_ERROR", f"{type(exc).__name__}: {exc}")
    answer = wa.finalize_answer(verb, answer)
    print(json.dumps(answer))
    return wa.exit_code_for_answer(answer)


if __name__ == "__main__":
    sys.exit(main())


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-27 23:57 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Created this module as the one maker BO-4300a-1 requires: every route
#   (epic/feature/ac/fastlane/scratch kinds so far; "ticket" kind is
#   BO-4300a-1-ii's --ticket path) now gets an identically-shaped answer from
#   ensure/locate/list/verify/remove/where. Clones are hardlinked local-path
#   clones (--no-checkout, --local, no --shared/--reference) per ADR-018
#   Amendment 1; no os.symlink anywhere. The marker registry
#   (.leafcutter/workspace.json) is the only clone listing -- no git command
#   lists clones. Split locate/list/remove into worktree_admin.py, and moved
#   identity/landing-place/repo-root-resolution helpers into worktree_git.py,
#   to keep this file under the package's file-size ratchet.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-28 02:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Fixed pr-reviewer H-2/H-3 (2026-09-28 00:43) and ac-validator's
#   independent re-confirmation (2026-09-28 00:50): main() now derives its
#   exit code from wg.exit_code_for_answer() (0/2/64/1) instead of a
#   hardcoded 0-or-1, _err() derives status ok/refused/error from the code
#   via wg.status_for_code() instead of always "error", cmd_ensure/
#   _create_workspace now attach repo_root/repo_root_posix/layout/hub
#   (BO-4300c-2 'Common fields') as soon as they resolve, and
#   _create_workspace's install-build config path is derived via
#   wg.derive_config_path() (real skills_config.json discovery) instead of
#   guessing ".pre-commit-config.yaml" -- a file --config-path never reads.
#   CLONE_FAILED/CHECKOUT_FAILED/BAD_KIND collapsed onto the contract's own
#   GIT_FAILED/USAGE codes. Full parity with BO-4300c-2's per-stage
#   checks-dict shape (hooks_pre_commit_fired et al., branch-safety checks)
#   remains deferred to BO-4300c-1-ii/BO-4300b-1, neither of which is built
#   yet -- documented, not silently claimed.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-30 22:05 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
#   BO-4300c-2/b-5/b-5-i: the answer table moved to worktree_answer.py and
#   path spelling to worktree_paths.py; main() now always prints one JSON
#   object (USAGE on a parse failure, INTERNAL_ERROR on any exception); every
#   path is answered native + POSIX; the marker stores hub/project_root
#   relative to the workspace; an unreachable hub on clone answers
#   FETCH_FAILED (refused). (ADR-018)
# - 2026-09-30 23:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
#   BO-4300b-1/2/3: project resolution, the landing place and config
#   derivation now come from worktree_layout.py. A workspace lands at
#   <landing-root>/<kind>/<slug>; --landing-root is parsed here and validated
#   before anything is written; NO_REPO / AMBIGUOUS_REPO refusals write
#   nothing; a location holding another project's workspace is OCCUPIED
#   (occupant other-project). (ADR-018)
# - 2026-10-01 00:30 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
#   BO-4300c-1/-i/-ii/-iii, b-4: ok now means worktree_readiness.prove_ready
#   proved every ingredient (build, restored tracked files, per-stage
#   canaries, branch/base/independence); a refusal carries checks and no
#   workspace location. (ADR-018)
# ===========================================================================
