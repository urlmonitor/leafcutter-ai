"""
MODULE: workspace_core
GOAL: Hold the primitives every part of the workspace maker shares: running
    processes, naming a piece of work, the marker record, and scanning the
    landing place.
BUSINESS CONTEXT: The maker (worktree.py) is split across small modules so no
    file outgrows the size limit. Work identity and naming live in ONE table
    here, so the same identity from any route yields the same landing location
    and the same line of work (BO-4300a-2 will extend the alias table).
ARCHITECTURE: Stdlib-only, imported by name from the maker's own directory.
    Deployed beside worktree.py by its own named deploy-manifest entry (that
    deploy phase is non-recursive). Project resolution is NOT here: it lives in
    ``workspace_root``. Git runs as a subprocess with the working directory
    set; stdin is always closed and nothing prompts.

# DECISION HISTORY
# ================================================================================
# - 2026-10-14 12:00 [python-coder]: Created when worktree.py's counted
#   lines passed the 400-line limit; split by concern into core, checks and
#   create modules, each with a named deploy entry. (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01)
# - 2026-10-14 17:00 [python-coder]: Added discard_tree and run(extra_env).
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-070)
# - 2026-10-14 18:00 [python-coder]: REFUSAL_CODES: a declined request answers
#   status "refused" (TICKET_NOT_ON_BASE, OCCUPIED), not "error".
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04) (BO-4300a-1-ii)
"""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

from workspace.workspace_root import LANDING_NAME, MARKER_NAME, resolve_project_root

MAKER_VERSION = "1.0.0"
SCHEMA_VERSION = 1
PROTECTED = frozenset({"main", "master"})
# Requests the maker declines (answer status "refused", exit 2) rather than fails.
REFUSAL_CODES = frozenset({"TICKET_NOT_ON_BASE", "OCCUPIED"})
KINDS = ("ticket", "feature", "ac", "fastlane", "epic", "scratch")
_PREFIX = {"ticket": "ticket/", "feature": "feature/", "ac": "ac/",
           "fastlane": "fastlane/", "epic": "EPIC-", "scratch": ""}
# Legacy spellings of one work identity, stripped before naming (the one table).
_ALIASES = {"epic": ("EPIC-",)}

log = logging.getLogger("worktree")


class MakerError(Exception):
    """A classified failure, emitted as an error or refused answer."""

    def __init__(self, code: str, message: str, **extra: object) -> None:
        super().__init__(message)
        self.code, self.extra = code, extra

    @property
    def refused(self) -> bool:
        """True when the maker declined the request (as opposed to failing)."""
        return self.code in REFUSAL_CODES

    def payload(self, verb: str) -> dict:
        """Return the error or refused answer for this failure."""
        return {"status": "refused" if self.refused else "error", "code": self.code,
                "verb": verb, "message": str(self), **self.extra}


