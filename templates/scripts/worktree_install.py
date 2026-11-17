"""
MODULE: worktree_install
GOAL: Decide what the workspace maker runs to build the install inside a new
    workspace, in every layout the package is installed in: the package's own
    (self-host) layout, an adopter that keeps the package in a submodule or
    sub-folder, and an adopter that declares an install command of its own
    (BO-4300b-2-iii, BO-4300b-2-iv).
BUSINESS CONTEXT: The maker used to run ``<workspace>/scripts/build.py`` only,
    which is the package's own layout. In an adopter that folder is the
    adopter's own (DIAGraph keeps the package at ``<repo>/leafcutter/``), so
    every workspace was cloned and then refused BOOTSTRAP_FAILED
    "scripts/build.py is absent", and the package submodule was never fetched
    into the fresh clone. Some adopters must also install through a wrapper
    that re-applies settings a bare build drops (DIAGraph's
    ``scripts/rebuild_leafcutter.py``).
ARCHITECTURE: Stdlib-only, deployed beside ``worktree_readiness.py``, whose
    ``run_install_build`` calls :func:`install_command`. Every git call goes
    through ``worktree_git.run_git`` (working directory = the workspace). The
    package folder is recognised by its signature -- ``scripts/build.py`` AND
    ``templates/scripts/worktree.py`` -- so an adopter's own
    ``scripts/build.py`` is never taken for the package's. The declaration is
    the install-config key ``workspace_install_command`` (an argument list,
    never a shell string). Every refusal is an :class:`InstallSetupError`
    whose message is the answer's failure excerpt.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import worktree_git as wg

_log = logging.getLogger(__name__)

CONFIG_KEY = "workspace_install_command"
_BUILD = Path("scripts") / "build.py"
_SIGNATURE = Path("templates") / "scripts" / "worktree.py"
# Fetching a package submodule clones a whole repository; the plain git timeout is too short.
_SUBMODULE_TIMEOUT_SECONDS = 900


class InstallSetupError(Exception):
    """The workspace's install build cannot be set up; the message is the refusal excerpt."""


def is_package(folder: Path) -> bool:
    """True when *folder* holds the package: its build entry point and its own maker source."""
    return (folder / _BUILD).is_file() and (folder / _SIGNATURE).is_file()


def submodule_paths(workspace: Path) -> list[str]:
    """The submodule paths the workspace's own ``.gitmodules`` declares, in declaration order."""
    if not (workspace / ".gitmodules").is_file():
        return []
    proc = wg.run_git(["config", "--file", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"], workspace)
    if proc.returncode != 0:  # 1 = no path entries at all
        return []
    return [line.split(" ", 1)[1].strip() for line in proc.stdout.splitlines() if " " in line.strip()]


def _sub_folders(workspace: Path) -> list[str]:
    """The workspace's immediate, non-hidden sub-folders, sorted (hidden ones hold installs, never the package)."""
    try:
        return sorted(p.name for p in workspace.iterdir() if p.is_dir() and not p.name.startswith("."))
    except OSError as exc:
        _log.warning("worktree_install: cannot list %s: %s", workspace, exc)
        return []


def init_package_submodule(workspace: Path, project_root: Path | None) -> list[str]:
    """Fetch the package submodule into *workspace*; return the paths initialised.

    Only a submodule whose copy in the main checkout (*project_root*) is the
    package, and whose copy in the workspace is not yet populated, is touched.

    Raises:
        InstallSetupError: ``git submodule update --init`` failed (git's own message quoted).
    """
    done: list[str] = []
    for rel in submodule_paths(workspace):
        if project_root is None or is_package(workspace / rel) or not is_package(project_root / rel):
            continue
        proc = wg.run_git(["submodule", "update", "--init", "--", rel], workspace, timeout=_SUBMODULE_TIMEOUT_SECONDS)
        if proc.returncode != 0:
            msg = f"git submodule update --init -- {rel} failed: {(proc.stderr or proc.stdout or '').strip()}"
            raise InstallSetupError(msg)
        done.append(rel)
    return done


def package_dir(workspace: Path) -> Path | None:
    """The package folder inside *workspace*: the root, then each submodule, then each sub-folder."""
    for rel in ("", *submodule_paths(workspace), *_sub_folders(workspace)):
        folder = workspace / rel if rel else workspace
        if is_package(folder):
            return folder
    return None


def declared_command(config_path: Path) -> list[str] | None:
    """The adopter's declared install command from *config_path*, or ``None`` when none is declared.

    Raises:
        InstallSetupError: the key holds anything but a list of non-empty strings.
    """
    if not config_path.is_file():
        return None  # the caller answers NO_CONFIG for a missing config
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        _log.warning("worktree_install: cannot read %s: %s", config_path, exc)
        return None  # the build itself reports an unreadable config
    value = data.get(CONFIG_KEY) if isinstance(data, dict) else None
    if value is None or value == []:
        return None
    if not isinstance(value, list) or not all(isinstance(word, str) and word for word in value):
        msg = f"{CONFIG_KEY} in {config_path} must be a list of non-empty strings (an argument list), got {value!r}"
        raise InstallSetupError(msg)
    return value


def _substitute(words: list[str], values: dict[str, str]) -> list[str]:
    """Replace each ``{name}`` placeholder of *values* in every word (no other formatting)."""
    out = []
    for word in words:
        for name, value in values.items():
            word = word.replace("{" + name + "}", value)
        out.append(word)
    return out


def install_command(workspace: Path, config_path: Path, project_root: Path | None = None) -> list[str]:
    """The argument list that builds *workspace*'s install, run with the workspace as working directory.

    Initialises the package submodule first. A declared ``workspace_install_command`` wins; else the
    package's own ``scripts/build.py`` at its real location; else a top-level ``scripts/build.py``.

    Raises:
        InstallSetupError: no build was found, the declaration is malformed, or the submodule fetch failed.
    """
    init_package_submodule(workspace, project_root)
    package = package_dir(workspace)
    declared = declared_command(config_path)
    if declared is not None:
        if package is None and any("{package_dir}" in word for word in declared):
            msg = f"{CONFIG_KEY} names {{package_dir}}, but no package folder was found in {workspace}"
            raise InstallSetupError(msg)
        values = {"python": sys.executable, "workspace": str(workspace), "config_path": str(config_path),
                  "package_dir": str(package or "")}
        return _substitute(declared, values)
    build = (package or workspace) / _BUILD
    if not build.is_file():
        searched = ", ".join(submodule_paths(workspace)) or "none"
        msg = (f"scripts/build.py is absent: no package folder (scripts/build.py with {_SIGNATURE.as_posix()}) "
               f"in the workspace root, its submodules ({searched}) or its sub-folders, and no {CONFIG_KEY}")
        raise InstallSetupError(msg)
    return [sys.executable, str(build), "--target-dir", str(workspace), "--config-path", str(config_path)]


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-11-17 [python-coder/BO-4300b-2-iii]: (#TICKETLESS reason=quick-fix-ac-first)
#   Created: the install build is found from the workspace itself (self-host root, package
#   submodule -- fetched first --, package sub-folder, then a top-level scripts/build.py),
#   and an adopter may declare workspace_install_command (BO-4300b-2-iv). Reproduced in
#   DIAGraph (build v21.0.93): the hard-coded <workspace>/scripts/build.py refused every
#   epic workspace. Own module so worktree_readiness.py does not grow. (ADR-018)
# ===========================================================================
