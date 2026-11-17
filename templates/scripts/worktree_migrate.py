"""
MODULE: worktree_migrate
GOAL: The workspace maker's ``migrate-legacy`` verb: bring over or retire every
    workspace made the old way (a linked git worktree) without losing work, and
    keep git's automatic housekeeping from pruning the shared history until the
    last one is gone (AC BO-4300f-3, f-3-i, f-3-ii).
BUSINESS CONTEXT: Every existing project still holds old-style workspaces that
    share the main copy's version history. A workspace holding nothing unsent
    is retired (folder and registration); one holding unsent work is brought
    over as a marker-bearing clone ONLY when provably lossless, otherwise left
    untouched and listed for a human decision (Q10). Stuck registrations made
    from a Linux shell ("locked initializing") are removed individually. While
    any old-style workspace remains, ``gc.auto 0`` / ``maintenance.auto false``
    are held on the main copy (ADR-018 migration step 2) and the previous values
    are restored by the run that clears the last one.
ARCHITECTURE: Stdlib-only. The unsent-work verdict is ``worktree_remove.
    unsent_work`` (BO-4100c-1), imported, never copied. The identity of a
    brought-over workspace comes from ``worktree_identity`` (canonical prefixes,
    then declared aliases) and its place from ``worktree_layout``; what must be
    kept or reported comes from ``worktree_migrate_guards`` and the copy-and-prove
    steps from ``worktree_migrate_carry``. Registrations are read as
    plain files under ``<git-common-dir>/worktrees`` and deleted individually
    (no ``git worktree prune``, which would touch entries this verb does not
    own). The report is ONE JSON object (``retired``, ``brought_over``,
    ``needs_decision``, ``unfinished_removed``) that is byte-stable across
    re-runs. ``--preview`` changes no folder, registration, ref or config (it
    still refreshes remote-tracking refs to take the unsent verdict).
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg
import worktree_identity as wi
import worktree_layout as wl
import worktree_migrate_carry as wmc
import worktree_migrate_guards as wmg
import worktree_paths as wp
import worktree_remove as wrm

_log = logging.getLogger(__name__)

_HELD = {"gc.auto": "0", "maintenance.auto": "false"}
_RECORD = "leafcutter.cutover.previous-"
_UNSET = "<unset>"


@dataclass(frozen=True)
class Registration:
    """One entry of the main copy's ``worktrees`` administrative folder."""

    admin: Path
    folder: Path | None
    branch: str | None
    stuck: bool
    lock: str | None = None


@dataclass(frozen=True)
class Context:
    """What every per-workspace step needs: the project, its hub, the landing root, preview."""

    repo_root: Path
    hub: str
    place: Path
    preview: bool


# --------------------------------------------------------------- registrations

def _text(path: Path) -> str:
    """The stripped text of *path*, or an empty string when absent or unreadable."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def registrations(repo_root: Path) -> list[Registration]:
    """Every linked-worktree registration of *repo_root*, in name order (read-only)."""
    proc = wg.run_git(["rev-parse", "--git-common-dir"], repo_root)
    common = Path(proc.stdout.strip() or ".git")
    admin_root = (common if common.is_absolute() else repo_root / common) / "worktrees"
    if not admin_root.is_dir():
        return []
    found = []
    for entry in sorted(admin_root.iterdir()):
        gitdir, head = _text(entry / "gitdir"), _text(entry / "HEAD")
        folder = Path(gitdir).parent if gitdir else None
        branch = head[len("ref: refs/heads/"):] if head.startswith("ref: refs/heads/") else None
        lock = _text(entry / "locked") if (entry / "locked").exists() else None
        stuck = lock == wmg.WSL_LOCK and (folder is None or not folder.exists())
        found.append(Registration(entry, folder, branch, stuck, lock))
    return found


def identity_for(branch: str) -> wi.Identity | None:
    """The one canonical identity a legacy *branch* maps to, else ``None``.

    The canonical ``<kind>/`` prefixes are tried first, the kinds' declared
    legacy aliases second, so a line is never given two identities (A4). The
    slug is whatever ``wi.slugify`` makes of the rest; whether it is usable is
    :func:`identity_problem`'s call.
    """
    canonical = [(kind, f"{kind}/") for kind in wg.VALID_KINDS]
    declared = [(kind, prefix) for kind, aliases in wi.LEGACY_ALIASES.items() for prefix, _why in aliases]
    for kind, prefix in [*canonical, *declared]:
        if branch.startswith(prefix) and len(branch) > len(prefix):
            return wi.Identity(kind, wi.slugify(branch[len(prefix):]))
    return None


def identity_problem(branch: str | None) -> tuple[wi.Identity | None, str | None]:
    """``(identity, None)`` for a mappable line, else ``(None, why it is left for a decision)``."""
    ident = identity_for(branch) if branch else None
    if ident is None:
        return None, f"no kind prefix or declared alias maps line of work {branch!r} to a kind and name"
    problem = wi.slug_problem(ident.slug)
    if problem is not None:
        return None, f"the name part of line of work {branch!r} cannot name a workspace: {problem}"
    return ident, None


# ----------------------------------------------------------------- housekeeping

def _config_get(repo_root: Path, key: str) -> str | None:
    """The main copy's local value of config *key*, or ``None`` when unset."""
    proc = wg.run_git(["config", "--local", "--get", key], repo_root)
    return proc.stdout.strip() if proc.returncode == 0 else None


