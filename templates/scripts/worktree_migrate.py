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
    brought-over workspace comes from ``worktree_identity``'s declared aliases
    and its place from ``worktree_layout`` (Q4 + Q5). Registrations are read as
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
import os
import shutil
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg
import worktree_identity as wi
import worktree_layout as wl
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
        stuck = _text(entry / "locked").startswith("initializing") and (folder is None or not folder.exists())
        found.append(Registration(entry, folder, branch, stuck))
    return found


def _rmtree_onerror(func: Any, target: str, _exc: Any) -> None:
    """Clear the read-only bit and retry the failed deletion once."""
    os.chmod(target, stat.S_IWRITE)
    func(target)


def _drop(path: Path) -> str | None:
    """Delete the folder *path* (a registration or a failed clone); an error text, or ``None``."""
    try:
        shutil.rmtree(path, onerror=_rmtree_onerror)
    except OSError as exc:
        _log.warning("_drop: could not delete %s: %s", path, exc)
        return f"could not delete {path}: {exc}"
    return None


def identity_for(branch: str) -> wi.Identity | None:
    """The canonical identity a legacy *branch* maps to through the declared aliases, else ``None``."""
    declared = [(kind, prefix) for kind, aliases in wi.LEGACY_ALIASES.items() for prefix, _why in aliases]
    for kind, prefix in [*declared, *((kind, f"{kind}/") for kind in wg.VALID_KINDS)]:
        if branch.startswith(prefix) and len(branch) > len(prefix):
            return wi.Identity(kind, wi.slugify(branch[len(prefix):]))
    return None


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

def _status_paths(folder: Path) -> set[str] | None:
    """Every path git reports as changed or untracked in *folder* (rename sources included), or ``None``."""
    proc = wg.run_git(["status", "--porcelain=v1", "-z", "--untracked-files=all"], folder)
    if proc.returncode != 0:
        return None
    parts, paths, i = proc.stdout.split("\0"), set(), 0
    while i < len(parts):
        item = parts[i]
        i += 1
        if len(item) < 4:
            continue
        paths.add(item[3:])
        if item[0] in "RC" and i < len(parts) and parts[i]:
            paths.add(parts[i])
            i += 1
    return paths


def _bytes(path: Path) -> bytes | None:
    """The file's bytes, or ``None`` when it is not a readable file."""
    try:
        return path.read_bytes() if path.is_file() else None
    except OSError as exc:
        _log.warning("_bytes: cannot read %s: %s", path, exc)
        return None


def _carry(src: Path, dst: Path, paths: set[str]) -> None:
    """Write each changed path's current bytes from *src* into *dst* (or remove it there if gone)."""
    for rel in sorted(paths):
        source, target = src / rel, dst / rel
        if source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        elif target.exists():
            os.chmod(target, stat.S_IWRITE)
            target.unlink()


def _lossless(src: Path, dst: Path, paths: set[str], commits: list[str]) -> str | None:
    """Why the clone is NOT provably lossless, or ``None`` when every check holds."""
    head = [wg.run_git(["rev-parse", "HEAD"], folder).stdout.strip() for folder in (src, dst)]
    if not head[0] or head[0] != head[1]:
        return "the clone's HEAD is not the original's"
    for sha in commits:
        if wg.run_git(["cat-file", "-e", f"{sha}^{{commit}}"], dst).returncode != 0:
            return f"commit {sha} is missing from the clone"
    if _status_paths(dst) != paths:
        return "the clone's changed-file set differs from the original's"
    differing = [rel for rel in sorted(paths) if _bytes(src / rel) != _bytes(dst / rel)]
    return f"content differs for {differing[0]}" if differing else None


def _marker(ctx: Context, reg: Registration, ident: wi.Identity, target: Path) -> dict[str, Any]:
    """The ready marker for a brought-over workspace (hub and project stored relative to it)."""
    base = wg.run_git(["rev-parse", "origin/main"], target).stdout.strip() or None
    return {
        "schema_version": 1, "kind": ident.kind, "slug": ident.slug, "branch": reg.branch,
        "hub": wp.portable(ctx.hub, target), "project_root": wp.portable(str(ctx.repo_root), target),
        "base_commit": base, "maker_version": wg.MAKER_VERSION, "state": "ready", "line_of_work": "resumed",
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "brought_over_from": str(reg.folder),
    }


