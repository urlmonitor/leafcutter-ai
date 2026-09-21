"""
MODULE: build_colors
GOAL: Shared ANSI color constants and print helpers for the build pipeline.
BUSINESS CONTEXT: Centralises terminal colour output so warnings, errors, and
    success messages are visually distinct. Respects the NO_COLOR convention
    (https://no-color.org/) and dumb terminals.
ARCHITECTURE: Pure functions, no side effects on import. Every build module
    imports from here instead of defining its own ANSI constants. All print
    helpers route through the private ``_emit`` helper so output degrades
    gracefully instead of crashing when the console's stdout encoding cannot
    represent a character (e.g. a Windows cp1252 console and the '✓' glyph).
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


def _emit(text: str) -> None:
    """Print text, degrading gracefully if stdout's encoding can't represent it.

    Resolves ``sys.stdout`` at call time (not import time) so redirection or
    monkeypatching in callers/tests still works. On a console whose encoding
    cannot represent every character (e.g. a Windows cp1252 console and the
    '✓' glyph), ``print()`` raises ``UnicodeEncodeError`` instead of
    degrading. This helper catches that case, re-encodes the text using the
    current stdout's encoding with ``errors="replace"``, decodes it back to
    str, and prints the result instead. On a UTF-8 capable console this is a
    no-op and output is byte-identical to a bare ``print(text)``.

    Args:
        text: The already-formatted line to print.
    """
    try:
        print(text)
    except UnicodeEncodeError:
        stdout = sys.stdout
        encoding = getattr(stdout, "encoding", None) or "ascii"
        safe_text = text.encode(encoding, errors="replace").decode(encoding)
        print(safe_text)


def warn(msg: str) -> None:
    _emit(f"  {YELLOW}[WARNING]{RESET} {msg}")


def error(msg: str) -> None:
    _emit(f"  {RED}[ERROR]{RESET} {msg}")


def success(msg: str) -> None:
    _emit(f"  {GREEN}✓{RESET} {msg}")


def info(msg: str) -> None:
    _emit(f"  {msg}")


def dry_run(msg: str) -> None:
    _emit(f"  {DIM}[DRY-RUN]{RESET} {msg}")


def heading(label: str) -> None:
    _emit(f"{BOLD}{label}:{RESET}")


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-16 00:00 [python-coder]: Added private _emit() helper and routed
#   warn/error/success/info/dry_run/heading through it so output degrades via
#   errors="replace" instead of raising UnicodeEncodeError when sys.stdout's
#   encoding cannot represent a character (e.g. a Windows cp1252 console and
#   the '✓' glyph printed by success()). sys.stdout is resolved at call time,
#   not import time, so no import-time side effects are introduced and
#   redirection/monkeypatching still work; UTF-8 consoles are unaffected.
#   (#TICKETLESS reason=console-encoding-crash-quickfix)
# ====================================================================