def hold_housekeeping(repo_root: Path) -> None:
    """Hold automatic housekeeping off, recording each previous value once (re-runs keep the first)."""
    for key, held in _HELD.items():
        record = _RECORD + key.replace(".", "-")
        if _config_get(repo_root, record) is None:
            previous = _config_get(repo_root, key)
            wg.run_git(["config", "--local", record, _UNSET if previous is None else previous], repo_root)
        wg.run_git(["config", "--local", key, held], repo_root)


def restore_housekeeping(repo_root: Path) -> None:
    """Put the recorded previous housekeeping values back (unset again if they were unset)."""
    for key in _HELD:
        record = _RECORD + key.replace(".", "-")
        previous = _config_get(repo_root, record)
        if previous is None:
            continue
        if previous == _UNSET:
            wg.run_git(["config", "--local", "--unset", key], repo_root)
        else:
            wg.run_git(["config", "--local", key, previous], repo_root)
        wg.run_git(["config", "--local", "--unset", record], repo_root)


# --------------------------------------------------------------------- bring over

# ------------------------------------------------------------------ per workspace

def _decide(base: dict[str, Any], reason: str) -> tuple[str, dict[str, Any]]:
    """A ``needs_decision`` outcome: the old workspace is left exactly as it is."""
    return "needs_decision", {**base, "reason": reason}


def _both(why: str, folder: Path | None, target: Path, admin: Path) -> str:
    """A reason that names BOTH locations (the old workspace and the verified copy) and what remains of each."""
    return (f"{why}. Nothing further was deleted: the old workspace is at {folder} (its registration is {admin}) "
            f"and the verified brought-over copy is at {target}; decide which to keep.")


def _retire(ctx: Context, reg: Registration, base: dict[str, Any],
            before: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]]:
    """Remove the old workspace's folder and its registration (it holds nothing unsent).

    The git-ignored files the deletion removes are listed first, from git's
    own ignored listing, on the entry and in the preview (A9b). Just before
    the delete the folder is checked unchanged since *before* (M-2).
    """
    folder = reg.folder if reg.folder is not None and reg.folder.exists() else None
    ignored = wmg.ignored_paths(folder) if folder else []
    if ignored is None:
        return _decide(base, "could not check which ignored files it holds; it is left as it is")
    if not ctx.preview:
        if folder and before is not None and wmc.snapshot(folder, []) != before:
            return _decide(base, "it changed after it was checked (or could not be checked again); it is left as it is")
        failure = wrm.delete_whole_folder(folder) if folder else None
        if failure is not None:
            return _decide(base, f"{failure} What remains is still at {folder}; its registration {reg.admin} was kept.")
        error = wrm.delete_whole_folder(reg.admin)
        if error is not None:
            return _decide(base, f"its folder was removed but its registration {reg.admin} could not be: {error}")
    return "retired", {**base, "ignored_removed": ignored}


def _finish_bring_over(reg: Registration, base: dict[str, Any], brought: dict[str, Any], target: Path,
                       before: dict[str, Any], carried: list[str]) -> tuple[str, dict[str, Any]]:
    """Retire the old folder once it is shown unchanged since the proof; the verified copy is NEVER deleted here."""
    folder = reg.folder
    if folder is None or wmc.snapshot(folder, carried) != before:
        return _decide(base, _both("the old workspace changed while it was copied (or could not be checked again)",
                                   folder, target, reg.admin))
    failure = wrm.delete_whole_folder(folder)
    if failure is not None:
        return _decide(base, _both(f"the old folder could not be fully removed ({failure}); it may be partly deleted",
                                   folder, target, reg.admin))
    error = wrm.delete_whole_folder(reg.admin)
    if error is not None:
        return _decide(base, _both(f"the old folder was removed but its registration could not be ({error})",
                                   folder, target, reg.admin))
    return "brought_over", brought