def _git_steps(ctx: Context, reg: Registration, target: Path) -> str | None:
    """Clone the hub to *target* and check the legacy line out on it; the failing step, or ``None``."""
    branch = reg.branch or ""
    steps = [
        (["clone", "--no-checkout", "--local", ctx.hub, str(target)], ctx.repo_root),
        (["fetch", str(ctx.repo_root), f"+refs/heads/{branch}:refs/heads/{branch}"], target),
        (["checkout", "-f", branch], target),
    ]
    for cmd, cwd in steps:
        proc = wg.run_git(cmd, cwd)
        if proc.returncode != 0:
            return f"git {cmd[0]} failed: {proc.stderr.strip()}"
    if wg.run_git(["rev-parse", "--verify", "-q", f"refs/remotes/origin/{branch}"], target).returncode == 0:
        wg.run_git(["branch", f"--set-upstream-to=origin/{branch}"], target)
    return None


def _build_clone(ctx: Context, reg: Registration, ident: wi.Identity, target: Path,
                 unsent: dict[str, Any]) -> str | None:
    """Make the marker-bearing clone at *target*; a reason it could not be proved lossless, else ``None``."""
    folder = reg.folder
    paths = _status_paths(folder) if folder else None
    if folder is None or paths is None:
        return "the changed files of the old workspace could not be listed"
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        reason = _git_steps(ctx, reg, target)
        if reason is None:
            _carry(folder, target, paths)
            reason = _lossless(folder, target, paths, unsent["commits"])
        if reason is None:
            wg.write_marker(target, _marker(ctx, reg, ident, target))
    except OSError as exc:
        _log.warning("_build_clone: %s", exc)
        reason = f"file operation failed: {exc}"
    if reason is not None:
        _drop(target)
        if not any(target.parent.iterdir()):
            target.parent.rmdir()
    return reason


# ------------------------------------------------------------------ per workspace

def _decide(base: dict[str, Any], reason: str) -> tuple[str, dict[str, Any]]:
    """A ``needs_decision`` outcome: the old workspace is left exactly as it is."""
    return "needs_decision", {**base, "reason": reason}


def _retire(ctx: Context, reg: Registration, base: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Remove the old workspace's folder and its registration (it holds nothing unsent)."""
    if not ctx.preview:
        failure = wrm._delete_tree(reg.folder) if reg.folder and reg.folder.exists() else None  # noqa: SLF001
        if failure is not None:
            return _decide(base, failure["message"])
        error = _drop(reg.admin)
        if error is not None:
            return _decide(base, error)
    return "retired", base


def _bring_over(ctx: Context, reg: Registration, base: dict[str, Any],
                unsent: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Bring the unsent work over to its canonical place, or list it for a decision (never guessing)."""
    ident = identity_for(reg.branch) if reg.branch else None
    if ident is None:
        return _decide(base, f"no declared alias maps line of work {reg.branch!r} to a kind and name")
    target = wl.workspace_path_for(ctx.place, ident.kind, ident.slug)
    if target.exists():
        return _decide(base, f"{target} is already occupied")
    brought = {**base, "workspace_path": str(target)}
    if ctx.preview:
        return "brought_over", brought
    reason = _build_clone(ctx, reg, ident, target, unsent)
    if reason is not None:
        return _decide(base, f"not provably lossless, left untouched: {reason}")
    outcome, entry = _retire(ctx, reg, base)
    if outcome != "retired":
        _drop(target)
        return _decide(base, f"the brought-over copy was withdrawn: {entry['reason']}")
    return "brought_over", brought


def handle(ctx: Context, reg: Registration) -> tuple[str, dict[str, Any]]:
    """Take the BO-4100c-1 verdict for one old workspace and act on it; ``(bucket, report entry)``."""
    base = {"path": str(reg.folder), "branch": reg.branch}
    if reg.folder is None or not reg.folder.exists():
        return _retire(ctx, reg, base)  # a registration whose folder is gone holds nothing
    unsent, refusal = wrm.unsent_work(reg.folder)
    if unsent is None:
        return _decide(base, (refusal or {}).get("message", "the unsent work could not be classified"))
    if not unsent["commits"] and not unsent["files"]:
        return _retire(ctx, reg, base)
    return _bring_over(ctx, reg, base, unsent)


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
                _drop(reg.admin)
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
# ===========================================================================
