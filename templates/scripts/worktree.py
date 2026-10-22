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
    ratchet. The per-work lock, the set-aside of the work's uncommitted
    changes, the half-made-folder helpers and the abort-only test seam live in
    ``worktree_ensure_state`` (BO-4300d); asking again re-readies a ready
    workspace or completes a half-made one in place. A caller-supplied condition this script cannot classify is
    answered as ``{"status": "error", "code": "INTERNAL_ERROR", ...}`` on
    stdout -- never a raw traceback, never an "ok" answer for a request that
    did not actually succeed.
    A ``--kind ticket --ticket`` workspace records its ticket against its
    branch in its own git config (``worktree_ticket_record``, BO-400e-3-ix).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

import worktree_admin
import worktree_answer as wa
import worktree_ensure_state as wes
import worktree_ensure_steps as wst
import worktree_git as wg
import worktree_identity as wi
import worktree_layout as wl
import worktree_migrate
import worktree_paths as wp
import worktree_readiness as wr
import worktree_remove
import worktree_ticket_record as wtr

_log = logging.getLogger(__name__)


_err = wa.error_answer  # the one status/code rule (worktree_answer owns the table)


def _repo_context(repo_root: Path) -> dict[str, Any]:
    """Build the BO-4300c-2 'Common fields' this maker can supply as soon as repo_root resolves."""
    return {**wp.repo_fields(repo_root), "layout": wl.layout_for(repo_root)}


def _start_line(workspace_path: Path, ident: wi.Identity, place: Path, ticket: wi.TicketRequest | None,
                *, discard: bool = True) -> tuple[str, str, dict[str, Any] | None]:
    """Check out the line of work: resume the one hub line, else start fresh at origin/main.

    Returns ``(branch, line_of_work, refusal)``; a refusal discards the clone
    this request just made (*discard*), never a folder being finished.
    """
    lines = wi.hub_lines(workspace_path, ident)
    refusal = wi.line_refusal(lines, ident)
    branch, line = (lines[0], "resumed") if lines else (ident.branch, "new")
    if refusal is None and ticket is not None:
        refusal = wi.base_ticket_refusal(workspace_path, f"origin/{branch}" if lines else "origin/main", ticket)
    if refusal is None:
        cmd = ["checkout", "-b", branch, "--track", f"origin/{branch}"] if lines else ["checkout", "-B", branch, "origin/main"]
        proc = wg.run_git(cmd, workspace_path)
        if proc.returncode != 0:
            refusal = wst.step_error("GIT_FAILED", "checkout", "Could not check out the line of work.")
    if refusal is not None and discard:
        wi.discard_new_clone(workspace_path, place)
    return branch, line, refusal


def _checkout_line(hub: str, ident: wi.Identity, place: Path, workspace_path: Path, args: argparse.Namespace,
                   ticket: wi.TicketRequest | None, *, discard: bool,
                   ) -> tuple[tuple[str, str, str, str] | None, dict[str, Any] | None]:
    """Point origin at the hub, fetch (pruned), and check out the line.

    Returns ``((branch, line, base, fetch_status), refusal)``.
    """
    fetch_status, fetch_refusal = wst.sync_with_hub(hub, workspace_path, args.allow_stale_base)
    if fetch_refusal is not None:
        if discard and fetch_refusal.get("code") == "GIT_FAILED":
            wi.discard_new_clone(workspace_path, place)  # a half-set-up clone this request made
        return None, fetch_refusal
    base_commit = wg.run_git(["rev-parse", "origin/main"], workspace_path).stdout.strip()
    if not base_commit:
        return None, wst.step_error("FETCH_FAILED", "resolve-base", "origin/main did not resolve to a commit after fetch.")
    branch, line_of_work, refusal = _start_line(workspace_path, ident, place, ticket, discard=discard)
    if refusal is not None:
        return None, refusal
    wes.abort_if("after_branch")
    return (branch, line_of_work, base_commit, fetch_status), None


