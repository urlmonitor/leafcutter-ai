"""
MODULE: worktree_git
GOAL: Low-level git-subprocess, marker-registry, and install-build primitives
    for templates/scripts/worktree.py, the one maker every workspace route
    goes through.
BUSINESS CONTEXT: BO-4300a-1 ("Every route that asks gets the same kind of
    workspace from the same maker") requires ONE place that runs git,
    reads/writes the marker registry, and drives the per-workspace install
    build -- so no caller can quietly reimplement a slightly different
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
import sys
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


def is_clean(workspace: Path) -> bool:
    """Return ``True`` when no TRACKED path in *workspace* is modified/staged.

    Untracked files are deliberately not a dirtiness signal here: the
    install build always leaves real, untracked artefacts behind (e.g.
    ``INSTALLED_MARKER.txt``) that are never meant to be committed, and a
    workspace that already contains those is still "clean" in the sense
    this check exists for (BOOTSTRAP_DIRTIED_TRACKED). ``restore_dirtied_
    tracked`` uses the identical "??"-exclusion rule so the two can never
    disagree about what counts as dirty.
    """
    proc = run_git(["status", "--porcelain"], workspace)
    if proc.returncode != 0:
        return False
    for line in proc.stdout.splitlines():
        if line.strip() and line[:2] != "??":
            return False
    return True


def _same_location(a: str, b: str) -> bool:
    """Best-effort equality of two path-or-URL strings, resolving filesystem paths."""
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return a == b


def hooks_dir(workspace: Path) -> Path | None:
    """Resolve the effective git hooks directory for *workspace*.

    Uses ``git rev-parse --git-common-dir`` (read-only, no ``-C`` spelling
    concern since this can never be a commit) rather than any ``__file__``-
    based walk.

    Args:
        workspace: Absolute path to the workspace root.

    Returns:
        Absolute path to the hooks directory, or ``None`` when it cannot be
        resolved.
    """
    proc = run_git(["rev-parse", "--git-common-dir"], workspace)
    if proc.returncode != 0:
        return None
    common_dir_str = proc.stdout.strip()
    if not common_dir_str:
        return None
    common_dir = Path(common_dir_str)
    if not common_dir.is_absolute():
        common_dir = (workspace / common_dir).resolve()
    return common_dir / "hooks"


def compute_checks(workspace: Path, hub: str) -> dict[str, bool]:
    """Compute the read-only readiness checks for *workspace*.

    Deliberately excludes ``hooks_canary_rejected`` -- proving that requires
    an actual commit attempt, which is a write and therefore only ever done
    once, during ``ensure`` (see :func:`run_canary`); callers that need it
    outside of ``ensure`` read the value the marker already stored.

    Args:
        workspace: Absolute path to the workspace root.
        hub: The hub URL/path this workspace's origin is expected to equal.

    Returns:
        Dict with boolean keys ``is_independent_repo``, ``origin_matches_hub``,
        ``gc_auto_disabled``, ``hooks_installed``, ``working_tree_clean``.
    """
    origin = origin_url(workspace)
    hooks = hooks_dir(workspace)
    return {
        "is_independent_repo": (workspace / ".git").is_dir(),
        "origin_matches_hub": bool(origin) and _same_location(origin, hub),
        "gc_auto_disabled": git_config_get(workspace, "gc.auto") == "0",
        "hooks_installed": bool(hooks and (hooks / "pre-commit").is_file()),
        "working_tree_clean": is_clean(workspace),
    }


def run_canary(workspace: Path) -> bool:
    """Attempt one real commit of a generic canary file, then revert it either way.

    Proves whether *some* protection fires without the maker needing to know
    any project-specific "known bad" content: the canary content is generic
    ("LEAFCUTTER_WORKSPACE_CANARY_PROBE"), so a hook tuned to a specific
    secret/sentinel pattern will not necessarily reject it -- the boolean
    this returns records what actually happened, never an assumption.
    Whichever way the commit went, the workspace is restored to exactly the
    state it was in before this call: a rejected commit is unstaged and the
    probe file removed; an accepted commit is undone with a hard reset to
    the prior HEAD.

    Args:
        workspace: Absolute path to the workspace root. Must already be a
            checked-out git repository with at least one commit.

    Returns:
        ``True`` when the commit was rejected (a hook fired), ``False`` when
        it succeeded (no hook rejected the generic probe content).
    """
    head_before = run_git(["rev-parse", "HEAD"], workspace).stdout.strip()
    canary_file = workspace / _CANARY_FILE_NAME
    try:
        canary_file.write_text(_CANARY_CONTENT, encoding="utf-8")
    except OSError as exc:
        _log.warning("run_canary: cannot write probe file at %s: %s", canary_file, exc)
        return False

    run_git(["add", "-A", "--", _CANARY_FILE_NAME], workspace)
    commit_proc = run_git(["commit", "-q", "-m", "leafcutter workspace canary probe"], workspace)
    rejected = commit_proc.returncode != 0

    if rejected:
        run_git(["reset", "-q"], workspace)
        with contextlib.suppress(OSError):
            canary_file.unlink()
    elif head_before:
        run_git(["reset", "-q", "--hard", head_before], workspace)

    return rejected


def run_install_build(workspace: Path, config_path: Path) -> tuple[bool, str | None]:
    """Run the workspace's own install build with an explicit config path.

    Args:
        workspace: Absolute path to the workspace root. Its own
            ``scripts/build.py`` (checked out from the project's own
            contents, never the maker's own location) is what gets run.
        config_path: Absolute path to the config file to pass explicitly.

    Returns:
        ``(True, None)`` on a zero exit. ``(False, "BOOTSTRAP_FAILED")`` when
        the workspace has no ``scripts/build.py``, the build launches but
        exits non-zero, or cannot be launched at all -- ``BOOTSTRAP_FAILED``
        is the BO-4300c-2 result-contract code for every "the install
        failed" outcome, so callers never see this maker's own internal
        subtypes. ``(False, "NO_CONFIG")`` when *config_path* does not exist
        -- kept distinct because it is the maker's own precondition check,
        not a build-process failure.
    """
    build_script = workspace / "scripts" / "build.py"
    if not build_script.is_file():
        return False, "BOOTSTRAP_FAILED"
    if not config_path.is_file():
        return False, "NO_CONFIG"

    try:
        proc = subprocess.run(
            [sys.executable, str(build_script), "--target-dir", str(workspace), "--config-path", str(config_path)],
            cwd=str(workspace),
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("run_install_build: failed to launch %s: %s", build_script, exc)
        return False, "BOOTSTRAP_FAILED"

    worktree_answer.forward_child_output(proc)
    if proc.returncode != 0:
        _log.warning("run_install_build: %s exited %s", build_script, proc.returncode)
        return False, "BOOTSTRAP_FAILED"
    return True, None


def restore_dirtied_tracked(workspace: Path) -> list[str]:
    """Restore any TRACKED path the install build modified; return their names.

    Untracked files the build wrote (e.g. ``INSTALLED_MARKER.txt``) are left
    alone -- only tracked, modified/deleted paths are restored, matching the
    decision memo's ``bootstrap.restored_tracked`` contract.

    Args:
        workspace: Absolute path to the workspace root.

    Returns:
        List of tracked paths (relative to *workspace*) that were dirtied
        and then restored via ``git checkout --``. Empty when the tree was
        already clean of tracked changes.
    """
    status = run_git(["status", "--porcelain"], workspace).stdout
    dirtied: list[str] = []
    for line in status.splitlines():
        if not line.strip():
            continue
        code, rel_path = line[:2], line[3:].strip()
        if code[0] != "?" and code[1] != "?":
            dirtied.append(rel_path)
    if dirtied:
        run_git(["checkout", "--", *dirtied], workspace)
    return dirtied


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
# ===========================================================================
