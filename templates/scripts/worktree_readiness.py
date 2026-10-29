"""
MODULE: worktree_readiness
GOAL: Decide, from the finished workspace as it exists, whether the workspace
    maker may answer "ready" -- and if not, which ingredient is false
    (BO-4300c-1, c-1-i, c-1-ii, c-1-iii, b-4).
BUSINESS CONTEXT: "Ready" used to mean "the maker ran its steps". It now means
    the workspace is an independent copy on its own (non-main) line of work,
    based on the fresh shared tip (or, for a resumed line, holding every
    commit of its remote line), built by an install that finished, with every
    protection the project DECLARES shown to fire by a real operation it
    rejects, and no change to a version-controlled file the work did not
    make. Any false ingredient is a refusal naming it and carrying no
    workspace location.
ARCHITECTURE: Stdlib-only; every git call goes through ``worktree_git.run_git``
    (working directory = the workspace, never ``git -C``). The stage set comes
    from the workspace's own generated ``.pre-commit-config.yaml``; the known-bad
    input for each stage comes from the install's own ``commit_guardian.json``
    (``stage_canaries``). Shims are installed by the install's own
    ``install_pre_commit_shims.py`` run as a separate process. No link is
    created anywhere (the build is told to copy its shims). There is no flag or
    environment switch that skips an ingredient. Canaries are ``run_canaries``
    (in the sibling ``worktree_canaries`` module, deployed beside this one):
    they leave the branch tip, index and tree exactly as before.
"""

from __future__ import annotations

import hashlib
import logging
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import workspace_root
import worktree_answer as wa
import worktree_git as wg
import worktree_log_root as wlr
from worktree_canaries import (  # noqa: F401  (hooks_dir/install_dir re-exported for callers)
    declared_stages, hooks_dir, install_dir, install_shims, run_canaries,
)

_log = logging.getLogger(__name__)

KNOWN_STAGES = ("pre-commit", "commit-msg", "post-merge")
PROTECTED_BRANCHES = ("main", "master")
_EXCERPT_BYTES = 4096


