"""
MODULE: _operation_record
GOAL: Resolve the git directory with plumbing and detect which git
    operation record (``MERGE_HEAD`` / ``REVERT_HEAD`` / ``CHERRY_PICK_HEAD``),
    if any, is currently in progress — with ONE general predicate, never a
    merge-specific branch.
BUSINESS CONTEXT: Split out of ``_authored_change.py`` (GE-120e-4, ticket 35)
    to keep that module under the project's 400-line file-size ratchet. This
    module answers exactly one question — "which operation record is
    present, if any" — that ``_authored_change._derive_authored_change()``
    combines with the states a commit is built on to decide the authored
    change set. Extending the probe from ``MERGE_HEAD`` alone (GE-120e-1) to
    all three refs (GE-120e-4) is what lets a bare ``git revert`` or
    ``git cherry-pick`` of a large recorded changeset be recognised the same
    way a merge already was, without a second, disagreeing derivation
    (Implementation Notes: "EXTEND GE-120e-1'S SHARED SOURCE, DO NOT ADD A
    SECOND DERIVATION").
ARCHITECTURE: A leaf module with no imports beyond the standard library,
    consumed only by ``_authored_change.py``. Deliberately does not import
    anything from ``_authored_change.py`` (that would be circular, since
    ``_authored_change.py`` imports from here) — ``_run_git`` is duplicated
    at leaf-module scope rather than shared, the same "small, focused leaf"
    shape as ``_resolve_root.py``.
DOC_LINKS:
  - docs/architecture/components/commit-guardian.md
DECISION HISTORY:
  - 2026-09-07 [python-coder/GE-120e-4]: Created by splitting
    ``_resolve_git_dir`` / ``_detect_operation_record`` / their
    ``_OPERATION_RECORDS`` constant out of ``_authored_change.py``, which had
    grown past the 400-line file-size limit once GE-120e-4's three-way
    operation-record probe (replacing GE-120e-1's ``MERGE_HEAD``-only probe)
    was added there.
    (#EPIC-TrustThatAGreenCheckActuallyChecked/35)
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_GIT_TIMEOUT = 30

# Ordered candidates for the operation-record probe below. Git does not
# allow overlapping in-progress operations (a repo cannot have both
# MERGE_HEAD and CHERRY_PICK_HEAD at once), so at most one of these is ever
# present; the fixed order only makes the (otherwise unreachable) multiple-
# present case deterministic rather than expressing any priority.
_OPERATION_RECORDS: tuple[str, ...] = ("MERGE_HEAD", "REVERT_HEAD", "CHERRY_PICK_HEAD")


def _run_git(args: list[str], cwd: Path) -> subprocess.CompletedProcess | None:
    """Run a git subcommand with ``cwd`` as the working directory.

    Never raises: an ``OSError`` or timeout is logged at WARNING and reported
    to the caller as ``None`` so a git failure degrades to a could-not-check
    outcome, never to a wider scan.

    Args:
        args: Arguments to append to ``git`` (e.g. ``["rev-parse", "--git-dir"]``).
        cwd: Working directory the command is run in.

    Returns:
        The completed process, or ``None`` when the invocation could not be
        run or timed out.
    """
    try:
        return subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("git %s failed in %s: %s", args, cwd, exc)
        return None


def resolve_git_dir(cwd: Path) -> Path | None:
    """Resolve the git directory for *cwd* with plumbing, never a hard-coded path.

    Uses ``git rev-parse --git-dir`` rather than assuming ``<cwd>/.git`` is a
    directory: drives in this repository run inside linked git worktrees,
    where the git directory lives elsewhere (a ``.git`` FILE pointing at
    ``<main-repo>/.git/worktrees/<name>``) and the operation-record refs this
    function exists to find live in THAT directory, not under ``cwd``. A
    hard-coded path would make the probe below a silent no-op in exactly
    that environment.

    Args:
        cwd: Working directory to resolve the git directory for.

    Returns:
        The resolved, absolute git directory, or ``None`` when the
        invocation failed, timed out, or exited non-zero.
    """
    result = _run_git(["rev-parse", "--git-dir"], cwd)
    if result is None or result.returncode != 0:
        return None
    git_dir = result.stdout.strip()
    if not git_dir:
        return None
    resolved = Path(git_dir)
    if not resolved.is_absolute():
        resolved = (cwd / resolved).resolve()
    return resolved


def detect_operation_record(git_dir: Path) -> str | None:
    """Return whichever operation-record ref is present under *git_dir*.

    ONE GENERAL PREDICATE, NEVER A MARKER SWITCH: this checks all three
    candidates (``MERGE_HEAD``, ``REVERT_HEAD``, ``CHERRY_PICK_HEAD``) the
    same way — file existence directly under the git directory — and returns
    the first one found, rather than branching on "is a merge in particular
    under way" (AC GE-120e-4's fourth clause forbids exactly that). Checking
    file existence directly (rather than one ``git rev-parse --verify``
    subprocess per candidate) is what keeps this a zero-additional-subprocess
    probe versus the single-ref check it replaces — GE-120e-4's performance
    budget caps the derivation at "at most one additional git invocation
    beyond GE-120e-1's derivation", and this adds none.

    Args:
        git_dir: The git directory to check, as resolved by
            :func:`resolve_git_dir`.

    Returns:
        The name of the first present operation-record ref, or ``None`` when
        none of the three is in progress (the ordinary-commit path).
    """
    for name in _OPERATION_RECORDS:
        if (git_dir / name).is_file():
            return name
    return None


def scope_ref(operation_record: str) -> str:
    """Return the git rev-expression naming *operation_record*'s own incoming state.

    Not a behavioural branch on "which operation is this" — every record is
    scoped the same way by the caller ("differing from this rev-expression
    is authored, matching it is carried-in from the recorded change"). This
    is a data lookup over the three records' differing GIT REFERENCE FRAMES,
    forced by git's own semantics rather than chosen by this module:

    - ``MERGE_HEAD`` names the OTHER branch's tip — the incoming content a
      merge is bringing in — so the record itself is the incoming state.
    - ``CHERRY_PICK_HEAD`` names the commit being reproduced here — a clean
      pick's result equals that commit's own tree — so the record itself is
      again the incoming state.
    - ``REVERT_HEAD`` instead names the commit being UNDONE. A revert's
      result (absent conflicts) equals that commit's PARENT tree, not the
      commit itself — reverting ``HEAD`` even sets ``REVERT_HEAD`` to the
      SAME SHA as ``HEAD``, so scoping against ``REVERT_HEAD`` verbatim
      would compare the staged tree to itself's pre-image and exclude
      nothing. ``REVERT_HEAD~1`` is the incoming state for a revert.

    Args:
        operation_record: One of ``MERGE_HEAD`` / ``REVERT_HEAD`` /
            ``CHERRY_PICK_HEAD``, as returned by :func:`detect_operation_record`.

    Returns:
        The git rev-expression to diff the staged content against.
    """
    if operation_record == "REVERT_HEAD":
        return f"{operation_record}~1"
    return operation_record
