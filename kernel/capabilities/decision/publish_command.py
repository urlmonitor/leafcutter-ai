"""
MODULE: kernel.capabilities.decision.publish_command
GOAL: Build the `decisions publish` command the kernel prints, runnable verbatim from any shell.
BUSINESS CONTEXT: Plain `python -m kernel` failed in the owner's shell (system interpreter, kernel
    not importable); the printed command must work as shown and say where it writes.
ARCHITECTURE: Pure string building from `sys.executable` and `kernel.config.repo_root`; used by
    the decision executor when it stages a record.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from kernel.config import repo_root


def publish_folder() -> Path:
    """Return the folder `decisions publish` writes into (the kernel checkout's docs/decisions)."""
    return repo_root() / "docs" / "decisions"


def _quote(arg: str) -> str:
    """Quote an argument only when it contains whitespace (plain form works in every shell)."""
    return f'"{arg}"' if any(ch.isspace() for ch in arg) else arg


def publish_command(run_id: str) -> str:
    """Return the publish command as a plain argv that runs verbatim from any shell and directory.

    It names the interpreter the kernel runs under and scripts/run_kernel.py, which puts the
    `kernel` package on the import path itself (no venv activation, cwd or PYTHONPATH needed).
    """
    launcher = repo_root() / "scripts" / "run_kernel.py"
    parts = [_quote(a) for a in (sys.executable, str(launcher))]
    command = " ".join([*parts, "decisions", "publish", "--run-id", run_id])
    if os.name == "nt" and any(p.startswith('"') for p in parts):
        return f"& {command}"  # PowerShell needs `&` to run a quoted executable
    return command
