"""
MODULE: scripts/evals/agent_launch/locate.py
GOAL: Find the claude CLI the way the platform's own shell finds it.
BUSINESS CONTEXT: TQ-200d-5-ii. The standard npm install on Windows puts claude, claude.cmd and claude.ps1
    on the path and no claude.exe; the bare name ``claude`` cannot start any of them without a shell.
ARCHITECTURE: ``find_claude`` answers, in order: the LEAFCUTTER_EVAL_CLAUDE_CLI setting (on every platform,
    never replaced by the path when it names a missing program); on Windows the PATH and PATHEXT lookup
    of ``shutil.which``; elsewhere the bare name ``claude``. ``command`` decides how to start the answer.
"""

from __future__ import annotations

import os
import shutil
import sys

CLI_ENV_VAR = "LEAFCUTTER_EVAL_CLAUDE_CLI"
PROGRAM = "claude"


def is_windows() -> bool:
    """True on Windows; read at call time so a test can change ``sys.platform``."""
    return sys.platform.startswith("win")


def find_claude() -> str:
    """The program to start: the setting, else (Windows) the PATH/PATHEXT lookup, else the name ``claude``."""
    setting = os.environ.get(CLI_ENV_VAR)
    if setting:
        return setting
    if is_windows():
        return shutil.which(PROGRAM) or PROGRAM
    return PROGRAM
