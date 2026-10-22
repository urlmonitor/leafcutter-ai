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
import shutil
import subprocess
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from urllib.parse import unquote

import workspace_root
import worktree_answer

_log = logging.getLogger(__name__)

MAKER_VERSION = "1"

# One scheme for every kind: the line of work is ``<kind>/<slug>``; legacy
# spellings are declared in worktree_identity.LEGACY_ALIASES (BO-4300a-2).
VALID_KINDS: tuple[str, ...] = ("ticket", "feature", "ac", "fastlane", "epic", "scratch")

_CANARY_FILE_NAME = ".leafcutter_workspace_canary_probe.txt"
_CANARY_CONTENT = "LEAFCUTTER_WORKSPACE_CANARY_PROBE\n"
_GIT_TIMEOUT_SECONDS = 60


def no_prompt_env(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """Return a copy of *base* (default ``os.environ``) with every interactive prompt disabled.

    Sets ``GIT_TERMINAL_PROMPT=0`` and ``GCM_INTERACTIVE=never``; adds
    ``GIT_SSH_COMMAND="ssh -o BatchMode=yes"`` only when none of
    ``GIT_SSH_COMMAND``, ``GIT_SSH`` or a configured ``core.sshCommand`` is
    present, so a caller's own ssh setup is never overridden (BO-4300c-2).
    """
    env = dict(os.environ if base is None else base)
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "never"
    if "GIT_SSH_COMMAND" not in env and "GIT_SSH" not in env and not workspace_root.ssh_command_configured():
        env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
    return env


def git_env() -> dict[str, str]:
    """Environment for every maker child process: the caller's, with prompts disabled."""
    return no_prompt_env()


def run_git(args: list[str], cwd: Path, timeout: int = _GIT_TIMEOUT_SECONDS,
            encoding: str | None = None) -> subprocess.CompletedProcess:
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
        encoding: Decode output with this codec (errors replaced) instead of the
            locale default -- for callers reading unquoted non-ASCII paths.

    Returns:
        The completed process (real or synthesized on launch failure).
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            stdin=subprocess.DEVNULL,
            env=git_env(),
            capture_output=True,
            text=True,
            encoding=encoding,
            errors="replace" if encoding else None,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("run_git: 'git %s' failed to launch in %s: %s", " ".join(args), cwd, exc)
        return subprocess.CompletedProcess(args=["git", *args], returncode=1, stdout="", stderr=str(exc))
    worktree_answer.forward_git_output(args, proc)
    return proc


def copy_optional_files(repo_root: Path, workspace_path: Path) -> list[str]:
    """Best-effort copy ``.env``/``.mcp.json`` from the main checkout into the workspace.

    Returns the names actually copied (BO-4300c-2 ``bootstrap.env_copied``).
    """
    copied: list[str] = []
    for name in (".env", ".mcp.json"):
        src = repo_root / name
        if not src.is_file() or (workspace_path / name).exists():
            continue  # never overwrite a copy the work may have changed
        try:
            shutil.copy2(src, workspace_path / name)
        except OSError as exc:
            _log.warning("copy_optional_files: could not copy %s: %s", src, exc)
        else:
            copied.append(name)
    return copied


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


_REMOTE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9+.-]*://|[\w.-]+@[\w.-]+:)")
_DRIVE_URL_RE = re.compile(r"^/[A-Za-z]:")


def _trim_location(text: str) -> str:
    """Strip trailing separators and one ``.git`` suffix (and the separators before it)."""
    text = text.rstrip("/\\")
    if text.endswith(".git"):
        text = text[: -len(".git")].rstrip("/\\")
    return text


def _file_url_path(text: str) -> str | None:
    """The local path a ``file://`` URL names (``file:///C:/x`` -> ``C:/x``), else ``None``."""
    if text[:7].lower() != "file://":
        return None
    path = unquote(text[7:])
    if _DRIVE_URL_RE.match(path):
        return path[1:]
    return path if path.startswith("/") else "//" + path  # file://host/share -> UNC


def _canonical_location(text: str) -> str:
    """Comparable form of a path-or-URL: local paths normalised, remote URLs exact bar ``/`` and ``.git``."""
    text = text.strip()
    local = _file_url_path(text)
    if local is None and _REMOTE_RE.match(text):
        return _trim_location(text)
    local = _trim_location(text if local is None else local)
    if not Path(local).is_absolute():
        return local  # never resolved against the cwd
    local = os.path.normpath(local)
    if os.name == "nt":
        try:
            local = str(Path(local).resolve())
        except OSError as exc:
            _log.warning("same_location: cannot resolve %s: %s", local, exc)
        local = os.path.normcase(local)
    return local


def same_location(a: str, b: str) -> bool:
    """Equality of two path-or-URL strings: equal text first, then their canonical forms."""
    return a == b or _canonical_location(a) == _canonical_location(b)


def normalize_slug(raw: str, kind: str | None = None) -> str:
    """Normalise a work-identity slug; the naming table lives in ``worktree_identity``."""
    import worktree_identity  # noqa: PLC0415 - function-level: identity imports this module
    return worktree_identity.normalize_slug(raw, kind)


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
# - 2026-10-10 09:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
#   The naming table moved to worktree_identity.py (BO-4300a-2); normalize_slug
#   here only delegates so worktree_admin's locate uses the same rule, and
#   KIND_BRANCH_PREFIX was retired (every kind's line is <kind>/<slug>). (ADR-018)
# - 2026-10-12 20:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/12)
#   copy_optional_files moved here from worktree.py (file-size ratchet) to make
#   room for wiring the migrate-legacy verb. (ADR-018)
# ===========================================================================