def _install_and_mark(repo_root: Path, hub: str, ident: wi.Identity, workspace_path: Path, args: argparse.Namespace,
                      ticket: wi.TicketRequest | None, line: tuple[str, str, str, str], action: str,
                      marker: dict[str, Any] | None = None) -> dict[str, Any]:
    """Install inside the folder, prove every ingredient, mark it ready, and build the ok answer.

    The work's uncommitted changes (if any) are set aside around the set-up and
    put back byte for byte, so finishing or re-readying never overwrites them.
    """
    branch, line_of_work, base_commit, fetch_status = line
    wg.run_git(["config", "gc.auto", "0"], workspace_path)
    wg.run_git(["config", "maintenance.auto", "false"], workspace_path)
    env_copied = wg.copy_optional_files(repo_root, workspace_path)

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
    wes.arm_after_install()
    with wes.work_set_aside(workspace_path):
        proof = wr.prove_ready(workspace_path, hub, kind=ident.kind, branch=branch, project_root=repo_root,
                               config_path=config_path, line_of_work=line_of_work)
    if proof.get("status") in ("refused", "error"):
        return proof  # a refusal never carries a workspace location
    checks = proof["checks"]
    ready = {**(marker or {}), **wst.build_marker(ident.kind, ident.slug, branch, hub, repo_root, base_commit, "ready",
                                               checks, workspace=workspace_path)}
    if marker and marker.get("created_at"):
        ready["created_at"] = marker["created_at"]
    ready["hooks_stages_declared"] = proof["hooks_stages_declared"]
    ready["line_of_work"] = line_of_work
    wes.write_ready_marker(workspace_path, ready)

    answer = {
        "status": "ok",
        "mechanism": "clone",
        "workspace_action": action,
        "kind": ident.kind,
        "slug": ident.slug,
        "branch": branch,
        "line_of_work": line_of_work,
        "hub": hub,
        **wp.path_fields(workspace_path),
        **wst.ok_fields(workspace_path, base_commit, fetch_status, action == "created"),
        "bootstrap": wst.bootstrap_fields(proof["bootstrap"], config_path, env_copied),
        "hooks_stages_declared": proof["hooks_stages_declared"],
        "checks": checks,
    }
    return wtr.finish(answer, ident.kind, ticket, workspace_path)


def _create_workspace(repo_root: Path, hub: str, ident: wi.Identity, place: Path, workspace_path: Path,
                       args: argparse.Namespace, ticket: wi.TicketRequest | None) -> dict[str, Any]:
    """Clone the main checkout, fetch the hub, checkout, install, and mark a brand-new workspace ready."""
    workspace_path.parent.mkdir(parents=True, exist_ok=True)
    clone_refusal = wst.clone_main_checkout(repo_root, workspace_path)
    if clone_refusal is not None:
        wi.discard_new_clone(workspace_path, place)
        return clone_refusal
    wg.write_marker(workspace_path, wst.build_marker(ident.kind, ident.slug, ident.branch, hub, repo_root, None,
                                                  "creating", workspace=workspace_path))
    wes.abort_if("after_clone")
    line, refusal = _checkout_line(hub, ident, place, workspace_path, args, ticket, discard=True)
    if refusal is not None:
        return refusal
    return _install_and_mark(repo_root, hub, ident, workspace_path, args, ticket, line, "created")


def _resume_workspace(repo_root: Path, hub: str, ident: wi.Identity, place: Path, workspace_path: Path,
                      args: argparse.Namespace, ticket: wi.TicketRequest | None,
                      marker: dict[str, Any]) -> dict[str, Any]:
    """Re-ready a ready workspace, or complete a half-made one, in place (the folder is never deleted)."""
    at_risk = wes.rescue_refusal(workspace_path) or wtr.conflict_refusal(workspace_path, ident.kind, ticket)
    if at_risk is not None:
        return at_risk
    state = marker.get("state")
    if state not in ("ready", "creating") or not (workspace_path / ".git").is_dir():
        return wes.incomplete_refusal(workspace_path, marker)
    wes.clear_torn_markers(workspace_path)
    action = "re-readied" if state == "ready" else "completed"
    if state == "creating" and not wes.checked_out(workspace_path):
        line, refusal = _checkout_line(hub, ident, place, workspace_path, args, ticket, discard=False)
        if refusal is not None:
            return refusal
        return _install_and_mark(repo_root, hub, ident, workspace_path, args, ticket, line, action, marker)
    fetch_status = wst.FETCH_SKIPPED
    if state == "ready":
        fetch_status, fetch_refusal = wst.refresh_main(workspace_path, args.allow_stale_base)
        if fetch_refusal is not None:
            return fetch_refusal
    branch, line_of_work, base = wes.head_state(workspace_path)
    if not ident.matches_branch(branch):
        return wes.incomplete_refusal(workspace_path, {**marker, "state": f"on line {branch!r}, not this work's"})
    if state == "ready":  # the line already begun: its recorded start, never moved or rebased
        base, line_of_work = marker.get("base_commit") or base, "resumed"
    return _install_and_mark(repo_root, hub, ident, workspace_path, args, ticket, (branch, line_of_work, base, fetch_status),
                             action, marker)


