"""
MODULE: worktree
GOAL: Be the one maker of workspaces: every route that needs an isolated copy of
    the project asks this file, and gets the same kind of workspace and the same
    answer shape back.
BUSINESS CONTEXT: Long-running builds, quick fixes, requirements sessions, the
    workspace skill and a person at a terminal each used to make workspaces in
    their own way, so each got different protections. One maker removes that
    difference (ADR-070, ADR-018 section 1, decision memo 2026-09-25).
ARCHITECTURE: Stdlib-only CLI, run as ``python <install>/scripts/worktree.py
    <verb> ...`` from any cwd. Verbs: ensure, locate, list, verify, remove,
    where. A workspace is a hardlinked local-path ``git clone --no-checkout``
    of the main checkout, with origin re-pointed at the hub, started from
    ``origin/main`` as fetched at request time, with its own install built by
    the project's own build entry point and an explicit config path. The marker
    ``.leafcutter-workspace.json`` is the registry (state creating, then ready).
    This file holds the verbs and the CLI; project resolution is the separate
    ``workspace.workspace_root`` module, and the shared primitives, readiness
    checks and creation sequence are ``workspace.workspace_core``,
    ``workspace.workspace_checks`` and ``workspace.workspace_create`` (the
    ``scripts/workspace/`` package, each with its own named deploy entry). Every answer
    is ONE JSON object on stdout; the maker never reads stdin and never
    prompts. No symlink is ever made. Git commits (the canary) run with the
    working directory set, never as ``git -C <path> commit``.

# DECISION HISTORY
# ================================================================================
# - 2026-10-14 12:00 [python-coder]: Created. The marker is a root-level
#   file excluded through .git/info/exclude (not under .leafcutter/) so no
#   install build can rewrite or clean it. An ensure on an existing ready
#   workspace re-verifies (including the canary) but does not rebuild. The
#   up-front discard authorisation for remove (Q8 open) is the --discard flag.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
# - 2026-10-14 17:00 [python-coder]: remove uses the shared discard_tree.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-070)
# - 2026-10-14 18:00 [python-coder]: A declined request (TICKET_NOT_ON_BASE,
#   OCCUPIED) answers status "refused" and exits 2; a folder with no marker is
#   OCCUPIED. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04) (BO-4300a-1-ii)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from workspace.workspace_checks import require_ready  # noqa: E402
from workspace.workspace_core import (  # noqa: E402
    KINDS, MAKER_VERSION, MakerError, dirname_for, discard_tree, log, make_plan,
    must, normalize_slug, out, plan_from_marker, read_marker, resolve_project, scan,
)
from workspace.workspace_create import (  # noqa: E402
    create_workspace, derive_build, ticket_fields, ticket_rel,
)


def _entry(ws: Path, marker: dict) -> dict:
    """Return the identity fields every answer about a workspace carries."""
    return {"kind": marker.get("kind"), "slug": marker.get("slug"),
            "branch": marker.get("branch"), "state": marker.get("state"),
            "hub": marker.get("hub"), "project_root": marker.get("project_root"),
            "base_commit": marker.get("base_commit"), "workspace_path": str(ws),
            "workspace_path_posix": ws.as_posix(), "worktree_path": str(ws)}


def _ok(verb: str, **fields: object) -> dict:
    """Return an ok answer with the fields common to every verb."""
    return {"status": "ok", "code": "OK", "verb": verb, "mechanism": "clone",
            "maker_version": MAKER_VERSION, **fields}


def _ready_answer(verb: str, plan: dict, base: str, checks: dict) -> dict:
    """Return the one ok answer shape for a ready workspace."""
    ws = plan["ws"]
    origin_main = out(ws, "rev-parse", "refs/remotes/origin/main")
    return _ok(verb, **_entry(ws, read_marker(ws) or {}), origin_main_commit=origin_main,
               base_matches_origin_main=origin_main == base, checks=checks)


def _find(project: Path, path: str) -> tuple[Path, dict]:
    """Return the (workspace, marker) at ``path`` in the landing place or raise."""
    want = os.path.realpath(path)
    for ws, marker in scan(project):
        if os.path.realpath(ws) == want:
            return ws, marker
    raise MakerError("NOT_FOUND", "no such workspace in the landing place")


def verb_ensure(args: argparse.Namespace) -> dict:
    """Make (or re-verify) the workspace for one piece of work."""
    if args.kind == "scratch" and args.ticket:
        raise MakerError("USAGE", "--ticket is not accepted with --kind scratch")
    plan = make_plan(args.kind, args.slug, args.repo_root)
    ws = plan["ws"]
    rel = ticket_rel(plan, args.ticket) if args.ticket else None
    resumed = ws.exists()
    if resumed:
        marker = read_marker(ws)
        if not marker:
            raise MakerError("OCCUPIED", f"{ws} holds something that is not a workspace",
                             workspace_path=str(ws))
        if marker.get("state") != "ready":
            raise MakerError("WORKSPACE_INCOMPLETE", f"{ws} exists but is not ready; "
                             "remove it and ensure again", workspace_path=str(ws))
        base = marker.get("base_commit") or ""
        answer = _ready_answer("ensure", plan, base, require_ready(plan, base, True))
    else:
        build = derive_build(plan["project"], args.config_path)
        wanted = (args.ticket, rel) if rel else None
        base, checks = create_workspace(plan, args.allow_stale_base, build, wanted)
        answer = _ready_answer("ensure", plan, base, checks)
    if rel:
        answer.update(ticket_fields(plan, rel, args.ticket, resumed))
    return answer


def verb_locate(args: argparse.Namespace) -> dict:
    """Find one workspace by path, branch, or kind plus slug (read-only)."""
    project = resolve_project(args.repo_root)
    if args.path:
        return _ok("locate", **_entry(*_find(project, args.path)))
    found = scan(project)
    if args.branch:
        match = [(w, m) for w, m in found if m.get("branch") == args.branch]
    elif args.kind and args.slug:
        name = dirname_for(args.kind, normalize_slug(args.kind, args.slug))
        match = [(w, m) for w, m in found if w.name == name]
    else:
        raise MakerError("BAD_ARGUMENT", "locate needs --path, --branch, or --kind and --slug")
    if not match:
        raise MakerError("NOT_FOUND", "no such workspace in the landing place")
    return _ok("locate", **_entry(*match[0]))


def verb_list(args: argparse.Namespace) -> dict:
    """List every workspace marker in the landing place (read-only)."""
    found = scan(resolve_project(args.repo_root))
    return _ok("list", workspaces=[_entry(w, m) for w, m in found])


def verb_verify(args: argparse.Namespace) -> dict:
    """Re-check one workspace's readiness (read-only)."""
    ws, marker = _find(resolve_project(args.repo_root), args.path)
    if (args.kind and args.kind != marker.get("kind")) or (
            args.slug and normalize_slug(marker["kind"], args.slug) != marker.get("slug")):
        raise MakerError("IDENTITY_MISMATCH", "the workspace belongs to other work")
    if marker.get("state") != "ready":
        raise MakerError("NOT_READY", "the workspace marker is not ready",
                         workspace_path=str(ws))
    plan = plan_from_marker(ws, marker)
    base = marker.get("base_commit") or ""
    return _ready_answer("verify", plan, base, require_ready(plan, base, True))


