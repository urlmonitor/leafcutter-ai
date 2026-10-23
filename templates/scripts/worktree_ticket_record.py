"""
MODULE: worktree_ticket_record
GOAL: Record, in a single-ticket workspace the maker makes, which ticket its
    branch is being built for (git config ``branch.<branch>.leafcutterTicket``),
    and refuse a request that would reuse that workspace for a different
    ticket (BO-400e-3-ix).
BUSINESS CONTEXT: Finalization (``finalize_closable_set.py derive``) reads the
    record in the checkout it finalizes instead of guessing the ticket from a
    branch name that drops the ticket's date, folds its case and can be chosen
    freely. Two tickets whose names give the same slug land in the same
    workspace; letting the second overwrite the first record would make
    finalization close the wrong ticket.
ARCHITECTURE: Stdlib-only; imports ``worktree_git`` (the git boundary),
    ``worktree_answer`` (the code table) and ``worktree_identity`` (the
    in-workspace ticket fields). Took over the logic of the retired setup
    script's sibling ``_setup_ticket_branch_record.py`` (``_ticket_record_rel``,
    ``_refuse_conflicting_record``, ``_record_built_for_ticket``). The value is
    the ticket's project-relative POSIX path -- the form ``_ticket_record_rel``
    produced; ``worktree_identity.resolve_ticket`` already refuses a ticket
    outside the project. The record lives in the workspace clone's own config,
    never in a file in the tree, so recording never makes the branch "change"
    its own ticket. Only the ``ticket`` kind records; every other kind is
    left untouched.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg
import worktree_identity as wi

_log = logging.getLogger(__name__)

RECORD_KEY = "leafcutterTicket"
RECORDING_KIND = "ticket"
_RECORD_PATTERN = r"^branch\..*\.leafcutterticket$"  # git lower-cases the variable name


def _records(workspace: Path) -> tuple[list[tuple[str, str]] | None, str]:
    """Every ``(key, ticket)`` record in *workspace*'s config; ``(None, why)`` when git could not say.

    ``git config --get-regexp`` exits 1 when nothing matches -- that is "no
    record", not a failure.
    """
    proc = wg.run_git(["config", "--get-regexp", _RECORD_PATTERN], workspace)
    if proc.returncode not in (0, 1):
        return None, proc.stderr.strip()
    pairs = [line.partition(" ") for line in proc.stdout.splitlines() if line.strip()]
    return [(key, value.strip()) for key, _sep, value in pairs], ""


def conflict_refusal(workspace: Path, kind: str, ticket: wi.TicketRequest | None) -> dict[str, Any] | None:
    """Refuse, before anything is written, a ticket workspace already recorded for a DIFFERENT ticket.

    The same ticket after a lane move (00_inbox -> 01_todo -> done) keeps its
    file name and is not a conflict; :func:`finish` then rewrites the stored
    path. Returns ``None`` when there is nothing to refuse.
    """
    if kind != RECORDING_KIND or ticket is None or not (workspace / ".git").is_dir():
        return None  # no clone yet: nothing recorded, and git must not read a parent repository
    records, why = _records(workspace)
    if records is None:
        return wa.error_answer("GIT_FAILED", f"Could not read the ticket record in {workspace}: {why}")
    for key, recorded in records:
        if Path(recorded).name != ticket.rel.name:
            branch = key[len("branch."):-len(RECORD_KEY) - 1]
            return wa.error_answer(
                "BUILT_FOR_OTHER_TICKET",
                f"The workspace's line {branch} is already being built for {recorded}; refusing to use it "
                f"for {ticket.rel.as_posix()}. Nothing was changed; ask with a different --slug for this ticket.",
                branch=branch, recorded_ticket=recorded, ticket_path=ticket.arg)
    return None


def _record(workspace: Path, branch: str, rel: str) -> dict[str, Any] | None:
    """Write ``branch.<branch>.leafcutterTicket = rel`` (one value); a no-op when already so."""
    key = f"branch.{branch}.{RECORD_KEY}"
    current = wg.run_git(["config", "--get-all", key], workspace).stdout.splitlines()
    if current == [rel]:
        return None
    proc = wg.run_git(["config", "--replace-all", key, rel], workspace)
    if proc.returncode != 0:
        _log.warning("_record: git config %s failed in %s: %s", key, workspace, proc.stderr.strip())
        return wa.error_answer("GIT_FAILED", f"Could not record the built-for ticket on {branch}: "
                                             f"{proc.stderr.strip()}")
    return None


def finish(answer: dict[str, Any], kind: str, ticket: wi.TicketRequest | None, workspace: Path) -> dict[str, Any]:
    """Attach the in-workspace ticket fields to an ok *answer* and, for a ticket workspace, record the ticket.

    Returns the ok answer, or the refusal/error that replaces it (a record
    that could not be written fails the request: a branch without it would
    silently fall into "cannot identify" at finalization).
    """
    refusal = wi.attach_ticket(answer, ticket, workspace)
    if refusal is not None:
        return refusal
    if kind != RECORDING_KIND or ticket is None:
        return answer
    return _record(workspace, answer["branch"], ticket.rel.as_posix()) or answer


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-21 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/20]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/20)
#   Created for BO-400e-3-ix after main's merge (b5b958875) added the
#   built-for-ticket record to the retired setup script. Moved its logic
#   here rather than importing scripts/build_orchestration/_setup_ticket_branch_record.py:
#   that sibling deploys to a different folder than the maker in the source
#   and deployed layouts, so the maker could not import it from both. The
#   record now lives in the workspace clone's config (where finalize runs),
#   not the main checkout's; a conflicting record is refused as the new
#   BUILT_FOR_OTHER_TICKET code before any write. (ADR-018)
# ===========================================================================
