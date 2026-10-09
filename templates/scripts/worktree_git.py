"""
MODULE: worktree_git
GOAL: Low-level git-subprocess and marker-registry primitives for
    templates/scripts/worktree.py, the one maker every workspace route goes
    through (the install build and readiness proofs live in worktree_readiness).
BUSINESS CONTEXT: BO-4300a-1 ("Every route that asks gets the same kind of
    workspace from the same maker") requires ONE place that runs git,
    and reads/writes the marker registry -- so no caller can quietly reimplement a slightly different
    recipe. This module carries that plumbing out of worktree.py's own CLI
    dispatch so each file stays small and single-purpose (the same split
    build_deploy_manifest_helpers.py already uses relative to build.py).
    Project resolution, the landing place and config derivation moved to
    worktree_layout.py (ADR-018 A1.12); this module keeps no copy.
ARCHITECTURE: Pure stdlib (json, os, subprocess, tempfile, contextlib,
    logging, pathlib). ``run_git`` is the single subprocess boundary every
    other function in this module goes through, always with its working
    directory set to the target (never ``git -C <path> ...`` for anything
    that could be a commit -- KI-CG-20260925-commit-delegation-hook-misses-
    git-dash-c). The marker registry (``.leafcutter/workspace.json`` inside
    each workspace) is this module's only persistent state; no git command
    lists clones, so ``worktree.py``'s ``locate``/``list`` verbs read this
    file, never ``git worktree list``.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import worktree_answer

_log = logging.getLogger(__name__)

MAKER_VERSION = "1"

KIND_BRANCH_PREFIX: dict[str, str] = {
    "ticket": "ticket",
    "feature": "feature",
    "ac": "ac-authoring",
    "fastlane": "fast-lane",
    "epic": "epic",
    "scratch": "scratch",
}
VALID_KINDS: tuple[str, ...] = tuple(KIND_BRANCH_PREFIX)

_CANARY_FILE_NAME = ".leafcutter_workspace_canary_probe.txt"
_CANARY_CONTENT = "LEAFCUTTER_WORKSPACE_CANARY_PROBE\n"
_GIT_TIMEOUT_SECONDS = 60
_SLUG_DISALLOWED = re.compile(r"[^a-z0-9._-]+")

def run_git(args: list[str], cwd: Path, timeout: int = _GIT_TIMEOUT_SECONDS) -> subprocess.CompletedProcess:
    """Run ``git <args>`` with the working directory set to *cwd*.

    The single subprocess boundary for this module. Never uses ``git -C`` --
    the working directory is always set via ``cwd=`` so the same spelling is
    used whether the call could commit or not (KI-CG-20260925-commit-
    delegation-hook-misses-git-dash-c). A launch failure (missing git binary,
    OS-level error) is converted into a synthetic non-zero
    ``CompletedProcess`` rather than raising, so every caller can uniformly
    branch on ``.returncode``.

    Args:
        args: The git subcommand and its arguments, without the leading "git".
        cwd: Absolute path to run git in.
        timeout: Seconds to wait before giving up.

    Returns:
        The completed process (real or synthesized on launch failure).
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("run_git: 'git %s' failed to launch in %s: %s", " ".join(args), cwd, exc)
        return subprocess.CompletedProcess(args=["git", *args], returncode=1, stdout="", stderr=str(exc))
    worktree_answer.forward_git_output(args, proc)
    return proc


def marker_path(workspace: Path) -> Path:
    """Return the absolute path of *workspace*'s marker file.

    Lives at ``<workspace>/.leafcutter/workspace.json`` -- outside version
    control and outside anything the install build rewrites or cleans (the
    install build's own stub only ever writes ``INSTALLED_MARKER.txt`` and
    the git hook, never ``.leafcutter/``).

    Args:
        workspace: Absolute path to the workspace root.

    Returns:
        Absolute path to the marker file (may not exist yet).
    """
    return workspace / ".leafcutter" / "workspace.json"


def write_marker(workspace: Path, data: dict[str, Any]) -> None:
    """Atomically write *data* as the marker for *workspace* (temp file + replace).

    Args:
        workspace: Absolute path to the workspace root.
        data: The marker fields to persist (schema_version, kind, slug,
            branch, hub, project_root, base_commit, maker_version, state,
            created_at, and optionally checks).

    Raises:
        OSError: Propagated after logging when the write cannot complete --
            a marker that silently failed to write would make every later
            ``verify``/``locate`` call see a workspace that does not exist.
    """
    path = marker_path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".workspace-", suffix=".json.tmp")
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(tmp_name, str(path))
    except OSError as exc:
        with contextlib.suppress(OSError):
            os.remove(tmp_name)
        _log.warning("write_marker: failed to write marker at %s: %s", path, exc)
        raise


