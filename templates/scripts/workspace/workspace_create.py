"""
MODULE: workspace_create
GOAL: Make a new workspace end to end: clone, re-point origin at the hub, start
    from the hub's main as fetched now, copy local files, run the workspace's
    own install build, prove readiness, and mark it ready.
BUSINESS CONTEXT: Every route gets its workspace through this one sequence, so
    no route can skip a readiness ingredient (decision memo 2026-09-25,
    "Consequences for the standalone script's contract", step 1).
ARCHITECTURE: Stdlib-only helper of worktree.py, deployed beside it by its own
    named deploy-manifest entry. The clone is a hardlinked local-path
    ``--no-checkout`` clone (no --shared, no --reference). The build entry point
    and config come from the main checkout's own install config with the
    top_level_packages prefix stripped; NO_CONFIG when that is impossible.
    The derived config is written inside the workspace's .git so no build can
    rewrite it. No symlink is ever made.

# DECISION HISTORY
# ================================================================================
# - 2026-10-14 12:00 [python-coder]: Split out of worktree.py. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
# - 2026-10-14 17:00 [python-coder]: A failed ensure deletes its half-made
#   workspace so a retry is not blocked; an unreachable hub is FETCH_FAILED
#   unless --allow-stale-base. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-070)
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from workspace.workspace_checks import CANARY_FILE, require_ready
from workspace.workspace_core import MakerError, discard_tree, git, log, must, out, run, write_marker
from workspace.workspace_root import MARKER_NAME

CONFIG_COPY = "workspace_build_config.json"
_CONFIG_NAMES = (".claude/skills_config.json", ".leafcutter/config/skills_config.json")


def _strip_prefixes(value: object, pkgs: list[str]) -> object:
    """Return ``value`` with every top-level-package path prefix removed."""
    if isinstance(value, dict):
        stripped = {k: _strip_prefixes(v, pkgs) for k, v in value.items()}
        if "top_level_packages" in stripped:
            stripped["top_level_packages"] = []
        return stripped
    if isinstance(value, list):
        return [_strip_prefixes(v, pkgs) for v in value]
    for pkg in pkgs if isinstance(value, str) else ():
        if value.startswith(pkg + "/"):
            return value[len(pkg) + 1:]
    return value


def _main_config(project: Path) -> tuple[dict, list[str]]:
    """Read the main install's config and strip the top_level_packages prefix."""
    for rel in _CONFIG_NAMES:
        path = project / rel
        if not path.is_file():
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise MakerError("NO_CONFIG", f"cannot read {path}: {exc}") from exc
        if isinstance(data, dict):
            pkgs = [p.strip("/") for p in data.get("top_level_packages") or []
                    if isinstance(p, str) and p.strip("/")]
            return _strip_prefixes(data, pkgs), pkgs
    raise MakerError("NO_CONFIG", f"the main checkout {project} has no install config")


def derive_build(project: Path, config_path: str | None) -> tuple:
    """Return (build entry relative to the root, derived config or None, explicit config)."""
    if config_path:
        given = Path(os.path.abspath(config_path))
        if not given.is_file():
            raise MakerError("NO_CONFIG", f"--config-path {given} is not a file")
        data, prefixes, explicit = None, [], given
    else:
        data, prefixes = _main_config(project)
        explicit = None
    for prefix in ("", *prefixes):
        entry = Path(prefix) / "scripts" / "build.py"
        if (project / entry).is_file():
            return entry, data, explicit
    raise MakerError("NO_BUILD_ENTRY", f"no scripts/build.py found in {project}")


def _clone(plan: dict, created_at: str) -> None:
    """Clone the main checkout, re-point origin at the hub, write the marker."""
    ws = plan["ws"]
    try:
        ws.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise MakerError("CLONE_FAILED", f"cannot create {ws.parent}: {exc}") from exc
    must(ws.parent, "CLONE_FAILED", "clone", "--local", "--no-checkout",
         str(plan["project"]), str(ws))
    must(ws, "CLONE_FAILED", "remote", "set-url", "origin", plan["hub"])
    exclude = ws / ".git" / "info" / "exclude"
    try:
        exclude.parent.mkdir(parents=True, exist_ok=True)
        with exclude.open("a", encoding="utf-8") as handle:
            handle.write(f"/{MARKER_NAME}\n/{CANARY_FILE}\n")
    except OSError as exc:
        raise MakerError("INTERNAL_ERROR", f"cannot exclude the marker: {exc}") from exc
    write_marker(plan, "creating", "", created_at)


