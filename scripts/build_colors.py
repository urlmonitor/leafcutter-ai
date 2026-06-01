"""
MODULE: build_colors
GOAL: Shared ANSI color constants and print helpers for the build pipeline.
BUSINESS CONTEXT: Centralises terminal colour output so warnings, errors, and
    success messages are visually distinct. Respects the NO_COLOR convention
    (https://no-color.org/) and dumb terminals.
ARCHITECTURE: Pure functions, no side effects on import. Every build module
    imports from here instead of defining its own ANSI constants.
"""

from __future__ import annotations

import os
import sys


def _colors_enabled() -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    if not hasattr(sys.stdout, "isatty"):
        return False
    return sys.stdout.isatty()


_ENABLED = _colors_enabled()

RESET = "\033[0m" if _ENABLED else ""
BOLD = "\033[1m" if _ENABLED else ""
DIM = "\033[2m" if _ENABLED else ""
RED = "\033[91m" if _ENABLED else ""
GREEN = "\033[92m" if _ENABLED else ""
YELLOW = "\033[93m" if _ENABLED else ""
CYAN = "\033[96m" if _ENABLED else ""


def warn(msg: str) -> None:
    print(f"  {YELLOW}[WARNING]{RESET} {msg}")


def error(msg: str) -> None:
    print(f"  {RED}[ERROR]{RESET} {msg}")


def success(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {msg}")


def dry_run(msg: str) -> None:
    print(f"  {DIM}[DRY-RUN]{RESET} {msg}")


def heading(label: str) -> None:
    print(f"{BOLD}{label}:{RESET}")