def _bring_over(ctx: Context, reg: Registration, base: dict[str, Any],
                unsent: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Bring the unsent work over to its canonical place, or list it for a decision (never guessing)."""
    ident, problem = identity_problem(reg.branch)
    folder = reg.folder
    if ident is None or folder is None or reg.branch is None:
        return _decide(base, problem or "no identity")
    target = wl.workspace_path_for(ctx.place, ident.kind, ident.slug)
    if target.exists():
        return _decide(base, f"{target} is already occupied")
    ignored = wmg.ignored_paths(folder)
    if ignored is None:
        return _decide(base, "could not check which ignored files it holds; it is left as it is")
    carried, install = wmc.split_ignored(ignored)
    brought = {**base, "workspace_path": str(target), "next": f"ensure --kind {ident.kind} --slug {ident.slug}",
               "ignored_removed": install}
    if ctx.preview:
        return "brought_over", brought
    before = wmc.snapshot(folder, carried, unsent)
    if before is None:
        return _decide(base, "could not check what it holds; it is left as it is")
    reason = wmc.build_clone(ctx.repo_root, ctx.hub, folder, reg.branch, ident, target, before, carried)
    if reason is not None:
        return _decide(base, f"not provably lossless, left untouched: {reason}")
    return _finish_bring_over(reg, base, brought, target, before, carried)


def handle(ctx: Context, reg: Registration) -> tuple[str, dict[str, Any]]:
    """Take the BO-4100c-1 verdict for one old workspace and act on it; ``(bucket, report entry)``."""
    base = {"path": str(reg.folder), "branch": reg.branch}
    kept = wmg.blocker(ctx.repo_root, reg.admin, reg.folder, reg.branch, reg.lock)
    if kept is not None:
        return _decide(base, kept)
    if reg.folder is None or not reg.folder.exists():
        return _retire(ctx, reg, base)  # a registration whose folder is gone holds nothing
    unsent, refusal = wrm.unsent_work(reg.folder)
    if unsent is None:
        return _decide(base, (refusal or {}).get("message", "the unsent work could not be classified"))
    if unsent["commits"] or unsent["files"]:
        return _bring_over(ctx, reg, base, unsent)
    before = None if ctx.preview else wmc.snapshot(reg.folder, [], unsent)
    if before is None and not ctx.preview:
        return _decide(base, "could not check what it holds; it is left as it is")
    return _retire(ctx, reg, base, before)


def _summary(report: dict[str, Any]) -> str:
    """One stable sentence saying what the run did or that nothing is left but the listed decisions."""
    done = len(report["retired"]) + len(report["brought_over"]) + len(report["unfinished_removed"])
    left = len(report["needs_decision"])
    if not done:
        return ("Nothing left to do" + (f" other than the {left} workspace(s) listed in needs_decision."
                                        if left else "."))
    return f"Handled {done} old-style workspace(s); {left} left in needs_decision."


def cmd_migrate_legacy(args: argparse.Namespace) -> dict[str, Any]:
    """Retire or bring over every old-style workspace of ``--repo-root``; ``--preview`` changes nothing."""
    repo_root, refusal = wl.resolve_repo_root(args.repo_root)
    if refusal is not None:
        return refusal
    place, usage = wl.landing_for(args.landing_root, repo_root)
    if usage is not None:
        return usage
    hub = wg.origin_url(repo_root)
    if hub is None:
        return wa.error_answer("NO_HUB", f"{repo_root} has no 'origin' remote; cannot determine the hub.")
    ctx, regs = Context(repo_root, hub, place, bool(args.preview)), registrations(repo_root)
    report: dict[str, Any] = {"retired": [], "brought_over": [], "needs_decision": [], "unfinished_removed": []}
    if regs and not ctx.preview:
        hold_housekeeping(repo_root)
    for reg in regs:
        if reg.stuck:
            report["unfinished_removed"].append(reg.admin.name)
            if not ctx.preview:
                wrm.delete_whole_folder(reg.admin)
            continue
        bucket, entry = handle(ctx, reg)
        report[bucket].append(entry)
    if not ctx.preview and not report["needs_decision"]:
        restore_housekeeping(repo_root)
    return {"status": "ok", "preview": ctx.preview, **report, "message": _summary(report),
            **wp.repo_fields(repo_root)}


def add_parser(sub: Any) -> None:
    """Register the ``migrate-legacy`` verb's arguments on the maker's subparsers."""
    parser = sub.add_parser("migrate-legacy")
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--repo-root")
    parser.add_argument("--landing-root")


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-12 20:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12)
#   Created: BO-4300f-3/-i/-ii. A brought-over workspace is cloned from the
#   hub, the legacy line fetched from the main copy, and its uncommitted and
#   untracked bytes carried; it is kept only after HEAD, every unsent commit,
#   the changed-file set and every file's bytes match, and its marker is
#   written 'ready' with line_of_work 'resumed' so a later ensure re-readies
#   it. Housekeeping is held and its previous values recorded under
#   leafcutter.cutover.* until needs_decision is empty. (ADR-018)
# - 2026-10-22 [python-coder/EPIC-WorkspaceMakerHardening/08]: clone the main
#   checkout (A1), marker 'creating' + `next` (A8), canonical-first identity
#   (A4), shared delete/status helpers (M17), guards and ignored_removed (A9).
#   Rework (pr-reviewer): the verified copy is never deleted; the old folder is
#   deleted only after an unchanged re-check; guards fail closed; ignored files
#   are carried. (ADR-018)
# ===========================================================================
