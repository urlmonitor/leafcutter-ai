"""
MODULE: build_precommit_install
GOAL: Resolve a usable ``pre-commit`` binary and run ``pre-commit install``
    against a target project after ``.pre-commit-config.yaml`` has been
    written.
BUSINESS CONTEXT: Extracted from build_helpers.py, which was already over
    the check-file-size ratchet (an already-oversized file may be worked on
    but must not end up longer than it stood at HEAD) before the BP-1500g-1
    change that grew it further. This "last mile" installer -- distinct
    from ``build_precommit.py``, which generates the config file's content,
    not from install_shims/ownership -- is a self-contained family with no
    dependency on BP-1500g-1's ownership-attribution change, so it is what
    moves to make room, the same shape PR #769 used when it extracted the
    knowledge phases out of build_phases.py.
ARCHITECTURE: Three functions. ``install_hooks`` is the public entry point
    build.py calls (imported there as ``install_hooks as _install_hooks``,
    re-exported by name with no change needed since build.py already
    imports it from ``build_helpers`` -- moved here and re-imported by
    ``build_helpers.py`` in turn, so that existing import keeps resolving).
    ``_resolve_precommit_cmd`` (three-tier binary detection: PATH, importable
    Python module, known install locations) and ``_precommit_known_paths``
    (the known-location generator) are private helpers used only by it.
    Pure move: no behaviour change.
"""

from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

from build_colors import dry_run as _dry_run
from build_colors import error as _error
from build_colors import info as _info
from build_colors import success as _success
from build_colors import warn as _warn


def _resolve_precommit_cmd():
    """Return the command list to invoke pre-commit, or None if unavailable.

    Three-tier detection:
    1. ``shutil.which("pre-commit")`` — binary on PATH.
    2. ``importlib.util.find_spec("pre_commit")`` — installed as a Python
       package in the same environment running build.py (handles the common
       case where pip installed it but the Scripts/ dir isn't on PATH).
    3. Probe known pip/pipx install locations — handles non-interactive shells
       where ~/.local/bin or Scripts/ aren't in PATH.
    """
    if shutil.which("pre-commit"):
        return ["pre-commit"]
    if importlib.util.find_spec("pre_commit"):
        return [sys.executable, "-m", "pre_commit"]
    for candidate in _precommit_known_paths():
        if not candidate.is_file():
            continue
        try:
            probe = subprocess.run(
                [str(candidate), "--version"],
                capture_output=True,
                timeout=5,
            )
            if probe.returncode == 0:
                return [str(candidate)]
        except (OSError, subprocess.TimeoutExpired):
            continue
    return None


def _precommit_known_paths():
    """Yield common install locations for the pre-commit binary."""
    home = Path.home()
    yield home / ".local" / "bin" / "pre-commit"
    exe_dir = Path(sys.executable).parent
    yield exe_dir / "pre-commit"
    if sys.platform == "win32":
        yield exe_dir / "Scripts" / "pre-commit.exe"
    else:
        yield exe_dir / "Scripts" / "pre-commit"


def install_hooks(target_root, dry_run=False):
    """Run ``pre-commit install`` after build.py writes .pre-commit-config.yaml.

    Closes the "last mile" gap: the generated config exists on disk but
    ``pre-commit install`` must be run to wire ``.git/hooks/pre-commit`` to it.
    This function is idempotent — calling it multiple times on the same project
    is safe.

    Args:
        target_root: Absolute path to the target project root.
        dry_run: When True, prints the action but does not run any subprocess.

    Returns:
        One of "installed", "dry-run", "failed",
        "skipped (pre-commit not found)", "skipped (custom hooksPath)",
        or "skipped (not a git repo)".
    """
    # 1. Resolve pre-commit binary (PATH lookup, then Python module fallback).
    precommit_cmd = _resolve_precommit_cmd()
    if precommit_cmd is None:
        _warn("pre-commit not found; skipping hook install")
        _info("         Pre-commit runs code-quality checks automatically before")
        _info("         each commit. Install it with:")
        _info("")
        _info("           pip install pre-commit")
        _info("")
        _info("         Then re-run this build to complete hook setup.")
        return "skipped (pre-commit not found)"

    # 2. Dry-run guard (before any subprocess calls that mutate state).
    if dry_run:
        _dry_run("would run pre-commit install")
        return "dry-run"

    # 3. Check core.hooksPath git config.
    try:
        hooks_path_result = subprocess.run(
            ["git", "-C", str(target_root), "config", "--get", "core.hooksPath"],
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        # git binary not found — degrade safely rather than hard-failing.
        _warn(f"hooks: could not read core.hooksPath (git not found): {exc}")
        hooks_path_result = None
    if hooks_path_result is not None and hooks_path_result.returncode == 0:
        hooks_path_value = hooks_path_result.stdout.strip()
        default_hooks = Path(target_root) / ".git" / "hooks"
        is_default = (
            hooks_path_value.lower() in (".git/hooks", ".git\\hooks")
            or Path(hooks_path_value).resolve() == default_hooks.resolve()
        )
        if is_default:
            try:
                subprocess.run(
                    ["git", "-C", str(target_root), "config", "--unset", "core.hooksPath"],
                    capture_output=True,
                )
            except OSError as exc:
                _warn(f"hooks: could not unset core.hooksPath (git not found): {exc}")
            else:
                _info("hooks: cleared redundant core.hooksPath (.git/hooks)")
        elif hooks_path_value:
            _warn(
                f"core.hooksPath is set to '{hooks_path_value}' "
                "(non-default); skipping pre-commit install"
            )
            return "skipped (custom hooksPath)"

    # 3.5. Guard: verify target_root is inside a git working tree.
    # Using `git rev-parse --git-dir` is more robust than checking for a .git
    # directory directly: it also handles worktrees and nested repos correctly.
    try:
        git_check = subprocess.run(
            ["git", "-C", str(target_root), "rev-parse", "--git-dir"],
            capture_output=True,
        )
    except OSError as exc:
        # git binary not found — degrade safely rather than hard-failing.
        _warn(f"hooks: could not verify git repo (git not found): {exc}")
        git_check = None

    if git_check is not None and git_check.returncode != 0:
        _info("hooks: skipping pre-commit install (target is not a git repo)")
        return "skipped (not a git repo)"

    # 4. Run pre-commit install.
    try:
        subprocess.run(
            [*precommit_cmd, "install"],
            cwd=str(target_root),
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
        _error(f"pre-commit install failed: {stderr.strip()}")
        return "failed"

    _success("hooks: pre-commit install OK")
    return "installed"


# DECISION HISTORY
# ================================================================================
# - 2026-09-14 [python-coder]: Created this module, moving install_hooks,
#   _resolve_precommit_cmd, and _precommit_known_paths out of
#   build_helpers.py (over the check-file-size ratchet) so it could shrink
#   back under it. build_helpers.py re-imports install_hooks so build.py's
#   existing `from build_helpers import install_hooks as _install_hooks`
#   keeps resolving with no edit. Pure move, no behaviour change.
#   (#BP-1500g-1/extract-unrelated-headroom)
# ====================================================================
