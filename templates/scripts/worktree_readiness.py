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
import subprocess
import sys
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg
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
    env = {**os.environ, "LEAFCUTTER_SHIM_STRATEGY": "copy"}
    try:
        proc = subprocess.run(
            [sys.executable, str(build_script), "--target-dir", str(workspace), "--config-path", str(config_path)],
            cwd=str(workspace), capture_output=True, text=True, timeout=300, check=False, env=env,
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
    """True only when ``git diff HEAD`` ran and named no tracked change (fails closed on a git error)."""
    proc = wg.run_git(["diff", "--name-only", "-z", "HEAD"], workspace)
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
    leftover = [p for p in build_made if p in still]
    return [p for p in build_made if p not in still], sorted(set(unrestorable + leftover))


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


def compute_checks(workspace: Path, hub: str, *, branch: str, project_root: Path, base_ref: str | None = None,
                   line_of_work: str = "new") -> dict[str, Any]:
    """Read the ingredient checks off the workspace as it now exists (no writes).

    ``base_is_fresh``: a newly started line's tip is origin/main as read now;
    a resumed line holds every commit of ``origin/<branch>`` (the maker never
    resets or rebases it). *base_ref* overrides what ``origin/main`` resolves to.
    """
    own_git = (workspace / ".git").is_dir()
    current = _git(workspace, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    head = _git(workspace, "rev-parse", "HEAD").stdout.strip()
    if line_of_work == "resumed":
        remote = _git(workspace, "rev-parse", "--verify", "-q", f"origin/{branch}")
        fresh = remote.returncode != 0 or _git(
            workspace, "merge-base", "--is-ancestor", f"origin/{branch}", "HEAD").returncode == 0
    else:
        fresh = bool(head) and head == (base_ref or _git(workspace, "rev-parse", "origin/main").stdout.strip())
    origin = wg.origin_url(workspace)
    hooks = hooks_dir(workspace)
    clean = tree_is_clean(workspace)
    return {
        "is_independent_repo": own_git,
        "not_main_checkout": own_git and workspace.resolve() != project_root.resolve(),
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


_STRUCTURAL = ("is_independent_repo", "not_main_checkout", "branch_matches", "not_protected_branch", "base_is_fresh")


def _failed_structural(checks: dict[str, Any]) -> list[str]:
    """The structural ingredients that are false, in declaration order."""
    return [k for k in _STRUCTURAL if checks.get(k) is not True]


def _refuse_structural(failed: list[str], checks: dict[str, Any], boot: dict[str, Any]) -> dict[str, Any]:
    """Refusal for a false structural ingredient (ON_PROTECTED_BRANCH, else VERIFY_FAILED); no location."""
    code = "ON_PROTECTED_BRANCH" if "not_protected_branch" in failed else "VERIFY_FAILED"
    return wa.error_answer(code, "Not ready -- untrue of the workspace: " + ", ".join(failed) + ".",
                           checks=checks, failed_ingredients=failed, bootstrap=boot)


def prove_ready(workspace: Path, hub: str, *, kind: str, branch: str, project_root: Path, config_path: Path,
                line_of_work: str = "new") -> dict[str, Any]:
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
    restored, leftover = restore_build_changes(workspace, before)
    boot["restored_tracked"] = restored
    if leftover:
        return wa.error_answer("BOOTSTRAP_DIRTIED_TRACKED",
                               "The install build changed version-controlled files that could not be restored: "
                               + ", ".join(leftover), bootstrap={**boot, "dirtied_tracked": leftover},
                               checks={"build_ok": True, "tree_clean": False})
    install_shims(workspace)
    stages = declared_stages(workspace)
    checks = {"build_ok": True, **compute_checks(workspace, hub, branch=branch, project_root=project_root,
                                                 line_of_work=line_of_work)}
    failed = _failed_structural(checks)
    if failed:
        return _refuse_structural(failed, checks, boot)
    if kind != "scratch" and not tree_is_clean(workspace):
        # Canaries reset --hard; never run them over uncommitted work (or a tree we cannot read).
        checks["tree_clean"] = checks["working_tree_clean"] = False
        return _refuse_structural(["tree_clean"], checks, boot)
    fired = {} if kind == "scratch" else run_canaries(workspace, stages, branch)
    checks.update(hook_checks(stages, fired, kind))
    after = compute_checks(workspace, hub, branch=branch, project_root=project_root, line_of_work=line_of_work)
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


def stored_checks(computed: dict[str, Any], marker: dict[str, Any]) -> dict[str, Any]:
    """Overlay the proofs only ``ensure`` can make (build, freshness, per-stage hooks) from *marker*.

    Re-reading an existing workspace recomputes what is read-only and reuses
    the stored result of each write-based proof.
    """
    stored = marker.get("checks") or {}
    keep = {k: v for k, v in stored.items() if k.startswith("hooks_") or k in ("build_ok", "base_is_fresh")}
    return {**computed, **keep}


# ===========================================================================
# DECISION HISTORY
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
# ===========================================================================
