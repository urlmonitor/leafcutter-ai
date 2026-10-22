"""
MODULE: scripts/build_orchestration/_fcs_close.py
GOAL: Close exactly the records of a persisted closable set through the checking mechanisms, and
    prove nothing outside the set changed while doing so.
BUSINESS CONTEXT: BO-400e-3-iii, -iv, -v. A ticket is closed only through set_ticket_status.py (no
    --force, ADR-047), an acceptance criterion only through mark_ac_done.py and only when the ticket
    that delivered it was closed in this run. Every other ticket and criterion must read exactly as
    it did before, and a leak is reported by the run itself rather than assumed away.
ARCHITECTURE: Stdlib. The only input is the set file derive persisted under the worktree's git dir;
    its digest is recomputed before anything is written, so an edited file is refused. Each record's
    status and content hash is captured before and after the closers run; any difference outside the
    set is reported (outside_set_changes for a status change, out_of_set_paths for any change) and
    empties commit_paths so no closure commit is made over a leak.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path

from _fcs_derive import git
from _fcs_records import (
    AC_ROOT, TICKET_ROOT, ac_work_status_of, read_ticket, set_digest, ticket_status_of,
)

logger = logging.getLogger(__name__)

Snapshot = dict[str, tuple[str | None, str]]


class SetRefused(Exception):  # noqa: N818 - a refusal, not an error of the program
    """The persisted set cannot be trusted; nothing is closed."""


def load_set(worktree: Path, set_file: str) -> dict:
    """Read the persisted set; refuse a file outside the git dir, unreadable, or with a stale digest."""
    proc = git(worktree, "rev-parse", "--absolute-git-dir")
    git_dir = Path(proc.stdout.strip()).resolve()
    target = Path(set_file).resolve()
    if proc.returncode != 0 or git_dir not in target.parents:
        raise SetRefused("set_file_outside_git_dir")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        logger.warning("cannot read set file %s: %s", target, exc)
        raise SetRefused("set_file_unreadable") from exc
    records = data.get("records") if isinstance(data, dict) else None
    if not isinstance(records, list) or data.get("set_digest") != set_digest(records):
        raise SetRefused("set_digest_mismatch")
    return data


def _digest_and_status(path: Path, is_ticket: bool) -> tuple[str | None, str]:
    """(status, content hash) of one record file; an unreadable file reads (None, 'unreadable')."""
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("cannot snapshot %s: %s", path, exc)
        return None, "unreadable"
    status = ticket_status_of(text) if is_ticket else ac_work_status_of(text)
    return status, hashlib.sha1(raw).hexdigest()  # noqa: S324 - a change detector, not a secret


def snapshot(worktree: Path) -> Snapshot:
    """rel path -> (status, content hash) for every ticket and acceptance-criterion file."""
    out: Snapshot = {}
    for root, pattern, is_ticket in ((TICKET_ROOT, "*.md", True), (AC_ROOT, "*.yaml", False)):
        base = worktree / root
        if not base.is_dir():
            continue
        for path in base.rglob(pattern):
            if path.is_file():
                out[path.relative_to(worktree).as_posix()] = _digest_and_status(path, is_ticket)
    return out


def _run(argv: list[str], cwd: Path) -> tuple[int, str]:
    """Run one closer; (exit code, combined output). A closer that cannot run reads as exit -1."""
    try:
        proc = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, check=False, timeout=300)
    except (OSError, subprocess.SubprocessError) as exc:
        logger.warning("closer %s could not run: %s", argv[1:2], exc)
        return -1, str(exc)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def _close_ticket(worktree: Path, scripts: Path, rel: str) -> tuple[bool, str | None]:
    """Close one ticket through set_ticket_status.py; (closed, refusal reason)."""
    argv = [sys.executable, str(scripts / "set_ticket_status.py"), "--ticket", str(worktree / rel),
            "--status", "done", "--no-stage"]
    code, output = _run(argv, worktree)
    return code == 0, None if code == 0 else (output or f"exit {code}")


def _close_ac(worktree: Path, scripts: Path, ac_id: str) -> tuple[bool, str | None]:
    """Close one criterion through mark_ac_done.py; (closed, refusal reason)."""
    argv = [sys.executable, str(scripts / "ac_store" / "mark_ac_done.py"), "--ac", ac_id,
            "--ac-root", str(worktree / AC_ROOT)]
    code, output = _run(argv, worktree)
    return code == 0, None if code == 0 else (output or f"exit {code}")


def _delivering_tickets(worktree: Path, ticket_records: list[dict]) -> dict[str, str]:
    """source_ac id -> path of the in-set ticket that names it."""
    mapping: dict[str, str] = {}
    for record in ticket_records:
        data = read_ticket(worktree / record["path"])
        source = data.get("source_ac") if data else None
        if isinstance(source, str) and source:
            mapping[source] = record["path"]
    return mapping


def _outcomes(worktree: Path, scripts: Path, records: list[dict]) -> dict[tuple[str, str], tuple[str, str | None]]:
    """(kind, path) -> (result, reason): tickets close first, then only the criteria they delivered."""
    tickets = [r for r in records if r["kind"] == "ticket"]
    outcomes: dict[tuple[str, str], tuple[str, str | None]] = {}
    for record in tickets:
        closed, reason = _close_ticket(worktree, scripts, record["path"])
        outcomes[("ticket", record["path"])] = ("closed" if closed else "refused", reason)
    delivered_by = _delivering_tickets(worktree, tickets)
    for record in (r for r in records if r["kind"] == "ac"):
        ticket = delivered_by.get(record["id"])
        if ticket is None or outcomes[("ticket", ticket)][0] != "closed":
            outcomes[("ac", record["path"])] = ("left_open", "ticket not closed")
            continue
        closed, reason = _close_ac(worktree, scripts, record["id"])
        outcomes[("ac", record["path"])] = ("closed" if closed else "refused", reason)
    return outcomes


def _results(records: list[dict], outcomes: dict, before: Snapshot, after: Snapshot) -> list[dict]:
    """One result entry per record with its before/after status."""
    entries = []
    for record in records:
        result, reason = outcomes[(record["kind"], record["path"])]
        entries.append({
            "kind": record["kind"], "id": record["id"], "path": record["path"],
            "before": before.get(record["path"], (None, ""))[0],
            "after": after.get(record["path"], (None, ""))[0],
            "result": result, "reason": reason,
        })
    return entries


def _outside(before: Snapshot, after: Snapshot, in_set: set[str]) -> tuple[list[dict], list[str]]:
    """(status changes, every changed path) among the files outside the set."""
    changes: list[dict] = []
    paths: list[str] = []
    for path in sorted((set(before) | set(after)) - in_set):
        old, new = before.get(path, (None, "")), after.get(path, (None, ""))
        if old == new:
            continue
        paths.append(path)
        if old[0] != new[0]:
            changes.append({"path": path, "id": path.rsplit("/", 1)[-1].rsplit(".", 1)[0],
                            "before": old[0], "after": new[0]})
    return changes, paths


def close(worktree: Path, set_file: str, scripts_root: Path) -> dict:
    """Close the persisted set and report results, out-of-set changes and the commit path list."""
    data = load_set(worktree, set_file)
    records = data["records"]
    before = snapshot(worktree)
    outcomes = _outcomes(worktree, scripts_root, records)
    after = snapshot(worktree)
    changes, stray = _outside(before, after, {r["path"] for r in records})
    commit_paths = [] if stray else sorted(
        r["path"] for r in records
        if outcomes[(r["kind"], r["path"])][0] == "closed" and before.get(r["path"]) != after.get(r["path"])
    )
    return {
        "set_digest": data["set_digest"], "results": _results(records, outcomes, before, after),
        "outside_set_changes": changes, "commit_paths": commit_paths, "out_of_set_paths": stray,
    }


# DECISION HISTORY
# ================================================================================
# - 2026-10-16 12:00 [python-coder]: Created closer that reads only the digest-checked persisted set and reports leaks. (#BO-400e/3-iii)