def _refuse_unsaved(ws: Path, branch: str | None) -> None:
    """Raise when the workspace holds uncommitted or unpushed work."""
    if out(ws, "status", "--porcelain"):
        raise MakerError("UNSAVED_WORK", "the workspace has uncommitted changes",
                         workspace_path=str(ws))
    pushed = branch and out(ws, "rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}")
    upstream = f"origin/{branch}" if pushed else "origin/main"
    if out(ws, "rev-list", "--count", f"{upstream}..HEAD") not in (None, "0"):
        raise MakerError("UNSAVED_WORK", f"the workspace has commits not on {upstream}",
                         workspace_path=str(ws))


def verb_remove(args: argparse.Namespace) -> dict:
    """Delete one workspace; refuses unsaved work unless --discard was given."""
    ws, marker = _find(resolve_project(args.repo_root), args.path)
    if not args.discard:
        _refuse_unsaved(ws, marker.get("branch"))
    if args.delete_remote_branch and marker.get("branch"):
        must(ws, "REMOTE_DELETE_FAILED", "push", "origin", "--delete", marker["branch"])
    try:
        discard_tree(ws)
    except OSError as exc:
        raise MakerError("REMOVE_FAILED", f"cannot delete {ws}: {exc}") from exc
    return _ok("remove", **_entry(ws, marker), removed=True)


def verb_where(_args: argparse.Namespace) -> dict:
    """Print the maker's own absolute path."""
    return _ok("where", maker_path=os.path.realpath(__file__))


class _Parser(argparse.ArgumentParser):
    """An argument parser that raises a classified error instead of exiting."""

    def error(self, message: str) -> None:  # type: ignore[override]
        raise MakerError("BAD_ARGUMENT", message)


def _build_parser() -> argparse.ArgumentParser:
    """Build the verb parser."""
    top = _Parser(prog="worktree.py")
    sub = top.add_subparsers(dest="verb", required=True, parser_class=_Parser)

    def verb(name: str, *flags: str) -> argparse.ArgumentParser:
        sp = sub.add_parser(name)
        for flag in ("--repo-root", *flags):
            sp.add_argument(flag)
        return sp

    ens = verb("ensure", "--ticket", "--config-path")
    ens.add_argument("--kind", required=True, choices=KINDS)
    ens.add_argument("--slug", required=True)
    ens.add_argument("--allow-stale-base", action="store_true")
    loc = verb("locate", "--slug", "--path", "--branch")
    loc.add_argument("--kind", choices=KINDS)
    verb("list")
    ver = verb("verify", "--slug")
    ver.add_argument("--path", required=True)
    ver.add_argument("--kind", choices=KINDS)
    rem = verb("remove")
    rem.add_argument("--path", required=True)
    rem.add_argument("--discard", action="store_true")
    rem.add_argument("--delete-remote-branch", action="store_true")
    sub.add_parser("where")
    return top


_VERBS = {"ensure": verb_ensure, "locate": verb_locate, "list": verb_list,
          "verify": verb_verify, "remove": verb_remove, "where": verb_where}


def main(argv: list[str] | None = None) -> int:
    """Run one verb and print its single JSON answer; exit 0 only on ok."""
    words = sys.argv[1:] if argv is None else argv
    verb = words[0] if words and words[0] in _VERBS else "unknown"
    try:
        args = _build_parser().parse_args(words)
        payload, code = _VERBS[args.verb](args), 0
    except MakerError as exc:
        payload, code = exc.payload(verb), 2 if exc.refused else 1
    except Exception as exc:  # noqa: BLE001 - boundary: unclassified becomes an error answer
        log.warning("unclassified failure in %s: %r", verb, exc)
        payload = MakerError("INTERNAL_ERROR", f"{type(exc).__name__}: {exc}").payload(verb)
        code = 1
    sys.stdout.write(json.dumps(payload) + "\n")
    return code


if __name__ == "__main__":
    sys.exit(main())