def _ensure_locked(repo_root: Path, hub: str, ident: wi.Identity, place: Path, workspace_path: Path,
                   args: argparse.Namespace, ticket: wi.TicketRequest | None) -> dict[str, Any]:
    """The ensure decision, taken while holding this work's lock: create, re-ready, or complete."""
    refusal = wi.occupied_refusal(repo_root, ident, workspace_path, hub)
    if refusal is not None and not (refusal.get("code") == "OCCUPIED" and wes.empty_folder(workspace_path)):
        return refusal
    marker = wg.read_marker(workspace_path) if workspace_path.exists() else None
    if marker is None:
        return _create_workspace(repo_root, hub, ident, place, workspace_path, args, ticket)
    return _resume_workspace(repo_root, hub, ident, place, workspace_path, args, ticket, marker)


def cmd_ensure(args: argparse.Namespace) -> dict[str, Any]:
    """Create (or idempotently confirm) the workspace for ``--kind``/``--slug``."""
    if args.kind not in wg.VALID_KINDS:
        return _err("USAGE", f"Unknown --kind {args.kind!r}; expected one of {wg.VALID_KINDS}.")
    if args.ticket and args.kind == "scratch":
        return _err("USAGE", "--ticket cannot be combined with --kind scratch.")

    repo_root, refusal = wl.resolve_repo_root(args.repo_root)
    if refusal is not None:
        return refusal
    place, usage = wl.landing_for(args.landing_root, repo_root)
    if usage is not None:
        return usage
    ctx = _repo_context(repo_root)
    ticket, ticket_usage = wi.resolve_ticket(args.ticket, repo_root)
    if ticket_usage is not None:
        return {**ticket_usage, **ctx}

    hub = wg.origin_url(repo_root)
    if hub is None:
        return {**_err("NO_HUB", f"{repo_root} has no 'origin' remote; cannot determine the hub."), **ctx}
    ctx["hub"] = hub

    ident = wi.resolve(args.kind, args.slug)
    workspace_path = wl.workspace_path_for(place, args.kind, ident.slug)

    with wes.ensure_lock(place, repo_root, ident.kind, ident.slug) as in_progress:
        if in_progress is not None:
            return {**in_progress, **ctx}
        return {**_ensure_locked(repo_root, hub, ident, place, workspace_path, args, ticket), **ctx}


def cmd_verify(args: argparse.Namespace) -> dict[str, Any]:
    """Read-only readiness re-check of the workspace marker at ``--path``."""
    bad_override = wl.override_refusal(args)
    if bad_override is not None:
        return bad_override
    workspace_path = wp.resolve_arg(args.path)
    marker = wg.read_marker(workspace_path)
    if marker is None:
        return _err("NOT_FOUND", f"No leafcutter workspace marker found at {workspace_path}.")
    if marker.get("state", "ready") != "ready":
        return worktree_remove.incomplete_answer(workspace_path, marker)
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
    remove_p.add_argument("--force", action="store_true", help="accepted and ignored: loss needs --discard-token")
    remove_p.add_argument("--discard-token")
    remove_p.add_argument("--delete-remote-branch", action="store_true")
    remove_p.add_argument("--repo-root")

    sub.add_parser("where")
    worktree_migrate.add_parser(sub)
    for name in ("ensure", "locate", "list", "verify", "remove"):
        sub.choices[name].add_argument("--landing-root")
    return parser


_DISPATCH = {
    "ensure": cmd_ensure,
    "locate": worktree_remove.cmd_locate,
    "list": worktree_admin.cmd_list,
    "verify": cmd_verify,
    "remove": worktree_remove.cmd_remove,
    "where": cmd_where,
    "migrate-legacy": worktree_migrate.cmd_migrate_legacy,
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
# - 2026-10-12 09:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/07)
#   BO-4300d-1/-i/-ii, d-2/-i/-ii/-iii: ensure now runs under a per-work lock
#   (worktree_ensure_state); a ready workspace is re-readied (fetch, rebuild,
#   fresh canaries, the work's uncommitted changes set aside and put back) and
#   a half-made one is completed in place, answered workspace_action
#   created | re-readied | completed. verify and locate refuse a workspace
#   whose marker is not ready (INCOMPLETE). (ADR-018)
# - 2026-10-12 20:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12)
#   BO-4300f-3: wired the migrate-legacy verb (worktree_migrate.py). (ADR-018)
# - 2026-10-21 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/20]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/20) BO-400e-3-ix: a ticket workspace records
#   its ticket and refuses a different one first (worktree_ticket_record). (ADR-018)
# - 2026-10-22 [python-coder/EPIC-WorkspaceMakerHardening/05]:
#   (#EPIC-WorkspaceMakerHardening/05) A1: ensure clones the main checkout and
#   fetches the hub with pruning (worktree_ensure_steps); M4: failed git
#   steps answer with ``step`` and no git text; M9c: the ok answer carries the
#   BO-4300c-2 base, fetch, created and bootstrap fields. (ADR-018)
# ===========================================================================