def run(cmd: list[str], cwd: Path, timeout: int = 900,
        extra_env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a command with stdin closed; failure to start is rc 127, logged."""
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", **(extra_env or {})}
    try:
        return subprocess.run(  # noqa: S603
            cmd, cwd=str(cwd), stdin=subprocess.DEVNULL, capture_output=True,
            text=True, env=env, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("could not run %s in %s: %s", cmd[:2], cwd, exc)
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run git with the working directory set to ``cwd``."""
    return run(["git", *args], cwd)


def out(cwd: Path, *args: str) -> str | None:
    """Return git's stripped stdout, or None when git failed."""
    done = git(cwd, *args)
    return done.stdout.strip() if done.returncode == 0 else None


def must(cwd: Path, code: str, *args: str) -> str:
    """Return git's stdout or raise a classified error."""
    done = git(cwd, *args)
    if done.returncode != 0:
        raise MakerError(code, f"git {args[0]} failed: {done.stderr.strip()[-600:]}")
    return done.stdout.strip()


def _on_rm_error(func: object, path: str, _exc: object) -> None:
    """Clear a read-only bit and retry (git objects are read-only on Windows)."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)  # type: ignore[operator]
    except OSError as exc:
        log.warning("cannot delete %s: %s", path, exc)
        raise


def discard_tree(path: Path) -> None:
    """Delete a workspace folder; a failure is logged and raised."""
    try:
        shutil.rmtree(path, onerror=_on_rm_error)
    except OSError as exc:
        log.warning("cannot delete %s: %s", path, exc)
        raise


def normalize_slug(kind: str, raw: str) -> str:
    """Return the one normalised spelling of a work identity."""
    slug = raw.strip()
    for alias in _ALIASES.get(kind, ()):
        if slug.lower().startswith(alias.lower()):
            slug = slug[len(alias):]
    slug = re.sub(r"\.{2,}", ".", re.sub(r"[^A-Za-z0-9._-]+", "-", slug)).strip("-.")
    slug = re.sub(r"\.lock$", "", slug)
    if not slug:
        raise MakerError("BAD_ARGUMENT", f"slug {raw!r} names no work identity")
    return slug


def branch_for(kind: str, slug: str) -> str | None:
    """Return the line of work for an identity (None for a detached scratch)."""
    return None if kind == "scratch" else _PREFIX[kind] + slug


def dirname_for(kind: str, slug: str) -> str:
    """Return the landing-place folder name for an identity."""
    return (branch_for(kind, slug) or f"scratch/{slug}").replace("/", "-")


def resolve_project(repo_root: str | None) -> Path:
    """Resolve the main checkout through the shared resolver or raise."""
    found = resolve_project_root(os.getcwd(), repo_root)
    if found["status"] == "ok":
        return Path(found["project_root"])
    code = found["status"]
    raise MakerError(code, f"cannot resolve the project: {code}",
                     **{k: v for k, v in found.items() if k != "status"})


def hub_of(project: Path) -> str:
    """Return the hub URL from the main checkout's origin or raise NO_HUB."""
    url = out(project, "remote", "get-url", "origin")
    if not url:
        raise MakerError("NO_HUB", f"{project} has no origin to use as the hub")
    return url


def make_plan(kind: str, raw_slug: str, repo_root: str | None) -> dict:
    """Build the identity plan (names and places) for an ensure request."""
    project = resolve_project(repo_root)
    slug = normalize_slug(kind, raw_slug)
    return {"kind": kind, "slug": slug, "branch": branch_for(kind, slug),
            "project": project, "hub": hub_of(project),
            "ws": project.parent / LANDING_NAME / dirname_for(kind, slug)}


def read_marker(ws: Path) -> dict | None:
    """Return the workspace's marker record, or None when absent or unreadable."""
    try:
        data = json.loads((ws / MARKER_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def write_marker(plan: dict, state: str, base: str, created_at: str) -> None:
    """Write the marker atomically (temp file plus replace)."""
    ws = plan["ws"]
    record = {"schema_version": SCHEMA_VERSION, "kind": plan["kind"],
              "slug": plan["slug"], "branch": plan["branch"], "hub": plan["hub"],
              "project_root": str(plan["project"]), "base_commit": base,
              "maker_version": MAKER_VERSION, "state": state, "created_at": created_at}
    tmp = ws / (MARKER_NAME + ".tmp")
    try:
        tmp.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, ws / MARKER_NAME)
    except OSError as exc:
        log.warning("cannot write marker in %s: %s", ws, exc)
        raise MakerError("INTERNAL_ERROR", f"cannot write the marker: {exc}") from exc


def plan_from_marker(ws: Path, marker: dict) -> dict:
    """Rebuild an identity plan from a workspace's marker."""
    return {"kind": marker.get("kind"), "slug": marker.get("slug"),
            "branch": marker.get("branch"), "hub": marker.get("hub"),
            "project": Path(marker.get("project_root") or ""), "ws": ws}


def scan(project: Path) -> list[tuple[Path, dict]]:
    """List the landing place's workspaces that belong to ``project``."""
    landing = project.parent / LANDING_NAME
    try:
        children = sorted(c for c in landing.iterdir() if c.is_dir())
    except OSError:
        return []
    mine = os.path.realpath(project)
    found = [(c, read_marker(c)) for c in children]
    return [(c, m) for c, m in found
            if m and os.path.realpath(m.get("project_root") or "") == mine]