def run_install_build(workspace: Path, config_path: Path) -> dict[str, Any]:
    """Run the workspace's own install build; never creates a link (BO-4300b-4).

    Returns:
        ``{"ok": bool, "code": str | None, "excerpt": str}``. ``code`` is
        ``BOOTSTRAP_FAILED`` for every failed-install outcome and ``NO_CONFIG``
        when *config_path* is missing; ``excerpt`` is the bounded tail (4 KB) of
        the build's own stderr, one line per `` | `` -- also relayed to stderr,
        never stdout.
    """
    build_script = workspace / "scripts" / "build.py"
    if not build_script.is_file():
        return {"ok": False, "code": "BOOTSTRAP_FAILED", "excerpt": "scripts/build.py is absent"}
    if not config_path.is_file():
        return {"ok": False, "code": "NO_CONFIG", "excerpt": ""}
    try:
        proc = wlr.build_with_inherited_log_root(
            [sys.executable, str(build_script), "--target-dir", str(workspace), "--config-path", str(config_path)],
            Path(__file__).resolve().parents[1],
            cwd=str(workspace), capture_output=True, text=True, timeout=300, check=False,
            env={**os.environ, "LEAFCUTTER_SHIM_STRATEGY": "copy"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("run_install_build: failed to launch %s: %s", build_script, exc)
        return {"ok": False, "code": "BOOTSTRAP_FAILED", "excerpt": f"could not launch the build: {exc}"}
    wa.forward_child_output(proc)
    if proc.returncode == 0:
        return {"ok": True, "code": None, "excerpt": ""}
    _log.warning("run_install_build: %s exited %s", build_script, proc.returncode)
    text = (proc.stderr or proc.stdout or "").encode("utf-8", "replace")[-_EXCERPT_BYTES:].decode("utf-8", "ignore")
    excerpt = " | ".join(line.strip() for line in text.splitlines() if line.strip())
    return {"ok": False, "code": "BOOTSTRAP_FAILED", "excerpt": excerpt[-(_EXCERPT_BYTES - 64):]}


def tracked_changes(workspace: Path) -> list[str]:
    """Tracked paths differing from HEAD in the index or tree (``git diff HEAD``; untracked excluded)."""
    proc = wg.run_git(["diff", "--name-only", "-z", "HEAD"], workspace)
    if proc.returncode != 0:
        return []
    return sorted(p for p in proc.stdout.split("\0") if p)


def tree_is_clean(workspace: Path) -> bool:
    """True only when HEAD resolves and ``git status`` named no tracked change (fails closed on a git error).

    ``git status`` with untracked files excluded, not ``git diff HEAD``: porcelain
    ``git diff`` rewrites ``.git/index`` to refresh a stat-dirty entry even under
    ``GIT_OPTIONAL_LOCKS=0``, while ``git status`` honours it -- verify must never write.
    """
    if wg.run_git(["rev-parse", "--verify", "-q", "HEAD"], workspace).returncode != 0:
        return False  # no commit (or not a repo): unreadable, never clean
    proc = wg.run_git(["status", "--porcelain", "-z", "--untracked-files=no"], workspace)
    return proc.returncode == 0 and not any(proc.stdout.split("\0"))


def _digest(workspace: Path, rel: str) -> str:
    """Content digest of *rel* in *workspace* ('deleted' when it does not exist)."""
    try:
        return hashlib.sha256((workspace / rel).read_bytes()).hexdigest()
    except OSError:
        return "deleted"


def snapshot_tracked(workspace: Path) -> dict[str, str]:
    """Snapshot the tracked-file state before the build: each already-changed path -> digest."""
    return {rel: _digest(workspace, rel) for rel in tracked_changes(workspace)}


def restore_build_changes(workspace: Path, before: dict[str, str]) -> tuple[list[str], list[str]]:
    """Put back every tracked path the build changed; never touch the work's own changes.

    Returns:
        ``(restored, unrestorable)``. A path that was already changed before
        the build and differs now cannot be told apart from the work's own
        edits, so it is reported (never restored away); so is any path the
        restore could not bring back.
    """
    after = tracked_changes(workspace)
    build_made = [p for p in after if p not in before]
    unrestorable = [p for p in after if p in before and _digest(workspace, p) != before[p]]
    for start in range(0, len(build_made), 100):
        wg.run_git(["checkout", "HEAD", "--", *build_made[start:start + 100]], workspace)
    still = set(tracked_changes(workspace))
    return [p for p in build_made if p not in still], sorted(set(unrestorable) | (set(build_made) & still))


def _git(workspace: Path, *args: str) -> subprocess.CompletedProcess:
    """``git <args>`` with cwd = workspace (never ``-C``)."""
    return wg.run_git(list(args), workspace)


def hook_checks(stages: list[str], fired: dict[str, bool], kind: str) -> dict[str, Any]:
    """Build the per-stage ``hooks_*_fired`` keys and their conjunction ``hooks_canary_rejected``.

    Scratch: every one is ``'n/a'``. Otherwise pre-commit is never ``'n/a'``
    (undeclared is ``False``); the other two are ``'n/a'`` only when the
    project does not declare that stage.
    """
    keys = {s: "hooks_" + s.replace("-", "_") + "_fired" for s in (*KNOWN_STAGES, *stages)}
    if kind == "scratch":
        return {**{k: "n/a" for k in keys.values()}, "hooks_canary_rejected": "n/a"}
    out: dict[str, Any] = {}
    for stage, key in keys.items():
        if stage in stages:
            out[key] = fired.get(stage, False)
        else:
            out[key] = False if stage == "pre-commit" else "n/a"
    out["hooks_canary_rejected"] = all(v is True for v in out.values() if v != "n/a")
    return out


_REPARSE_POINT = 0x400  # Windows FILE_ATTRIBUTE_REPARSE_POINT (symlink or junction)
_INSTALL_PATHS = (".leafcutter", ".pre-commit-config.yaml", os.path.join(".git", "hooks"))


def is_link(path: Path) -> bool:
    """True when *path* itself is a symlink or a Windows reparse point (junction); a missing path is not."""
    try:
        info = path.lstat()
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)


def install_paths_regular(workspace: Path) -> bool:
    """True when nothing under the install and protection paths is a link (BO-4300b-4, lstat only)."""
    for rel in _INSTALL_PATHS:
        root = workspace / rel
        if is_link(root):
            return False
        for here, dirs, files in os.walk(root, followlinks=False):
            if any(is_link(Path(here, name)) for name in (*dirs, *files)):
                return False
    return True


def _norm(path: Path) -> str:
    """Resolved, case-normalised spelling of *path* for comparing two locations."""
    return os.path.normcase(str(path.resolve()))


def is_independent(workspace: Path) -> bool:
    """True when the workspace owns its object store: real ``.git`` dir, own common dir, no alternates."""
    git_dir = workspace / ".git"
    if is_link(git_dir) or not git_dir.is_dir() or (git_dir / "objects" / "info" / "alternates").exists():
        return False
    common = _git(workspace, "rev-parse", "--path-format=absolute", "--git-common-dir")
    text = common.stdout.strip() if common.returncode == 0 else ""
    return bool(text) and _norm(Path(text)) == _norm(git_dir)


def same_project(workspace: Path, project_root: Path) -> bool:
    """True when the shared resolver, run in *workspace*, names *project_root* as its project."""
    found = workspace_root.resolve(str(workspace), None)
    return found.get("status") == "ok" and _norm(Path(found["project_root"])) == _norm(project_root)


def compute_checks(workspace: Path, hub: str, *, branch: str, project_root: Path, base_ref: str | None = None,
                   line_of_work: str = "new") -> dict[str, Any]:
    """Read the ingredient checks off the workspace as it now exists (no writes).

    ``base_is_fresh``: a newly started line's tip is origin/main as read now;
    a resumed line holds every commit of ``origin/<branch>`` (the maker never
    resets or rebases it). *base_ref* overrides what ``origin/main`` resolves to.
    """
    own_git = is_independent(workspace)
    current = _git(workspace, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    head = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    if line_of_work == "resumed":
        target = base_ref or f"origin/{branch}"  # the SHA the line was built from, never a re-read ref
        remote = _git(workspace, "rev-parse", "--verify", "-q", target)
        fresh = remote.returncode != 0 or _git(workspace, "merge-base", "--is-ancestor", target, "HEAD").returncode == 0
    else:
        fresh = bool(head) and head == (base_ref or _git(workspace, "rev-parse", "origin/main").stdout.strip())
    origin = wg.origin_url(workspace)
    hooks = hooks_dir(workspace)
    clean = tree_is_clean(workspace)
    return {
        "is_independent_repo": own_git,
        "not_main_checkout": workspace.resolve() != project_root.resolve(),
        "same_project": same_project(workspace, project_root),
        "install_paths_regular": install_paths_regular(workspace),
        "branch_matches": current == branch,
        "not_protected_branch": current not in PROTECTED_BRANCHES,
        "base_is_fresh": fresh,
        "tree_clean": clean,
        "precommit_config_present": (workspace / ".pre-commit-config.yaml").is_file(),
        "origin_matches_hub": bool(origin) and wg.same_location(origin, hub),
        "gc_auto_disabled": wg.git_config_get(workspace, "gc.auto") == "0",
        "hooks_installed": bool(hooks and (hooks / "pre-commit").is_file()),
        "working_tree_clean": clean,
    }


_SHARED = ("is_independent_repo", "not_main_checkout", "same_project", "origin_matches_hub", "gc_auto_disabled",
           "install_paths_regular", "branch_matches", "not_protected_branch")
_STRUCTURAL = (*_SHARED, "base_is_fresh")
# verify judges the ingredients read-only: it never refuses on base_is_fresh or tree_clean (a moved hub and
# uncommitted work are normal), but does on the recorded build and hook-stage proofs.
VERIFY_REFUSALS = _SHARED


def failed_for_verify(checks: dict[str, Any]) -> list[str]:
    """The ingredients ``verify`` refuses on that are not true: its own set, then every false hook stage."""
    failed = [k for k in VERIFY_REFUSALS if checks.get(k) is not True]
    if checks.get("build_ok") is False:  # absent (a cut-over marker) is not-known, never a refusal
        failed.append("build_ok")
    return failed + [k for k, v in checks.items() if k.startswith("hooks_") and v is False]


def _failed_structural(checks: dict[str, Any]) -> list[str]:
    """The structural ingredients that are false, in declaration order."""
    return [k for k in _STRUCTURAL if checks.get(k) is not True]


def _refuse_structural(failed: list[str], checks: dict[str, Any], boot: dict[str, Any]) -> dict[str, Any]:
    """Refusal for a false structural ingredient (ON_PROTECTED_BRANCH, else VERIFY_FAILED); no location."""
    code = "ON_PROTECTED_BRANCH" if "not_protected_branch" in failed else "VERIFY_FAILED"
    return wa.error_answer(code, "Not ready -- untrue of the workspace: " + ", ".join(failed) + ".",
                           checks=checks, failed_ingredients=failed, bootstrap=boot)


def prove_ready(workspace: Path, hub: str, *, kind: str, branch: str, project_root: Path, config_path: Path,
                line_of_work: str = "new", base_ref: str | None = None) -> dict[str, Any]:
    """Build the install inside *workspace*, then prove every readiness ingredient.

    Returns a refusal answer (status/code/message, ``checks``, no location) when
    any ingredient is false, else ``{"checks", "bootstrap", "hooks_stages_declared"}``.
    """
    before = snapshot_tracked(workspace)
    build = run_install_build(workspace, config_path)
    boot: dict[str, Any] = {"build_ok": build["ok"], "restored_tracked": []}
    if not build["ok"]:
        boot["failure_excerpt"] = build["excerpt"]
        return wa.error_answer(build["code"], "The install build failed inside the new workspace; it is not ready.",
                               bootstrap=boot, checks={"build_ok": False})
    boot["restored_tracked"], leftover = restore_build_changes(workspace, before)
    if leftover:
        return wa.error_answer("BOOTSTRAP_DIRTIED_TRACKED",
                               "The install build changed version-controlled files that could not be restored: "
                               + ", ".join(leftover), bootstrap={**boot, "dirtied_tracked": leftover},
                               checks={"build_ok": True, "tree_clean": False})
    install_shims(workspace)
    stages = declared_stages(workspace)
    checks = {"build_ok": True, **compute_checks(workspace, hub, branch=branch, project_root=project_root,
                                                 line_of_work=line_of_work, base_ref=base_ref)}
    failed = _failed_structural(checks)
    if failed:
        return _refuse_structural(failed, checks, boot)
    if kind != "scratch" and not tree_is_clean(workspace):
        # Canaries reset --hard; never run them over uncommitted work (or a tree we cannot read).
        checks["tree_clean"] = checks["working_tree_clean"] = False
        return _refuse_structural(["tree_clean"], checks, boot)
    fired = {} if kind == "scratch" else run_canaries(workspace, stages, branch)
    checks.update(hook_checks(stages, fired, kind))
    after = compute_checks(workspace, hub, branch=branch, project_root=project_root, line_of_work=line_of_work,
                           base_ref=base_ref)
    checks.update(tree_clean=after["tree_clean"], working_tree_clean=after["tree_clean"])
    inactive = [] if kind == "scratch" else sorted(
        {s for s in stages if fired.get(s) is not True} | ({"pre-commit"} if "pre-commit" not in stages else set()))
    if inactive:
        return wa.error_answer("HOOKS_INACTIVE", "Declared protections did not fire inside the workspace: "
                               + ", ".join(inactive) + ".", checks=checks, inactive_stages=inactive,
                               hooks_stages_declared=stages, bootstrap=boot)
    failed = [k for k in (*_failed_structural(after), "tree_clean") if after.get(k) is not True]
    if failed:
        return _refuse_structural(failed, checks, boot)
    return {"checks": checks, "bootstrap": boot, "hooks_stages_declared": stages}


def with_restored_tree(checks: dict[str, Any], workspace: Path) -> dict[str, Any]:
    """*checks* with ``tree_clean`` re-read after the work's set-aside changes were put back (one definition)."""
    clean = tree_is_clean(workspace)
    return {**checks, "tree_clean": clean, "working_tree_clean": clean}


def stored_checks(computed: dict[str, Any], marker: dict[str, Any]) -> dict[str, Any]:
    """Overlay the proofs only ``ensure`` can make (build, freshness, per-stage hooks) from *marker*.

    Re-reading an existing workspace recomputes what is read-only and reuses
    the stored result of each write-based proof.
    """
    stored = marker.get("checks") or {}
    keep = {k: v for k, v in stored.items() if k.startswith("hooks_") or k in ("build_ok", "base_is_fresh")}
    return {**computed, "build_ok": None, **keep}  # None: no recorded build result (not-known)


# ===========================================================================
# DECISION HISTORY
# - 2026-10-25 [python-coder/EPIC-WorkspaceMakerHardening/11]: (#EPIC-WorkspaceMakerHardening/11)
#   prove_ready takes ``base_ref`` (the SHA the line was built from) so base_is_fresh never reads a moved ref. (ADR-018)
# ===========================================================================
# - 2026-10-01 00:30 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
#   Created: readiness moved out of worktree_git.py (compute_checks, canary,
#   install build, restore) and rebuilt per BO-4300c-1/-i/-ii/-iii and
#   BO-4300b-4. Stage set from the workspace's own hook declaration (stdlib
#   parser, column-0 block lists handled), one real canary per declared stage
#   from the install's own stage_canaries, tracked-file snapshot/restore, the
#   build told to copy its shims (no links). (ADR-018)
# - 2026-10-09 12:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
#   Split for the file-size limit: the canary-proving group moved to
#   worktree_canaries.py and is imported here by name. No behaviour change. (ADR-018)
# - 2026-10-16 20:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/17]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/17) run_install_build passes the project's durable log root via worktree_log_root (INF-500d-4-iii). (ADR-018)
# - 2026-10-23 12:00 [smart-bug-resolver/EPIC-WorkspaceMakerHardening/07]: (#EPIC-WorkspaceMakerHardening/07)
#   tree_is_clean reads `git status --porcelain --untracked-files=no`, not `git diff HEAD`: diff's
#   auto-refresh rewrote .git/index for a stat-dirty file even under GIT_OPTIONAL_LOCKS=0, so
#   verify was not read-only (BO-4300c-1). (ADR-018)
# ===========================================================================
