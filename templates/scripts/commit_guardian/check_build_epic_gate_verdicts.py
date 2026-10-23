"""
MODULE: check_build_epic_gate_verdicts.py
GOAL: Pre-commit hook -- on /build-epic, refuse to commit a ticket unless the red-baseline reader's and the
    wrong-version runner's own verdicts are on record for it, readable, passing and (wrong-version) fresh.
BUSINESS CONTEXT: TQ-500g-1-viii. The gates were prompt-only on /build-epic, so a supervisor that skipped
    one still committed. Only the commit itself runs code on every /build-epic path, and a marker that
    build-epic.js opens before it dispatches each ticket scopes the check to that route.
ARCHITECTURE: Reads records only (``<git-dir>/leafcutter/gate-verdicts/<ticket-key>/``, written by the gate
    CLIs through gate_verdict_records.py), never ticket comments or the supervisor's summary. With no open
    marker it costs one git call and one directory listing and exits 0. With a marker open, the commit must
    stage the marked ticket file, and that ticket needs both records. Staleness (wrong-version only): every
    staged code path (extension in file_size.checked_extensions, minus the digest exclusions) must appear in
    the record's ``paths`` with the sha256 of its STAGED content. An error before any marker is found exits
    0 with a warning; once a marker is found, any error blocks. The shared record module is imported only then,
    from the deployed layout (``../build_orchestration``) or the source tree (``<repo>/scripts/build_orchestration``).

# DECISION HISTORY
# - 2026-10-22 12:00 [python-coder/TQ-500g-1-viii]: Initial implementation.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True  # a hook must leave the working copy as it found it

_HERE = Path(__file__).resolve().parent
_GIT_TIMEOUT_SECONDS = 60
_ERRORS = (OSError, ValueError, KeyError, TypeError, ImportError, subprocess.SubprocessError)


def _git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run one git command in the current directory, capturing its output as text.

    Args:
        *args: The git arguments.

    Returns:
        The completed process (the caller checks ``returncode``).
    """
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=_GIT_TIMEOUT_SECONDS, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[check-build-epic-gate-verdicts] git {args[0]} could not run: {exc}", file=sys.stderr)
        raise


def _open_markers(root: Path) -> dict[str, Path]:
    """List the ticket folders under *root* that hold an ``open.json``.

    Args:
        root: ``<git-dir>/leafcutter/gate-verdicts`` (may not exist).

    Returns:
        ``{ticket key: folder}``.
    """
    if not root.is_dir():
        return {}
    with os.scandir(root) as entries:
        return {e.name: Path(e.path) for e in entries if e.is_dir() and (Path(e.path) / "open.json").is_file()}


def _staged() -> dict[str, str]:
    """Return ``{path: status letter}`` of the index against HEAD (no rename detection).

    Raises:
        subprocess.SubprocessError: git could not list the staged paths.
    """
    proc = _git("diff", "--cached", "--name-status", "-z", "--no-renames")
    if proc.returncode != 0:
        msg = f"git diff --cached failed: {proc.stderr.strip()}"
        raise subprocess.SubprocessError(msg)
    parts = proc.stdout.split("\0")
    return {parts[i + 1]: parts[i] for i in range(0, len(parts) - 1, 2) if parts[i]}


def _staged_sha(path: str, status: str) -> str | None:
    """Return the sha256 of *path*'s staged content, or None when the commit deletes it."""
    if status == "D":
        return None
    try:
        proc = subprocess.run(["git", "show", f":{path}"], capture_output=True, timeout=_GIT_TIMEOUT_SECONDS, check=False)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[check-build-epic-gate-verdicts] git show could not run: {exc}", file=sys.stderr)
        raise
    if proc.returncode != 0:
        msg = f"git show :{path} failed"
        raise subprocess.SubprocessError(msg)
    return hashlib.sha256(proc.stdout).hexdigest()


def _same_up_to_line_endings(path: str, recorded: str | None, staged_sha: str | None) -> bool:
    """Say whether the working file is the recorded content and only line endings differ from the index.

    With ``core.autocrlf`` the index holds LF where the working file (the bytes the record hashed) holds CRLF.
    """
    if recorded is None or staged_sha is None or not Path(path).is_file():
        return False
    data = Path(path).read_bytes()
    return hashlib.sha256(data).hexdigest() == recorded and hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest() == staged_sha


def _survivor_names(verdict: dict) -> str:
    """Name the wrong versions that survived (from ``survivors`` and the blocking rows)."""
    rows = [r for r in verdict.get("results") or [] if isinstance(r, dict) and (r.get("blocking") is True or r.get("result") == "survived")]
    names = [str(s.get("wrong_version")) for s in verdict.get("survivors") or [] if isinstance(s, dict)]
    names += [str(r.get("wrong_version")) for r in rows]
    return ", ".join(dict.fromkeys(n for n in names if n and n != "None"))


