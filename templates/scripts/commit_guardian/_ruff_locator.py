"""
MODULE: _ruff_locator
GOAL: Answer "is ruff installed, and which version?" ONCE for the lint-gate
    family (check_lint_gate.py in every mode, and through its CLI
    run_ci_local.py and BO-570-3), using GE-108e's discovery rule.
BUSINESS CONTEXT: BP-1300e-1-iii. A commit-time check that cannot find its
    linter must refuse and say so; it must never present itself as passed.
    GE-108e fixed the discovery rule for the edit-time hook: the MODULE form
    (`python -m ruff`) first, the bare executable second, because a machine
    where ruff is importable but exposes no console script was wrongly
    reported "not installed" by an executable-only lookup.
ARCHITECTURE: Stdlib only. The edit-time hook
    (templates/hooks/check_exception_handling_hook.py) is deployed to
    .claude/hooks/ and is self-contained by its own header, so it cannot
    import this module and this module must not import from it; "one answer"
    is held by a behavioural cross-check test instead. Module absence is
    detected by a non-zero exit WITH "No module named ruff" on stderr -- never
    by a non-zero exit alone, which any real failure also produces. The
    version is probed once with `<prefix> --version` and returned with the
    prefix so no caller probes again. The three typed results are the only
    ways locate() answers; nothing here raises for an absent or broken ruff.

DECISION HISTORY
- 2026-10-12 [python-coder/BP-1300e-1-iii]: Created. A third result,
    FailedToStart, carries ruff's own stderr for a ruff that is present but
    exits before inspecting anything (and for an unparseable --version line).
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

MODULE_MISSING_MARKER = "No module named ruff"
_VERSION_LINE = re.compile(r"^ruff\s+(\S+)")
PROBE_TIMEOUT = 30


@dataclass(frozen=True)
class Located:
    """ruff was found and answered `--version`."""

    prefix: tuple[str, ...]
    version: str
    form: str


@dataclass(frozen=True)
class NotInstalled:
    """Neither the module form nor the executable form exists."""

    tried: tuple[str, ...]


@dataclass(frozen=True)
class FailedToStart:
    """ruff is present but exits before inspecting any file."""

    prefix: tuple[str, ...]
    stderr: str


def parse_version(text: str) -> str | None:
    """Return the version token of a ``ruff <version>`` line, else None (pure)."""
    match = _VERSION_LINE.match(text.strip())
    return match.group(1) if match else None


def _probe(prefix: list[str]) -> tuple[int, str, str] | None:
    """Run ``<prefix> --version``; (returncode, stdout, stderr) or None if unlaunchable."""
    try:
        done = subprocess.run(
            [*prefix, "--version"], capture_output=True, text=True, check=False, timeout=PROBE_TIMEOUT
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("cannot probe %s: %s", prefix, exc)
        return None
    return done.returncode, done.stdout, done.stderr


def _answer(prefix: list[str], form: str, probe: tuple[int, str, str] | None) -> Located | FailedToStart:
    """Turn one probe into Located or FailedToStart (the probe did start or fail)."""
    if probe is None:
        return FailedToStart(tuple(prefix), f"could not launch {' '.join(prefix)}")
    code, out, err = probe
    version = parse_version(out) if code == 0 else None
    if version is None:
        detail = err.strip() or out.strip() or f"exit status {code} and no version line"
        return FailedToStart(tuple(prefix), detail)
    return Located(tuple(prefix), version, form)


def locate() -> Located | NotInstalled | FailedToStart:
    """Find ruff: module form first, executable as fallback (GE-108e).

    Returns:
        Located (argv prefix + version), NotInstalled (both forms tried), or
        FailedToStart (present but cannot run).
    """
    module_prefix = [sys.executable, "-m", "ruff"]
    probe = _probe(module_prefix)
    if probe is None or probe[0] == 0 or MODULE_MISSING_MARKER not in probe[2]:
        return _answer(module_prefix, "module", probe)
    exe = shutil.which("ruff")
    if exe is None:
        return NotInstalled((f"{sys.executable} -m ruff", "ruff on PATH"))
    return _answer([exe], "executable", _probe([exe]))
