"""
MODULE: scripts/build_orchestration/_fcs_derive.py
GOAL: Work out which tickets and source acceptance criteria a finishing branch may close: only
    what the branch was built to deliver AND itself changed since it left main.
BUSINESS CONTEXT: BO-400e-3-ii, -viii. Step 3.5 of finalize-feature used to close every ticket a
    two-dot `git diff origin/main HEAD` listed, so records main changed after the branch point (or
    a ticket edited in passing) were closed on the branch's account. The set is now computed here
    from the branch's own history, fixed before anything is written.
ARCHITECTURE: Stdlib plus git subprocesses. Measures from the merge base of HEAD and the base ref
    (never a two-dot comparison). A path counts only when it differs between the merge base and
    HEAD AND one of the branch's own first-parent, non-merge commits touched it, so content that
    arrived by merging main never qualifies. The single-ticket branch's built-for ticket is read
    from git config branch.<branch>.leafcutterTicket (BO-400e-3-ix) and from nothing else. The set
    and its digest are persisted under the worktree's git dir for the closer to read.
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from _fcs_records import (
    find_ac_record, is_ac_path, is_ticket_path, listing_text, read_ticket, set_digest,
    ticket_record_status,
)

logger = logging.getLogger(__name__)

RECORD_KEY = "leafcutterTicket"
SET_FILE_NAME = "leafcutter_closable_set.json"


class GitDirError(OSError):
    """The worktree's git dir could not be located, so the set cannot be persisted."""

    def __init__(self, worktree: Path, detail: str) -> None:
        super().__init__(f"cannot locate the git dir of {worktree}: {detail}")


class GitCallFailed(RuntimeError):
    """A git call the derivation depends on exited non-zero; an empty answer must not read as 'no changes'."""

    def __init__(self, command: str, returncode: int, stderr: str) -> None:
        super().__init__(f"git {command} exited {returncode}: {stderr}")


class AmbiguousRecord(ValueError):
    """The branch carries more than one built-for-ticket record, so none can be trusted."""

    def __init__(self, branch: str, values: list[str]) -> None:
        super().__init__(f"branch {branch} has {len(values)} recorded tickets: {', '.join(values)}")