def _verdict_problem(label: str, verdict: dict, *, rows_matter: bool, owed: bool) -> str | None:
    """Judge one gate verdict as the gate left it.

    Args:
        label: ``red-baseline`` or ``wrong-version``.
        verdict: The verdict stored in the record.
        rows_matter: True for the wrong-version verdict, whose rows must agree with ``gate_passed``.
        owed: True when the ticket has a ``source_ac``, so a not-applicable verdict is never a pass.

    Returns:
        The reason to block, or None. ``applicable`` false with ``gate_passed`` true passes.
    """
    survivors = _survivor_names(verdict) if rows_matter else ""
    if verdict.get("gate_passed") is not True:
        why = survivors or str(verdict.get("reason") or verdict.get("outcome") or "no reason given")
        return f"{label} verdict did not pass: {why}"
    if verdict.get("applicable") is False:
        return f"{label} verdict says not applicable but the ticket has a source_ac" if owed else None
    if survivors:
        return f"{label} verdict says passed but its rows show a surviving wrong version: {survivors}"
    return None


def _stale_paths(code: list[str], staged: dict[str, str], recorded: dict) -> list[str]:
    """Return the staged code paths whose staged sha256 differs from (or is absent in) the record."""
    stale = []
    for path in code:
        sha = _staged_sha(path, staged[path])
        if path not in recorded or (recorded[path] != sha and not _same_up_to_line_endings(path, recorded[path], sha)):
            stale.append(path)
    return stale


def _ticket_problems(key: str, folder: Path, code: list[str], staged: dict[str, str], source_ac: object) -> list[str]:
    """Return every reason the marked ticket *key* may not be committed (empty when it may).

    Args:
        key: The ticket key.
        folder: Its record folder.
        code: The staged code paths.
        staged: ``{path: status}`` of the index.
        source_ac: The marker's snapshot of the ticket's ``source_ac`` (anything but a list of strings is unreadable).
    """
    import gate_verdict_records as gvr

    if not isinstance(source_ac, list) or not all(isinstance(i, str) for i in source_ac):
        return [f"{key}: the marker has no readable source_ac, so the verdicts cannot be tied to the ticket"]
    owed = bool(source_ac)
    problems: list[str] = []
    records: dict[str, dict | None] = {}
    for gate, label in (("red_baseline", "red-baseline"), ("wrong_version", "wrong-version")):
        rec, err = gvr.read_record(folder, gate)
        records[gate] = rec
        if rec is None:
            problems.append(f"{key}: {label} verdict is {err}")
            continue
        reason = _verdict_problem(label, rec["verdict"], rows_matter=gate == "wrong_version", owed=owed)
        if owed and set(rec["ids"]) != set(source_ac):
            reason = f"{label} record is for {sorted(rec['ids'])} but the ticket's source_ac is {sorted(source_ac)}"
        if reason:
            problems.append(f"{key}: {reason}")
    wv = records["wrong_version"]
    if wv is not None and not problems and (owed or wv["verdict"].get("applicable") is not False):
        problems += [f"{key}: wrong-version verdict is out of date for the code as it now stands ({p})"
                     for p in _stale_paths(code, staged, wv["paths"])]
    return problems


def _judge(markers: dict[str, Path]) -> list[str]:
    """Return the reasons to block this commit given the open *markers* (empty list: let it through).

    Raises:
        ImportError, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError: anything that
            keeps the check from completing; the caller blocks on it.
    """
    for candidate in (_HERE.parent / "build_orchestration", _HERE.parent.parent.parent / "scripts" / "build_orchestration"):
        if candidate.is_dir() and str(candidate) not in sys.path:
            sys.path.append(str(candidate))
    import gate_verdict_records as gvr
    from config import BUILD_EPIC_GATE_VERDICTS_SEVERITY, CHECKED_EXTENSIONS

    staged = _staged()
    code = [p for p in staged if p.endswith(tuple(CHECKED_EXTENSIONS)) and not gvr.is_excluded(p)]
    wanted = {}
    for key, folder in markers.items():
        marker = json.loads((folder / "open.json").read_text(encoding="utf-8"))
        if gvr.rel_posix(str(marker["ticket_path"])) in staged:
            wanted[key] = (folder, marker.get("source_ac"))
    if not wanted:
        if not code:
            return []
        return [f"code is staged but no ticket file of an open marker is ({', '.join(markers)}); stage the ticket file "
                "being committed. Markers are closed by the drive or by a human, never by the committing agent."]
    problems = [p for key, (folder, ac) in wanted.items() for p in _ticket_problems(key, folder, code, staged, ac)]
    return problems if BUILD_EPIC_GATE_VERDICTS_SEVERITY == "block" else []


def main() -> int:
    """Pre-commit hook entry point.

    Returns:
        0 = let the commit through, 1 = blocked (a deliberate refusal, or an error after a marker was found).
    """
    try:
        proc = _git("rev-parse", "--absolute-git-dir")
        if proc.returncode != 0:
            print("[check-build-epic-gate-verdicts] not a git repository, skipped", file=sys.stderr)
            return 0
        markers = _open_markers(Path(proc.stdout.strip()) / "leafcutter" / "gate-verdicts")
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"[check-build-epic-gate-verdicts] could not look for a marker, skipped: {exc}", file=sys.stderr)
        return 0
    if not markers:
        return 0
    try:
        problems = _judge(markers)
    except _ERRORS as exc:
        print(f"BLOCKED: the gate-verdict check could not complete ({type(exc).__name__}: {exc}); markers open: {', '.join(markers)}")
        return 1
    for problem in problems:
        print(f"BLOCKED: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
