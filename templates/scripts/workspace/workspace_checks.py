"""
MODULE: workspace_checks
GOAL: Prove a workspace is ready by recomputing every readiness check from the
    workspace on disk, including a canary commit that a real hook must reject.
BUSINESS CONTEXT: A workspace whose protections were never shown to fire is the
    failure this family exists to prevent, so readiness is measured, never
    assumed, and the same checks answer ensure, verify and re-ensure.
ARCHITECTURE: Stdlib-only helper of worktree.py, deployed beside it by its own
    named deploy-manifest entry. ``checks_for`` returns one dict whose key set
    is identical for every route given the same hook declaration;
    ``require_ready`` raises NOT_READY when any check other than a tolerated
    staleness is not true. The canary is a ``git commit`` run with the working
    directory set, never as ``git -C <path> commit``.

# DECISION HISTORY
# ================================================================================
# - 2026-10-14 12:00 [python-coder]: Split out of worktree.py. The canary
#   exercises the pre-commit stage; other declared stages are checked for an
#   installed hook file. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
# - 2026-10-14 17:00 [python-coder]: Canary no longer resets --hard or runs on a
#   dirty tree, stages with -f (the canary is excluded), and needs a passing
#   --no-verify control commit before a rejection counts as proof.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-070)
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from workspace.workspace_core import PROTECTED, MakerError, git, log, out, run
from workspace.workspace_root import resolve_project_root

CANARY_FILE = ".leafcutter-canary-known-bad.py"
# Identity for the canary's own commits, so a missing git identity can never
# be mistaken for a hook rejection.
_IDENTITY = {"GIT_AUTHOR_NAME": "leafcutter-canary", "GIT_AUTHOR_EMAIL": "canary@invalid",
             "GIT_COMMITTER_NAME": "leafcutter-canary",
             "GIT_COMMITTER_EMAIL": "canary@invalid"}


def hook_stages(ws: Path) -> list[str]:
    """Return the hook stages the workspace's own hook declaration names."""
    try:
        text = (ws / ".pre-commit-config.yaml").read_text(encoding="utf-8")
    except OSError:
        return ["pre-commit"]
    inline = re.search(r"^default_install_hook_types:\s*\[([^\]]*)\]", text, re.M)
    block = re.search(r"^default_install_hook_types:\s*\n((?:[ \t]*-[ \t]*\S+\n?)+)",
                      text, re.M)
    if inline:
        names = [s.strip().strip("'\"") for s in inline.group(1).split(",")]
    elif block:
        names = [ln.strip().lstrip("-").strip().strip("'\"")
                 for ln in block.group(1).splitlines()]
    else:
        names = []
    return list(dict.fromkeys(["pre-commit", *[n for n in names if n]]))


def _unlink(path: Path) -> None:
    """Remove a file if present; a failure is logged, not raised."""
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        log.warning("cannot remove %s: %s", path, exc)


def _commit(ws: Path, *flags: str) -> bool:
    """Commit what is staged (working directory set); True when HEAD moved."""
    before = out(ws, "rev-parse", "HEAD")
    run(["git", "commit", *flags, "-m", "leafcutter workspace canary (must be rejected)"],
        ws, extra_env=_IDENTITY)
    return out(ws, "rev-parse", "HEAD") != before


def canary(ws: Path, tree_clean: bool = True) -> bool:
    """Commit a known-bad file; True only when a hook, not anything else, rejects it.

    Not proven (False) when the tree holds work, so no user change is ever
    committed or reset. A control commit with ``--no-verify`` must succeed, so a
    rejection caused by anything other than a hook never reads as proof. Only
    the canary's own commits are undone, with a soft reset.
    """
    head = out(ws, "rev-parse", "HEAD")
    if not tree_clean or not head:
        log.warning("canary not run in %s: tree is not clean or has no commit", ws)
        return False
    try:
        (ws / CANARY_FILE).write_text("def broken(:\n", encoding="utf-8")
    except OSError as exc:
        log.warning("cannot write the canary in %s: %s", ws, exc)
        return False
    # The canary is in .git/info/exclude, so adding it needs -f; without it
    # the commit would fail for want of content and read as a hook rejection.
    if git(ws, "add", "-f", "--", CANARY_FILE).returncode != 0:
        log.warning("cannot stage the canary in %s", ws)
        _unlink(ws / CANARY_FILE)
        return False
    proven = False
    if _commit(ws):
        git(ws, "reset", "--soft", head)
    elif _commit(ws, "--no-verify"):
        proven = True
        git(ws, "reset", "--soft", head)
    git(ws, "reset", "-q", "--", CANARY_FILE)
    _unlink(ws / CANARY_FILE)
    return proven and out(ws, "rev-parse", "HEAD") == head


def _is_independent(ws: Path, hub: str) -> bool:
    """True when the workspace has its own git directory, origin at the hub."""
    git_dir = ws / ".git"
    common = out(ws, "rev-parse", "--git-common-dir") or ""
    common_abs = Path(common) if os.path.isabs(common) else ws / common
    return (git_dir.is_dir() and not git_dir.is_symlink()
            and os.path.realpath(common_abs) == os.path.realpath(git_dir)
            and not (git_dir / "objects" / "info" / "alternates").exists()
            and out(ws, "remote", "get-url", "origin") == hub)


def hub_tip(ws: Path) -> str | None:
    """Return the hub's main tip as read right now."""
    line = out(ws, "ls-remote", "origin", "refs/heads/main") or ""
    return line.split()[0] if line else None


def checks_for(plan: dict, base: str) -> dict:
    """Recompute every readiness check from the workspace on disk."""
    ws, branch = plan["ws"], plan["branch"]
    config = ws / ".pre-commit-config.yaml"
    again = resolve_project_root(ws, None).get("project_root")
    checks = {
        "is_independent_repo": _is_independent(ws, plan["hub"]),
        "not_main_checkout": os.path.realpath(ws) != os.path.realpath(plan["project"]),
        "same_project": again is not None
        and os.path.realpath(again) == os.path.realpath(plan["project"]),
        "branch_matches": out(ws, "symbolic-ref", "--short", "-q", "HEAD") == branch,
        "not_protected_branch": branch not in PROTECTED,
        "base_is_fresh": hub_tip(ws) == base,
        "build_ok": (ws / ".leafcutter").is_dir(),
        "tree_clean": out(ws, "status", "--porcelain") == "",
        "precommit_config_present": config.is_file() and not config.is_symlink(),
    }
    for stage in hook_stages(ws):
        checks[f"hooks_{stage.replace('-', '_')}_fired"] = (
            ws / ".git" / "hooks" / stage).is_file()
    checks["hooks_canary_rejected"] = canary(ws, checks["tree_clean"])
    return checks


def require_ready(plan: dict, base: str, tolerate_stale: bool = False) -> dict:
    """Compute checks and raise NOT_READY when any ingredient is missing."""
    checks = checks_for(plan, base)
    skip = {"base_is_fresh"} if tolerate_stale else set()
    failing = [k for k, v in checks.items() if v is not True and k not in skip]
    if failing:
        raise MakerError("NOT_READY", f"workspace is not ready: {failing}",
                         workspace_path=str(plan["ws"]), checks=checks)
    return checks
