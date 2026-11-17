"""
MODULE: _usable_stream_parity_core
GOAL: The shared vocabulary of the usable-stream parity check (AC INF-500d-4-ix): the
    errors it reports, the ``Verdict`` every implementation answers with, the three
    ways it runs something (a command, bash, a fresh Python probe) and the one way a
    write is judged (``write_verdict``).
BUSINESS CONTEXT: ``_usable_stream_parity_rows`` (the declaration table) and
    ``_usable_stream_parity_copies`` (the copies) both need these; keeping
    them here lets each stay under the file-size limit without a circular import.
    A copy that writes is usable only when it exits 0 AND the declared stream gained
    exactly one line AND nothing else in the row's tree changed.
ARCHITECTURE: Every run goes through ``run_command`` / ``run_bash``, which turn an OS or
    subprocess failure into a ``CopyRunError`` naming what was being run, so a copy that
    cannot be run is reported by the check instead of vanishing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

from unit_tests.feedback import _inf_500d_4_helpers as h


class ParityError(Exception):
    """Base class of every failure this check reports instead of hiding; reads ``<subject>: <reason>``."""

    def __init__(self, subject: str, reason: str) -> None:
        super().__init__(f"{subject}: {reason}")


class CopyNotFoundError(ParityError):
    """A copy's file, snippet or command is absent from the layout (the message names the copy)."""


class CopyRunError(ParityError):
    """A copy was found but could not be run or its answer could not be read."""


@dataclass(frozen=True)
class Verdict:
    """One implementation's answer for one row: usable or not, where it would write, why not.

    ``stray`` is set when running the implementation changed something other than "the declared
    stream gained one line" (a second line, another file): the report fails on it whatever the row.
    """

    usable: bool
    location: Path | None = None
    detail: str = ""
    stray: bool = False


def run_command(cmd: list[str], cwd: Path, label: str, *, python_on_path: bool = False) -> subprocess.CompletedProcess[str]:
    """Run *cmd* in *cwd* (TMPDIR confined to the system temp dir); a failure to run it names *label*.

    ``python_on_path`` puts the running interpreter's directory first on PATH, as a deployed shell step expects.
    """
    env = h.make_env(Path(tempfile.gettempdir()))
    if python_on_path:
        env["PATH"] = os.path.dirname(sys.executable) + os.pathsep + env.get("PATH", "")
    try:
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(cwd),
                              timeout=h.RUN_TIMEOUT, check=False, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        reason = f"could not run {cmd[0]}: {exc}"
        raise CopyRunError(label, reason) from exc


def run_bash(command: str, cwd: Path, label: str) -> subprocess.CompletedProcess[str]:
    """Run *command* with ``bash -c`` from *cwd*, exactly as the deployed text states it."""
    return run_command(["/bin/bash", "-c", command], cwd, label, python_on_path=True)


def python_verdict(args: list[str], cwd: Path, label: str) -> Verdict:
    """Run ``python -I -S -B -c <probe> args`` (stdlib only, so no site import); read its JSON line."""
    proc = run_command([sys.executable, "-I", "-S", "-B", "-c", *args], cwd, label)
    if proc.returncode != 0:
        reason = f"probe exited {proc.returncode}: {proc.stderr.strip()[-300:]}"
        raise CopyRunError(label, reason)
    try:
        data = json.loads(proc.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError) as exc:
        reason = f"probe printed no readable verdict: {proc.stdout!r}"
        raise CopyRunError(label, reason) from exc
    location = data.get("location")
    return Verdict(location is not None, Path(location) if location else None, data.get("detail", ""))


def file_digests(tree: Path) -> dict[str, str]:
    """Every regular file below *tree* mapped to its content digest (a new or appended file shows)."""
    return {str(path): h.sha256(path) for path in tree.rglob("*")
            if path.is_file() and not path.is_symlink()}


TreeState = tuple[dict[str, str], int]


def tree_state(tree: Path, stream: Path | None) -> TreeState:
    """The digests of every file below *tree* plus how many lines the declared *stream* holds now."""
    lines = len(stream.read_bytes().splitlines()) if stream is not None and stream.is_file() else 0
    return file_digests(tree), lines


def write_verdict(before: TreeState, after: TreeState, stream: Path | None, returncode: int, stderr: str) -> Verdict:
    """Judge a run by what it did: usable iff it exited 0, the declared *stream* gained exactly one line,
    and no other file in the tree changed. Any other change is ``stray`` and never usable."""
    (digests_before, lines_before), (digests_after, lines_after) = before, after
    changed = sorted(p for p in digests_before.keys() | digests_after.keys()
                     if digests_before.get(p) != digests_after.get(p))
    gained = lines_after - lines_before
    if returncode == 0 and changed == [str(stream)] and gained == 1:
        return Verdict(True, stream)
    if not changed:
        why = stderr.strip()[:200] if returncode != 0 else "exited 0 but wrote nothing"
        return Verdict(False, None, why)
    names = ", ".join(Path(p).name for p in changed[:4])
    detail = (f"exit {returncode}; changed {len(changed)} file(s) ({names}); "
              f"the declared stream gained {gained} line(s), expected exactly 1 and nothing else")
    return Verdict(False, None, detail, stray=True)


# DECISION HISTORY
# ================================================================================
# - 2026-10-14 11:00 [python-coder]: Created the shared errors, Verdict and run helpers of the parity check. (#TICKET-INF-500d-4-ix)
# - 2026-10-14 16:00 [python-coder]: Added write_verdict (exit 0 + exactly one line in the declared stream + nothing else changed), Verdict.stray, and a local bash runner. (#TICKET-INF-500d-4-ix)