def read_marker(workspace: Path) -> dict[str, Any] | None:
    """Read *workspace*'s marker file, or return ``None`` when absent/invalid.

    Args:
        workspace: Absolute path to the workspace root.

    Returns:
        The parsed marker dict, or ``None`` when the file is missing,
        unreadable, or not valid JSON.
    """
    path = marker_path(workspace)
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        _log.warning("read_marker: cannot read %s: %s", path, exc)
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        _log.warning("read_marker: invalid JSON at %s: %s", path, exc)
        return None


def origin_url(workspace: Path) -> str | None:
    """Return *workspace*'s ``origin`` remote URL, or ``None`` if unset/unreadable."""
    proc = run_git(["remote", "get-url", "origin"], workspace)
    if proc.returncode != 0:
        return None
    url = proc.stdout.strip()
    return url or None


def git_config_get(workspace: Path, key: str) -> str | None:
    """Return the value of git config *key* inside *workspace*, or ``None``."""
    proc = run_git(["config", "--get", key], workspace)
    if proc.returncode != 0:
        return None
    value = proc.stdout.strip()
    return value or None


def same_location(a: str, b: str) -> bool:
    """Best-effort equality of two path-or-URL strings, resolving filesystem paths."""
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


def normalize_slug(raw: str) -> str:
    """Normalise a caller-supplied work-identity slug to a safe directory/branch fragment."""
    slug = _SLUG_DISALLOWED.sub("-", raw.strip().lower())
    return slug.strip("-") or "workspace"


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-27 23:57 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Created this module to carry worktree.py's git-subprocess, marker-
#   registry, canary and install-build plumbing out of the CLI dispatch file
#   so each stays small and single-purpose. No git command lists clones, so
#   the marker registry here (.leafcutter/workspace.json per workspace) is
#   the only source locate/list ever read.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-28 02:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Fixed pr-reviewer H-2/H-3 (2026-09-28 00:43, corroborated by ac-validator
#   2026-09-28 00:50): added derive_config_path() (real skills_config.json
#   discovery mirroring build.py's own _resolve_skills_config_path order,
#   with top_level_packages-prefix stripping per ADR-018 Amendment 1 A1.3 --
#   replaces the hardcoded ".pre-commit-config.yaml" guess, a file
#   --config-path never reads); added status_for_code/exit_code_for_answer/
#   finalize_answer/layout_for so worktree.py and worktree_admin.py apply one
#   shared BO-4300c-2 status/exit-code/common-fields rule instead of each
#   hardcoding exit 1. Per-stage hook-check-dict parity with BO-4300c-2's
#   full `checks` shape remains deferred: it needs BO-4300c-1-ii's per-stage
#   hook declaration (not yet built) and BO-4300b-1's branch-safety checks
#   (not yet built) as real inputs, not a renamed copy of this maker's own
#   five checks.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-28 02:42 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01]:
#   Fixed pr-reviewer H-2 (2026-09-28 02:15): honestly narrowed
#   derive_config_path()'s docstring instead of pre-empting BO-4300b-1's own
#   layout-detection scope (see the docstring's own "KNOWN LIMITATION" for
#   the full trace). No functional change.
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/01) (ADR-018)
# - 2026-09-30 22:05 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
#   Moved status_for_code/exit_code_for_answer/finalize_answer and the refused
#   set to worktree_answer.py; run_git and run_install_build now forward the
#   child's output to stderr; --repo-root accepts any shell's spelling via
#   worktree_paths. (ADR-018)
#   landing_place() now follows the Q5 sibling rule
#   <parent>/<project-dir-name>-worktrees (the red baseline's fixtures require
#   it; ticket 04 owns moving/extending it). (ADR-018)
# - 2026-09-30 23:10 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/04)
#   Moved resolve_repo_root, landing_place, layout_for, derive_config_path,
#   _read_top_level_packages and iter_markers to worktree_layout.py (A1.12);
#   no copy kept here. (ADR-018)
# - 2026-10-01 00:30 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/05)
#   Moved compute_checks, run_canary, run_install_build,
#   restore_dirtied_tracked, hooks_dir and is_clean to worktree_readiness.py
#   (BO-4300c-1); _same_location became the public same_location. (ADR-018)
# ===========================================================================
