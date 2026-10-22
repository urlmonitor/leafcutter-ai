"""
MODULE: worktree_layout
GOAL: Own where a workspace lives and how it is configured: project
    resolution as the maker's answer (refusals included), the one landing
    rule, the validated ``--landing-root`` override, the dev/consumer
    classification and the install-config derivation (ADR-018 Amendment 1
    A1.8-A1.12, BO-4300b-1/2/3).
BUSINESS CONTEXT: The same request must give the same workspace wherever it
    starts, two projects' ``alpha`` must never collide, and nothing may be
    written inside the project. One module computing the location for
    ``ensure``, ``locate``, ``list``, ``verify`` and ``remove`` is what keeps
    those five verbs agreeing. It also carries the file-size ratchet's
    overflow from ``worktree.py`` and ``worktree_git.py``.
ARCHITECTURE: Stdlib-only. Depends on ``workspace_root`` (A1.8 resolution),
    ``worktree_answer`` (refusal shapes), ``worktree_paths`` (path spelling)
    and ``worktree_git`` (git runner, marker files); none of them imports this
    module. The landing root is ``<parent-of-project>/<project-dir-name>-
    worktrees`` and a workspace lands at ``<landing-root>/<kind>/<slug>``; it
    is derived only from the resolved project, never from cwd, the maker's
    location, an environment variable or a config key. Only an explicit,
    validated ``--landing-root`` overrides it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any

import workspace_root
import worktree_answer as wa
import worktree_git as wg
import worktree_paths as wp

_log = logging.getLogger(__name__)

# build.py's own skills_config.json auto-detection order (see worktree_git
# history): derive_config_path finds the file build.py itself would find.
_CONFIG_PLATFORM_DIRS: tuple[str, ...] = (".claude", ".gemini", ".cursor", ".github", ".cline")
_DERIVED_CONFIG = ("derived_skills_config.json",)


def _norm(path: Path) -> str:
    """Return a comparable spelling of *path* (resolved, case-folded on Windows)."""
    return os.path.normcase(str(path.resolve()))


def _inside(child: Path, parent: Path) -> bool:
    """Return True when *child* is *parent* or lies beneath it."""
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def resolve_repo_root(repo_root_arg: str | None) -> tuple[Path | None, dict[str, Any] | None]:
    """Resolve the project for this request, or build the refusal that says why not.

    Args:
        repo_root_arg: The caller's ``--repo-root`` value, or ``None``.

    Returns:
        ``(project, None)`` on success, else ``(None, answer)`` where *answer*
        is the ready-to-print ``NO_REPO`` (naming ``searched_from``, and the
        marker when a workspace's recorded project is gone) or
        ``AMBIGUOUS_REPO`` (listing every candidate) refusal. Nothing is
        written in either case.
    """
    arg = str(wp.resolve_arg(repo_root_arg)) if repo_root_arg else None
    result = workspace_root.resolve(str(Path.cwd()), arg)
    if result["status"] == "ok":
        return Path(result["project_root"]), None
    if result["status"] == "AMBIGUOUS_REPO":
        names = ", ".join(result["candidates"])
        return None, wa.error_answer(
            "AMBIGUOUS_REPO", f"More than one project could be meant ({names}); name one with --repo-root.",
            candidates=result["candidates"], searched_from=result["searched_from"])
    extra = {"marker": result["marker"]} if "marker" in result else {}
    message = f"No project found ({result['reason']}); searched from {result['searched_from']}."
    answer = wa.error_answer("NO_REPO", message, searched_from=result["searched_from"], **extra)
    answer["status"] = "refused"  # BO-4300b-3-i: a missing project is a refusal (exit 2), not a crash
    return None, answer


def landing_place(repo_root: Path) -> Path:
    """Return the project's one landing root: ``<parent>/<project-dir-name>-worktrees``.

    Derived only from the resolved main checkout; identical in the dev and
    consumer layouts. Nothing is ever created inside the project's tree.
    """
    return repo_root.parent / f"{repo_root.name}-worktrees"


def workspace_path_for(place: Path, kind: str, slug: str) -> Path:
    """Return where the workspace for *kind*/*slug* lives under landing root *place*."""
    return place / kind / slug


def _override_rule_broken(raw: str, project: Path) -> str | None:
    """Return the A1.10 rule the override *raw* breaks, or ``None`` when it is acceptable."""
    path = wp.to_native(raw)
    if not path.is_absolute():
        return "it must be an absolute folder"
    if _inside(path, project):
        return f"it must lie outside the project's working tree ({project})"
    existing = path
    while not existing.exists() and existing.parent != existing:
        existing = existing.parent
    for folder in (path, *path.resolve().parents):
        if wg.marker_path(folder).is_file():
            return f"it must not lie inside an existing workspace ({folder})"
    if wg.run_git(["rev-parse", "--show-toplevel"], existing).returncode == 0:
        return "it must not lie inside another git repository"
    if not existing.is_dir() or not os.access(existing, os.W_OK):
        return f"it must be creatable and writable (nearest existing folder: {existing})"
    return None


def landing_for(landing_root_arg: str | None, project: Path) -> tuple[Path | None, dict[str, Any] | None]:
    """Return ``(landing root, None)`` for the request, or ``(None, USAGE answer)``.

    An explicit *landing_root_arg* is validated BEFORE anything is written
    (A1.10: absolute, outside the project, inside no workspace and no other
    repository, creatable and writable). It is never read from an
    environment variable or config and never remembered.
    """
    if landing_root_arg is None:
        return landing_place(project), None
    broken = _override_rule_broken(landing_root_arg, project)
    if broken is not None:
        return None, wa.error_answer("USAGE", f"Invalid --landing-root {landing_root_arg!r}: {broken}.")
    return wp.to_native(landing_root_arg).resolve(), None


def override_refusal(args: Any) -> dict[str, Any] | None:
    """For verbs that take ``--path``: the refusal for a bad ``--landing-root``, else ``None``."""
    if getattr(args, "landing_root", None) is None:
        return None
    project, refusal = resolve_repo_root(args.repo_root)
    return refusal if project is None else landing_for(args.landing_root, project)[1]


def project_of(workspace: Path, marker: dict[str, Any]) -> Path | None:
    """Return the project recorded in *marker* (spelled relative to *workspace*), or ``None``."""
    stored = marker.get("project_root")
    return Path(wp.from_portable(stored, workspace)) if isinstance(stored, str) and stored else None


def other_project_occupant(workspace: Path, marker: dict[str, Any], project: Path) -> dict[str, Any] | None:
    """Return the ``occupant`` answer field when *workspace* holds another project's workspace."""
    recorded = project_of(workspace, marker)
    if recorded is not None and _norm(recorded) == _norm(project):
        return None
    return {"path": str(workspace), "kind": "other-project", "branch": marker.get("branch")}


def iter_markers(place: Path, project: Path | None = None):
    """Yield ``(workspace_path, marker)`` for each workspace under *place*/``<kind>``/``<slug>``.

    When *project* is given, only workspaces whose marker records that
    project are yielded (locate and list filter by ``project_root``).
    """
    if not place.is_dir():
        return
    for kind_dir in sorted(place.iterdir()):
        if not kind_dir.is_dir():
            continue
        for child in sorted(kind_dir.iterdir()):
            marker = wg.read_marker(child) if child.is_dir() else None
            if marker is None:
                continue
            recorded = project_of(child, marker)
            if project is None or (recorded is not None and _norm(recorded) == _norm(project)):
                yield child, marker


def _git_toplevel_of(path: Path) -> Path | None:
    """Return the git toplevel enclosing *path*, or ``None`` when it is not one."""
    proc = wg.run_git(["rev-parse", "--show-toplevel"], path)
    text = proc.stdout.strip() if proc.returncode == 0 else ""
    return Path(text).resolve() if text else None


def layout_for(repo_root: Path) -> str:
    """Return ``'consumer'`` when *repo_root*'s parent is a different git repo, else ``'dev'``.

    Reported as the BO-4300c-2 ``layout`` field; it does not change where
    workspaces land.
    """
    parent_toplevel = _git_toplevel_of(repo_root.parent)
    return "consumer" if parent_toplevel is not None and parent_toplevel != repo_root else "dev"


def _read_json(path: Path) -> dict[str, Any] | None:
    """Best-effort read of a JSON object from *path*; ``None`` when unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.warning("worktree_layout: cannot read %s: %s", path, exc)
        return None
    return data if isinstance(data, dict) else None


def _strip_prefix(value: Any, name: str) -> Any:
    """Remove ``<name>/`` where it starts a string or a whitespace-separated token, at every depth."""
    if isinstance(value, str):
        return re.sub(rf"(?<!\S){re.escape(name)}/", "", value)
    if isinstance(value, list):
        return [_strip_prefix(item, name) for item in value]
    if isinstance(value, dict):
        return {key: _strip_prefix(item, name) for key, item in value.items()}
    return value


def _first_config(folder: Path) -> Path | None:
    """Return the first ``<folder>/<d>/skills_config.json`` in build.py's auto-detect order."""
    for platform_dir in _CONFIG_PLATFORM_DIRS:
        candidate = folder / platform_dir / "skills_config.json"
        if candidate.is_file():
            return candidate
    return None


def _write_derived(workspace: Path, text: str) -> Path | None:
    """Write *text* as the workspace's derived config file; ``None`` when the write fails."""
    target = workspace.joinpath(".leafcutter", *_DERIVED_CONFIG)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
    except OSError as exc:
        _log.warning("worktree_layout: cannot write %s: %s", target, exc)
        return None
    return target


def _own_config(project: Path, workspace: Path) -> Path | None:
    """A1.11 step 1: the project's own config, passed unchanged or copied byte for byte."""
    found = _first_config(project)
    if found is None:
        return None
    in_workspace = workspace / found.relative_to(project)
    if in_workspace.is_file():
        return in_workspace
    target = workspace.joinpath(".leafcutter", *_DERIVED_CONFIG)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(found, target)
    except OSError as exc:
        _log.warning("worktree_layout: cannot copy %s to %s: %s", found, target, exc)
        return None
    return target


def _enclosing_config(project: Path, workspace: Path) -> Path | None:
    """A1.11 step 2: the enclosing install's config, rewritten for a package that IS the project."""
    found = _first_config(project.parent)
    data = _read_json(found) if found is not None else None
    packages = data.get("top_level_packages") if data else None
    if not isinstance(packages, list):
        return None
    if project.name not in [str(p).rstrip("/") for p in packages]:
        return None
    data["top_level_packages"] = [p for p in packages if str(p).rstrip("/") != project.name]
    return _write_derived(workspace, json.dumps(_strip_prefix(data, project.name), indent=2) + "\n")


def derive_config_path(repo_root: Path, workspace_path: Path) -> tuple[Path | None, str | None]:
    """Derive the install config for *workspace_path* from its project (ADR-018 A1.11).

    1. The project's own ``<d>/skills_config.json`` (``d`` in build.py's
       auto-detect order): the workspace's own file at the same relative path
       when it has one, otherwise a byte-identical copy written to
       ``<workspace>/.leafcutter/derived_skills_config.json``.
    2. Otherwise the first ``<parent-of-project>/<d>/skills_config.json``, but
       only when its ``top_level_packages`` names the project's folder: the
       ``<project>/`` prefix is stripped at every depth, the project's own
       entry is dropped, and the result is written to the derived-config file.
    Never reads above the project's parent, nor any install output root.

    Returns:
        ``(config path inside workspace_path, None)`` or ``(None, "NO_CONFIG")``.
    """
    derived = _own_config(repo_root, workspace_path) or _enclosing_config(repo_root, workspace_path)
    return (derived, None) if derived is not None else (None, "NO_CONFIG")


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-30 23:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
#   Created: resolve_repo_root, landing_place, layout_for, derive_config_path
#   moved out of worktree_git.py (ADR-018 A1.12) and extended. resolve_repo_root
#   now returns (project, refusal): NO_REPO names searched_from (answered
#   "refused" per BO-4300b-3-i, exit 2) and AMBIGUOUS_REPO lists every
#   candidate. Workspaces land at <landing-root>/<kind>/<slug>; --landing-root
#   is validated (A1.10) before anything is written. derive_config_path now
#   follows A1.11: it fixes the carried H-2 finding (enclosing install's
#   config with the package prefix stripped) and the KNOWN LIMITATION note is
#   gone. (ADR-018)
# ===========================================================================
