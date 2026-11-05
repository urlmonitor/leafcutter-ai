"""
MODULE: worktree_log_root
GOAL: Hand the project's enduring log root to the install build the workspace
    maker runs inside a new workspace, and retry once without it when the
    workspace's own build predates the flags (INF-500d-4-iii, ADR-069 section 3).
BUSINESS CONTEXT: Logs written inside a workspace must survive its removal.
    The retired bootstrap read the project's recorded declaration and passed
    ``--log-root``; the maker now does the same, reading the declaration of the
    install that deployed it. When the root cannot be read the build is told
    ``--no-log-root`` and a loud warning names the path tried and why.
ARCHITECTURE: Stdlib-only, deployed beside ``worktree_readiness.py``. The root
    is read from ``<install_root>/config/knowledge_sink.json`` -- never derived
    from a repository path. ``operational_log_root`` wins; a legacy declaration
    uses the parent of ``knowledge_emission_sink``; the root must be absolute.
    Warnings go to stderr only (the maker's stdout is one JSON answer).
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import worktree_git as wg

_NO_ROOT = "--no-log-root"


def _recorded_root(declaration: Path) -> str:
    """The absolute root recorded in *declaration*; raises ``ValueError``/``OSError`` otherwise."""
    data = json.loads(declaration.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("the declaration is not a JSON object")
    root = data.get("operational_log_root")
    if root is None:
        try:
            root = str(Path(data["knowledge_emission_sink"]).parent)
        except (KeyError, TypeError) as exc:
            raise ValueError("neither operational_log_root nor knowledge_emission_sink is recorded") from exc
    if not isinstance(root, str) or not Path(root).is_absolute():
        raise ValueError(f"{root!r} is not an absolute path")
    return root


def inherited_log_root_args(install_root: Path) -> tuple[list[str], str | None]:
    """Build flags for the workspace build: ``(["--log-root", root], None)`` or ``(["--no-log-root"], warning)``."""
    declaration = Path(install_root) / "config" / "knowledge_sink.json"
    try:
        return ["--log-root", _recorded_root(declaration)], None
    except (OSError, ValueError) as exc:
        return [_NO_ROOT], (f"WARNING: no enduring log root readable from {declaration} ({exc}); "
                            "logs written in this workspace will not survive its removal.")


def _run_build(argv: list[str], **run_kwargs: Any) -> subprocess.CompletedProcess:
    """Run one build invocation; a launch failure or timeout surfaces as ``subprocess.SubprocessError``."""
    try:
        kwargs = {k: v for k, v in run_kwargs.items() if k not in ("stdin", "env")}
        caller_env = run_kwargs.get("env")
        env = wg.git_env() if caller_env is None else wg.no_prompt_env(caller_env)
        return subprocess.run(argv, stdin=subprocess.DEVNULL, env=env, **kwargs)  # noqa: PLW1510
    except (OSError, subprocess.SubprocessError) as exc:
        raise subprocess.SubprocessError(f"workspace build {argv[0]!r} did not complete: {exc}") from exc


def run_with_inherited_log_root(cmd: list[str], flags: list[str], **run_kwargs: Any) -> subprocess.CompletedProcess:
    """Run ``cmd + flags``; if the build rejects the flags (exit 2, "unrecognized arguments") retry once without."""
    proc = _run_build([*cmd, *flags], **run_kwargs)
    if flags and proc.returncode == 2 and "unrecognized arguments" in (proc.stderr or ""):
        print(f"WARNING: the workspace's build rejected {flags[0]}; built without it, so logs written in this "
              "workspace have no durable log root and will not survive its removal.", file=sys.stderr)
        proc = _run_build(cmd, **run_kwargs)
    return proc


def build_with_inherited_log_root(cmd: list[str], install_root: Path, **run_kwargs: Any) -> subprocess.CompletedProcess:
    """Run the workspace build *cmd* with the root inherited from *install_root*, warning on stderr."""
    flags, warning = inherited_log_root_args(install_root)
    if warning:
        print(warning, file=sys.stderr)
    return run_with_inherited_log_root(cmd, flags, **run_kwargs)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-16 20:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/17]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/17)
#   Created: the maker's install build inherits the project's durable log root
#   (read from the deploying install's declaration), with one retry for an
#   older build. Own module so worktree_readiness.py does not grow. (ADR-018, ADR-069)
# - 2026-10-17 12:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/17]: (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/17)
#   Both build calls now go through _run_build, which re-raises OSError/SubprocessError
#   as SubprocessError with context (check-exception-handling IO-001); the caller's
#   existing handler in worktree_readiness.run_install_build still catches it unchanged.
# ===========================================================================
