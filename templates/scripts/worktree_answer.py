"""
MODULE: worktree_answer
GOAL: The single owner of the workspace maker's result contract (BO-4300c-2):
    the complete code table, the status/exit-code mapping, the common answer
    fields, the stdout/stderr discipline, and the usage-error parser.
BUSINESS CONTEXT: Nearly every BO-4300 AC expects one readable answer from
    the maker. The code enum used to be edited piecemeal by several tickets
    (a collision in the failed run); it is declared in full here so later
    tickets add behaviour, never table rows. The answer channel (stdout)
    carries exactly one JSON object; every child process's own output is
    forwarded to stderr so it stays available but never pollutes the answer.
ARCHITECTURE: Stdlib-only, no sibling imports (so ``worktree_git``,
    ``worktree_admin`` and ``worktree`` can all import it without a cycle).
    ``status_for_code`` / ``exit_code_for_answer`` / ``finalize_answer`` are
    the only place a code becomes a status, an exit code, or an ``OK``
    marker. ``forward_child_output`` is the one place a captured child
    process's output is relayed to stderr. ``MakerParser`` turns argparse's
    own exit-2 usage failure into a :class:`UsageError` so ``main()`` can
    still print one JSON object (status error, code USAGE, exit 64).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from typing import Any, NoReturn

# ANSWER_SCHEMA_VERSION versions the BO-4300c-2 result contract (adding a
# field is compatible; renaming or removing one bumps it).
ANSWER_SCHEMA_VERSION = 1

# The COMPLETE BO-4300c-2 code enum (plus the legacy REFUSED code
# worktree_admin still emits for a dirty/unpushed remove). REFUSED_CODES are
# well-understood preconditions (status "refused", exit 2); every other code
# is an "error" (exit 1; USAGE exits 64).
ALL_CODES: frozenset[str] = frozenset({
    "OK", "NOT_FOUND", "INCOMPLETE", "OCCUPIED", "OCCUPIED_LEGACY_WORKTREE",
    "IN_PROGRESS", "NO_REPO", "AMBIGUOUS_REPO", "NO_HUB", "FETCH_FAILED",
    "GIT_FAILED", "NO_CONFIG", "BOOTSTRAP_FAILED", "BOOTSTRAP_DIRTIED_TRACKED",
    "WORK_AT_RISK", "HOOKS_INACTIVE", "VERIFY_FAILED", "UNSENT_WORK",
    "PROCESS_HOLDS_FILES", "ON_PROTECTED_BRANCH", "TICKET_NOT_ON_BASE",
    "AMBIGUOUS_LINE", "USAGE", "INTERNAL_ERROR", "REFUSED",
})
REFUSED_CODES: frozenset[str] = frozenset({
    "NOT_FOUND", "INCOMPLETE", "OCCUPIED", "OCCUPIED_LEGACY_WORKTREE",
    "IN_PROGRESS", "AMBIGUOUS_REPO", "NO_HUB", "FETCH_FAILED", "NO_CONFIG",
    "BOOTSTRAP_FAILED", "BOOTSTRAP_DIRTIED_TRACKED", "WORK_AT_RISK",
    "HOOKS_INACTIVE", "VERIFY_FAILED", "UNSENT_WORK", "PROCESS_HOLDS_FILES",
    "ON_PROTECTED_BRANCH", "TICKET_NOT_ON_BASE", "AMBIGUOUS_LINE", "REFUSED",
})
EXIT_USAGE = 64

# Git subcommands whose own stdout is progress text ("HEAD is now at ...")
# worth relaying; query commands' stdout is data the caller already consumed.
_CHATTY_STDOUT = frozenset({"clone", "fetch", "checkout", "reset", "commit", "push", "add"})


class UsageError(Exception):
    """The caller's arguments were unusable (answered as code USAGE, exit 64)."""


class MakerParser(argparse.ArgumentParser):
    """ArgumentParser whose failures raise :class:`UsageError` instead of exiting 2."""

    def error(self, message: str) -> NoReturn:
        """Raise :class:`UsageError` carrying argparse's own message."""
        raise UsageError(message)


def status_for_code(code: str) -> str:
    """Return the BO-4300c-2 status ('ok'|'refused'|'error') for *code*.

    Never raises: an unrecognised code is itself the abnormal case the
    error path reports, so it classifies as ``'error'``.
    """
    if code == "OK":
        return "ok"
    return "refused" if code in REFUSED_CODES else "error"


def exit_code_for_answer(answer: dict[str, Any]) -> int:
    """Return the exit code for *answer*: 0 ok, 2 refused, 64 USAGE, 1 other error."""
    if answer.get("status") == "ok":
        return 0
    if answer.get("code") == "USAGE":
        return EXIT_USAGE
    return 2 if answer.get("status") == "refused" else 1


def error_answer(code: str, message: str, **extra: Any) -> dict[str, Any]:
    """Build a non-ok answer whose status is derived from *code*."""
    return {"status": status_for_code(code), "code": code, "message": message, **extra}


def finalize_answer(verb: str, answer: dict[str, Any]) -> dict[str, Any]:
    """Attach ``schema_version``, ``verb`` and (for an ok answer) ``code: OK``.

    Never overwrites a field the verb handler already set. Mutates and
    returns *answer*.
    """
    answer.setdefault("schema_version", ANSWER_SCHEMA_VERSION)
    answer.setdefault("verb", verb)
    if answer.get("status") == "ok":
        answer.setdefault("code", "OK")
    elif "code" not in answer:
        answer["code"] = "INTERNAL_ERROR"
    return answer


def forward_child_output(proc: subprocess.CompletedProcess, forward_stdout: bool = True) -> None:
    """Relay a captured child process's output to stderr (never to stdout).

    Args:
        proc: A completed process run with ``capture_output=True, text=True``.
        forward_stdout: Also relay the child's stdout (progress text).
    """
    chunks = [proc.stderr]
    if forward_stdout:
        chunks.insert(0, proc.stdout)
    for chunk in chunks:
        if isinstance(chunk, str) and chunk:
            sys.stderr.write(chunk if chunk.endswith("\n") else chunk + "\n")


def forward_git_output(args: list[str], proc: subprocess.CompletedProcess) -> None:
    """Relay a git call's output to stderr; stdout only for progress-style subcommands."""
    forward_child_output(proc, forward_stdout=bool(args) and args[0] in _CHATTY_STDOUT)


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-09-30 22:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/03)
#   Created: moved status_for_code/exit_code_for_answer/finalize_answer out of
#   worktree_git.py and declared the complete BO-4300c-2 code enum (incl.
#   AMBIGUOUS_LINE, Q4) so tickets 04-08 and 12 never edit the table. An ok
#   answer now always carries code OK. (ADR-018)
# ===========================================================================