def git(worktree: Path, *args: str) -> subprocess.CompletedProcess:
    """Run `git -C <worktree> ...`; a missing git raises OSError, a git failure is a return code."""
    try:
        return subprocess.run(
            ["git", "-C", str(worktree), *args], capture_output=True, text=True, check=False, timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("git %s could not run in %s: %s", " ".join(args[:2]), worktree, exc)
        raise


def _git_stdout(worktree: Path, *args: str) -> str:
    """stdout of a git call whose failure must not be mistaken for an empty result (BO-400e-3-viii)."""
    proc = git(worktree, *args)
    if proc.returncode != 0:
        raise GitCallFailed(" ".join(args[:2]), proc.returncode, proc.stderr.strip())
    return proc.stdout


def merge_base(worktree: Path, base_ref: str) -> str | None:
    """The merge base of *base_ref* and HEAD, None when git cannot name one."""
    proc = git(worktree, "merge-base", base_ref, "HEAD")
    sha = proc.stdout.strip()
    if proc.returncode != 0 or not sha:
        logger.warning("merge-base %s HEAD failed (rc=%s): %s", base_ref, proc.returncode, proc.stderr.strip())
        return None
    return sha


def _diff_since(worktree: Path, base: str) -> tuple[set[str], dict[str, str]]:
    """(paths present at HEAD that differ from *base*, rename map old -> new) from `diff base HEAD`."""
    tokens = _git_stdout(worktree, "diff", "--name-status", "-M", "-z", base, "HEAD").split("\0")
    present: set[str] = set()
    renames: dict[str, str] = {}
    i = 0
    while i < len(tokens) and tokens[i]:
        code = tokens[i][0]
        if code in "RC" and i + 2 < len(tokens):
            old, new = tokens[i + 1], tokens[i + 2]
            if code == "R":
                renames[old] = new
            present.add(new)
            i += 3
            continue
        if code != "D" and i + 1 < len(tokens):
            present.add(tokens[i + 1])
        i += 2
    return present, renames


def _own_commit_paths(worktree: Path, base: str) -> set[str]:
    """Paths touched by the branch's own first-parent, non-merge commits since *base*."""
    out = _git_stdout(worktree, "log", "--first-parent", "--no-merges", "-M", "--name-only", "-z", "--format=", f"{base}..HEAD")
    return {token for token in out.split("\0") if token}


def branch_changes(worktree: Path, base: str) -> tuple[list[str], dict[str, str]]:
    """(sorted paths the branch itself changed since *base*, rename map old -> new)."""
    present, renames = _diff_since(worktree, base)
    own = _own_commit_paths(worktree, base)
    return sorted(present & own), renames


def recorded_ticket(worktree: Path, branch: str) -> str | None:
    """The ticket path recorded against *branch* at setup (BO-400e-3-ix), None when absent.

    Reads every value (``--get-all``, as setup does); more than one is ambiguous and raises
    AmbiguousRecord rather than picking one.
    """
    proc = git(worktree, "config", "--get-all", f"branch.{branch}.{RECORD_KEY}")
    values = [line.strip() for line in proc.stdout.splitlines() if line.strip()] if proc.returncode == 0 else []
    if len(values) > 1:
        raise AmbiguousRecord(branch, values)
    return values[0] if values else None


def _in_epic_folder(rel: str, branch: str) -> bool:
    """True when *rel* is a ticket inside tickets/<lane>/epics/<branch>/."""
    return rel.startswith("tickets/") and f"/epics/{branch}/" in "/" + rel


def _ticket_record(worktree: Path, rel: str) -> tuple[dict, object] | None:
    """(record, source_ac) for the ticket at *rel*, None when it cannot be read."""
    data = read_ticket(worktree / rel)
    if data is None:
        return None
    record = {"kind": "ticket", "id": rel.rsplit("/", 1)[-1], "path": rel, "status": ticket_record_status(data)}
    return record, data.get("source_ac")


def _select(worktree: Path, tickets: list[str]) -> tuple[list[dict], list[str]]:
    """(records to close, paths already done) for the in-bound changed *tickets*."""
    ticket_records: list[dict] = []
    ac_records: dict[str, dict] = {}
    done: list[str] = []
    for rel in sorted(tickets):
        loaded = _ticket_record(worktree, rel)
        if loaded is None:
            continue
        record, source_ac = loaded
        if record["status"] == "done":
            done.append(rel)
            continue
        ticket_records.append(record)
        found = find_ac_record(worktree, source_ac) if isinstance(source_ac, str) and source_ac else None
        if found is None:
            continue
        path, status = found
        if status == "done":
            done.append(path)
        else:
            ac_id = str(source_ac)  # a str here: found is None unless source_ac was one
            ac_records[ac_id] = {"kind": "ac", "id": ac_id, "path": path, "status": status}
    return ticket_records + [ac_records[key] for key in sorted(ac_records)], sorted(done)


def _skeleton(branch: str, base_ref: str) -> dict:
    """The reply shape every outcome shares."""
    return {
        "outcome": "undeterminable", "reason_code": None, "branch": branch,
        "branch_kind": "epic" if branch.startswith("EPIC-") else "single_ticket",
        "base_ref": base_ref, "merge_base": None, "built_for_ticket": None, "records": [],
        "already_done": [], "changed_not_closable": [], "set_digest": set_digest([]),
        "set_file": None, "listing_text": listing_text([]),
    }


def _persist(worktree: Path, reply: dict) -> None:
    """Write the records and digest under the worktree's git dir and name the file in *reply*."""
    proc = git(worktree, "rev-parse", "--absolute-git-dir")
    git_dir = proc.stdout.strip()
    if proc.returncode != 0 or not git_dir:
        raise GitDirError(worktree, proc.stderr.strip())
    target = Path(git_dir) / SET_FILE_NAME
    payload = {"records": reply["records"], "set_digest": reply["set_digest"]}
    target.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    reply["set_file"] = str(target)


def _settle(worktree: Path, reply: dict, outcome: str, reason: str | None, records: list[dict] | None = None) -> dict:
    """Stamp the outcome, records, digest and listing; persist the set unless undeterminable."""
    reply["outcome"], reply["reason_code"] = outcome, reason
    reply["records"] = records or []
    reply["set_digest"] = set_digest(reply["records"])
    reply["listing_text"] = listing_text(reply["records"])
    if outcome != "undeterminable":
        _persist(worktree, reply)
    return reply


def _undetermined(worktree: Path, reply: dict, reason: str, detail: str) -> dict:
    """Settle *reply* as undeterminable with *reason*, keeping *detail* for the halt message."""
    reply["detail"] = detail
    return _settle(worktree, reply, "undeterminable", reason)


def _candidate_paths(worktree: Path, bound: list[str]) -> list[str]:
    """The in-bound tickets plus the source AC records they would close."""
    paths = list(bound)
    for rel in bound:
        data = read_ticket(worktree / rel)
        source_ac = data.get("source_ac") if data else None
        found = find_ac_record(worktree, source_ac) if isinstance(source_ac, str) and source_ac else None
        if found is not None:
            paths.append(found[0])
    return sorted(set(paths))


def _uncommitted_changes(worktree: Path, paths: list[str]) -> list[str]:
    """Tracked *paths* whose working-tree content differs from HEAD (a failed git call raises)."""
    if not paths:
        return []
    out = _git_stdout(worktree, "diff", "--name-only", "-z", "HEAD", "--", *paths)
    return sorted(token for token in out.split("\0") if token)


def _evaluate(worktree: Path, reply: dict, bound: list[str], changed: list[str]) -> dict:
    """Pick the closable records among the in-bound changed tickets and settle the reply.

    Status is read from the working tree while membership comes from committed history, so a
    candidate record with uncommitted edits (a closure left behind by an earlier halted run)
    is undeterminable, never 'already done'.
    """
    try:
        dirty = _uncommitted_changes(worktree, _candidate_paths(worktree, bound))
    except GitCallFailed as exc:
        logger.warning("uncommitted-record check failed: %s", exc)
        return _undetermined(worktree, reply, "diff_failed", str(exc))
    if dirty:
        return _undetermined(worktree, reply, "uncommitted_record_changes", ", ".join(dirty))
    records, done = _select(worktree, bound)
    in_set = {record["path"] for record in records}
    reply["already_done"] = done
    reply["changed_not_closable"] = [p for p in changed if p not in in_set and p not in done]
    if records:
        return _settle(worktree, reply, "closable", None, records)
    single = reply["branch_kind"] == "single_ticket"
    reason = ("built_for_already_done" if single else "all_already_done") if done else "no_records_changed"
    return _settle(worktree, reply, "nothing_to_close", reason)


def derive(worktree: Path, branch: str, base_ref: str) -> dict:
    """Work out the closable set for *branch*; evaluation order is fixed (BO-400e-3-ii).

    Merge base first (unknown is undeterminable; so is a git failure while listing the branch's
    changes, reason diff_failed with git's stderr in ``detail``), then 'the branch changed nothing' (nothing to
    close, no built-for ticket needed), then, for a single-ticket branch only, the built-for
    ticket (absent is undeterminable). Nothing here falls back to a guess.
    """
    reply = _skeleton(branch, base_ref)
    base = merge_base(worktree, base_ref)
    if base is None:
        return _settle(worktree, reply, "undeterminable", "merge_base_unknown")
    reply["merge_base"] = base
    try:
        changed_paths, renames = branch_changes(worktree, base)
    except GitCallFailed as exc:
        logger.warning("branch change detection failed: %s", exc)
        return _undetermined(worktree, reply, "diff_failed", str(exc))
    tickets = [p for p in changed_paths if is_ticket_path(p)]
    changed = sorted(tickets + [p for p in changed_paths if is_ac_path(p)])
    reply["changed_not_closable"] = changed
    if not changed:
        return _settle(worktree, reply, "nothing_to_close", "no_records_changed")
    if reply["branch_kind"] == "epic":
        return _evaluate(worktree, reply, [p for p in tickets if _in_epic_folder(p, branch)], changed)
    try:
        built = recorded_ticket(worktree, branch)
    except AmbiguousRecord as exc:
        return _undetermined(worktree, reply, "ambiguous_ticket_record", str(exc))
    if built is None:
        return _settle(worktree, reply, "undeterminable", "built_for_unknown")
    built = renames.get(built, built)
    reply["built_for_ticket"] = built
    if built not in tickets:
        return _settle(worktree, reply, "nothing_to_close", "built_for_not_changed")
    return _evaluate(worktree, reply, [built], changed)


# DECISION HISTORY
# ================================================================================
# - 2026-10-16 12:00 [python-coder]: Created merge-base derivation with the own-commit rule so main-only changes never enter the set. (#BO-400e/3-ii)