def _branch_on_hub(ws: Path, branch: str, allow_stale: bool) -> bool:
    """True when the hub already holds ``branch``; an unreachable hub is an error.

    Under --allow-stale-base an unreachable hub is logged and the line of work
    starts fresh from the existing origin/main.
    """
    done = git(ws, "ls-remote", "--heads", "origin", branch)
    if done.returncode != 0:
        if not allow_stale:
            raise MakerError("FETCH_FAILED", f"could not ask the hub about {branch}")
        log.warning("hub unreachable; starting %s fresh from origin/main", branch)
        return False
    return bool(done.stdout.strip())


def _checkout(plan: dict, allow_stale: bool) -> str:
    """Fetch the hub's main, check out the line of work; return the base commit."""
    ws, branch = plan["ws"], plan["branch"]
    if git(ws, "fetch", "origin", "main").returncode != 0 and not allow_stale:
        raise MakerError("FETCH_FAILED", "could not fetch origin main from the hub "
                         "(--allow-stale-base accepts the existing origin/main)")
    base = out(ws, "rev-parse", "refs/remotes/origin/main")
    if not base:
        raise MakerError("FETCH_FAILED", "the workspace has no origin/main to start from")
    remote_ref = f"refs/remotes/origin/{branch}"
    if branch is None:
        must(ws, "CHECKOUT_FAILED", "checkout", "--detach", base)
    elif _branch_on_hub(ws, branch, allow_stale) and git(
            ws, "fetch", "origin", f"{branch}:{remote_ref}").returncode == 0:
        must(ws, "CHECKOUT_FAILED", "checkout", "-B", branch, remote_ref)
    else:
        must(ws, "CHECKOUT_FAILED", "checkout", "-B", branch, "--no-track", base)
    must(ws, "CHECKOUT_FAILED", "config", "gc.auto", "0")
    must(ws, "CHECKOUT_FAILED", "config", "maintenance.auto", "false")
    return base


def _copy_env_files(plan: dict) -> None:
    """Copy .env and .mcp.json from the main checkout when they exist."""
    for name in (".env", ".mcp.json"):
        src = plan["project"] / name
        if not src.is_file():
            continue
        try:
            shutil.copy2(src, plan["ws"] / name)
        except OSError as exc:
            raise MakerError("COPY_FAILED", f"cannot copy {name}: {exc}") from exc


def _build(plan: dict, build: tuple) -> None:
    """Run the workspace's own install build with an explicit config path."""
    entry, data, explicit = build
    ws = plan["ws"]
    config = explicit
    if config is None:
        config = ws / ".git" / CONFIG_COPY
        try:
            config.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except OSError as exc:
            raise MakerError("NO_CONFIG", f"cannot write the build config: {exc}") from exc
    done = run([sys.executable, str(ws / entry), "--target-dir", str(ws),
                "--config-path", str(config)], ws, timeout=1800)
    if done.returncode != 0:
        raise MakerError("BUILD_FAILED", f"the install build exited {done.returncode}: "
                         f"{(done.stderr or done.stdout).strip()[-800:]}")


def create_workspace(plan: dict, allow_stale: bool, build: tuple) -> tuple[str, dict]:
    """Make a new workspace end to end; return (base commit, ready checks)."""
    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        _clone(plan, created_at)
        base = _checkout(plan, allow_stale)
        _copy_env_files(plan)
        _build(plan, build)
        checks = require_ready(plan, base, tolerate_stale=allow_stale)
        write_marker(plan, "ready", base, created_at)
    except Exception as exc:  # noqa: BLE001 - boundary: clean up, then re-raise
        _abandon(plan["ws"], exc)
        raise
    return base, checks


def _abandon(ws: Path, exc: Exception) -> None:
    """Delete the half-made workspace so the next ensure can start clean."""
    log.warning("ensure failed (%s); removing the half-made workspace %s", exc, ws)
    try:
        discard_tree(ws)
    except OSError:
        return
    if isinstance(exc, MakerError):
        exc.extra.pop("workspace_path", None)


def ticket_fields(plan: dict, ticket: str) -> dict:
    """Return the ticket's working location inside the workspace."""
    raw = Path(ticket)
    try:
        rel = raw.relative_to(plan["project"]) if raw.is_absolute() else raw
    except ValueError as exc:
        raise MakerError("TICKET_NOT_FOUND", f"{ticket} is not inside the project") from exc
    inside = plan["ws"] / rel
    if not inside.is_file():
        raise MakerError("TICKET_NOT_FOUND", f"{rel} does not exist in the workspace",
                         workspace_path=str(plan["ws"]))
    return {"ticket_path_in_worktree": str(inside),
            "ticket_path_in_worktree_posix": inside.as_posix()}
