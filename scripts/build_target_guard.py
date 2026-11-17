"""
MODULE: scripts/build_target_guard.py
GOAL: Refuse a build that would install the package into its own repository
    unless the caller named that target explicitly (BO-4300f-2, decision Q6).
BUSINESS CONTEXT: With no ``--target-dir``, ``build.py`` targets the current
    folder. Run from the package root, that wrote a stale ``.leafcutter/``
    install inside the package repository -- a second copy of every script,
    including the former workspace set-up scripts. The package's own
    workspaces carry their own install, built with an explicit
    ``--target-dir``; CI passes ``--target-dir .``; ``build-self.sh`` passes the
    workspace. So an EXPLICIT target is never refused, and only the implicit
    one is.
ARCHITECTURE: One function over (argv, package root, cwd), argparse only. The package root is derived by the caller from the
    build's own location, never from a folder name. ``build.py`` calls it before
    its other imports (an import writes bytecode into the package), so nothing
    is written before the refusal.

DECISION HISTORY
====================================================================
- 2026-10-13 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/14,
  BO-4300f-2]: Created the implicit-build refusal. (#BO-4300f-2)
====================================================================
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def refuse_implicit_package_build(argv: list[str], package_root: Path, cwd: Path | None = None) -> str | None:
    """The refusal message when an implicit build would target the package repository, else None.

    Args:
        argv: The build's command-line arguments (without the program name).
        package_root: The package repository root, derived from the build's own location.
        cwd: The folder an implicit build would target; defaults to the current folder.

    Returns:
        A message naming the rule and the ``--target-dir`` remedy, or None
        when the build may proceed (an explicit target is never refused).
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--target-dir", "-t")
    explicit, _rest = parser.parse_known_args(argv)
    if explicit.target_dir:
        return None
    if (cwd or Path.cwd()).resolve() != package_root.resolve():
        return None
    return (
        "build refused: no --target-dir was given and the current folder is the package repository "
        f"itself ({package_root}). A build must not install the package into its own repository. "
        "Pass --target-dir <folder> to name where the install goes (for example a workspace "
        "made by scripts/worktree.py, or --target-dir . to install here on purpose)."
    )


def exit_if_implicit_package_build(argv: list[str], package_root: Path) -> None:
    """Exit the process with the refusal message when the build is refused; else return."""
    message = refuse_implicit_package_build(argv, package_root)
    if message:
        sys.exit(message)
